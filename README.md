<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img alt="LOGO" src="https://github.com/quietlysnow/MBCCtools/blob/main/resource/base/image/1.jpg" width="256" height="256" />
</p>

<div align="center">

# MBCCtools

</div>

本仓库为 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 所提供的项目模板，开发者可基于此模板直接创建自己的 MaaXXX 项目。

> **MaaFramework** 是基于图像识别技术、运用 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 开发经验去芜存菁、完全重写的新一代自动化黑盒测试框架。
> 低代码的同时仍拥有高扩展性，旨在打造一款丰富、领先、且实用的开源库，助力开发者轻松编写出更好的黑盒测试程序，并推广普及。

## 即刻开始

- [📄 快速开始](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/1.1-%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.md)
- [🎞️ 视频教程](https://www.bilibili.com/video/BV1yr421E7MW)

## 如何开发

0. 使用右上角 `Use this template` - `Create a new repository` 来基于本模板创建您自己的项目。

1. 克隆本项目及子项目（地址请修改为您基于本模板创建的新项目地址）。

    ```bash
    git clone https://github.com/MaaXYZ/MaaPracticeBoilerplate.git
    ```

2. 下载 MaaFramework 的 [Release 包](https://github.com/MaaXYZ/MaaFramework/releases)，解压到 `deps` 文件夹中。

3. 下载通用资源子模块（MaaCommonAssets）

    ```bash
    git submodule update --init --recursive
    ```

    请注意，子模块仓库体积较大，请确认您已经成功下载，否则后续 OCR（文字识别）将报错并无识别结果。  
    若 git 命令始终无法成功下载，也可尝试前往 [Mirror酱](https://mirrorchyan.com/zh/projects?rid=MaaCommonAssets&source=ghtempl-readme) 手动下载后解压到 `assets/MaaCommonAssets` 文件夹中，目录结构为 `assets/MaaCommonAssets/OCR`。

4. 配置资源文件。

    ```bash
    python ./configure.py
    ```

    若报错 `File Not Found: XXXXXX`，则说明上一步 MaaCommonAssets 未正常下载，请再次检查！

5. 进行开发工作，按您的业务需求修改 `assets` 中的资源文件，请参考 [MaaFramework 相关文档](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/1.1-%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.md#%E8%B5%84%E6%BA%90%E5%87%86%E5%A4%87)。

6. 完成开发后，上传您的代码并发布版本。

    ```bash
    # 配置 git 信息（仅第一次需要，后续不用再配置）
    git config user.name "您的 GitHub 昵称"
    git config user.email "您的 GitHub 邮箱"
    
    # 提交修改
    git add .
    git commit -m "XX 新功能"
    git push origin HEAD -u
    ```

7. 发布您的版本

    需要**先**修改仓库设置 `Settings` - `Actions` - `General` - `Read and write permissions` - `Save`

    ```bash
    # CI 检测到 tag 会自动进行发版
    git tag v1.0.0
    git push origin v1.0.0
    ```

8. 更多操作，请参考 [个性化配置](./docs/zh_cn/个性化配置.md)（可选）


## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献（下面链接改成你自己的项目地址）:

[![Contributors](https://contrib.rocks/image?repo=MaaXYZ/MaaFramework&max=1000)](https://github.com/MaaXYZ/MaaFramework/graphs/contributors)
