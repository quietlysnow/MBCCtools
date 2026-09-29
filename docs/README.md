# MaaFramework 文档本地副本

本目录是 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 官方中文文档的本地副本，供本项目（MBCCtools）开发时查阅，目录结构与上游 `docs/zh_cn` 保持一致。

- 来源仓库：`MaaXYZ/MaaFramework`
- 分支：`main`
- 同步 commit：`b8492836568adaabec434199405083ff29c47413`（2026-09-17）
- 同步日期：2026-09-19
- 本运行时 MaaFramework 版本：**v5.13.0**

## 索引

| 文档 | 内容 | 本项目相关度 |
| ---- | ---- | ---- |
| [1.1-快速开始](zh_cn/1.1-快速开始.md) | 三种开发思路、资源目录结构规范、调试与打包 | 高，项目走**方案二：JSON + 自定义逻辑扩展** |
| [1.2-术语解释](zh_cn/1.2-术语解释.md) | MaaFW 专有术语 | 高 |
| [1.3-Custom&Agent](zh_cn/1.3-Custom&Agent.md) | 自定义识别/动作与 Agent 服务 | **高，方案二核心参考** |
| [2.1-集成文档](zh_cn/2.1-集成文档.md) | 库集成方式 | 低，前端由 MFAAvalonia 负责 |
| [2.2-集成接口一览](zh_cn/2.2-集成接口一览.md) | C/C++ 接口清单 | 低 |
| [2.3-回调协议](zh_cn/2.3-回调协议.md) | 回调消息与自定义通知 | 中，涉及 `focus` 通知时查阅 |
| [2.4-控制方式说明](zh_cn/2.4-控制方式说明.md) | 各平台截图/输入方式 | 中，控制器为 Adb |
| [3.1-任务流水线协议](zh_cn/3.1-任务流水线协议.md) | **Pipeline 协议：字段、算法、动作、节点属性、默认属性** | **最高，核心参考** |
| [3.2-ProjectInterface协议](zh_cn/3.2-ProjectInterface协议.md) | v1 协议，已废弃 | 无，直接用 3.3 |
| [3.3-ProjectInterfaceV2协议](zh_cn/3.3-ProjectInterfaceV2协议.md) | **`interface.json` 协议：task/option/resource/controller、资源覆盖** | **最高，核心参考** |
| [4.1-构建指南](zh_cn/4.1-构建指南.md) | 编译 MaaFW 本体 | 无 |
| [4.2-标准化接口设计](zh_cn/4.2-标准化接口设计.md) | 自定义控制单元接口设计 | 低 |
| [5.1-问题反馈](zh_cn/5.1-问题反馈.md) | 反馈规范与日志要求 | 中 |
| [NodeJS/J1.1-快速开始](zh_cn/NodeJS/J1.1-快速开始.md) | Node.js binding | 低 |
| [NodeJS/J1.2-自定义识别_操作](zh_cn/NodeJS/J1.2-自定义识别_操作.md) | Node.js 自定义扩展 | 低 |
| [NodeJS/J1.3-打包](zh_cn/NodeJS/J1.3-打包.md) | Node.js 打包 | 低 |

## 重新同步

文档会随上游更新，需要重新拉取时，从上游 `main` 分支按同名路径覆盖本目录即可，并更新上方的 commit 与日期。

> 注意：本地副本仅供查阅。若与上游冲突，以 [官方仓库](https://github.com/MaaXYZ/MaaFramework/tree/main/docs/zh_cn) 为准；涉及运行行为时，还需与本项目的 MaaFramework v5.13.0 版本能力对齐（各字段的引入版本见 3.1 的「版本变更」表）。
