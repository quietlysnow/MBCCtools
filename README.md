<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<img alt="LOGO" src="https://github.com/quietlysnow/MBCCtools/blob/main/resource/base/image/logo.png" width="256" height="256" />

# MBCCtools
 
基于MaaFramework的 无期迷途 小助手。图像技术 + 模拟控制，解放双手！  
由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 强力驱动！
</div>

## 📖 项目说明

本项目基于 [MACC](https://github.com/mxia9416/MACC) 项目开发，因原项目长期未更新且无法联系作者，故重新编写此项目，开发过程中参考了 MACC 的设计思路。

本项目主要使用 Pipeline 低代码方式实现，欢迎各位开发者指导交流。

> ⏰ 项目为个人业余时间开发，随缘更新。发现的 Bug 会找时间修复，建议及时更新最新版本。

> 🤖 由于个人精力有限，本项目现已使用 AI 辅助开发，以**官服**功能为主。

### 已实现功能
- **游戏启动**：关闭广告、禁闭者情绪检测
- **秘盟捐赠**
- **好友点数**
- **日常奖励**：监管奖励、免费礼包、体力领取
- **每日派遣**：可选区域
- **体力扫荡**：浊暗之阱、记忆风暴、淘金狂热、恶兆之种、极域搜寻、禁区探查、帕尔马废墟
- **刷取材料**：在秘金盛宴 N3/N4 刷取对应材料
- **监察密令奖励**
  

## 使用说明

下载地址：<https://github.com/quietlysnow/MBCCtools/releases>

#### Windows 用户
- **绝大多数用户**：下载 `MBCCtools-win-x86_64.zip`
- **ARM 架构用户**：下载 `MBCCtools-win-aarch64.zip`  
  ⚠️ 注意：Windows 设备绝大多数为 x86_64 架构，除非明确知道自己的设备是 ARM 架构，否则请选择 x86_64 版本
- 解压后运行 .exe 文件。
- 本人没有用过macos,无法给出使用指南。

## 注意事项

**应用程序错误**：通常缺少运行库，请安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) 以及 [.NET 10.0](https://dotnet.microsoft.com/en-us/download/dotnet/10.0)
- **兼容性**：基于 MuMu模拟器5，2560×1440（280DPI）平板版开发
- **分辨率建议**：
  - 1280×720 (240DPI)：MAA 原生支持，兼容性最佳
  - 如遇问题可尝试切换至 720p 分辨率

## 🔧 开发说明

> ⚠️ 仅当需要开发本项目时才需要关注此部分，普通用户请直接[下载发布版](https://github.com/quietlysnow/MBCCtools/releases) 

本地开发**不需要 `deps`，也不需要运行 `install.py`**：

0. 克隆本仓库（已无子模块，`--recursive` 可省略）

    ```bash
    git clone https://github.com/quietlysnow/MBCCtools.git
    ```

1. 准备 GUI：下载最新发布包解压到任意目录（或使用现成的部署目录），把仓库的 `resource/` 同步进去；`interface.json` 用发布包自带的（如果改了任务/选项，需要换成仓库那份，见贡献指南）。
2. 用 VSCode、任意 IDE 或 [MaaPipelineEditor](https://github.com/kqcoxn/MaaPipelineEditor) 编辑 `resource/*/pipeline/*.json`；Custom 识别/动作写在 `agent/`。
3. 重启 GUI 后重跑任务。

完整步骤、节点写法约定与提交前自检见 [贡献指南](CONTRIBUTING.md)。

> `deps` 只在**本地复现发布包**时才需要（把 MaaFramework Release 解压到 `deps/` 再运行 `install.py`）；这一步平时由 CI 完成，开发阶段不用管，细节见贡献指南。

## 开发相关

- [贡献指南](CONTRIBUTING.md)：环境准备、pipeline 写法约定、提交前自检与 PR 流程
- [MaaFW 开发思路](https://maafw.com/docs/1.1-QuickStarted)  
  MBCCtools 目前使用其中第二种方式
- [Pipeline 流水线协议](https://maafw.com/docs/3.1-PipelineProtocol)

更多文档请前往 [MaaFramework 官网](https://maafw.com/docs) 查看

## 🙏 致谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献:

[![Contributors](https://contrib.rocks/image?repo=quietlysnow/MBCCtools&max=1000)](https://github.com/quietlysnow/MBCCtools/graphs/contributors)
