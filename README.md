<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<img alt="LOGO" src="https://github.com/quietlysnow/MBCCtools/blob/main/resource/base/image/logo.jpg" width="256" height="256" />

# MBCCtools
 
基于MaaFramework的 无期迷途 小助手。图像技术 + 模拟控制，解放双手！  
由 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 强力驱动！
</div>

## 说明

本项目是基于另一项目MACC (https://github.com/mxia9416/MACC) 而诞生的，MACC作者太久未更新且无渠道联系，故本人自行编写了本项目，开发过程有参考MACC。
本人纯新手，不会代码，使用纯 Pipeline 低代码编写，欢迎大佬指导。

## 功能介绍

目前已有的功能：

- 启动游戏:<br>消除广告/禁闭者情绪检测/奖励领取
- 秘盟捐赠
- 好友点数
- 监管奖励
- 领取免费礼包
- 一键派遣
- 领取体力
- 扫荡作战:<br> 记忆风暴/浊暗之阱/暗域/淘金狂热/恶兆之种/极域搜寻/禁区探查/帕尔马废墟
- 领取监察密令奖励
  
后续会添加其他功能比如刷材料之类的
## 使用说明

下载地址：<https://github.com/quietlysnow/MBCCtools/releases>

### Windows用户

- 对于绝大部分用户，请下载 `MBCCtools-win-x86_64.zip`
- 若确定自己的电脑是 arm 架构，请下载 `MBCCtools-win-aarch64.zip`  
  请注意！Windows 的电脑几乎全都是 x86_64 的，可能占 99.999%，除非你非常确定自己是 arm，否则别下这个！_
- 解压后运行 `MFAAvalonia.exe`。
- 本人没有用过macos,无法给出使用指南。
## 注意事项

- 提示“应用程序错误”，一般是缺少运行库，请安装一下 [vc_redist](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- MAA framework 2.0 版本已支持 mumu 后台保活，会在 run task 时获取 mumu 最前台的 tab
- 基于MuMu模拟器5，2560*1440（280DPI）平板版开发，其它模拟器或分辨率如遇到问题，可首先尝试上述配置
- 因MAA基于720p开发图像识别，1280*720(240DPI)理论上有最强适配性，如1080p遇到问题，可换720p尝试
- 反馈问题请附上日志文件 `debug/maa.log`以及问题界面的截图，谢谢！

## How to build

**如果你要编译源码才看这节，否则直接 [下载](https://github.com/quietlysnow/MBCCtools/releases) 即可**

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
  MACC 目前使用其中第一种方式（纯 Pipeline 低代码）
- [Pipeline 流水线协议](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF%E5%8D%8F%E8%AE%AE.md)

更多文档请前往 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 主仓库查看

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献（下面链接改成你自己的项目地址）:

[![Contributors](https://contrib.rocks/image?repo=MaaXYZ/MaaFramework&max=1000)](https://github.com/MaaXYZ/MaaFramework/graphs/contributors)
