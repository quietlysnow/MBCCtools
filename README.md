<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<img alt="LOGO" src="https://github.com/quietlysnow/MBCCtools/blob/main/resource/base/image/logo.jpg" width="256" height="256" />

# MBCCtools
 
基于MaaFramework的 无期迷途 小助手。图像技术 + 模拟控制，解放双手！  
由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 强力驱动！
</div>

## 📖 项目说明

本项目基于 [MACC](https://github.com/mxia9416/MACC) 项目开发，因原项目长期未更新且无法联系作者，故重新编写此项目，开发过程中参考了 MACC 的设计思路。

本项目主要使用 Pipeline 低代码方式实现，欢迎各位开发者指导交流。

> ⏰ 项目为个人业余时间开发，随缘更新。发现的 Bug 会找时间修复，建议及时更新最新版本。

### 已实现功能
- **游戏启动**：关闭广告、禁闭者情绪检测
- **秘盟捐赠**
- **好友点数**
- **日常奖励**：监管奖励、免费礼包、体力领取
- **每日派遣**：可选区域
- **体力扫荡**：浊暗之阱、记忆风暴、淘金狂热、恶兆之种、极域搜寻、禁区探查、帕尔马废墟
- **监察密令奖励**
  
后续会添加其他功能比如刷材料之类的

## 使用说明

下载地址：<https://github.com/quietlysnow/MBCCtools/releases>

#### Windows 用户
- **绝大多数用户**：下载 `MBCCtools-win-x86_64.zip`
- **ARM 架构用户**：下载 `MBCCtools-win-aarch64.zip`  
  ⚠️ 注意：Windows 设备绝大多数为 x86_64 架构，除非明确知道自己的设备是 ARM 架构，否则请选择 x86_64 版本
- 解压后运行 `MFAAvalonia.exe`。
- 本人没有用过macos,无法给出使用指南。

## 注意事项

**应用程序错误**：通常缺少运行库，请安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- **兼容性**：基于 MuMu模拟器5，2560×1440（280DPI）平板版开发
- **分辨率建议**：
  - 1280×720 (240DPI)：MAA 原生支持，兼容性最佳
  - 如遇问题可尝试切换至 720p 分辨率

## 🔧 编译说明

> ⚠️ 仅当需要开发本项目时才需要关注此部分，普通用户请直接[下载发布版](https://github.com/quietlysnow/MBCCtools/releases) 

0. 完整克隆本项目及子项目

    ```bash
    git clone --recursive https://github.com/quietlysnow/MBCCtools.git
    ```

1. 下载 MaaFramework 的 [Release 包](https://github.com/MaaXYZ/MaaFramework/releases)，解压到 `deps` 文件夹中
2. 安装

    ```python
    python ./install.py
    ```

生成的二进制及相关资源文件在 `install` 目录下

## 开发相关

- [MaaFW 开发思路](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/1.1-%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.md#%E5%BC%80%E5%8F%91%E6%80%9D%E8%B7%AF)  
  MBCCtools 目前使用其中第一种方式（纯 Pipeline 低代码）
- [Pipeline 流水线协议](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF%E5%8D%8F%E8%AE%AE.md)

更多文档请前往 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 主仓库查看

## 🙏 致谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献:

[![Contributors](https://contrib.rocks/image?repo=quietlysnow/MBCCtools&max=1000)](https://github.com/quietlysnow/MBCCtools/graphs/contributors)
