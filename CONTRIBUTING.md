# 贡献指南

感谢你愿意参与 MBCCtools！调整一个识别阈值、补一张模板图、新增一个任务都欢迎。开始之前请花几分钟看完这篇，能省掉大部分来回沟通。

- 交流语言：中文。
- 初次上手先读 [README](README.md)。
- 协议细节以 [MaaFramework 官网文档](https://maafw.com/docs/1.1-QuickStarted) 为准。
- 项目以 **Pipeline（JSON 低代码）** 为主：能用 pipeline 表达的逻辑不要写成代码。

## 1. 改动应该放在哪

| 你想改的内容 | 位置 |
| --- | --- |
| pipeline 节点、识别模板图、阈值 | 本仓库 `resource/*/pipeline/`、`resource/base/image/` |
| 任务清单、选项（option）、文案 | 本仓库 `interface.json` |
| Custom 识别/动作、联网采集与落档 | 本仓库 `agent/` |
| 公告、更新日志 | 本仓库 `resource/Announcement/`、`resource/Release.md`、`resource/Changelog.md` |
| 界面页面、侧栏、样式、通知 | **不在本仓库**：`quietlysnow/MFAAvalonia-MBCC`（GUI fork） |
| 布局、日志、模拟器实例配置 | 运行时状态，谁生成谁持有，不入库 |

判定口径很简单：**看改它要不要重发 GUI** —— 内容（公告、选项图标、角色头像）走资源包留在本仓库，控件与交互逻辑去 fork。

## 2. 快速开始

改任务节点、换模板图、调阈值都不需要打包，准备模拟器和最新发布版 GUI 就能开始。

1. fork 并克隆本仓库：

    ```bash
    git clone https://github.com/<你的账号>/MBCCtools.git
    ```

2. 下载最新的 [MBCCtools 发布包](https://github.com/quietlysnow/MBCCtools/releases)，解压到你的本地文件夹。
3. 用仓库里的 `resource/` 覆盖你的本地文件夹里的 `resource/`，确保跑的是仓库里的最新改动，而不是发布包里那份发行版资源。
    - `interface.json` 保留发布包自带的：它的 `agent.child_exec` 指向包内便携 Python，直接换成仓库那份会让 agent 找不到解释器。
4. 运行 `MFAAvalonia.exe`，连接模拟器，开始任务。
5. 修改仓库里的 `resource/*/pipeline/*.json`，同步到你的本地文件夹后**重启 MFAAvalonia** 再跑任务（资源在启动/首次连接时加载，热改不生效）。

调阈值、核对 ROI、确认模板能不能命中时，先用 `tools/recognition_probe.py` 离线跑一张截图，比反复启动模拟器快得多：

```bash
python tools/recognition_probe.py 截图.png 密盟兑换/数量减号.png --roi 425,220,770,395
python tools/recognition_probe.py 截图.png --ocr "获得物资"
```

它会打印命中框与得分最高的几条结果（OCR 模式打印识别文本），需要 Pillow 或 opencv-python 之一。

测差异包时加 `--overlay global` 或 `--overlay bilibili`。

提交时改的是你 clone 的仓库，不是发布包里的副本。建议固定「仓库改 → 拷到你的本地文件夹 → 验证」这个方向，避免两边分叉。

## 3. 改 agent（本地调试）

> 说明：`agent/` 下的内容均为使用 DeepSeek 开发。

`agent/` 里的 Custom 识别/动作由 GUI 以子进程方式启动，源码 `interface.json` 的 `child_exec` 是裸 `python`。

本地调试这一块**不需要 `deps`**：

1. 把 GUI 文件放在仓库根目录（这些部署产物已被 `.gitignore` 忽略），或使用已有的部署目录；
2. 让系统 `python` 能 import `maa`：

    ```bash
    pip install -r requirements.txt
    ```

3. 运行 `MFAAvalonia.exe`，跑会用到 Custom 节点的任务（例如「抽卡记录」）；
4. 改完 `agent/` 后重启 GUI 再跑。

版本对齐：`requirements.txt` 里的 `MaaFw` 必须与 GUI 实际加载的 `runtimes/<platform>/native/MaaFramework.dll` 属于同一协议代（当前钉 5.12.3），否则 Custom 节点会直接拒连。

`agent/` 里也不要引入 `cv2` 一类重依赖 —— 发布包只装 `requirements.txt` 里的包。

## 4. 本地复现打包（可选，通常不需要）

发布包由 CI 构建，本地开发不用做这一步；只有要验证打包链路时才需要 `deps`。

`deps` **不在仓库里**（`.gitignore` 已排除 `/deps/`），要自己建。前提：

- Python 3.13；
- 能访问 GitHub（会下载包内便携解释器，缓存在 `deps/.agent-runtime-cache/`）。

```bash
mkdir deps
# 把 MAA-win-x86_64-*.zip（或对应平台）里的内容平铺解压到 deps/
python ./install.py                 # 可带版本号：python ./install.py v0.0.0-test
```

`deps` 的布局必须是（压缩包内容平铺，不要多套一层）：

```text
deps/
├─ bin/                  # MaaFramework.dll 等
└─ share/MaaAgentBinary/
```

缺了会报 `Please download the MaaFramework to "deps" first.`。平台对应的压缩包（版本用最新即可）：

| 平台 | 压缩包 |
| --- | --- |
| Windows x64 | `MAA-win-x86_64-*.zip` |
| Windows ARM | `MAA-win-aarch64-*.zip` |
| macOS | `MAA-macos-*.zip` |

生成的 `install/` 里有 `resource/`、`agent/`、包内 Python 与 `interface.json`，但**没有 GUI**。

发布 CI 的顺序是「先把 MFAAvalonia 发布包铺进 `install/`，再跑 `install.py`」。本地要跑完整包，就照这个顺序：

```bash
mkdir -p install
# 解压 MFAAvalonia-MBCC 的 release 到 install/
python ./install.py v0.0.0-test
```

## 5. Pipeline 写法约定（摘要）

完整约定见仓库根 [`AGENTS.md`](AGENTS.md) §4–§6（该文件主要写给 AI 助手，但条款就是本项目的人工约定）。

协议字段以 [MaaFramework 官网的 3.1 任务流水线协议](https://maafw.com/docs/3.1-PipelineProtocol) 为准。

- **统一 Pipeline v2 对象式**，新增节点不要写 v1 扁平式：

    ```jsonc
    "节点名": {
        "recognition": { "type": "OCR", "param": { "expected": "领取", "roi": [0, 0, 0, 0] } },
        "action": { "type": "Click" },
        "next": ["..."]
    }
    ```

> **以下内容交给 AI 阅读即可**，人工贡献者扫一眼就够。

- **节点名、文件名用中文**，变体后缀沿用 `_SecondClick` / `_异常处理` / `回主页` 等现有写法。
- **格式**：4 空格缩进、LF、UTF-8 无 BOM、文件末尾单个换行、`"key": value` 冒号后一个空格。
  - 坐标数组保持单行紧凑写法。
  - **不要对整个文件跑格式化**，会产生上百行无意义 diff。
- **pipeline JSON 不写注释**（`//` 和 `_comment` 都不要），`resource/default_pipeline.json` 是唯一例外。
- **坐标**一律 1280×720 基准的绝对像素 `[x, y, w, h]`，纯点击点写 `[x, y, 1, 1]`。
- **`next` 顺序即优先级**，命中第一个就中断后续；专有分支放前，兜底放最后。
- **弹窗/异常恢复用 `[JumpBack]`**，不要写进 `on_error`（错误处理路径不执行回跳）。
- **`timeout` / `on_error` 属于上一节点**：想控制「等某个节点出现多久」，改父节点，不要写进自己的 `action.param`。
- **`focus`** 只给真的执行动作的节点，文案默认取节点名（`X入口` → `进入X`、`X_异常处理` → `处理X异常`）。
- **阈值**要压误判就显式写在节点上；`resource/default_pipeline.json` 当前不生效，不要指望它的默认值。
- **新增任务**：
  - `entry` 节点必须在合并后的 pipeline 里真实存在，并在 `interface.json` 的 `task` 里登记。
  - option 的 `pipeline_override` 引用的节点名同样要能找到。

## 6. 模板图规范

- **截图**：从原始截图上原样裁剪，不要缩放、压缩或重绘。
  - 推荐用 [maa-support-extension](https://github.com/neko-para/maa-support-extension) 或 [MFAToolsPlus](https://github.com/SweetSmellFox/MFAToolsPlus) 在模拟器上截取。
  - 它们会自动把截图统一成 720p，模拟器分辨率不必严格设成 1280×720。
- `template` 相对 `image/` 根目录解析，裸文件名或带子目录的相对路径都行（如 `密盟兑换/数量减号.png`）。
- 模板要带足够区分度：`TemplateMatch` 走灰度，同形不同色的元素只能靠形状差异或阈值区分。
- 新增/替换图片后，确认 pipeline 里的引用路径与文件名完全一致。

## 7. 多服差异（overlay）

- 三个 bundle：
  - `base`：官服主包。
  - `bilibili`：B服差异。
  - `global`：国际服差异。
- 加载顺序由 `interface.json` 的 `resource` 决定，同名 task / 节点后者整体覆盖前者。
- 差异包里**只放需要改的节点**，未出现的继续由 `base` 提供；被 base 取代的旧拷贝要删掉，不要留陈旧副本。
- 改 `base` 里的共享节点会同时影响三个服 —— 只影响单服的改动，放进对应的 overlay。

## 8. 提交前自检

```bash
# 1) pipeline JSON 语法（不允许注释）
python -c "import json,pathlib;[json.loads(p.read_text(encoding='utf-8')) for b in ('base','bilibili','global') for p in pathlib.Path('resource',b,'pipeline').rglob('*.json')]"

# 2) 资源包能被框架加载（差异包是 overlay，单独加载会失败，属正常）
pip install -r requirements.txt
python check_resource.py resource/base
```

人工再确认：

- `next` / `on_error` / `target` / `template` 里的每个节点名或图片路径都真实存在；
- 坐标没有超出 1280×720；
- 最好在模拟器上实机跑一遍；**无法实机验证的改动，请在 PR 里注明「未验证」**，并写清期望行为。

## 9. 提交 PR

- 从 `main` 切功能分支，一个 PR 只做一件事；改共享节点时说明对 B服 / 国际服的影响。
- Commit message 沿用仓库现状：`fix(体力): …`、`feat(密盟兑换): …`、`docs: …`，scope 用中文模块名。
- 不需要改 `interface.json` 的 `version`，也不要动 `resource/Release.md`、`resource/Changelog.md` 与公告 —— 这些在发版时由维护者统一处理。
- 不要提交 `record/`、`install/`、`deps/`、`debug/`、`logs/`、`resource/mfa_layout.json` 等运行时产物（`.gitignore` 已覆盖，提交前 `git status` 看一眼）。
- 识别、坐标类改动请附截图（改前改后）或离线识别结果。
- 涉及实机的，写明机型、分辨率与模拟器版本。
- Bug 反馈请使用仓库的 Issue 模板，附上版本号与日志。

## 10. 常见坑

- `timeout` 写进 `action.param` 不生效，必须写在节点级。
- `is_sub` / `interrupt` 已废弃，用 `[JumpBack]`。
- checkbox 类型的 option 不是并集：同名节点同字段后者覆盖前者，多选白名单要靠「每个目标一个节点 + `enabled` 开关」。
- `agent/` 代码不能依赖 `cv2` 等未写进 `requirements.txt` 的包。
- 界面相关行为请去 GUI fork，不要在本仓库新增 C# 文件（本仓库不应出现界面源码）。
