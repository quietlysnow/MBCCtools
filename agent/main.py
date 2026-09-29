"""MBCCtools AgentServer —— 方案二的自定义识别/动作实现入口。

由 MFAAvalonia / MaaPiCli 按 interface.json 的 "agent" 段作为子进程拉起，
最后一个命令行参数是 AgentClient 下发的连接标识符（socket id），需原样传给
AgentServer.start_up()。

自定义识别名与 pipeline 里的 custom_recognition 字段一一对应（大小写敏感）。
"""

import datetime
import json
import pathlib
import re
import sys

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch


def _log(msg):
    # AgentServer 由 UI 以子进程方式拉起，stderr 会进 UI 日志
    print(f"[MBCCtools-agent] {msg}", file=sys.stderr, flush=True)


def _parse_param(argv):
    """custom_*_param 在协议里是任意 JSON，框架整包透传，绑定层给的是字符串。
    识别器与动作节点的字段名不同，这里一并取。"""
    raw = getattr(argv, "custom_recognition_param", None)
    if raw is None:
        raw = getattr(argv, "custom_action_param", None)
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as e:
            _log(f"custom_*_param 不是合法 JSON: {e} / {raw!r}")
            return {}
    return raw or {}


def _as_rect(value, default):
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(v) for v in value]
    return default


def _as_x_range(value):
    """badge_x 是 [x0, x1] 两个数，不是四元 rect，别复用 _as_rect"""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    return None


def _rect_of(value):
    """识别结果里的 box 在不同绑定版本可能是 Rect 对象或 [x,y,w,h] 列表，统一成列表"""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [int(v) for v in value]
    if all(hasattr(value, a) for a in ("x", "y", "w", "h")):
        return [int(value.x), int(value.y), int(value.w), int(value.h)]
    return None


def _corner_key(box, roi, image_wh, corner):
    """离参考角越近越小。JSON 的 order_by 只能按横/纵/分值/面积排，
    按"到某个屏幕角的距离"择优是这里必须写代码的部分。"""
    x, y, w, h = box
    cx, cy = x + w / 2.0, y + h / 2.0
    rx, ry, rw, rh = roi
    if rw <= 0 or rh <= 0:
        rx, ry, rw, rh = 0, 0, image_wh[0], image_wh[1]
    right, bottom = rx + rw, ry + rh

    if corner == "top_left":
        ax, ay = rx, ry
    elif corner == "bottom_left":
        ax, ay = rx, bottom
    elif corner == "bottom_right":
        ax, ay = right, bottom
    else:  # top_right，关弹窗按钮的常见位置
        ax, ay = right, ry
    return (cx - ax) ** 2 + (cy - ay) ** 2


@AgentServer.custom_recognition("CloseButton")
class CloseButton(CustomRecognition):
    """在画面里找"最像关闭按钮"的那个图样，返回它的位置。

    pipeline 参数（写在 custom_recognition_param 里）:
        templates: [str]  模板名，相对 image/ 根，如 "弹窗关闭按钮.png"。必选
        threshold: float|[float]  与 templates 一一对应，默认 0.7
        corner:    str  top_right | top_left | bottom_left | bottom_right，默认 top_right
    节点自身的 roi 会作为搜索范围；不写 roi 就是全屏。
    """

    def analyze(self, context, argv):
        param = _parse_param(argv)
        templates = param.get("templates") or []
        if isinstance(templates, str):
            templates = [templates]
        if not templates:
            _log("CloseButton: custom_recognition_param 缺 templates，视为未命中")
            return None

        thresholds = param.get("threshold", 0.7)
        if not isinstance(thresholds, list):
            thresholds = [thresholds] * len(templates)
        if len(thresholds) != len(templates):
            _log(f"CloseButton: threshold 数量 {len(thresholds)} != templates 数量 {len(templates)}")
            thresholds = (thresholds + [0.7] * len(templates))[: len(templates)]

        corner = param.get("corner", "top_right")

        # argv.roi 是 Rect（只有 x/y/w/h 四个属性，没有 to_list），
        # 而序列化走 dataclasses.asdict，直接塞 Rect 会变成对象而非 [x,y,w,h]
        roi = [argv.roi.x, argv.roi.y, argv.roi.w, argv.roi.h]
        if tuple(roi) == (0, 0, 0, 0):
            roi = _as_rect(param.get("roi"), roi)

        img_h, img_w = argv.image.shape[0], argv.image.shape[1]
        image_wh = (img_w, img_h)

        best = None
        tried = []
        for name, thr in zip(templates, thresholds):
            detail = context.run_recognition_direct(
                JRecognitionType.TemplateMatch,
                JTemplateMatch(template=[name], roi=roi, threshold=[float(thr)], order_by="Score"),
                argv.image,
            )
            box = getattr(detail, "box", None)
            hit = bool(getattr(detail, "hit", False)) and box is not None
            tried.append(f"{name}@{thr}={'hit' if hit else 'miss'}")
            if not hit:
                continue
            cand = [int(box.x), int(box.y), int(box.w), int(box.h)]
            key = _corner_key(cand, roi, image_wh, corner)
            if best is None or key < best[0]:
                best = (key, cand, name)

        if best is None:
            # 未命中要返回 None，不能抛异常：抛了会让整个任务失败而不是优雅跳过
            _log("CloseButton 未命中 | " + " ".join(tried))
            return None

        _log(f"CloseButton 命中 {best[2]} box={best[1]} | " + " ".join(tried))
        return self.AnalyzeResult(
            box=best[1],
            detail={"template": best[2], "candidates": tried, "corner": corner},
        )


