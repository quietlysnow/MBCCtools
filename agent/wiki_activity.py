"""BWIKI 活动采集 —— 从无期迷途 BWIKI 首页的「游戏日历」取当前活动与结束时间。

落档 record/活动.json，供 MFAAvalonia 的「活动提醒」页读取；与抽卡记录同一套
「agent 写文件、界面读文件」的分工（AGENTS.md §2）。界面不联网、不解析 HTML。

两个来源，都走同一个 api.php：

1. 活动 —— 解析「模板:日历提示」的 wikitext（即首页游戏日历区块的本体）。
   刻意不抓渲染后的 HTML：实测该模板对部分活动渲染出的 data-end 是坏的
   （第81期深阱残骸 / 数据间隙时序10 / 枪火铅灰与玫瑰 三条都渲染成 "+8 hours"），
   而 wikitext 里是正确值。渲染走的是模板里的日期表达式，解析 wikitext 反而更稳。
2. 监察密令 —— 语义查询（分类:监察密令，按创建日期倒序）取当前一期。
   密令页只记到日、没有时分，落档时标 precision=day，界面按"当天结束"算剩余。

网络失败不写文件、不抛异常，只记日志：文件里保留上一次的数据，界面继续显示旧的，
并靠 collected_at 让用户看出数据有多旧。
"""

import datetime
import json
import os
import pathlib
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

WIKI = "https://wiki.biligame.com/wqmt"
API = WIKI + "/api.php"
# 首页（%E9%A6%96%E9%A1%B5 = 首页）。这里必须是已编码形式：它同时用于 Referer 请求头，
# HTTP 头只接受 latin-1，直接写中文会在发请求时抛 codec 错。
HOME_PAGE = WIKI + "/%E9%A6%96%E9%A1%B5"

# BWIKI 对无 UA 的请求会拒，Referer 用首页（.scratch 的抓图脚本同一套）
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

DEFAULT_RECORD = "record/活动.json"
REFRESH_HOURS = 6
# 密令查询往回多取几期，再按结束日期过滤；日历提示模板里只留当前活动，不用过滤
COMMAND_LIMIT = 5
COMMAND_KEEP_DAYS_PAST_END = 3

# 游戏与 BWIKI 的时间都是北京时间，固定 +8 偏移（不理会夏令时，国内没有）
TZ = datetime.timezone(datetime.timedelta(hours=8))

_TIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d", "%Y/%m/%d")

# {{首页活动|活动名称=第34期破碎防线·暗域|开始时间=2026-09-21 5:00|结束时间=2026-11-02 4:00|链接=破碎防线}}
_HOME_ACTIVITY_CALL = re.compile(r"\{\{\s*首页活动\s*\|([^{}]*)\}\}")
_COMMAND_PERIOD = re.compile(r"第\s*(\d+)\s*期")


def _default_log(msg):
    # 与 main.py 的 _log 同一前缀：AgentServer 由 UI 以子进程拉起，stderr 会进 UI 日志
    print(f"[MBCCtools-agent] {msg}", file=sys.stderr, flush=True)


def _api(params, log=_default_log):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": HOME_PAGE})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_time(text):
    """wiki 里的时间写法不统一（2026-09-21 5:00 / 2026/11/14 12:00 / 2026-09-07），逐个试。"""
    text = (text or "").strip()
    for fmt in _TIME_FORMATS:
        try:
            dt = datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
        precision = "day" if "%H" not in fmt else "minute"
        return dt.replace(tzinfo=TZ), precision
    return None, None


def _item(name, type_, start_text, end_text, link, log):
    start, start_precision = _parse_time(start_text)
    end, end_precision = _parse_time(end_text)
    if end is None:
        log(f"活动「{name}」结束时间读不出（{end_text!r}），跳过")
        return None
    return {
        "name": name,
        "type": type_,
        "start": start.isoformat() if start else None,
        "end": end.isoformat(),
        # 密令页只记到日：界面按"当天结束"算剩余，不能当成 00:00
        "precision": end_precision,
        "link": link,
    }


