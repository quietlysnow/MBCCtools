from pathlib import Path

import shutil

assets_dir = Path(__file__).parent.resolve() / "assets"
# 本仓库的 OCR 模型直接随 resource/base/model/ocr 发布（MaaFW 在 bundle 根加载），
# MaaCommonAssets 子模块已移除：只有这里也找不到模型时才该中断打包
bundle_ocr_dir = Path(__file__).parent.resolve() / "resource" / "base" / "model" / "ocr"


def configure_ocr_model():
    assets_ocr_dir = assets_dir / "MaaCommonAssets" / "OCR"
    if not assets_ocr_dir.exists():
        if bundle_ocr_dir.exists():
            print(f"File Not Found: {assets_ocr_dir}（模型已随包发布，跳过导入）")
            return
        print(f"OCR 模型缺失：{bundle_ocr_dir} 与 {assets_ocr_dir} 都不存在")
        exit(1)

    ocr_dir = assets_dir / "resource" / "model" / "ocr"
    if not ocr_dir.exists():   # copy default OCR model only if dir does not exist
        shutil.copytree(
            assets_dir / "MaaCommonAssets" / "OCR" / "ppocr_v5" / "zh_cn",
            ocr_dir,
            dirs_exist_ok=True,
        )
    else:
        print("Found existing OCR directory, skipping default OCR model import.")


if __name__ == "__main__":
    configure_ocr_model()

    print("OCR model configured.")
