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
import time

try:
    import cv2
except ImportError:  # 页码放大用；缺失时退回原尺寸识别
    cv2 = None

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


def _as_point(value, default):
    """点位参数 [x, y]。形状与 _as_x_range 一样，但含义是坐标不是区间，别混用"""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    return default


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


# 累计记录：按追踪类型分文件存放在该目录下（<类型>.jsonl，如 活动.jsonl；
# 类型没识别出来的落 未判.jsonl）。出新卡池后跑一次就把没见过的追加进去
DEFAULT_ARCHIVE = "record/抽卡记录"
# focus 只能引用固定路径（占位符替换不了动态值），所以摘要也覆盖同一个文件
DEFAULT_REPORT = "record/抽卡记录.md"


class _RecordSession:
    """一次采集会话。path 是分类型档案目录，写入时按当前追踪类型落 <类型>.jsonl。

    store_counts 是开跑前从目录下所有档案读到的"每条记录出现过几次"，run_counts 是本次
    已经看到的次数；本次第 n 次看到某条记录时，只有 n > store_counts 才算新记录 ——
    这样十连里同秒重复的同名条目（实测存在）不会被误判成已采过。
    """

    def __init__(self, path, ts, store_counts):
        self.path = path
        self.ts = ts
        self.store_counts = store_counts
        self.run_counts = {}
        self.last_page = None
        self.back_keys = None
        self.stall_retries = 0
        self.attempts = 0
        self.new_count = 0
        # 页头追踪类型，由 GachaRecordPoolType 在采集前写入；没识别出来保持 None
        self.pool_type = None

    def file_for(self, pool_type):
        """当前类型对应的累计档案；类型没识别出来时落 未判.jsonl"""
        return self.path / f"{pool_type or '未判'}.jsonl"


_sessions = {}


def _project_root():
    # interface.json 与 agent/ 同级；不依赖 CWD，手动跑脚本时路径也一致
    return pathlib.Path(__file__).resolve().parent.parent


def _load_store(archive_dir):
    """读档案目录下所有 <类型>.jsonl，返回全局 key->出现次数 与总条数。

    身份键含时间+卡池+名称，跨类型不可能撞，全局一份去重计数即可。"""
    counts = {}
    total = 0
    for fp in sorted(archive_dir.glob("*.jsonl")):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                try:
                    key = json.loads(line)["key"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                counts[key] = counts.get(key, 0) + 1
                total += 1
    return counts, total


def _get_session(archive):
    session = _sessions.get(archive)
    if session is not None:
        return session
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    root = _project_root() / archive
    root.mkdir(parents=True, exist_ok=True)
    store_counts, total = _load_store(root)
    session = _RecordSession(root, ts, store_counts)
    _sessions[archive] = session
    _log(f"抽卡记录会话开始 -> {root}（已有 {total} 条）")
    return session


def _read_page_number(context, image, page_roi, min_score):
    """读底栏 ◀ 页码 ▶ 中间的数字，返回 int；读不到返回 None。

    页码渲染偏小（实测最小 8x12 像素，原尺寸直接 OCR 会把 '2' 读成 'C' 0.41），
    所以把该区域裁出来放大 4 倍再识别（实测放大后 0.96~1.0）。
    None 意味着这一眼读不出页码：不在记录页、或页面切换的中间帧。
    注：实测末页是"页码停住不再前进"（走 no_advance 那条），不是显示成 "-"——
    2026-10-10 常驻池末页与活动池第 50 页都是如此。"""
    x, y, w, h = page_roi
    crop = image[y:y + h, x:x + w]
    if cv2 is not None and crop.size:
        crop = cv2.resize(crop, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)
    detail = context.run_recognition_direct(
        JRecognitionType.OCR,
        JOCR(roi=[0, 0, crop.shape[1], crop.shape[0]]),
        crop,
    )
    results = getattr(detail, "all_results", None) or getattr(detail, "filtered_results", None) or []
    best = None
    for result in results:
        text = (getattr(result, "text", "") or "").strip()
        score = float(getattr(result, "score", 0.0))
        if not text.isdigit() or score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, int(text))
    return best[1] if best else None


