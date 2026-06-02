---
name: release-checklist
description: 每次发版时必须更新的文件清单
metadata:
  type: feedback
---

每次发版时必须更新以下文件：
- interface.json — 更新 version 字段
- resource/Announcement/0.更新说明.md — 只保留最新版本的更新说明，覆盖旧版本内容

**Why:** 用户之前指出发版时忘记更新 Release.md 和 Changelog.md，要求将这些步骤加入规则。0.更新说明.md 是应用内显示的更新公告，只应展示最新版本。

**How to apply:** 每次打 tag 发版前，检查以上两个文件是否已更新。0.更新说明.md 只保留最新版本的内容，不追加旧版本。