def fetch_home_activities(log=_default_log):
    """首页游戏日历里的活动。列表由 wiki 编辑维护在模板里，只放当前有效的那几条。"""
    parsed = _api({
        "action": "parse",
        "page": "模板:日历提示",
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }, log)
    wikitext = (parsed.get("parse") or {}).get("wikitext")
    if not wikitext:
        raise RuntimeError("模板:日历提示 没取到 wikitext")

    items = []
    for raw in _HOME_ACTIVITY_CALL.findall(wikitext):
        fields = {}
        for part in raw.split("|"):
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip()] = value.strip()
        name = fields.get("活动名称")
        if not name:
            continue
        link = fields.get("链接") or ""
        url = WIKI + "/" + urllib.parse.quote(link.replace(" ", "_")) if link else HOME_PAGE
        entry = _item(name, "活动", fields.get("开始时间"), fields.get("结束时间"), url, log)
        if entry:
            items.append(entry)
    log(f"首页日历取到 {len(items)} 个活动")
    return items


def fetch_commands(log=_default_log):
    """当前一期监察密令（语义查询里按创建日期倒序取最近几期，再按结束日期过滤）。"""
    parsed = _api({
        "action": "ask",
        "query": f"[[分类:监察密令]]|?密令名称|?开始时间|?结束时间"
                 f"|limit={COMMAND_LIMIT}|sort=创建日期|order=desc",
        "format": "json",
    }, log)
    results = (parsed.get("query") or {}).get("results") or {}
    if not results:
        raise RuntimeError("监察密令语义查询没返回结果")

    now = datetime.datetime.now(TZ)
    floor = now - datetime.timedelta(days=COMMAND_KEEP_DAYS_PAST_END)
    items = []
    for title, row in results.items():
        printouts = row.get("printouts") or {}

        def first(key):
            values = printouts.get(key) or []
            return str(values[0]) if values else ""

        start_text, end_text = first("开始时间"), first("结束时间")
        end, _ = _parse_time(end_text)
        if end is None or end < floor:
            continue
        period = _COMMAND_PERIOD.search(title)
        theme = first("密令名称")
        name = f"监察密令 第{period.group(1)}期" if period else title
        if theme:
            name += f"「{theme}」"
        entry = _item(name, "密令", start_text, end_text, row.get("fullurl") or HOME_PAGE, log)
        if entry:
            items.append(entry)
    log(f"密令语义查询取到 {len(items)} 条在期记录")
    return items


def collect(log=_default_log):
    """两个来源各自失败互不影响：一个挂了另一个照常落档，失败原因写进 errors 供界面提示。"""
    items, errors = [], []
    for label, fetch in (("活动", fetch_home_activities), ("密令", fetch_commands)):
        try:
            items.extend(fetch(log))
        except Exception as e:  # 网络/接口/格式变化都归到这里，不能让 agent 起不来
            errors.append(f"{label}: {e}")
            log(f"{label}采集失败：{e}")

    # 同名去重（日历提示里同一个活动通常只有一条，防编辑重复添加）
    deduped = {}
    for item in items:
        deduped[item["name"]] = item
    items = sorted(deduped.values(), key=lambda x: (x["end"], x["name"]))
    return {
        "source": HOME_PAGE,
        "collected_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
        "items": items,
        "errors": errors,
    }


def write(payload, root=None, log=_default_log):
    """先写临时文件再替换：界面随时在读它，不能读到写了一半的 JSON。"""
    path = (root or pathlib.Path(__file__).resolve().parent.parent) / DEFAULT_RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path


def refresh(root=None, log=_default_log):
    """抓一次并落档。返回摘要文本；两个来源都失败时返回 None（不覆盖旧文件）。"""
    payload = collect(log)
    if not payload["items"]:
        log(f"本次没抓到任何活动，保留旧文件。errors={payload['errors']}")
        return None
    path = write(payload, root, log)
    summary = (f"活动数据已更新：{len(payload['items'])} 条 -> {path.name}"
               f"（采集于 {payload['collected_at']}）")
    log(summary)
    return summary


def start_background_refresh(root=None, interval_hours=REFRESH_HOURS, log=_default_log):
    """起一个守护线程：启动先抓一次，之后每隔 interval_hours 再抓。

    放后台是不想挡住 AgentServer 与 UI 的握手；守护线程随进程退出，不需要收尾。
    """

    def loop():
        time.sleep(3)  # 让握手先完成，别在网络请求上抢启动那几百毫秒
        while True:
            try:
                refresh(root, log)
            except Exception as e:
                log(f"活动刷新线程异常：{e}")
            time.sleep(max(1, interval_hours) * 3600)

    thread = threading.Thread(target=loop, name="wiki-activity-refresh", daemon=True)
    thread.start()
    log(f"活动采集线程已启动：每 {interval_hours} 小时刷新一次 {DEFAULT_RECORD}")
    return thread


if __name__ == "__main__":
    # 手动跑一次看结果：python agent/wiki_activity.py
    sys.exit(0 if refresh() else 1)