def _probe_back(context, page_roi, min_score, back_point, page_no):
    """判停前的对照点击：点一次 ◀ 再看页码，区分"真到底"和"输入失灵"。

    末页没有任何可辨识的图像特征——2026-10-10 逐像素实测：末页的 ▶ 与可用页完全一致
    （最大像素差 0），游戏既不隐藏也不置灰，点它只是不动。但同一次实验里 ◀ / ▶ 在非末页
    都有响应，所以"点 ◀ 后页码变了"能反证输入通道是通的，剩下的可能就是列表到头。

    返回 (结论, 点击后的页码)：
        ok      通道正常（页码变了）→ 判定到达末页
        stall   点了没反应（页码没变）→ 疑似输入失灵
        unknown 点后读不到页码（离开记录页 / 中间帧）→ 状态不明
    注意本函数会真的翻回上一页；调用方都在收尾路径上，翻不翻回去无所谓。
    调用方在第 1 页会跳过本函数：那一页的 ◀ 本来就不可用，点了没反应说明不了任何事。
    """
    ctrl = context.tasker.controller
    ctrl.post_click(back_point[0], back_point[1]).wait()
    time.sleep(0.8)
    ctrl.post_screencap().wait()
    after = _read_page_number(context, ctrl.cached_image, page_roi, min_score)
    if after is None:
        return "unknown", after
    return ("ok" if after != page_no else "stall"), after


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


# 实测（2026-09-29 逐池截图）：抽卡页四个池是 活动/综合/定向/常驻，
# 记录页页头对应「{类型}追踪 · 近期抽卡记录(UTC+8)」。注意没有"常规"这个类型。
DEFAULT_POOL_TYPES = ["活动", "综合", "定向", "常驻"]
# OCR 把小字号的「综合」标签读成"统合"（置信度 1.0，形近字），类型匹配要把别名算上
TYPE_ALIASES = {"综合": ["统合"]}


def _match_type(text, types):
    """按包含匹配类型词（text 需已去空白），命中别名也算，返回规范类型名；没命中返回 None。"""
    for t in types:
        if t in text:
            return t
    for t, aliases in TYPE_ALIASES.items():
        if t in types and any(a in text for a in aliases):
            return t
    return None


