## 1.4.3 (2026-06-02)

### ✨ 新增

- 新增国际服（global）资源支持，pipeline 独立、image 复用 base @RomioLA

### 🔧 优化

- 月卡节点改用 OCR 文字识别"剩余"，替代原有 TemplateMatch 图片匹配，提高识别稳定性
- 月卡节点指定 roi 区域和点击 target 坐标

## 1.4.2 (2026-05-19)

### 🔧 优化

- 更新 pipeline 资源及 MaaNode 节点

## 1.4.1 (2026-05-18)

### 🔧 优化

- 移除 agent 模块，更新 pipeline 资源及 MaaNode 节点
- 强制 GitHub Actions 使用 Node.js 24 以适配即将到来的弃用

### 🐛 Bug修复

- 修复 install.py 中对已删除 agent 目录的引用

## 1.4.0 (2026-05-16)

### ✨ 新增

- 新增破碎防线 pipeline，支持自动领奖 @RealHath
- 项目 interface.json 新增 title 和 icon 字段

### 🐛 Bug修复

- 修复通行证密令流程卡住问题，新增等级奖励领取 @RealHath
- 修复通行证完成后缺少关闭界面跳转 @RealHath
- 修复领取密令等级奖励缺少点击动作 @RealHath
- 恢复 bilibili 友情点和监管 pipeline 配置 @RealHath

### 🔧 优化

- 移除 bilibili 冗余资源文件，B服复用 base 资源 @RealHath
- 移除启动流程中多余的 MaaPipelineEditor 元数据 @RealHath
- B服资源路径合并到 base

## 1.3.9 (2026-03-26)

### 🐛 Bug修复

- 修复友情点任务卡住的问题 @quietlysnow
- 修复监管任务卡住的问题 @quietlysnow

## 1.3.8 (2026-02-23)

### 🐛 Bug修复

- 更新 bilibili 启动 pipeline 配置 @quietlysnow

[已有 Mirror酱 CDK？点击前往高速下载](https://mirrorchyan.com/zh/projects?rid=MBCCtools)