## 1.5.2 (2026-10-20)

### ✨ 新增

- 新增「秘盟兑换」任务：在采购办 → 玩法兑换 → 秘盟兑换页按本月限购买满勾选物资，初阶 / 中阶 / 高阶三档自动依次切换，每档横滑一屏覆盖完整列表 @quietlysnow

### 🐛 Bug修复

- 抽卡记录：页码读不出时改用行内容判停，修复发布安装第 10 页起记录被静默截断的问题——发布包解释器没有 cv2，放大静默失效；现改用纯 numpy 放大 @quietlysnow
- 抽卡记录：补装 openpyxl，修复 xlsx 导出被静默跳过、只拿到 md 摘要的问题 @quietlysnow

### 🔧 优化

- 问题反馈模板：日志收集改为上传整个 logs 与 debug 文件夹，并去掉脚手架遗留的「MXX」占位文本 @quietlysnow
- AGENTS.md 补 §14 秘盟兑换与 §2.5 页号识别，修正选项组数量 @quietlysnow

[已有 Mirror酱 CDK？点击前往高速下载](https://mirrorchyan.com/zh/projects?rid=MBCCtools)
