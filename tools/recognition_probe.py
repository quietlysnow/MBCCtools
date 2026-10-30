"""离线对单张 1280x720 截图跑真 MaaFW 识别：不用模拟器、不连 Adb。

用法（以下示例在仓库根目录执行；工具也可从其他目录用绝对路径调用）：

    python tools/recognition_probe.py 截图.png 密盟兑换/数量减号.png --roi 425,220,770,395
    python tools/recognition_probe.py 截图.png --ocr "获得物资" --roi 0,0,1280,720
    python tools/recognition_probe.py 截图.png 密盟兑换/数量减号.png --overlay global

模板路径相对 image/；--overlay 会把 bilibili/ 或 global/ 依次叠在 base 上。
资源默认定位到本脚本所在仓库，也可用 --resource-root 指定另一份 resource/。

开发依赖：pip install -r requirements-dev.txt；已有 opencv-python 时也可用它读图。
--json 输出完整识别结果。退出码 0 表示识别已完成（含未命中），1 表示运行错误，2 表示参数错误。
截图与模板不自动缩放；1280x720 为项目识别基准。此工具不连接设备、不执行游戏动作。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from maa.controller import CustomController
from maa.library import Library
from maa.pipeline import JOCR, JTemplateMatch
from maa.resource import Resource
from maa.tasker import LoggingLevelEnum, Tasker

REPOSITORY = Path(__file__).resolve().parent.parent


def load_image(path: str) -> np.ndarray:
    try:
        from PIL import Image
    except ImportError:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("需要读图依赖：python -m pip install -r requirements-dev.txt") from exc
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"读不到截图：{path}")
        return image
    else:
        # MaaFW 的图像缓冲按 BGR 解释；PIL 读出来是 RGB，转一下。
        with Image.open(path) as image:
            return np.ascontiguousarray(np.asarray(image.convert("RGB"))[:, :, ::-1])


class StubController(CustomController):
    """仅向框架提供静态图；不创建 Adb 控制器，输入回调显式拒绝动作。"""

    def __init__(self, image: np.ndarray) -> None:
        super().__init__()
        self._image = image

    def connect(self) -> bool:
        return True

    def request_uuid(self) -> str:
        return "recognition-probe"

    def get_features(self) -> int:
        return 0

    def screencap(self) -> np.ndarray:
        return self._image

    def start_app(self, intent):
        raise RuntimeError("离线工具禁止启动应用")

    def stop_app(self, intent):
        raise RuntimeError("离线工具禁止停止应用")

    def click(self, x, y):
        raise RuntimeError("离线工具禁止点击")

    def swipe(self, x1, y1, x2, y2, duration):
        raise RuntimeError("离线工具禁止滑动")


def parse_roi(text: str) -> list[int]:
    try:
        parts = [int(v) for v in text.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--roi 需要 4 个整数：x,y,w,h") from exc
    if len(parts) != 4 or any(value < 0 for value in parts):
        raise argparse.ArgumentTypeError("--roi 需要 4 个非负整数：x,y,w,h")
    if parts != [0, 0, 0, 0] and (parts[2] == 0 or parts[3] == 0):
        raise argparse.ArgumentTypeError("--roi 的宽高必须大于 0；全屏请用 0,0,0,0")
    return parts


def parse_threshold(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--threshold 必须为 0 到 1 之间的数值") from exc
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("--threshold 必须为 0 到 1 之间的数值")
    return value


def run_recognition(args) -> int:
    image = load_image(args.image)
    if image.shape[:2] != (720, 1280):
        print(f"警告：截图是 {image.shape[1]}x{image.shape[0]}，本项目基准是 1280x720；未自动缩放", file=sys.stderr)

    roi = args.roi
    if roi != [0, 0, 0, 0] and (roi[0] + roi[2] > image.shape[1] or roi[1] + roi[3] > image.shape[0]):
        raise argparse.ArgumentTypeError("--roi 超出截图范围")
    bundles = ["base"] + ([args.overlay] if args.overlay else [])
    resource_root = args.resource_root.resolve()
    if args.template:
        template = Path(args.template)
        if template.is_absolute() or ".." in template.parts:
            raise ValueError("模板路径必须相对资源包的 image/ 目录")
        if not any((resource_root / bundle / "image" / template).exists() for bundle in bundles):
            raise ValueError(f"找不到模板：{args.template}；请核对 image/ 下的路径")

    # 日志留在被忽略的本地目录；JSON 模式的标准输出只包含结果。
    Tasker.set_stdout_level(LoggingLevelEnum.Off if args.json else LoggingLevelEnum.Error)
    Tasker.set_log_dir(REPOSITORY / ".scratch/recognition-probe")

    resource = Resource()
    for bundle in bundles:
        if not resource.post_bundle(resource_root / bundle).wait().succeeded:
            raise RuntimeError(f"资源加载失败：{resource_root / bundle}")

    controller = StubController(image)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("无法初始化静态图控制器")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("无法绑定离线识别资源")

    if args.ocr:
        param = JOCR(expected=[args.ocr], roi=roi)
        detail = tasker.post_recognition("OCR", param, image)
    else:
        param = JTemplateMatch(template=[args.template], threshold=[args.threshold], roi=roi)
        detail = tasker.post_recognition("TemplateMatch", param, image)

    result = detail.wait().get()
    recognitions = [node.recognition for node in result.nodes if node.recognition] if result else []
    if not detail.succeeded or not recognitions:
        raise RuntimeError("框架识别执行失败，未返回有效结果；请检查 .scratch/recognition-probe 中的日志")
    recognition = recognitions[0]
    all_results = sorted(recognition.all_results, key=lambda item: -item.score)
    report = {
        "framework_version": Library.version(),
        "algorithm": "OCR" if args.ocr else "TemplateMatch",
        "bundles": bundles,
        "image_size": [image.shape[1], image.shape[0]],
        "roi": roi,
        "hit": recognition.hit,
        "box": list(recognition.box) if recognition.box else None,
        "results": [{"score": item.score, "box": list(item.box),
                     **({"text": item.text} if args.ocr else {})} for item in all_results],
        "device_connected": False,
        "actions_executed": False,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0
    print("hit:", report["hit"], "box:", report["box"])
    if args.ocr:
        for result in all_results[:10]:
            print(f"  {result.score:.3f}  {result.box}  {result.text}")
    else:
        for result in all_results[:5]:
            print(f"  {result.score:.3f}  {result.box}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="离线跑一次 MaaFW 识别")
    parser.add_argument("image", help="1280x720 截图路径")
    parser.add_argument("template", nargs="?", help="模板路径，相对资源包的 image/ 目录")
    parser.add_argument("--ocr", metavar="REGEX", help="改为跑 OCR，值为 expected 正则")
    parser.add_argument("--roi", type=parse_roi, default="0,0,0,0", help="识别范围 x,y,w,h（默认全屏）")
    parser.add_argument("--threshold", type=parse_threshold, default=0.7, help="模板阈值（默认 0.7）")
    parser.add_argument("--overlay", choices=["bilibili", "global"], help="叠加差异包")
    parser.add_argument("--resource-root", type=Path, default=REPOSITORY / "resource", help="指定 resource/ 目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果；未命中仍返回 0，请读取 hit 字段")
    args = parser.parse_args()

    if bool(args.template) == bool(args.ocr):
        parser.error("模板路径和 --ocr 必须且只能给一个")
    try:
        return run_recognition(args)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"离线识别失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