# 累计记录：固定一个文件，出新卡池后跑一次就把没见过的追加进去，不产生第二份档案
DEFAULT_ARCHIVE = "record/抽卡记录.jsonl"
# focus 只能引用固定路径（占位符替换不了动态值），所以摘要也覆盖同一个文件
DEFAULT_REPORT = "record/抽卡记录.md"


class _RecordSession:
    """一次采集会话。

    store_counts 是开跑前从既有档案读到的"每条记录出现过几次"，run_counts 是本次已经看到的次数；
    本次第 n 次看到某条记录时，只有 n > store_counts 才算新记录 —— 这样十连里同秒重复的同名条目
    （实测存在）不会被误判成已采过。
    """

    def __init__(self, path, ts, store_counts):
        self.path = path
        self.ts = ts
        self.store_counts = store_counts
        self.run_counts = {}
        self.last_page = None
        self.last_keys = None
        self.pages = 0
        self.attempts = 0
        self.new_count = 0
        # 页头追踪类型，由 GachaRecordPoolType 在采集前写入；没识别出来保持 None
        self.pool_type = None


_sessions = {}


def _project_root():
    # interface.json 与 agent/ 同级；不依赖 CWD，手动跑脚本时路径也一致
    return pathlib.Path(__file__).resolve().parent.parent


