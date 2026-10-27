"""离线对单张 1280x720 截图跑真 MaaFW 识别：不用模拟器、不连 Adb。

用法（在仓库根目录执行）：

    python tools/recognition_probe.py 截图.png 密盟兑换/数量减号.png --roi 425,220,770,395
    python tools/recognition_probe.py 截图.png --ocr "获得物资" --roi 0,0,1280,720
    python tools/recognition_probe.py 截图.png 密盟兑换/数量减号.png --overlay global

模板路径相对 resource/base/image/；--overlay 会把 bilibili/ 或 global/ 依次叠在 base 上。

依赖：MaaFw（pip install -r requirements.txt）+ Pillow 或 opencv-python 任一
（两者都没有时：pip install pillow）。
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

try:
    from PIL import Image

    def load_image(path: str) -> np.ndarray:
        # MaaFW 的图像缓冲按 BGR 解释；PIL 读出来是 RGB，转一下。
        return np.array(Image.open(path).convert("RGB"))[:, :, ::-1]

except ImportError:
    try:
        import cv2

        def load_image(path: str) -> np.ndarray:
            image = cv2.imread(path)
            if image is None:
                raise SystemExit(f"读不到截图：{path}")
            return image

    except ImportError:
        raise SystemExit("需要 Pillow 或 opencv-python 读取截图：pip install pillow")

from maa.controller import CustomController
from maa.pipeline import JOCR, JTemplateMatch
from maa.resource import Resource
from maa.tasker import Tasker


class StubController(CustomController):
    """只提供 screencap 的假控制器，让 Tasker 能初始化；其余输入回调一律空实现。"""

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

    def __getattr__(self, _name: str):
        return lambda *_args, **_kwargs: True


def parse_roi(text: str) -> list[int]:
    parts = [int(v) for v in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("--roi 需要 4 个整数：x,y,w,h")
    return parts


def run_recognition(args) -> int:
    image = load_image(args.image)
    if image.shape[:2] != (720, 1280):
        print(f"警告：截图是 {image.shape[1]}x{image.shape[0]}，本项目基准是 1280x720")

    resource = Resource()
    if not resource.post_bundle("resource/base").wait().succeeded:
        print("resource/base 加载失败")
        return 1
    if args.overlay:
        if not resource.post_bundle(f"resource/{args.overlay}").wait().succeeded:
            print(f"resource/{args.overlay} 加载失败")
            return 1

    tasker = Tasker()
    tasker.bind(resource, StubController(image))

    roi = parse_roi(args.roi)
    if args.ocr:
        param = JOCR(expected=[args.ocr], roi=roi)
        detail = tasker.post_recognition("OCR", param, image)
    else:
        param = JTemplateMatch(template=[args.template], threshold=[args.threshold], roi=roi)
        detail = tasker.post_recognition("TemplateMatch", param, image)

    recognition = detail.wait().get().nodes[0].recognition
    print("hit:", recognition.hit, "box:", recognition.box)
    if args.ocr:
        for result in recognition.all_results[:10]:
            print(f"  {result.score:.3f}  {result.box}  {result.text}")
    else:
        for result in sorted(recognition.all_results, key=lambda r: -r.score)[:5]:
            print(f"  {result.score:.3f}  {result.box}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="离线跑一次 MaaFW 识别")
    parser.add_argument("image", help="1280x720 截图路径")
    parser.add_argument("template", nargs="?", help="模板路径，相对 resource/base/image/")
    parser.add_argument("--ocr", metavar="REGEX", help="改为跑 OCR，值为 expected 正则")
    parser.add_argument("--roi", default="0,0,0,0", help="识别范围 x,y,w,h（默认全屏）")
    parser.add_argument("--threshold", type=float, default=0.7, help="模板阈值（默认 0.7）")
    parser.add_argument("--overlay", choices=["bilibili", "global"], help="叠加差异包")
    args = parser.parse_args()

    if bool(args.template) == bool(args.ocr):
        parser.error("模板路径和 --ocr 必须且只能给一个")
    return run_recognition(args)


if __name__ == "__main__":
    sys.exit(main())
