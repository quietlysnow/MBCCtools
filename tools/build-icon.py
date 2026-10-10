"""从原画母版生成程序图标 logo.ico。

用法：
    python tools/build-icon.py 输出.ico [更多输出.ico ...]
    python tools/build-icon.py --check 输出.ico        # 只校验，不写入

默认从 resource/base/image/logo.png 取母版（1254x1254）。生成的 ICO 尺寸台阶：

    16 / 24 / 32         -> 裁切框「脸 + 护目镜」
    48 / 64 / 128 / 256  -> 整张原画

小尺寸用裁切框而不是缩整张原画：整幅原画缩到 16~32px 只剩色块，裁到脸和护目镜
之后至少还能看出两个镜片和头带。

帧格式是 BMP（<=64）与 PNG（>=128）混合，这是 Windows 图标最常见的排布：小帧走
DIB 兼容面最广，大帧走 PNG 压体积。两种载荷都交给 Pillow 序列化后原样搬运，不自己
拼 DIB 头，免得 biHeight / AND 掩码踩坑。
"""

import struct
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "resource" / "base" / "image" / "logo.png"

# 裁切框，坐标基准是原画缩到 512x512 时的像素，按母版实际尺寸等比换算
CROP_512 = (90, 116, 420, 392)
CROP_BASE = 512

SMALL_SIZES = (16, 24, 32)
LARGE_SIZES = (48, 64, 128, 256)
BMP_MAX = 64  # 这个尺寸及以下写成 DIB，其余写 PNG


def normalize_alpha(im):
    """把已经很实的像素提到全不透明。

    原画整体落在 alpha 240~254，几乎没有一个是 255；不处理的话图标在深色任务栏上
    会透出底色。只提升实心区域，边缘抗锯齿的过渡值保持原样。
    """
    r, g, b, a = im.split()
    a = a.point(lambda v: 255 if v >= 240 else v)
    return Image.merge("RGBA", (r, g, b, a))


def square_pad(im):
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((side - w) // 2, (side - h) // 2))
    return canvas


def render_all():
    master = Image.open(MASTER).convert("RGBA")
    scale = master.size[0] / CROP_BASE
    box = tuple(int(round(v * scale)) for v in CROP_512)
    face = square_pad(master.crop(box))

    frames = {}
    for size in SMALL_SIZES + LARGE_SIZES:
        art = face if size in SMALL_SIZES else master
        frame = art.resize((size, size), Image.LANCZOS)
        # 缩小会削对比，小尺寸再补一点锐化，否则 16px 只剩一层灰雾
        if size <= 32:
            frame = frame.filter(ImageFilter.UnsharpMask(radius=1, percent=70, threshold=0))
        frames[size] = normalize_alpha(frame)
    return frames


def pillow_payloads(frames, sizes, bitmap_format):
    """让 Pillow 把指定尺寸序列化成一个临时 ICO，再按尺寸把载荷取回来。"""
    ordered = sorted(sizes)
    buf = BytesIO()
    frames[ordered[-1]].save(
        buf,
        format="ICO",
        sizes=[(s, s) for s in ordered],
        append_images=[frames[s] for s in ordered],
        bitmap_format=bitmap_format,
    )
    data = buf.getvalue()
    count = struct.unpack("<H", data[4:6])[0]
    out = {}
    for i in range(count):
        off = 6 + i * 16
        w, _h, _cc, _r, _pl, _bpp, size, start = struct.unpack("<BBBBHHII", data[off:off + 16])
        out[w or 256] = data[start:start + size]
    return out


def build_ico():
    frames = render_all()
    small = pillow_payloads(frames, [s for s in SMALL_SIZES + LARGE_SIZES if s <= BMP_MAX], "bmp")
    large = pillow_payloads(frames, [s for s in LARGE_SIZES if s > BMP_MAX], None)

    payloads = {**small, **large}
    sizes = sorted(payloads)

    entries = b""
    blob = b""
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        data = payloads[size]
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,  # bColorCount
            0,  # bReserved
            1,  # wPlanes
            32,  # wBitCount
            len(data),
            offset,
        )
        blob += data
        offset += len(data)
    return struct.pack("<HHH", 0, 1, len(sizes)) + entries + blob


def describe(path):
    data = path.read_bytes()
    _reserved, _kind, count = struct.unpack("<HHH", data[:6])
    print(f"{path}  {len(data)} 字节  {count} 帧")
    ok = True
    for i in range(count):
        off = 6 + i * 16
        w, _h, _cc, _r, _pl, bpp, size, start = struct.unpack("<BBBBHHII", data[off:off + 16])
        declared = w or 256
        frame = data[start:start + size]
        if frame[:8] == b"\x89PNG\r\n\x1a\n":
            pw, ph = struct.unpack(">II", frame[16:24])
            fmt = "PNG"
        else:
            _hs, pw, ph = struct.unpack("<Iii", frame[:12])
            ph //= 2
            fmt = "DIB"
        flag = ""
        if (pw, ph) != (declared, declared):
            flag = "  <<< 目录标注与实际像素不符"
            ok = False
        print(f"   {declared:3d}px  实际 {pw}x{ph}  {fmt}  bpp={bpp}  {size} 字节{flag}")
    return ok


def main():
    args = sys.argv[1:]
    if args and args[0] == "--check":
        targets = [Path(a) for a in args[1:]]
        if not targets:
            sys.exit("--check 后面要给文件路径")
        sys.exit(0 if all(describe(p) for p in targets) else 1)

    if not MASTER.exists():
        sys.exit(f"找不到母版：{MASTER}")

    targets = [Path(a) for a in args] or [ROOT / "resource" / "base" / "image" / "logo.ico"]
    blob = build_ico()
    for target in targets:
        target.write_bytes(blob)
        print(f"已写入 {target}")
        describe(target)


if __name__ == "__main__":
    main()
