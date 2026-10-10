## 1.5.1 (2026-10-11)

### 🐛 Bug修复

- 修复发布安装（1.5.0 及更早）启动即报「Agent 启动失败」、任务连不上设备的问题：打包漏带 agent 脚本、又要求用户自备 Python，现改为包内自带便携解释器与 MaaFw 依赖 @quietlysnow
- 登录前处理新增「安装包检查中」等待轮询，timeout 30s → 90s（官服 / B服），修复冷启动较慢时任务抢跑 @quietlysnow

### 🔧 优化

- 程序图标重打：16/24/32 用「脸 + 护目镜」裁切、48 以上用原画；配套 GUI 更新到定制版 v1.1（窗口图标不再被缩成单帧 512）@quietlysnow
- 打包链路：四条腿各自在目标平台 runner 构建、包内运行时按平台现备；发版说明末尾的 Mirror酱 链接排版修正 @quietlysnow

[已有 Mirror酱 CDK？点击前往高速下载](https://mirrorchyan.com/zh/projects?rid=MBCCtools)