def _load_store_counts(path):
    counts = {}
    if not path.exists():
        return counts
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                key = json.loads(line)["key"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            counts[key] = counts.get(key, 0) + 1
    return counts


def _get_session(archive_pattern):
    session = _sessions.get(archive_pattern)
    if session is not None:
        return session
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _project_root() / archive_pattern.format(ts=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    session = _RecordSession(path, ts, _load_store_counts(path))
    _sessions[archive_pattern] = session
    _log(f"抽卡记录会话开始 -> {path}（已有 {sum(session.store_counts.values())} 条）")
    return session


def _rarity_by_row(context, image, row_boxes, rarity_dir, tiers, floor):
    """每档跑一次整目录 TemplateMatch，逐行取最高分的档。

    单张模板不行：同档徽章的花框逐角色不同，自己匹配自己 0.999、同档另一张只有 0.5~0.6，
    卡阈值必然漏档。所以 image/抽卡/<档>/ 下放多张样例，比的是 argmax 而不是阈值。
    留一法回测 20/20（正确档 >=0.74，错误档全 0）。出新档就往目录里补图，不用改代码。
    """
    best = [{} for _ in row_boxes]
    for tier in tiers:
        detail = context.run_recognition_direct(
            JRecognitionType.TemplateMatch,
            JTemplateMatch(template=[f"{rarity_dir}/{tier}"], threshold=[0.3]),
            image,
        )
        for result in (getattr(detail, "all_results", None) or []):
            box = _rect_of(getattr(result, "box", None))
            if box is None:
                continue
            cy = box[1] + box[3] / 2.0
            score = float(getattr(result, "score", 0.0))
            for row, (x, y, w, h) in enumerate(row_boxes):
                # 徽章比文字高，纵向占 [行中心, 行中心+27]，所以按行框上下各放 4px 去接它的中心
                if y - 4 <= cy <= y + h + 4:
                    if score > best[row].get(tier, 0.0):
                        best[row][tier] = score
                    break

    rarities = []
    for scores in best:
        if not scores:
            rarities.append(None)
            continue
        tier = max(scores, key=scores.get)
        top = scores[tier]
        rarities.append(tier if top >= floor else f"未知:{tier}:{top:.2f}")
    return rarities


def _ocr_rows(context, image, roi, min_score, line_tol, badge_x=None):
    """整页 OCR 后按 y 聚成行，返回 (行文本, 行外接框) 两组等长列表。

    行内按 x 排序，所以一行的 cells 就是"时间 / 卡池 / 角色名"这类列的原始顺序，
    不做语义解析。给了 badge_x（徽章列的横范围）就把落在该列里的 OCR 碎片剔掉，
    免得偶尔被读出来的"普"混进名字里。
    """
    detail = context.run_recognition_direct(
        JRecognitionType.OCR,
        JOCR(roi=roi),
        image,
    )
    results = getattr(detail, "all_results", None) or getattr(detail, "filtered_results", None) or []

    items = []
    for result in results:
        text = (getattr(result, "text", "") or "").strip()
        box = _rect_of(getattr(result, "box", None))
        if not text or box is None:
            continue
        if float(getattr(result, "score", 0.0)) < min_score:
            continue
        if badge_x and badge_x[0] <= box[0] + box[2] / 2.0 <= badge_x[1]:
            continue
        items.append((box[1] + box[3] / 2.0, box[0], box, text))
    items.sort()

    rows = []
    for cy, cx, box, text in items:
        if rows and abs(cy - rows[-1][0]) <= line_tol:
            rows[-1][1].append((cx, text, box))
        else:
            rows.append([cy, [(cx, text, box)]])

    cells_list = []
    box_list = []
    for _, cells in rows:
        cells.sort(key=lambda c: c[0])
        cells_list.append(tuple(c[1] for c in cells))
        boxes = [c[2] for c in cells]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        box_list.append([x0, y0, x1 - x0, y1 - y0])
    return cells_list, box_list


def _row_sig(cells):
    """一条记录的身份键：整行文本去掉空白后拼接。
    OCR 常把日期与时间之间的空格吃掉（实测 10 行里 3 行），不归一化就没法跟档案里的旧记录对上。"""
    return re.sub(r"\s+", "", "".join(cells))


def _page_number(context, image, page_roi, min_score):
    """读底栏 ◀ 页码 ▶ 中间那个数字。它是"这页到底刷没刷出来"最可靠的凭据：
    逐行比对会被 OCR 抖动骗过（同一页两次读出细微差别就以为翻动了），页码不会。
    两个箭头常被误读成 1 / 7 之类，所以按置信度取最高的那个纯数字。"""
    detail = context.run_recognition_direct(
        JRecognitionType.OCR,
        JOCR(roi=page_roi),
        image,
    )
    best = None
    for result in (getattr(detail, "all_results", None) or []):
        text = (getattr(result, "text", "") or "").strip()
        score = float(getattr(result, "score", 0.0))
        if not text.isdigit() or score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, int(text))
    return best[1] if best else None


def _read_page_number(context, argv, param):
    page_roi = _as_rect(param.get("page_roi"), None)
    if not page_roi:
        return None
    return _page_number(context, argv.image, page_roi, float(param.get("min_score", 0.5)))


DEFAULT_POOL_TYPES = ["活动", "常规", "定向", "常驻"]


@AgentServer.custom_recognition("GachaRecordPoolType")
class GachaRecordPoolType(CustomRecognition):
    """识别记录页页头的追踪类型，写进会话，随每条记录存档、导出时作「类型」列。

    页头是「{类型}追踪 · 近期抽卡记录(UTC+8)」的形态，按"包含"匹配四种类型
    （OCR 掉首字也能对上）；types 参数可覆盖清单，游戏改文案时不用动代码。
    只需在采集前跑一次：本任务里翻页不换池，类型整轮不变。
    未命中返回 None（不在记录页 / 文案变了）。此时也要把会话里的旧类型清掉，
    否则同一进程内第二次跑会把上一次的类型错挂到这次的记录上。
    类型识别不出来不阻断采集（父节点 on_error 照走），只是记录的 type 为 null。
    """

    def analyze(self, context, argv):
        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        session = _get_session(archive)

        roi = [argv.roi.x, argv.roi.y, argv.roi.w, argv.roi.h]
        if tuple(roi) == (0, 0, 0, 0):
            roi = _as_rect(param.get("roi"), roi)

        detail = context.run_recognition_direct(
            JRecognitionType.OCR,
            JOCR(roi=roi),
            argv.image,
        )
        results = getattr(detail, "all_results", None) or getattr(detail, "filtered_results", None) or []
        min_score = float(param.get("min_score", 0.5))
        types = param.get("types") or DEFAULT_POOL_TYPES

        best = None
        for result in results:
            text = (getattr(result, "text", "") or "").strip()
            box = _rect_of(getattr(result, "box", None))
            score = float(getattr(result, "score", 0.0))
            if not text or box is None or score < min_score:
                continue
            for t in types:
                if t in text and (best is None or score > best[0]):
                    best = (score, t, text, box)
                    break

        if best is None:
            session.pool_type = None
            _log(f"GachaRecordPoolType 在 roi={roi} 没认出追踪类型（{types}），本批记录不带 type")
            return None

        session.pool_type = best[1]
        _log(f"GachaRecordPoolType 追踪类型={best[1]}（原文「{best[2]}」，置信度 {best[0]:.2f}）")
        return self.AnalyzeResult(
            box=best[3],
            detail={"type": best[1], "text": best[2], "score": best[0]},
        )


@AgentServer.custom_recognition("GachaRecordFirstPage")
class GachaRecordFirstPage(CustomRecognition):
    """判断当前是不是记录列表的第 1 页，用来在采集前先把 ◀ 点回顶部。

    水位线是按"记录内容已存在"停的，前提是从第 1 页往下扫。要是开跑时停在中间页，
    第一屏全是旧记录，会被当成到底、一条新的都采不到还不报错，所以先把页码头归零。
    参数同 GachaRecordPage 的 page_roi / min_score。未命中 = 已在第 1 页，或读不到页码。
    """

    def analyze(self, context, argv):
        param = _parse_param(argv)
        game_page = _read_page_number(context, argv, param)
        if game_page in (None, 1):
            return None
        roi = _rect_of(argv.roi) or [0, 0, argv.image.shape[1], argv.image.shape[0]]
        _log(f"GachaRecordFirstPage 当前在第 {game_page} 页，先点 ◀ 回第 1 页")
        return self.AnalyzeResult(box=roi, detail={"page": game_page})


@AgentServer.custom_recognition("GachaRecordPage")
class GachaRecordPage(CustomRecognition):
    """读抽卡记录列表页当前可见的记录，追加进累计档案。

    记录页是"新在前、旧不改动"的（实测第 1 页 2026-09、第 50 页 2025-10），所以每次从第 1 页
    往下扫，**扫到第一条已经存在的记录就停** —— 出新卡池后跑一次，只追加新的那几页。

    pipeline 参数（写在 custom_recognition_param 里）:
        archive:        str    累计档案路径，默认 record/抽卡记录.jsonl；开跑前读它建水位线
        roi:            [x,y,w,h] 列表区域，不写就是全屏；节点自身的 roi 优先
        min_score:      float  OCR 置信度下限，默认 0.5
        line_tol:       int    判定"同一行"的 y 中心容差像素，默认 14
        badge_x:        [x0,x1] 徽章列的横向范围，用来剔掉该列里偶尔被 OCR 读出来的碎片，不给就不剔
        rarity_dir:     str  徽章模板根目录，相对 image/，默认 "抽卡"
        rarity_tiers:   [str] 有哪几档，对应 rarity_dir 下的同名子目录（如 抽卡/狂/*.png）；不给就不判档
        rarity_floor:   float 最高分低于它就算未匹配，落成 "未知:档:分值" 提醒补图，默认 0.5
        page_roi:       [x,y,w,h] 底栏页码数字的区域；用来分辨"这页还没刷出来"和"到底了"
        max_pages:      int    单次最多识别次数（防失控的兜底），默认 100
    每条记录附带 type 字段 = GachaRecordPoolType 在采集前识别出的追踪类型（未识别为 null）。
    命中 = 本页有没见过的记录并已追加；未命中 = 扫到水位线、页码没再往前、或达到 max_pages，
    交给父节点的 timeout/on_error 走到汇总导出。
    """

    def analyze(self, context, argv):
        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        session = _get_session(archive)

        roi = _rect_of(argv.roi) or [0, 0, argv.image.shape[1], argv.image.shape[0]]
        if tuple(roi) == (0, 0, 0, 0):
            h, w = argv.image.shape[0], argv.image.shape[1]
            roi = _as_rect(param.get("roi"), [0, 0, w, h])

        session.attempts += 1
        if session.attempts > int(param.get("max_pages", 100)):
            _log(f"GachaRecordPage 达到 max_pages，停止采集（本次已新增 {session.new_count} 条）")
            return None

        game_page = _read_page_number(context, argv, param)
        if param.get("page_roi") and game_page is None:
            # 配了 page_roi 却读不到页码 = 大概率根本不在抽卡记录页上。
            # 入口节点是直通的，不设这道门就会把当前屏幕上的任意文字当记录写进累计档案，
            # 而且水位线会让这份污染永久留下，所以宁可拒绝这一页。
            _log("GachaRecordPage 读不到页码，判定当前不在抽卡记录页，拒绝这一页")
            return None
        if game_page is not None and game_page == session.last_page:
            _log(f"GachaRecordPage 页码仍是 {game_page}，判定到底")
            return None
        page_no = game_page if game_page is not None else session.pages + 1

        rows, boxes = _ocr_rows(
            context,
            argv.image,
            roi,
            float(param.get("min_score", 0.5)),
            int(param.get("line_tol", 14)),
            _as_x_range(param.get("badge_x")),
        )
        if not rows:
            _log(f"GachaRecordPage 第 {page_no} 页没读出任何文本，视为未命中")
            return None

        keys = [_row_sig(cells) for cells in rows]
        if keys == session.last_keys:
            # 整页与上一页逐行相同 = 这一页被重采了（翻页没生效且没配 page_roi 时的兜底）。
            # 不能只靠下面的出现次数：同秒同名重复是真实存在的，那条规则分不清"重采"和"又抽中一次"。
            _log(f"GachaRecordPage 第 {page_no} 页与上一页逐行相同，判定到底")
            return None

        rarities = _rarity_by_row(
            context,
            argv.image,
            boxes,
            param.get("rarity_dir", "抽卡"),
            param.get("rarity_tiers") or [],
            float(param.get("rarity_floor", 0.5)),
        )
        unknown = [r for r in rarities if r and r.startswith("未知")]
        if unknown:
            _log(f"GachaRecordPage 有徽章没匹上任何档，需要往对应目录补图: {unknown}")

        # 自上而下走水位线：撞见一条档案里已有的记录，说明再往下全是旧的
        fresh = []
        for cells, key, rarity in zip(rows, keys, rarities):
            session.run_counts[key] = session.run_counts.get(key, 0) + 1
            if session.run_counts[key] > session.store_counts.get(key, 0):
                fresh.append((cells, key, rarity))
            else:
                break

        if not fresh:
            _log(f"GachaRecordPage 第 {page_no} 页第一条就撞上已记录的内容，水位线到了")
            return None

        # 只有这一页真的采到了才推进水位线：否则一次 OCR 抖动把页码记成"已看过"，
        # 重试就会被上面那句"页码仍是 N"挡死，整次采集停在半路。
        if game_page is not None:
            session.last_page = game_page
        session.last_keys = keys
        session.pages = page_no

        total = sum(session.store_counts.values())
        with open(session.path, "a", encoding="utf-8") as f:
            for cells, key, rarity in fresh:
                session.new_count += 1
                total += 1
                # 同步抬高水位线，否则本次运行内重复出现的同一页会被再采一遍
                session.store_counts[key] = session.store_counts.get(key, 0) + 1
                f.write(json.dumps(
                    {"index": total, "key": key, "rarity": rarity,
                     "type": session.pool_type, "cells": list(cells)},
                    ensure_ascii=False,
                ) + "\n")

        _log(f"GachaRecordPage 第 {page_no} 页：{len(rows)} 行，新增 {len(fresh)} 条，累计 {total} 条")
        return self.AnalyzeResult(
            box=boxes[-1],
            detail={
                "page": page_no,
                "rows": len(rows),
                "new_rows": len(fresh),
                "total": total,
                "archive": str(session.path),
            },
        )


_SHEET_BAD_CHARS = re.compile(r"[\\/*?:\[\]]")
# OCR 常把日期与时间之间那个空格吃掉（实测 10 行里 3 行），明细保留原样，导出层补回来
_TIME_FIX = re.compile(r"^(\d{4}-\d{2}-\d{2})(\d{2}:)")


def _record_time(rec):
    """导出层排序用；不补回那个空格，字符串排序就会把同一条记录排到错的位置"""
    cells = rec["cells"]
    return _TIME_FIX.sub(r"\1 \2", cells[0]) if len(cells) >= 3 else ""


def _sheet_name(pool, used):
    """Excel 工作表名不许带 \\ / * ? : [ ] 且最长 31 字符，卡池名要清洗并去重"""
    cleaned = _SHEET_BAD_CHARS.sub("_", pool)[:31] or "未命名"
    if cleaned in used:
        n = 2
        while f"{cleaned[:28]}_{n}" in used:
            n += 1
        cleaned = f"{cleaned[:28]}_{n}"
    used.add(cleaned)
    return cleaned


def _write_report(path, groups, session, total):
    """给 UI 弹窗看的 Markdown 摘要。只放分档计数和出货清单——几百行表格塞进弹窗没人看。"""
    counts = {}
    for recs in groups.values():
        for rec in recs:
            key = rec["rarity"] or "未判"
            counts[key] = counts.get(key, 0) + 1
    order = sorted(counts, key=lambda t: -counts[t])
    rare = [t for t in order if t != order[0]]

    lines = [
        "# 抽卡记录",
        "",
        f"本次新增 {session.new_count} 条，累计 {total} 条 · 完整明细见 `{path.with_suffix('.xlsx').name}`",
        "",
        "## 各卡池",
        "",
        "| 卡池 | 抽数 | " + " | ".join(order) + " |",
        "| --- | --- | " + " | ".join(["---"] * len(order)) + " |",
    ]
    for pool, recs in groups.items():
        row = [str(sum(1 for r in recs if (r["rarity"] or "未判") == t)) for t in order]
        lines.append(f"| {pool} | {len(recs)} | " + " | ".join(row) + " |")

    hits = [(rec, pool) for pool, recs in groups.items() for rec in recs
            if (rec["rarity"] or "未判") in rare]
    hits.sort(key=lambda x: _record_time(x[0]), reverse=True)
    lines += ["", f"## 出货（{'、'.join(rare)}，最近 {min(len(hits), 60)} 条）", ""]
    if hits:
        lines += ["| 时间 | 卡池 | 类型 | 稀有度 | 名称 | 档案序号 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for rec, pool in hits[:60]:
            cells = rec["cells"]
            name_ = cells[-1] if len(cells) >= 3 else " ".join(cells)
            lines.append(f"| {_record_time(rec)} | {pool} | {rec.get('type') or ''} "
                         f"| {rec['rarity']} | {name_} | {rec['index']} |")
        if len(hits) > 60:
            lines.append(f"\n更早的 {len(hits) - 60} 条见 xlsx。")
    else:
        lines.append("没有出货。")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@AgentServer.custom_action("GachaRecordExport")
class GachaRecordExport(CustomAction):
    """收尾：把累计档案转成 Excel（一个卡池一张表）+ Markdown 摘要，并结束会话。

    pipeline 参数（写在 custom_action_param 里）:
        archive:  str  与识别器同一个值，指向累计 JSONL
        excel:    str  导出路径，默认取 archive 换成 .xlsx（固定名字，每次覆盖）
        report:   str  Markdown 摘要的固定路径，节点 focus 里要写同一个值（占位符替换不了动态名）
    JSONL 是累计档案本体，Excel 与摘要都只是它的一个视图，随时可重建。
    """

    def run(self, context, argv):
        try:
            from openpyxl import Workbook
        except ImportError:
            # interface.json 的 child_exec 写的是裸 "python"，而 PATH 里还有第二个解释器
            # （F:\Python 装的是 MaaFw 5.10.4、没有 openpyxl）。解析到它时不能让节点抛异常
            # 打断流程，只跳过 xlsx，摘要与 JSONL 档案照常。
            Workbook = None
            _log(f"缺 openpyxl，跳过 xlsx。当前解释器 {sys.executable}；"
                 f"补依赖：\"{sys.executable}\" -m pip install openpyxl")

        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        session = _sessions.pop(archive, None)
        if session is None:
            _log("GachaRecordExport 没有进行中的会话（识别节点没跑过或已收尾）")
            return True
        if not session.path.exists():
            _log(f"GachaRecordExport 明细文件不存在: {session.path}")
            return True

        pattern = param.get("excel") or archive.replace(".jsonl", ".xlsx")
        out = _project_root() / pattern.format(ts=session.ts)
        out.parent.mkdir(parents=True, exist_ok=True)
        groups = {}
        total = 0
        with open(session.path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                cells = rec["cells"]
                total += 1
                groups.setdefault(cells[1] if len(cells) >= 3 else "未分类", []).append(rec)

        if Workbook is not None:
            wb = Workbook()
            wb.remove(wb.active)
            used = set()
            for pool, recs in groups.items():
                ws = wb.create_sheet(_sheet_name(pool, used))
                ws.append(["时间", "类型", "稀有度", "名称", "档案序号"])
                # 档案是"单次采集内部新在前、多次采集按跑的先后追加"，直接倒出来顺序是乱的，按时间重排
                for rec in sorted(recs, key=_record_time, reverse=True):
                    cells = rec["cells"]
                    # 实测列序为 时间 / 卡池 / 名称；列数不足就把原文并到名称里，不做猜测
                    time_, name_ = (cells[0], cells[-1]) if len(cells) >= 3 else ("", " / ".join(cells))
                    # 旧档案的行没有 type 字段，None 在单元格里落成空白
                    ws.append([_record_time(rec), rec.get("type"), rec["rarity"], name_, rec["index"]])
            wb.save(out)

        report = param.get("report") or DEFAULT_REPORT
        report_path = _project_root() / report
        _write_report(report_path, groups, session, total)
        _log(
            f"抽卡记录导出：本次新增 {session.new_count} 条 / 累计 {total} 条 / {len(groups)} 个卡池 "
            f"-> {out.name} + {report_path.name}"
        )
        return True


def _load_wiki_activity():
    """wiki_activity 与 main.py 同目录。按脚本跑时 sys.path[0] 已经是该目录，
    但入口方式不完全固定（UI / MaaPiCli / 手动调试），这里兜一下再导入。"""
    here = pathlib.Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import wiki_activity
    return wiki_activity


def main():
    if len(sys.argv) < 2:
        _log("缺少连接标识符。正常应由 UI 按 interface.json 的 agent 段拉起；"
             "手动调试: python agent/main.py <identifier>")
        return 1

    identifier = sys.argv[-1]
    if not AgentServer.start_up(identifier):
        _log(f"AgentServer.start_up({identifier!r}) 失败：检查 MaaAgentServer.dll 与 AgentClient 是否在跑")
        return 1

    # 活动数据：与任务无关的后台采集，抓 BWIKI 写 record/活动.json 供界面「活动提醒」页读取。
    # 纯网络采集、不注册任何 Custom 节点，失败也不影响任务（AGENTS.md §2 的分层）。
    try:
        _load_wiki_activity().start_background_refresh(_project_root(), log=_log)
    except Exception as e:
        _log(f"活动采集线程没起来（不影响任务）：{e}")

    try:
        import importlib.metadata

        fw = importlib.metadata.version("MaaFw")
    except Exception:
        fw = "?"
    _log(f"AgentServer 已启动，identifier={identifier}，解释器={sys.executable}，MaaFw={fw}，"
         f"已注册 CloseButton / GachaRecordPoolType / GachaRecordPage / GachaRecordFirstPage / GachaRecordExport")
    AgentServer.join()
    AgentServer.shut_down()
    return 0


if __name__ == "__main__":
    sys.exit(main())