@AgentServer.custom_recognition("GachaRecordPoolType")
class GachaRecordPoolType(CustomRecognition):
    """识别记录页页头的追踪类型，写进会话，随每条记录存档、导出时作「类型」列。

    页头是「{类型}追踪 · 近期抽卡记录(UTC+8)」的形态，按"包含"匹配四种类型
    （OCR 掉首字也能对上）；types 参数可覆盖清单，游戏改文案时不用动代码。
    开跑时跑一次：翻页不换池，类型整轮不变，本次采到的记录都归这个类型。
    未命中返回 None（不在记录页 / 文案变了）。此时也要把会话里的旧类型清掉，
    否则同一进程内第二次跑会把上一次的类型错挂到这次的记录上。
    类型识别不出来不阻断采集（父节点 on_error 照走），记录落 未判.jsonl。
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
            matched = _match_type(re.sub(r"\s+", "", text), types)
            if matched and (best is None or score > best[0]):
                best = (score, matched, text, box)

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
    """判断记录列表是否已回到第 1 页：点一次 ◀ 后行内容不再变化 = 已在第 1 页（◀ 已禁用）。

    水位线按"记录内容已存在"停，前提是从第 1 页往下扫；开跑停在中间页时第一屏全是旧记录，
    会被当成到底、一条新的都采不到还不报错，所以先把列表翻回顶部。
    早期实现读底栏页码，实测页码渲染大小不一（'2' 有时只有 8x12 像素）、OCR 读成 'C' 0.41，
    靠不住；改用行内容比对，行签名与上一眼相同就未命中放行，交给采集节点。
    本节点动作是点 ◀，坐标在抽卡页上紧挨「追踪一次」按钮，所以先过记录页门卫
    （页头「近期抽卡记录」），不在记录页绝不命中、绝不点击。
    参数与 GachaRecordPage 相同（roi 取列表区域），上一眼的行签名存会话的 back_keys。
    """

    def analyze(self, context, argv):
        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        session = _get_session(archive)

        roi = _rect_of(argv.roi) or [0, 0, argv.image.shape[1], argv.image.shape[0]]
        if tuple(roi) == (0, 0, 0, 0):
            h, w = argv.image.shape[0], argv.image.shape[1]
            roi = _as_rect(param.get("roi"), [0, 0, w, h])

        min_score = float(param.get("min_score", 0.5))
        line_tol = int(param.get("line_tol", 14))
        badge_x = _as_x_range(param.get("badge_x"))
        gate_roi = _as_rect(param.get("gate_roi"), [411, 210, 420, 55])
        gate_text = param.get("gate_text") or "近期抽卡记录"

        # 门卫：不在记录页（页头没有「近期抽卡记录」）绝不命中。本节点的动作是点 ◀，
        # 坐标在抽卡页上紧挨「追踪一次」按钮，一旦在错误页面点击可能误触抽卡。
        if not _ocr_find(context, argv.image, gate_roi, [gate_text], min_score):
            return None

        rows, _ = _ocr_rows(context, argv.image, roi, min_score, line_tol, badge_x)
        keys = [_row_sig(cells) for cells in rows]
        if not keys:
            # 读不到行（空池）：不点 ◀，交给采集节点的门卫与路由
            return None

        if keys == session.back_keys:
            # ◀ 点击可能延迟生效，首帧往往还是旧页：重截一帧确认，变了就继续翻
            time.sleep(0.6)
            ctrl = context.tasker.controller
            ctrl.post_screencap().wait()
            rows2, _ = _ocr_rows(context, ctrl.cached_image, roi, min_score, line_tol, badge_x)
            keys2 = [_row_sig(cells) for cells in rows2]
            if not keys2 or keys2 == keys:
                session.back_keys = None
                return None  # 内容稳定 = 已在第 1 页
            keys = keys2

        session.back_keys = keys
        return self.AnalyzeResult(box=roi, detail={"rows": len(rows)})


@AgentServer.custom_recognition("GachaRecordPage")
class GachaRecordPage(CustomRecognition):
    """读抽卡记录列表页当前可见的记录，追加进累计档案。

    两种采集方式由 stop_on_known 切换：
      完整识别（默认）：从第 1 页完整翻到最后一页，每页逐行与档案去重比对，只追加
                        没见过的记录。不会漏页，列表长时较慢。
      识别到已知停止：  从第 1 页往下扫，撞见第一条档案里已有的记录就立即停止——
                        出新卡池后跑一次只补最上面的新页，快，但中断过的采集会漏页。
    "翻到最后一页"的判定靠页码：每页读完翻页，下一眼读页码——页码前进 = 翻页成功；
    页码不变 = 点击延迟/丢失，重试翻页（最多 3 次，每次都先重截确认）；页码消失
    （游戏在末页后再翻会显示"-"）= 列表到头。页码区域裁出后放大 4 倍再 OCR，
    实测小字号也能 0.96~1.0 可靠读出。

    pipeline 参数（写在 custom_recognition_param 里）:
        archive:        str    分类型档案目录，默认 record/抽卡记录；开跑前读目录下所有
                               <类型>.jsonl 统计已有记录（去重计数），写入时按当前追踪类型
                               落 <类型>.jsonl
        roi:            [x,y,w,h] 列表区域，不写就是全屏；节点自身的 roi 优先
        gate_roi:       [x,y,w,h] 页头识别区域，默认 [414,218,425,60]，覆盖「…近期抽卡记录(UTC+8)」
        gate_text:      str    门卫关键词，默认 近期抽卡记录（只有记录页的页头有这行字）
        page_roi:       [x,y,w,h] 底栏页码区域，默认 [735,625,65,36]
        min_score:      float  OCR 置信度下限，默认 0.5
        line_tol:       int    判定"同一行"的 y 中心容差像素，默认 14
        badge_x:        [x0,x1] 徽章列的横向范围，用来剔掉该列里偶尔被 OCR 读出来的碎片，不给就不剔
        rarity_dir:     str  徽章模板根目录，相对 image/，默认 "抽卡"
        rarity_tiers:   [str] 有哪几档，对应 rarity_dir 下的同名子目录（如 抽卡/狂/*.png）；不给就不判档
        rarity_floor:   float 最高分低于它就算未匹配，落成 "未知:档:分值" 提醒补图，默认 0.5
        max_pages:      int    单次运行最多识别次数（防失控的兜底），默认 100
        stop_on_known:  bool  true = 识别到已知停止；缺省 false = 完整识别
        next_fresh:     str  每页读完（无论有无新记录）都去的节点，默认 抽卡记录翻页
        next_done:      str  判停（页码消失/同页/空页/不在记录页）时去的节点，默认 抽卡记录汇总
        next_last:      str  确认到达末页（含单页列表）时去的节点，默认 抽卡记录末页
        next_overflow:  str  达到 max_pages 时去的节点，默认 抽卡记录汇总
        back_point:     [x,y] 底栏 ◀ 的坐标，默认 [711,645]；判停时点它反证输入通道
        max_stall_retries: int 页码不动时连续重试翻页的上限，默认 2
    每条记录附带 type 字段 = GachaRecordPoolType 在本轮采集前识别出的追踪类型（未识别为 null）。
    路由是本设计的核心：识别几乎总是命中，"接下来去哪"由 override_next 按结果动态改写——
    每页读完都走 next_fresh 翻页继续，判停（页码消失/同页/空页/不在记录页）走 next_done 汇总
    导出，识别次数用尽走 next_overflow。
    绝不靠"未命中 + 超时"推进流程：那会触发框架的 error handling loop 检测（实测直接终止任务），
    还要白等 timeout。所以「翻页」节点不做识别（DirectHit + 定点 roi，roi 即点击点），
    翻页有没有生效一律交回页码仲裁，只有页码确实不再前进才收尾；收尾前再点一次 ◀
    反证输入通道（实测末页的 ▶ 与可用态像素级一致，图像上看不出"到底"，只能这样反证）。
    """

    def _route(self, context, argv, next_node, box, detail):
        """把本节点的 next 改写成 next_node 并以命中收场。

        override_next 是任务级持久的，所以每条路径都显式设置一次，保证下一轮状态确定；
        万一改写失败（节点名对不上），节点自身的静态 next 仍然兜底，流程不会断。
        """
        if not context.override_next(argv.node_name, [next_node]):
            _log(f"GachaRecordPage override_next({next_node}) 失败，沿用节点静态 next")
        return self.AnalyzeResult(box=box, detail=detail)

    def _scan_fresh(self, session, rows, keys, rarities):
        """整页逐行与档案去重比对：出现次数超过已存次数的才算新记录
        （十连里同秒重复的同名条目靠这个计数规则保留）。"""
        fresh = []
        for cells, key, rarity in zip(rows, keys, rarities):
            if len(cells) < 3:
                # 一条正经记录至少有 时间/卡池/名称 三列；空池的提示语、OCR 截断的行都不是记录
                continue
            session.run_counts[key] = session.run_counts.get(key, 0) + 1
            if session.run_counts[key] > session.store_counts.get(key, 0):
                fresh.append((cells, key, rarity))
        return fresh

    def analyze(self, context, argv):
        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        session = _get_session(archive)

        next_fresh = param.get("next_fresh") or "抽卡记录翻页"
        next_done = param.get("next_done") or "抽卡记录汇总"
        next_last = param.get("next_last") or "抽卡记录末页"
        next_overflow = param.get("next_overflow") or "抽卡记录汇总"
        gate_roi = _as_rect(param.get("gate_roi"), [411, 210, 420, 55])
        gate_text = param.get("gate_text") or "近期抽卡记录"
        page_roi = _as_rect(param.get("page_roi"), [735, 625, 65, 36])
        back_point = _as_point(param.get("back_point"), [711, 645])
        max_stall = int(param.get("max_stall_retries", 2))
        stop_on_known = bool(param.get("stop_on_known"))
        min_score = float(param.get("min_score", 0.5))
        line_tol = int(param.get("line_tol", 14))
        badge_x = _as_x_range(param.get("badge_x"))

        roi = _rect_of(argv.roi) or [0, 0, argv.image.shape[1], argv.image.shape[0]]
        if tuple(roi) == (0, 0, 0, 0):
            h, w = argv.image.shape[0], argv.image.shape[1]
            roi = _as_rect(param.get("roi"), [0, 0, w, h])

        session.attempts += 1
        if session.attempts > int(param.get("max_pages", 100)):
            _log(f"GachaRecordPage 达到 max_pages，转汇总导出（本次已新增 {session.new_count} 条）")
            return self._route(context, argv, next_overflow, roi,
                               {"reason": "max_pages", "new": session.new_count})

        ctrl = context.tasker.controller
        image = argv.image
        outcome = None
        rows = boxes = keys = rarities = None
        fresh = []
        for attempt in range(2):
            # 记录页门卫：页头「…近期抽卡记录(UTC+8)」只有记录页有。入口直通，
            # 没这道门就会把任意屏幕上的文字当记录写进累计档案，宁可放弃这一页。
            if not _ocr_find(context, image, gate_roi, [gate_text], min_score):
                outcome = ("off_page", {})
                rows = boxes = keys = rarities = None
            else:
                # 页码是"翻页是否生效 / 是否到最后一页"的主判据（裁出放大后 OCR，可靠）
                page_no = _read_page_number(context, image, page_roi, min_score)
                if page_no is None:
                    # 翻过最后一页（游戏把页码显示成"-"）或不在记录页
                    outcome = ("no_more_pages", {})
                    rows = boxes = keys = rarities = None
                elif page_no == session.last_page:
                    # 页码没动 = 翻页没生效（点击延迟/丢失）或已在最后一页
                    outcome = ("no_advance", {"page": page_no})
                else:
                    session.last_page = page_no
                    rows, boxes = _ocr_rows(context, image, roi, min_score, line_tol, badge_x)
                    keys = [_row_sig(cells) for cells in rows]
                    if not rows:
                        outcome = ("empty", {})
                    else:
                        rarities = _rarity_by_row(
                            context, image, boxes,
                            param.get("rarity_dir", "抽卡"),
                            param.get("rarity_tiers") or [],
                            float(param.get("rarity_floor", 0.5)),
                        )
                        unknown = [r for r in rarities if r and r.startswith("未知")]
                        if unknown:
                            _log(f"GachaRecordPage 有徽章没匹上任何档，需要往对应目录补图: {unknown}")
                        fresh = self._scan_fresh(session, rows, keys, rarities)
                        if stop_on_known and not fresh:
                            # 识别到已知停止：本页全是已入库的记录，下面的页只会更旧，
                            # 立即停（这一眼不是翻页后的确认，没有竞态，不需要重截）
                            outcome = ("known_stop", {})
                            break
                        outcome = None
            if outcome is None:
                break
            if attempt == 0:
                # 停一次再确认：翻页点击可能延迟生效，首帧往往还是旧页
                time.sleep(0.8)
                ctrl.post_screencap().wait()
                image = ctrl.cached_image

        if outcome is not None:
            reason, detail = outcome
            if reason == "no_advance" and session.stall_retries < max_stall:
                # 页码不动先别判停：模拟器卡顿、点击延迟/丢失都会这样。
                # 路由回「翻页」再点一次 ▶；每次回来都会先重截一帧确认，最多 max_stall 次。
                session.stall_retries += 1
                _log(f"GachaRecordPage 页码停在第 {detail.get('page')} 页，"
                     f"重试翻页（第 {session.stall_retries}/{max_stall} 次）")
                return self._route(context, argv, next_fresh,
                                   boxes[0] if boxes else roi, {"reason": reason, **detail})
            session.stall_retries = 0
            # 判停去哪儿：确认到达末页（含单页列表）走 next_last，其余（不在记录页 / 空页 /
            # 达到 max_pages / 识别到已知停止 / 输入疑似失灵）都走 next_done。
            done_target = next_done
            if reason == "no_advance":
                page_now = detail.get("page")
                if page_now is not None and page_now <= 1:
                    # 停在第 1 页：◀ 在这一页本就不可用，对照点击反证不了什么；
                    # 第 1 页上 ▶ 不动本身就是"列表只有一页"的证据。
                    detail["probe"] = "single_page"
                    done_target = next_last
                    _log("GachaRecordPage 判停：停在第 1 页，▶ 无响应即列表只有一页"
                         "（◀ 在第 1 页不可用，无法用对照点击反证输入通道）")
                else:
                    # 重试用尽仍不动：末页与"点击失灵"在图像上完全一样（实测 ▶ 像素级一致），
                    # 点一次 ◀ 反证输入通道——页码变了说明通道没问题，就是列表到底了。
                    verdict, after = _probe_back(
                        context, page_roi, min_score, back_point, page_now)
                    detail["probe"] = verdict
                    detail["probe_page"] = after
                    if verdict == "ok":
                        done_target = next_last
                        _log(f"GachaRecordPage 判停：点 ◀ 页码回到 {after}，输入通道正常，判定为最后一页")
                    elif verdict == "stall":
                        _log(f"GachaRecordPage ⚠ 判停：点 ◀ 后页码仍是 {after}，"
                             f"翻页与返回键都没响应，疑似输入通道失灵，本次采集可能不完整")
                    else:
                        _log("GachaRecordPage ⚠ 判停：点 ◀ 后读不到页码（可能已离开记录页），状态不明，请复核")
            _log(f"GachaRecordPage 判停（{reason}），转 {done_target} 导出")
            return self._route(context, argv, done_target,
                               boxes[0] if boxes else roi, {"reason": reason, **detail})

        # 本页读完了，页号记入会话供下一页判断翻页是否生效
        session.stall_retries = 0
        total = sum(session.store_counts.values())
        if fresh:
            target = session.file_for(session.pool_type)
            with open(target, "a", encoding="utf-8") as f:
                for cells, key, rarity in fresh:
                    session.new_count += 1
                    total += 1
                    # 同步抬上去重计数：同一条记录本轮再见到时不会被当成新的
                    session.store_counts[key] = session.store_counts.get(key, 0) + 1
                    f.write(json.dumps(
                        {"index": total, "key": key, "rarity": rarity,
                         "type": session.pool_type, "cells": list(cells)},
                        ensure_ascii=False,
                    ) + "\n")
            _log(f"GachaRecordPage 第 {page_no} 页：采到 {len(rows)} 行，新增 {len(fresh)} 条 -> {target.name}，累计 {total} 条")
        else:
            _log(f"GachaRecordPage 第 {page_no} 页：{len(rows)} 行都已入库，无新增，继续翻页")
        # 每页读完都翻页继续。override 每轮都显式重置，防止上一页留下的路由残留。
        return self._route(context, argv, next_fresh, boxes[-1],
                           {"page": page_no, "rows": len(rows), "new_rows": len(fresh),
                            "total": total, "archive": str(session.path)})


def _ocr_find(context, image, roi, targets, min_score, aliases=None):
    """在 roi 里找包含任一 target 的文字（去掉全部空白后按包含匹配，aliases 为每个
    target 的 OCR 误读别名），取置信度最高的一条。

    返回 (score, target, 原文, box)，找不到返回 None 并把 OCR 候选写进日志便于排查。"""
    aliases = aliases or {}
    detail = context.run_recognition_direct(JRecognitionType.OCR, JOCR(roi=roi), image)
    results = getattr(detail, "all_results", None) or getattr(detail, "filtered_results", None) or []
    best = None
    seen = []
    for result in results:
        text = re.sub(r"\s+", "", (getattr(result, "text", "") or ""))
        box = _rect_of(getattr(result, "box", None))
        score = float(getattr(result, "score", 0.0))
        if not text or box is None:
            continue
        seen.append((text, round(score, 2)))
        if score < min_score:
            continue
        for t in targets:
            names = [t] + list(aliases.get(t, []))
            if any(n in text for n in names) and (best is None or score > best[0]):
                best = (score, t, text, box)
                break
    if best is None and seen:
        _log(f"_ocr_find 在 roi={roi} 没匹配到 {targets}，OCR 候选: {seen}")
    return best


@AgentServer.custom_action("GachaRecordBeginRun")
class GachaRecordBeginRun(CustomAction):
    """一次任务运行的起点：丢弃同进程内可能残留的上一轮会话。

    AgentServer 进程常驻，上一轮若没走到汇总导出（用户手动停止、流程中断），
    _sessions 里会留下带旧去重计数 / 翻页状态的会话——下一轮判断会出错。
    入口节点先跑本动作，保证每轮都从全新会话开始（档案不动，
    去重计数由 _get_session 重新从档案统计）。
    """

    def run(self, context, argv):
        param = _parse_param(argv)
        archive = param.get("archive") or DEFAULT_ARCHIVE
        old = _sessions.pop(archive, None)
        if old is not None:
            _log(f"GachaRecordBeginRun 丢弃残留会话（上轮新增 {old.new_count} 条）")
        return True


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


def _type_order(groups):
    """xlsx 分表与摘要分组的展示顺序：四个追踪类型按固定序，其余（含「未判」）排后面。"""
    return (
        [t for t in DEFAULT_POOL_TYPES if t in groups]
        + sorted(t for t in groups if t not in DEFAULT_POOL_TYPES and t != "未判")
        + (["未判"] if "未判" in groups else [])
    )


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
        "## 各类型",
        "",
        "| 类型 | 抽数 | " + " | ".join(order) + " |",
        "| --- | --- | " + " | ".join(["---"] * len(order)) + " |",
    ]
    for type_name in _type_order(groups):
        recs = groups[type_name]
        row = [str(sum(1 for r in recs if (r["rarity"] or "未判") == t)) for t in order]
        lines.append(f"| {type_name} | {len(recs)} | " + " | ".join(row))

    hits = [(rec, type_name) for type_name, recs in groups.items() for rec in recs
            if (rec["rarity"] or "未判") in rare]
    hits.sort(key=lambda x: _record_time(x[0]), reverse=True)
    lines += ["", f"## 出货（{'、'.join(rare)}，最近 {min(len(hits), 60)} 条）", ""]
    if hits:
        lines += ["| 时间 | 类型 | 卡池 | 稀有度 | 名称 | 档案序号 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for rec, type_name in hits[:60]:
            cells = rec["cells"]
            name_ = cells[-1] if len(cells) >= 3 else " ".join(cells)
            pool_ = cells[1] if len(cells) >= 3 else ""
            lines.append(f"| {_record_time(rec)} | {type_name} | {pool_} "
                         f"| {rec['rarity']} | {name_} | {rec['index']} |")
        if len(hits) > 60:
            lines.append(f"\n更早的 {len(hits) - 60} 条见 xlsx。")
    else:
        lines.append("没有出货。")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@AgentServer.custom_action("GachaRecordExport")
class GachaRecordExport(CustomAction):
    """收尾：把分类型档案目录转成 Excel（一个追踪类型一张表）+ Markdown 摘要，并结束会话。

    pipeline 参数（写在 custom_action_param 里）:
        archive:  str  与识别器同一个值，指向分类型档案目录（<类型>.jsonl 所在处）
        excel:    str  导出路径，默认 archive 加 .xlsx 后缀（固定名字，每次覆盖）
        report:   str  Markdown 摘要的固定路径，默认 record/抽卡记录.md；界面侧直接读这个文件，
                       不走 focus 弹窗（2026-10-10 起 pipeline 里不再有引用它的 focus）
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
        if not any(session.path.glob("*.jsonl")):
            _log(f"GachaRecordExport 档案目录为空: {session.path}")
            return True

        pattern = param.get("excel") or f"{archive}.xlsx"
        out = _project_root() / pattern.format(ts=session.ts)
        out.parent.mkdir(parents=True, exist_ok=True)
        groups = {}
        total = 0
        for fp in sorted(session.path.glob("*.jsonl")):
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    total += 1
                    # 一个追踪类型一张表；没认出类型的记录落进「未判」
                    groups.setdefault(rec.get("type") or "未判", []).append(rec)

        if Workbook is not None:
            wb = Workbook()
            wb.remove(wb.active)
            used = set()
            for type_name in _type_order(groups):
                ws = wb.create_sheet(_sheet_name(type_name, used))
                ws.append(["时间", "卡池", "稀有度", "名称", "档案序号"])
                # 档案是"单次采集内部新在前、多次采集按跑的先后追加"，直接倒出来顺序是乱的，按时间重排
                for rec in sorted(groups[type_name], key=_record_time, reverse=True):
                    cells = rec["cells"]
                    # 实测列序为 时间 / 卡池 / 名称；列数不足就把原文并到名称里，不做猜测
                    time_, pool_, name_ = (
                        (cells[0], cells[1], cells[-1]) if len(cells) >= 3 else ("", "", " / ".join(cells))
                    )
                    ws.append([_record_time(rec), pool_, rec["rarity"], name_, rec["index"]])
            wb.save(out)

        report = param.get("report") or DEFAULT_REPORT
        report_path = _project_root() / report
        _write_report(report_path, groups, session, total)
        _log(
            f"抽卡记录导出：本次新增 {session.new_count} 条 / 累计 {total} 条 / {len(groups)} 个追踪类型 "
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
         f"已注册 CloseButton / GachaRecordBeginRun / GachaRecordPoolType / GachaRecordPage / "
         f"GachaRecordFirstPage / GachaRecordExport")
    AgentServer.join()
    AgentServer.shut_down()
    return 0


if __name__ == "__main__":
    sys.exit(main())
