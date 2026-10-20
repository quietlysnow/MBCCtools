# MBCCtools — Agent 规则

本文件是给 AI 编码助手的项目约束。规则来自**当前仓库里实际观察到的写法**，不是 MaaFramework 通用教程。
协议细节一律以本地文档副本 `docs/zh_cn/` 为准（见文末索引），本文只写「本项目怎么写」。

- §1–§11 是常驻开发约定；§12–§14 是具体维护操作与任务说明 —— §12/§13 由触发语唤起（听到就跑），§14 是秘盟兑换任务的现状与约束。
- 文中带数字的现状统计最后核对于 **2026-10-14**（§3、§4.2、§4.3、§4.6）；漂了就用 §8 的统计脚本重算，别手改。

## 1. 参考项目

- <https://github.com/MAA1999/M9A> 是《重返未来：1999》的 MaaFramework 项目，**与本项目不是同一个游戏**。只作**代码流程与写法组织**的参考：本文件某条约定存疑、或想看某个算法/动作节点的标准写法时，看它怎么组织。
- 它的游戏文案、节点名、坐标、图片、阈值一律不可照搬。它是**英文节点名 + `pipeline/` 分子目录 + 带子目录的 `template` 路径**，本项目是中文节点名 + 扁平 `pipeline/` + 裸文件名，三点都不同，不要参考着改名或挪文件。

## 2. 开发方式：方案二（JSON + 自定义逻辑扩展）

对应 `docs/zh_cn/1.1-快速开始.md` 的**方案二**（官方标注「推荐」）。细则以 `docs/zh_cn/1.3-Custom&Agent.md`、`3.1` §`Custom`、`3.3` §Agent 子进程环境变量为准，本文只写骨架。

**分层原则：主流程继续用 Pipeline 维护，只有 Pipeline 表达不了的逻辑才落到自定义代码。**

- 日常链路、界面跳转、找图、OCR、点击/滑动 —— 一律写在 `resource/*/pipeline/`，按 §4 的约定办。
- **可配置分支仍优先用 `interface.json` 的 `option` + `pipeline_override`**（见 §6），不要为了"给用户一个开关"去写 Python —— 那是方案一的活，不是自定义逻辑的活。
- 需要算法/复杂判断/动态改写流程/事件监听时，才用 `Custom`。判断标准：`3.1` 的内置算法（`TemplateMatch`/`FeatureMatch`/`ColorMatch`/`OCR`/`NeuralNetwork*`）+ `And`/`Or` + `order_by`/`index`/`expected` 正则确实覆盖不住。**能用 Pipeline 写的不要用代码写**，否则丢掉可视化维护、跨服 overlay、低门槛这三个优势。
- 引入或新增任何 Custom 之前**先向用户说明理由和替代方案**，不要顺手把简单逻辑代码化。

### 2.1 调用侧（Pipeline 节点）

`recognition`/`action` 取 `Custom`，注册名与参数写在各自的 `param` 里（本项目全量 v2，见 §4.1）：

```jsonc
"自定义处理模块": {
    "recognition": { "type": "Custom", "param": {
        "custom_recognition": "MyReco",          // 必选，注册时用的名字，大小写敏感
        "custom_recognition_param": { "any": "任意 JSON，原样透传" },
        "roi": [0, 0, 0, 0]                       // 可选，会作为 roi 传出
    }},
    "action": { "type": "Custom", "param": {
        "custom_action": "MyAct",                // 必选
        "custom_action_param": null,             // 可选，任意 JSON
        "target": true                            // 可选，含义同 Click.target，作为 box 传出
    }},
    "next": ["..."]
}
```

- 自定义识别器返回 `(x, y, w, h)` 或 false；自定义动作返回 bool。其余节点属性（`on_error`、`post_wait_freezes`、`focus`…）照常可用。
- `custom_*_param` 的键名不要和 `3.1` 的协议字段混淆——框架不解析它，只负责整包透传。

### 2.2 实现侧（AgentServer）

用 `maafw` 的 Agent 接口注册并常驻，UI 侧的 AgentClient 会在跑到 `MyReco`/`MyAct` 时把请求转发过来：

```python
from maa.agent.agent_server import AgentServer

@AgentServer.custom_recognition("MyReco")
class MyRecoImpl:
    def analyze(self, ctx): ...        # 取截图/参数，返回命中框或 False

@AgentServer.custom_action("MyAct")
class MyActImpl:
    def run(self, ctx): ...            # ctx.controller 可下发输入；ctx.override_next(...) 可动态改流程

AgentServer.start_up(sock_id)
```

- 语言可选 Python 或 Node.js（NodeJS 见 `docs/zh_cn/NodeJS/J1.2-自定义识别_操作.md`）。选定后不要两种混用。
- 完整示例：`MaaPracticeBoilerplate` commit `126a56c`（`1.1` §方案二 末尾链接）。
- 注意 `MaaAgentBinary/` 目录是 Android 端的**控制**代理（maatouch/minicap/minitouch），跟 Custom 的 AgentServer 无关，别搞混、别往里放代码。

### 2.3 接线（`interface.json`）

需要给 UI 一个可启动的 Agent 子进程（PI v2.5.0 起，`3.3` §Agent）：

```jsonc
"agent": {
    "child_exec": "python",                 // 源码里是开发用裸命令名；发布包会被改写成 ./agent/python/python.exe，见下
    "child_args": ["./agent/main.py"],
    "identifier": "MBCCtools"               // 可选；填了就用它建通信套接字
}
```

- UI 会向子进程注入 `PI_*` 环境变量（`PI_CLIENT_NAME`、`PI_CONTROLLER`、`PI_RESOURCE` 等，全表见 `3.3`）。**多服项目必须读 `PI_RESOURCE`** 来判断当前选中的是官服/B服/国际服，再加载对应资源。
- 多个 Agent 可写成数组形式。
- **`child_exec` 在源码与发布包里不一样**（照 M9A 的版式）：源码写裸命令名 `python`，走开发机 PATH；`install.py` 打包时由 `install_agent_runtime()` 改写成包内相对路径 `./agent/python/python.exe`（macOS 是 `./agent/python/bin/python3`），`check_agent()` 兜底 —— 声明了 agent 却缺脚本或解释器，打包直接失败。解释器与依赖由 `prepare_agent_runtime.py` 现备（Windows 用官方 embed zip，macOS 用 python-build-standalone；依赖钉在根目录 `requirements.txt`）。
- 该步骤只按平台解析 wheel、**不执行目标解释器**，所以宿主平台必须等于目标平台：`install.yml` 每条腿都在自己的 runner 上构建（`win-x64`/`win-arm64`/`macos-x64`/`macos-arm64`），跨平台构建会直接报错（M9A 同款约束）。

### 2.4 当前落地状态（2026-10-13 核对）

`agent/` 下两个脚本：`main.py`（注册自定义项、AgentServer 入口）与 `wiki_activity.py`（后台活动采集）。

**已注册 6 个**（名字大小写敏感）：识别 `CloseButton` / `GachaRecordPoolType` / `GachaRecordFirstPage` / `GachaRecordPage`；动作 `GachaRecordBeginRun` / `GachaRecordExport`。

已接入的 pipeline：

- `resource/base/pipeline/项目名.json` 的公共节点 `通用关闭弹窗`（`Custom` 识别 + `Click`，`target` 默认 true 即命中框本身）。识别器用 `context.run_recognition_direct` 调框架自带的 `TemplateMatch` 逐个模板匹配，再按「离 `corner` 指定的屏幕角最近」择优 —— 这一步是 JSON 表达不了的（`order_by` 只有 Horizontal/Vertical/Score/Area/Length/Random，不能按到某个角的距离排序）。未命中返回 `None`，不抛异常。
- `resource/base/pipeline/启动.json`：`登录前处理` 与 `登录后处理` 的 `next` **末尾**各挂一个 `[JumpBack]通用关闭弹窗`。`bilibili/`、`global/` 的 `启动.json` **还没接**，节点因定义在 `base` 而对三服可见但未被引用。
- `resource/base/pipeline/抽卡记录.json`（8 节点，base 独有）：开始采集 → 识别追踪类型 → 单页识别/翻页 → 汇总导出到 `record/抽卡记录/`。option「识别方式」通过覆盖 `抽卡记录_单页识别` 的 `custom_recognition_param`（archive/min_score/line_tol/badge_x/rarity_dir…）调参 —— 给 Custom 调参沿用这套，不要复制整份节点。
- AgentServer 启动时另起后台线程跑 `wiki_activity.py`：抓 BWIKI 活动写 `record/活动.json`（纯网络采集、不注册 Custom、失败不影响任务）。

设计取舍与边界（改的时候别破坏）：

- **通用关闭弹窗只放在原有专用处理器之后**。`关闭公告`/`一般弹窗` 等带写死坐标的节点全部保留，所以 Agent 没起来时行为和改动前一致（退化成本不受影响），Agent 起来时它只兜住"没枚举到的新弹窗"。等确认 `CloseButton` 稳定后，才谈得上删掉那些写死坐标。
- **不要把它插到 `首页` 之前**。那样任何带"关闭"图样的正常页面都会被提前点掉，属于新增误操作风险。
- **它的适用面比预想的窄**（2026-09-19 实机结论）：启动期最常见的两类弹窗 —— 空投「点击领取今日补给」和「情绪检测」台词窗 —— **画面上根本没有 X 按钮**，`CloseButton` 对它们必然未命中（未命中是正确返回，不是故障）。这类"点某句文案"的弹窗一律用 `OCR + Click` 解决，已落地的例子见 `base/pipeline/启动.json` 的 `今日补给`。别再把"找关闭按钮"当成启动流程的万能兜底。

验证状态与约束：

- 连通性已实测：2026-09-19 首次握手成功；2026-10-10 的实机日志里能看到 `通用关闭弹窗` 真的调到了 `CloseButton`（那几次是未命中，属正常返回）。**「命中后点掉弹窗」没有专门的回归记录，别当成已验证。**
- **AgentServer 的 Python 绑定版本必须与 AgentClient 的协议代一致**：当前钉 `pip install MaaFw==5.12.3`（与 MFA 加载的 v5.12.3 逐版本一致）。换 MaaFramework / MFAAvalonia 版本时，要同步重选 `MaaFw` 版本，否则 Custom 节点直接连不上。实测日志与「两份 dll」的坑见 §7.3。
- 自定义代码放 `agent/`，**不要**放进 `resource/`（会被当资源包扫描）。
- **发布包自 2026-10-11 起自带解释器**（版式见 §2.3）。加这道守卫的原因：v1.5.0 的发布包其实缺 `agent/`（`install_agent()` 于 `73011cf` 被删、agent 于 `21dfec6` 加回时没恢复），`child_exec` 又指望用户机器上有装好 MaaFw 的 python。开发根 `G:\MBCCtools工作区` 永远正常（`agent/` 就在 `interface.json` 旁边），只有发布安装才暴露 —— 别再用开发根的表现推断发布包。

### 2.5 抽卡记录页号识别（issue #36，2026-10-19 修）

**根因**：`抽卡记录_单页识别` 判停靠底栏页码，页码区只有 ~9x16 像素、必须先放大再 OCR。旧代码用 `cv2.resize` 放大，且 `import cv2` 失败时**静默退回原尺寸**；而发布包的便携解释器只装 `requirements.txt`（MaaFw 及其 numpy），**没有 cv2**，于是用户侧一直在原尺寸识别：两位数页码（第 10 页起）整块读不出来 → 被判成"没有下一页"，第 10 页起静默截断、任务照报"全部完成"；个位数也会掉到 0.37~0.46（阈值 0.5 之下），表现为"综合池一页都不翻"。开发机装了 cv2，所以本地从来没复现过。

改法与约束（别改回去）：

- **页号放大改用 `agent/main.py` 的 `_upscale`（纯 numpy 双线性，边界复制）**。实测与 `cv2.INTER_LINEAR` 只差舍入（max 1），对 OCR 结果等价（各帧 0.997~0.999）。**agent 代码一律不引 cv2 一类重依赖** —— 发布包不会装，只能按"它不在"来写。numpy 由 MaaFw 带入，可以用。
- **页码读不出来不再直接结束**：行内容（列表字号大、OCR 稳）作为第二判据 —— 与上一页逐行一致才算"没翻动"，有变化就照样当新一页采集；收尾时的 `_probe_back` 反证也同步支持行内容比对。`session.last_rows` / `session.pages_seen` 就是为此保留的，别删。
- **`requirements.txt` 要同时装 `openpyxl`**（抽卡记录导出的 xlsx）。它缺失时只打一行日志、静默跳过 xlsx——v1.5.1 的用户就只拿到 md 摘要。numpy/openpyxl 都能通过 `pip install --dry-run --only-binary :all: --platform <目标平台>` 预验（照 §2.3 的 pip 参数）。

离线复现与回归（不用模拟器、不用改真机）：`.scratch/gacha_sim.py`（**本地脚本，gitignored，随用随建**）用 `CustomController` 当"假游戏"，按帧序列返回截图、点 ▶/◀ 换页，能整条跑 `抽卡记录` 任务（落档到 `.scratch/gacha_sim/`，不碰 `record/`）。开关：`--blank-page N`（涂掉第 N 帧的页号，模拟"页码读不出但列表正常"）、`--drop-clicks N`（吞掉前 N 次 ▶，模拟丢点击）。回归口径：页码读不出也要采到全部页、丢点击要能重试恢复、真·单页（页码 1）要报"列表只有一页"、末页收尾走 `抽卡记录末页`。想问单帧页号在各种放大下的读数，用同目录的 `.scratch/pageno_probe.py`（帧源可取 `.scratch/*_720.png` 里那批记录页截图）。

**要验"发布包解释器里到底行不行"**，不必整包构建：`python prepare_agent_runtime.py --dest install/agent/python --platform win-x64` 单独备出包内解释器（只装 requirements，没有 cv2），再用 `install/agent/python/python.exe .scratch/packaged_probe.py` 跑同一个 `_read_page_number`。2026-10-19 实测：五帧真实截图全部读对（包含 1x 下读成 "C" 0.413、放大后 0.997 的那帧），`agent/main.py` 在该解释器里加载正常。跑完记得删 `install/` 与 `deps/`。

## 3. 目录与 bundle 结构

```
interface.json                 # ProjectInterface V2 清单，见 §6
agent/                         # 自定义识别/动作与活动采集（§2）
tools/                         # build-icon.py 等本地工具（§13）
record/                        # 运行时落档（抽卡记录/、活动.json），fork 侧页面只读它（§11）；不入库
install.py / prepare_agent_runtime.py / requirements.txt   # 打包链路（§2.3、§8）
resource/
├── default_pipeline.json      # ⚠ 见 §7.1
├── mfa_layout.json            # MFAAvalonia 界面布局，与算法无关
├── base/                      # 官服 bundle（主资源包）
│   ├── image/                 # 模板图片（材料/ 23 张、密盟兑换/ 10 张，另有 头像/、抽卡/）
│   ├── model/ocr/             # det.onnx / rec.onnx / keys.txt（PP-OCRv5_mobile）
│   └── pipeline/              # 21 个 JSON
├── bilibili/                  # B服 overlay：仅 pipeline/，3 个 JSON
└── global/                    # 国际服 overlay：仅 pipeline/，19 个 JSON（含 2 个 base 没有的新任务）
```

- bundle 根必须同时具备 `pipeline/`、`image/`、`model/ocr/` 才能被完整加载；框架**只**在 bundle 根目录下查找 `default_pipeline.json`（见 §7.1）。
- MaaFW 递归读取 `pipeline/` 下所有 `.json`；**路径中任一段以 `.` 开头的文件/目录会被跳过**（`_` 前缀不跳过）；JSON 顶层 key 以 `$` 开头的不解析。
- 仓库里原有一批编辑器画布元数据（`$__mpe_config_*` / `$__mpe_external_*` 根键、节点内 `$__mpe_code`，共 46 处，仅存在于 `base` 的 `启动.json` 与 `刷取材料.json`），**已于 2026-09-19 全部清除**。现在 `pipeline/` 里不应再出现任何 `$` 开头的键；若某工具回写后又把它们带回来，删掉即可，不影响运行。
- `bilibili/`、`global/` 没有自己的 `image/`，但 `template` 仍能引用 `base/image/` 下的图：**模板图管理器跨 bundle 累积**，因此差异包只放需要不同的 pipeline。

## 4. Pipeline 节点写法（核心）

### 4.1 统一使用 Pipeline v2（对象式）

**全仓节点已于 2026-09-19 全部转成 v2 形式**（当时 120 个原 v1 扁平节点被机械转换，逐节点通过「槽位归一化后键值完全相等」校验），此后新增节点一律是 v2。当前规模：三个 bundle 合计 **396 个节点定义**（base 243 / bilibili 35 / global 118）。新节点照 v2 写：

```jsonc
"节点名": {
    "recognition": { "type": "OCR", "param": { "expected": "领取", "roi": [0,0,0,0] } },
    "action": { "type": "Click" },
    "next": ["..."]
}
```

- 无参数的算法/动作也要写对象：`"action": { "type": "DoNothing" }`；纯分发节点（只有 `next`）不需要 `recognition`/`action`。
- 框架仍向后兼容 v1 扁平式，但**不要再新增 v1 写法**，避免两种形式重新混用。
- 转换时有 4 个节点（`监管.json/检查选项`、`项目名.json/难度选择` 及其 bilibili/global 对应件）原本把 `order_by`/`index` 写在 `action` 之后，现在归位到 `recognition.param` 内 —— MaaFW 按键名取值，与书写位置无关，行为不变。
- 转换只搬运了 `recognition`/`action` 及其参数，其余字段（`next`/`on_error`/`timeout`/`focus`/`post_wait_freezes`/`repeat`…）保持原位与原样的书写形态（含单行紧凑坐标数组）。

### 4.2 实际使用的取值集合

- `recognition` 用过：`OCR`(225)、`TemplateMatch`(66)、`DirectHit`(18)、`Custom`(4)；`action` 用过：`Click`(262)、`DoNothing`(48)、`Swipe`(34)、`StartApp`(3)、`Custom`(2)、`ClickKey`(1，`破碎防线_按返回键` 的 `key: 4`)、`StopTask`(1)。括号是 2026-10-14 的全仓节点数。
- `Custom` 只有 §2.4 里那两个任务在用。方案二（§2）**允许** `recognition: Custom` / `action: Custom`，但必须配套 AgentServer 实现与 `interface.json` 的 `agent` 段，且引入前先与用户对齐理由。
- 尚未使用：`FeatureMatch`、`ColorMatch`、`LongPress`（这两个早期用过、现已无）、`NeuralNetworkClassify`、`NeuralNetworkDetect`、`And`/`Or`、`Command`、`Shell`、`Scroll`、`InputText`、`MultiSwipe`。需要引入前先与用户确认。
- 不使用 `model` 字段（OCR 走 `base/model/ocr` 根目录默认模型）。
- `is_sub` / `interrupt` 在 v5.1 已废弃，**禁止使用**，用 `[JumpBack]` 替代。

### 4.3 字段使用约定（附现状统计）

**字段概貌**（全仓 396 个节点，2026-10-14；复核脚本见 §8）：

- 节点级常见：`next`(321) `focus`(287) `post_wait_freezes`(176) `timeout`(142) `post_delay`(111) `on_error`(72) `max_hit`(75) `pre_delay`(9)。
- 参数级：识别参数常用 `expected`(225) `roi`(215) `template`(66)；动作参数里 `target`(114) 最多，其次 `begin`/`end`(34，`Swipe` 专用)、`duration`(18)、`package`(3)。
- 少数派（照现有例子写，别自己发明组合）：`threshold`(24)、`order_by`/`index`(14)、`enabled`(13：9 处是 §14.2 的物资白名单开关、3 处是档位开关，1 处是公共节点 `任务间隔`)、`repeat`/`repeat_delay`(5)、`rate_limit`(1)。另有 10 处 `timeout` 误写在 `action.param` 里、属废值，见 §7.2。

- **`focus` 约定（2026-09-19 批量补齐后）**：凡是**真的执行动作**的节点（`Click`/`Swipe`/`ClickKey`/`StartApp` 等）都带一条进度通知，写在 `action` 成员之后，只用 `Node.Action.Succeeded` 这一个键：

  ```jsonc
  "focus": {
      "Node.Action.Succeeded": "进入浊暗之阱"
  }
  ```

  全仓 386 个节点中 **282 个**带 focus（`Node.Action.Succeeded` 257、`Node.Recognition.Succeeded` 23、`Node.Recognition.Starting` 2）。**不加** focus 的两类：① 纯分发节点、只有 `DoNothing`/`StopTask` 的节点（没有动作结果可上报）；② 纯手势与通用 UI 辅助节点（`左滑`/`右滑`/`上滑`/`第一次滑动`/`点击`/`侧边点击`/`返回按钮`/`点击关闭按钮`/`关闭界面` 等），它们在循环里被反复触发、名字又不含业务对象，只会刷日志。
- 文案默认取节点名本身，仅以下几类按规则改写：`X入口` → `进入X`；`X_异常处理` → `处理X异常`；`X_SecondClick` → `X二次点击`；`X_副本N` → 去掉 `_副本N` 后缀；`StartApp` 节点 → `启动游戏`。新增节点时照这套走，别写英文或留空。

- **延迟策略**：优先 `post_wait_freezes`（等画面静止），其次才用 `post_delay`。官方建议"增加中间节点，少用 delay"（`3.1` §等待画面静止）。
- **`timeout` / `on_error` 归属上一节点**：想控制"等某个节点出现多久"，改它**父节点**的 `timeout`；想超时后兜底，改父节点 `on_error`。这是本项目最常踩的坑，务必参考 `3.1` §属性字段的原文提示。
- **阈值要压误判就显式写**：全仓 22 处，集中在四类节点 —— 密盟兑换 8 处 `0.9`、破碎防线 8 处 `0.8`、监管 4 处 `0.9`、项目名通用按钮 2 处 `0.85`。`default_pipeline.json` 的默认值当前不生效（§7.1），所以改阈值必须写在节点上，并先按 §14.4 离线复测。
- 每个 task 的入口节点（`interface.json` 里的 `entry`）必须真实存在于合并后的 pipeline 中。MaaFW **按键名查找**，与键序无关；仓库惯例是入口节点写在文件开头、新增节点追加在末尾。

### 4.4 坐标

- 一律 4 元绝对像素 `[x, y, w, h]`，基准 **1280×720**（`README.md:45-48`，MuMu5 2560×1440 开发）。
- 纯点击点写成 `[x, y, 1, 1]`。
- `roi` = 识别范围，`box` = 命中的位置，`target` = 动作落点；`roi_offset` / `target_offset` 在其上叠加（`3.1` §roi/box/target 区分）。
- `target` / `begin` / `end` 在 v2 写法里都写在 `action.param` 内（`begin`/`end` 属于 `Swipe`）。`target` 可用 `true`（用本节点 `box`）、节点名字符串、`[Anchor]名`、`[x, y]` 或 `[x,y,w,h]`。
- 不要在节点里写 `"coordinateMode"`、`"pipeline_version"` 之类自造字段：MaaFW 只按协议字段名取值，多余 key 一律静默忽略、不报错，所以写错了只会表现为"节点行为莫名其妙"。

### 4.5 流程控制惯例

- 入口节点常写成只做分发的纯 `next` 节点（`派遣.json:2-11`、`体力.json:2-12`）。
- **弹窗/异常恢复用 `[JumpBack]`**（三个 bundle 合计 270 处；除它之外没有用别的回跳机制），挂在父节点 `next`/`on_error` 上，处理完自动回到父节点重新识别：`"[JumpBack]关闭界面"`。
- `next` 数组**顺序即优先级**：命中第一个就中断后续。把专有的、易误判的分支放前面，兜底分支放最后。
- 流程终止条件只有三种（`3.1` §终止条件）：`next` 为空、`next` 未命中且超时、外部 `StopTask`。所以链尾必须以 `DoNothing` 或明确终点收尾，否则会靠超时结束。

### 4.6 图片引用

- **`template` 相对 `image/` 根目录解析**，可写裸文件名，也可写带子目录的相对路径（如 `"密盟兑换/数量减号.png"`），还可整目录（递归加载其中所有图片）。
- 本项目现状（2026-10-14）：66 处 `template` 引用、37 张唯一图，两种写法并存 —— 裸文件名 56 处，带子目录 10 处（都在 `密盟兑换/`）。`resource/base/image/材料/` 下 23 张图仍然**只被 `interface.json` 的 `icon` 使用**，pipeline 未引用；要引用就写 `材料/xxx.png` —— 带子目录的相对路径是协议支持的写法，M9A 里 `Psychube/xxx.png` 就是这么写的（只借它的写法，图片素材不通用）。
- 图片必须是**无损原图缩放到 720p 后裁剪**（`1.1` §图像素材）。用 VSCode maa-support / MFA 工具箱 / ImageCropper 截取，不要手工缩放压缩过的截图。

### 4.7 命名与风格

- **节点名和文件名全部用中文**（`密盟`、`浊暗之阱`、`扫荡完成`、`职业选择`），不用驼峰/下划线英文。
- 变体后缀惯例：`_SecondClick`、`_异常处理`、`回主页`、数字后缀（`首页检查2`、`危机管理2`）、`_副本4`（历史遗留，勿模仿新增）。
- **通用/共享节点集中放在 `resource/base/pipeline/项目名.json`**（`主菜单`、`返回按钮`、`点击关闭按钮`、`左滑/右滑/上滑`、`扫荡完成`、`扫荡调令不足`、`难度选择`、`副本未开放` 等）。新增跨任务复用的节点放这里，不要在各业务文件里复制。文件名"项目名"是脚手架遗留，含义即"公共节点池"。
- 占位待办用空对象节点：`"TODO设置自动战斗": {}`（`破碎防线.json:61`）。
- **pipeline JSON 一律不写注释**（`//` 与 `_comment` 都不要）：全仓 43 个 pipeline 文件严格无注释，可直接用 `json.loads` 校验；只有 `resource/default_pipeline.json` 是 JSONC 允许注释。中文 key 直写，不做 `\uXXXX` 转义。
- **格式已于 2026-09-19 全量归一化**（30 个文件，逐文件通过「解析后对象与改前完全相等」校验）：`resource/**/*.json` + `interface.json` 统一为 **4 空格缩进、LF、UTF-8 无 BOM、无行尾空格、文件末尾单个换行、`"key": value` 冒号后一个空格**。写新代码就照这套。
- **坐标数组允许单行紧凑写法**（`"target": [185,330,1,1]`），这是本项目既有习惯且更省行数；不要为了"美观"把它拆成多行，也不要改动任何已有的换行位置 —— 归一化只动了行首缩进和单位宽度，没有重排换行。
- **禁止**再对整个文件做 reformat / 重新 `json.dump`（会把紧凑数组全部炸开成多行，产生上百行无意义 diff）。只改你真正要改的那几行。

## 5. 多服差异（overlay 规则）

`interface.json` 的 `resource` 决定加载顺序，**后加载的同名 task 与先加载的按顶层 key 合并覆盖**（列表整体替换、不逐项合并；`3.3` §资源覆盖）：

- 官服 `[base]` / B服 `[base, bilibili]` / 国际服 `[base, global]`，路径统一写 `{PROJECT_DIR}/resource/...`。
- 因此差异包里**只写需要改的节点**，未出现的节点继续由 `base` 提供。示例：
  - `package`：base `com.zy.wqmt.cn` / bilibili `com.zy.wqmt.bilibili` / global `com.zy.wqmt.global`（各 `启动.json` 的 `StartApp`）。
  - `友情点.json`：base 用 `OCR "领取"`，bilibili 同名节点改为 `TemplateMatch "一键领取.png"`。
  - `global/pipeline/密盟.json` 故意**删掉入口节点**（沿用 base 的）；global 另新增 base 没有的 `专案密令.json`、`时尚巡游.json`。**被 base 取代的整份旧拷贝要删掉**：`浊暗之阱.json` 等 3 个 overlay 已随 `19b54a5` 交回 base 接管 —— 差异包里只留真正的差异，陈旧拷贝一律删。
- 改 `base` 里的共享节点会同时影响三个服 —— 只该服需要的改动，一律放进 `bilibili/` 或 `global/`。

## 6. `interface.json` 规则

- 结构（实测字段清单，2026-10-13）：`interface_version/name/title/icon/version/mirrorchyan_rid/mirrorchyan_multiplatform/url/controller/resource/agent/task/option/github`。
- `controller` 只有一个 Adb（`"安卓端"`）；`agent` 段已按 §2.3 落地。不要凭空添加 `custom`/`account`/`preset`；其他顶层扩展先与用户对齐。
- 15 个 `task`，每项 `{name, entry, option?, doc?}`；`entry` 必须能在（合并后的）pipeline 中找到顶层节点。
- option 组现有 8 个：`作战区域`/`畸点选择`/`派遣区域`/`材料选择`/`关卡未开放备选`/`识别方式`/`兑换档位`/`兑换物资`。
- 参数化用 `option.<组名>.cases[]`，`case` 通过 `pipeline_override` 覆盖同名节点的 `next` / `expected` / `on_error` 实现分支，例如：
  - `"每日体力用途": { "next": "狄斯币" }`
  - `"派遣区域选择": { "expected": "..." }`、`"职业选择": { "expected": "坚韧" }`
- `case.icon` 写 `image/材料/xxx.png`、`image/密盟兑换/xxx.png`（相对所选资源目录），而顶层 `icon` 写 `resource/base/image/logo.ico`（相对项目根）——两种基准并存，新增时照抄同类字段的写法，不要"顺手统一"。
- `type: "checkbox"` 的多选**不是并集**（同名节点同字段后者覆盖前者）——白名单要靠「每目标一个节点 + `enabled` 开关」，见 §14.2。
- `doc` 用 **BBCode**：`[b]…[/b]`、`[color:orange]…[/color]`、`\n`。

## 7. 已知问题（不要静默"修复"）

### 7.1 `default_pipeline.json` 未被加载

`resource/default_pipeline.json` 是 JSONC 全局默认（`Default.rate_limit 2000 / timeout 30000 / pre_delay 500 / post_delay 200`、`TemplateMatch.threshold 0.7 / method 5`、`OCR.threshold 0.3 / model "OCR"`）。

但上游 `ResourceMgr::load_bundle()` 只在 **bundle 根目录**查找 `default_pipeline.json`（先找 `.jsonc` 再找 `.json`，与 `pipeline/`、`image/` 同级），本项目 bundle 根是 `resource/base`。该文件位于其上一层 `resource/`，**因此当前实际未被加载**，所有节点用的是框架内置默认（`rate_limit 1000`、`timeout 20000`、`pre/post_delay 200`、`TemplateMatch.threshold 0.7`、`OCR.threshold 0.3`）。

依据有三条：上游 `ResourceMgr::load_bundle()` 源码只在 bundle 根找该文件；`3.1` §默认属性原文写明「应放置在资源包（Bundle）的根目录下，与 `pipeline` 文件夹同级」；[M9A](https://github.com/MAA1999/M9A)（虽是不同的游戏，但同属 MaaFW 项目）也放在 `resource/base/default_pipeline.json`。三者一致，可判定本项目的放置位置有误。

推论与约束：
- 现有 timings 是在"这些默认不生效"的前提下跑通的。**擅自移动到 `resource/base/` 会改变全局节奏并可能引入回归**。要做需先向用户说明影响并取得确认，然后在模拟器上回归。
- 同理：`bilibili/`、`global/` 无默认文件，且"已加载节点不受后续 bundle 默认值影响"——多包默认值只能作用于各自之后加载的节点。
- 需要确定生效的默认参数，**写在节点上**最稳。
- 另注：`default_pipeline.jsonc` 优先于 `default_pipeline.json`（同一 bundle 根内二选一）。

### 7.2 `timeout` 被写进 `action.param`，实际不生效

`timeout` 是**节点级**字段，`DoNothing`/`Click` 没有这个动作参数。曾有 26 处写成 `"action": { "type": "DoNothing", "param": { "timeout": N } }`（三个 `启动.json` 16 处 + `global/采购办.json` 10 处），MaaFW 按键名取值 → **这个 N 从来没起过作用**，节点实际一直用框架默认 20000ms。

已处理：三个 `启动.json` 的 **16 处**已于 2026-09-19 搬到节点级（`base` 6、`bilibili` 4、`global` 6），逐文件通过「除该项外节点完全相等」校验。依据是实机日志：`首页` 想等 3 秒却实等 20 秒，弹窗轮询每轮白等约 17 秒。

**仍未处理**：`resource/global/pipeline/采购办.json` 的 8 处（`采购办网络恢复_*` 5000 共 7 处、`采购办滑动前等待` 2000）+ 2 处节点级与 param 里各有一个 `timeout`（`确认养成补给选中`、`确认免费礼包详情`，param 里那个 500 是废值）。

约束：
- 这 16 处属于**行为变更**（20000 → 3000/5000/15000/30000，超时路径会更早触发），**必须实机回归**；回退走 git 历史（搬迁发生在 `21dfec6`「接入 AgentServer」那次提交里；早先的备份目录 `G:/MBCCtools_backup_20260919/` 已删除）。
- 搬之前先确认该节点没有同时存在节点级 `timeout`；若两边都有，param 里那个是废值，直接删，别覆盖。
- 新增节点时 `timeout` 一律写在**节点级**，不要再塞进 `action.param`（历史遗留写法，`采购办.json` 里还残留若干处，别照着抄）。

### 7.3 运行时权威版本是 `runtimes/` 那份 MaaFramework.dll

MFAAvalonia 是 .NET 程序，按原生依赖解析规则加载的是 **`runtimes/win-x64/native/MaaFramework.dll`**（实测 v5.12.3）。曾经根目录还有一份同名副本（给 `MaaPiCli.exe` 用，一度是 v5.13.0、与 runtimes 不一致），**现已移除**——仓库里只有 runtimes 这一份；`.scratch/maafw5123/` 只是本地离线自测解包（gitignored，见 §14.4）。

- 想知道"本项目运行时到底是哪个版本"，读 `runtimes/win-x64/native/MaaFramework.dll` 的版本串，或直接看 `debug/maafw.log` 里 `AgentClient::connect` 打出的 client 版本，**不要**依赖其他位置的 dll。
- 这条直接决定 Custom 能不能用：AgentServer（Python 绑定）与 AgentClient（MFA 加载的那份）协议必须同代，5.12.x=protocol 7、5.13.x=protocol 8，跨代直接拒连（日志 `Protocol version mismatch` + `Please update AgentClient`，随后 MFA 还会抛一个自己侧的 `NullReferenceException`，那句 `Agent 'python' failed to start` 是它的连锁反应，不是真的启动命令失败）。
- 用 `MaaPiCli.exe` 调试前先确认它加载得到 dll（它的解析路径与 MFA 不同，历史上出现过两套版本不一致）—— 出问题先确认是谁在跑。

## 8. 修改后自检

没有本地单测，也没有 CI（且**没有 git 兜底**，动手前先自查、必要时自行复制一份备份）。可行的最小验证：

0. 项目外的临时备份（如 `G:/MBCCtools_backup_20260919/`）**已全部删除** —— 现在没有兜底目录，动手前先自查、必要时自己复制一份；回退一律走 git 历史。
1. **语义等价校验**（改格式/重构时的硬标准）：逐个文件 `json.loads(改前) == json.loads(改后)`，不等就回退。
2. JSON 语法必须合法。pipeline 文件不允许注释，可直接校验：
   `python -c "import json,pathlib;[json.loads(p.read_text(encoding='utf-8')) for b in ('base','bilibili','global') for p in pathlib.Path('resource',b,'pipeline').rglob('*.json')]"`
   （`resource/default_pipeline.json` 是 JSONC，不能用这条校验。）
3. 引用完整性：新增/改动的 `next` / `on_error` / `target` / `template` 字符串必须指向真实存在的节点名，或 `image/` 下真实存在的相对路径。
4. `interface.json` 每个 `task.entry`、每个 `pipeline_override` 的 key，都能在（对应服的）合并后 pipeline 中找到节点。
5. 坐标不得超出 1280×720 基准（`roi`/`target`/`begin`/`end` 的 `x+w`、`y+h`）。
6. 实机验证由用户完成：需要 Adb 连接的模拟器（1280×720）+ MFAAvalonia（首选；`MaaPiCli.exe` 的 dll 解析见 §7.3 的注意）。无法实机验证时，**明确说"未验证"**，不要声称功能正确。
7. 打包链路（`install.py` / `prepare_agent_runtime.py` / `install.yml`）本地复现：`mkdir -p deps/bin deps/share/MaaAgentBinary && python install.py v0.0.0-test`。会顺带去下载便携解释器与依赖（缓存在 `deps/.agent-runtime-cache/`），跑完删掉 `install/`、`deps/`。要验 agent 真能起来，不必开模拟器：用包内解释器拉起 `install/agent/main.py`，再用 MaaFw 的 `AgentClient` 连一次同 identifier 即可（能列出 `CloseButton` 等注册项就算通）。
8. **统计复核**（§3/§4.2/§4.3/§4.6 的数字漂了就用它重算；算完把新日期同步进文首与相应小节）：

    ```python
    import collections, json, pathlib
    root, nf, pf = pathlib.Path('resource'), collections.Counter(), collections.Counter()
    nodes = files = 0
    for b in ('base', 'bilibili', 'global'):
        fs = sorted((root / b / 'pipeline').rglob('*.json'))
        files += len(fs)
        for p in fs:
            for node in json.loads(p.read_text(encoding='utf-8')).values():
                if not isinstance(node, dict):
                    continue
                nodes += 1
                nf.update(node.keys())
                for s in (node.get('recognition'), node.get('action')):
                    if isinstance(s, dict) and isinstance(s.get('param'), dict):
                        pf.update(s['param'].keys())
    print('文件', files, '节点', nodes)
    print('节点级', {k: nf[k] for k in ('next', 'focus', 'timeout', 'post_wait_freezes',
                                        'post_delay', 'on_error', 'max_hit', 'pre_delay',
                                        'enabled', 'repeat', 'repeat_delay', 'rate_limit')})
    print('参数级', {k: pf[k] for k in ('expected', 'roi', 'template', 'target', 'begin', 'end',
                                        'duration', 'package', 'threshold', 'order_by', 'index')})
    ```

推荐工具（写进你的判断依据，不强制）：VSCode 插件 `nekosu.maa-support`（跳转/引用/按 MaaPiCli 运行/截图裁剪）；JSON Schema：根目录 `interface.schema.json`，pipeline 用上游的 `tools/pipeline.schema.json`（本地解包在 `.scratch/maafw5123/tools/`，可重下）。

## 9. 本地文档索引 `docs/zh_cn/`

上游 `MaaXYZ/MaaFramework` `main` 分支副本，同步于 commit `b849283`（2026-09-17），详见 `docs/README.md`。与运行时有差异时，**以实际生效的框架版本为准**（MFA 加载 `runtimes/win-x64/native/` 那份，实测 v5.12.3，见 §7.3），字段引入版本查 `3.1` §版本变更表。

| 场景 | 查哪份 |
| ---- | ---- |
| 任何 pipeline 字段、算法、动作、`next` 语义、节点属性、默认属性 | `docs/zh_cn/3.1-任务流水线协议.md` |
| `interface.json` / option / 资源覆盖 / 通知 | `docs/zh_cn/3.3-ProjectInterfaceV2协议.md`（`3.2` 是废弃的 v1） |
| 目录结构、图片规格、OCR 模型、调试与打包 | `docs/zh_cn/1.1-快速开始.md` |
| 术语 | `docs/zh_cn/1.2-术语解释.md` |
| Adb 截图/输入方式（本项目控制器） | `docs/zh_cn/2.4-控制方式说明.md` |
| 回调消息类型（`focus` 相关） | `docs/zh_cn/2.3-回调协议.md` |
| 提 issue / 日志要求 | `docs/zh_cn/5.1-问题反馈.md` |
| 自定义识别/动作、AgentServer 与 AgentClient 怎么搭（方案二，§2） | `docs/zh_cn/1.3-Custom&Agent.md` |
| 用 Node.js 写 Custom（若选 Node 而非 Python） | `docs/zh_cn/NodeJS/J1.1~J1.3` |
| C++/Win32 集成接口、构建 MaaFW 本体、自定义控制单元 | 本项目用不到，勿据此改代码 |

## 10. 通用行为约束

- 沟通与**所有节点名/文件名/文档内容用中文**；标识符语义保持中文这一项目惯例，不要"英文化"。
- 只改与需求直接相关的节点；不顺手重排、不改缩进、不批量格式化。
- 新增功能优先复用 `项目名.json` 的公共节点，而不是复制粘贴。
- 改动 `base` 之前先想清楚对 B服 / 国际服 的连带影响。
- 不确定的游戏 UI（分辨率、文案、阈值）标注清楚并交给用户在模拟器里验证，不要凭猜测填坐标。

## 11. 与 MFAAvalonia 工作区的分工

**界面相关改动不在本仓库做**，去 `G:/MFAAvalonia工作区`（MFAAvalonia 的定制 fork，README 里列了它自建的页面）。

| 要做的事 | 放哪 |
| --- | --- |
| pipeline 节点、Custom 识别/动作、模板图、OCR 模型、`default_pipeline.json` | 本仓库 |
| `interface.json`（任务/选项/文案）、`resource/Announcement/*.md` | 本仓库 |
| `agent/` 里的自定义逻辑、联网采集与落档到 `record/` | 本仓库 |
| 新增/修改界面页面、侧栏项、样式、通知呈现 | **MFAAvalonia 工作区** |

- MFAAvalonia 没有"资源侧声明自定义页面"的机制，界面只能写在 fork 里；反过来，游戏画面识别与联网抓取也不该塞进 fork —— 分层见 §2。
- 两边靠**文件契约**连接：本仓库往 `record/` 写（`抽卡记录/*.jsonl`、`抽卡记录.xlsx`、`抽卡记录.md`、`活动.json`；`record/` 不入库），fork 的页面只读文件、不联网。这样抓取/解析规则变了只需更新本仓库，用户不用重下 GUI。
- 想"不动 GUI 就发布内容"时用 `resource/Announcement/*.md`：MFAAvalonia 原生展示公告。
- fork 侧的约定（页面注册点、构建部署、截图核对）见 `G:/MFAAvalonia工作区/AGENTS.md`。

## 12. 维护操作：拉取禁闭者头像

**触发语：「更新禁闭者头像」** —— 听到这句就按本节跑一遍，不必再问；跑完把「补了谁 / 缺哪个 / 有没有多的」报给用户。

这群图**与 pipeline 无关**，全仓没有任何节点引用它们。用途在 MFAAvalonia fork 的「抽卡记录」页：按 `resource/base/image/头像/<稀有度>级/<名>.png` 找图，缺图退回首字色块。所以**文件名必须与角色名逐字一致、稀有度目录必须选对** —— 那是 fork 侧的查找路径，改个名就等于丢图。

### 12.1 来源与约定

- 来源页 <https://wiki.biligame.com/wqmt/头像图鉴>。它是 Semantic MediaWiki 的 `#ask` 动态渲染，**HTML 里没有名单**，只能走 `api.php`。
- 目录名 = wiki 的 `类别` 属性：`狂级` / `危级` / `普级`。
- **只取 `来源=禁闭者`**。同一 `类别` 下还有大量 `来源=装束`（皮肤头像，名字是「一帘烟雨」这类皮肤名而不是角色名）、以及 `活动`/`谜典`/`礼包`/`周边`/`特别装束影像` —— 一律不要。反过来，`幽冕·海拉`、`荒噬·伊琳娜` 属于 `来源=禁闭者`，是正常角色图，别漏。
- 文件名 = `角色名.png`。wiki 的文件页带「头像」后缀（`文件:阿兰恰头像.png`），**存盘时去掉**。
- **下载原图，不要缩略图**。原图就是 250×250，本地文件与 wiki 原图**逐字节一致**（2026-10-10 用卓娅比对 md5 确认）。注意别抓成 URL 里带 `/thumb/` 的那份。
- **只增不改**：已存在的文件不动；本地「多」出来的（wiki 没有）也不删，报给用户决定。

### 12.2 抓取要点（踩过的坑）

- 必须带 `User-Agent` 和 `Referer: https://wiki.biligame.com/wqmt/`，否则被 WAF 挡。被挡的表现是非标准 **HTTP 567**（不是 4xx/5xx）—— 看到 567 就退避重试，不是参数写错了。
- `limit` 要写在 **SMW 查询串里面**（`...|limit=500`）。当独立 URL 参数传**不生效**，只回默认 20 条，会让你误判成「本地莫名多了几十个」。
- 列表查询：`action=ask` + `query=[[分类:头像]][[来源::禁闭者]]|?名称|?类别|limit=500`，结果在 `query.results[*].printouts`。
- 原图 URL：`action=query&prop=imageinfo&iiprop=url|size&titles=文件:<名>头像.png`，取 `imageinfo[0].url`。逐个角色查即可（缺的通常个位数），请求之间 `sleep 0.5`。
- 若把脚本落成临时文件再跑：本工具的 `Write` 写 `/tmp/x.py` 实际落到 `G:/tmp/x.py`，与 Git Bash 的 `/tmp`（`C:\Users\...\AppData\Local\Temp`）**不是同一处**，Python 会报找不到文件。用 `G:/tmp/...` 这种带盘符的绝对路径。

### 12.3 参考实现（2026-10-10 实测通过）

```python
import json, os, sys, time, urllib.parse, urllib.request

WIKI = "https://wiki.biligame.com/wqmt/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://wiki.biligame.com/wqmt/"}
ROOT = sys.argv[1] if len(sys.argv) > 1 else "resource/base/image/头像"
ONLY = sys.argv[2:] or ["狂级", "危级", "普级"]


def api(params):
    url = WIKI + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# 1. 列表：来源=禁闭者（排除 装束/活动/谜典/礼包/周边/特别装束影像）
res = api({"action": "ask", "format": "json",
           "query": "[[分类:头像]][[来源::禁闭者]]|?名称|?类别|limit=500"})["query"]["results"]
want = {}
for v in res.values():
    p = v["printouts"]
    want.setdefault(p["类别"][0], set()).add(p["名称"][0])

# 2. 与本地比对，只补缺失
total = 0
for cat in ONLY:
    names = want.get(cat, set())
    d = os.path.join(ROOT, cat)
    have = {os.path.splitext(f)[0] for f in os.listdir(d)}
    missing, extra = sorted(names - have), sorted(have - names)
    print(f"{cat}: wiki {len(names)} / 本地 {len(have)}  缺 {missing or '无'}  多 {extra or '无'}")
    # 3. 取原图 URL 后落盘
    for name in missing:
        info = api({"action": "query", "format": "json", "prop": "imageinfo",
                    "iiprop": "url|size", "titles": f"文件:{name}头像.png"})["query"]["pages"]
        ii = next((p["imageinfo"][0] for p in info.values() if "imageinfo" in p), None)
        if not ii:
            print(f"  × {name}: wiki 上找不到 文件:{name}头像.png")
            continue
        req = urllib.request.Request(ii["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(os.path.join(d, name + ".png"), "wb") as f:
            f.write(data)
        print(f"  + {name}.png  {ii['width']}x{ii['height']}  {len(data)}B")
        total += 1
        time.sleep(0.5)
print("新增", total, "个")
```

把上面这段存成临时脚本（例如 `G:/tmp/upavatar.py`），在仓库根目录跑：`python G:/tmp/upavatar.py "resource/base/image/头像"`（不给第三个参数就是三个稀有度全查）。

### 12.4 自检

- 补完**立刻重跑一遍**：三段都应是「缺 无 多 无」+「新增 0 个」（幂等）。
- 抽查新文件：`250x250`、能正常打开、md5 与 wiki 原图一致。
- 文件名与角色名一致，尤其 `L.L..png`、`芭·菲.png` 这类带标点的 —— 对不上 fork 页面就取不到图。
- 这些图不参与 pipeline，**不用**跑 §8 的 JSON 校验；但要确认新增的 png 没被 `.gitignore` 挡掉。

### 12.5 现状

2026-10-10：狂级 74 / 危级 72 / 普级 14，与 wiki 完全一致，无缺失无多余。本次补入的只有 `狂级/阿兰恰.png`（2026 年新角色）。

## 13. 维护操作：重新生成程序图标

**触发语：「更新程序图标」** —— 听到这句就按本节跑一遍，跑完把三个落点与校验结果报给用户。

母版是 `resource/base/image/logo.png`（1254×1254，那幅角色插画）。生成命令：

```bash
python tools/build-icon.py 输出.ico [更多输出.ico ...]
python tools/build-icon.py --check 输出.ico        # 只校验，不写入
```

脚本把尺寸台阶分成两段，要换构图就改这里：

| 尺寸 | 画面 |
| ---- | ---- |
| 16 / 24 / 32 | 裁到「脸 + 护目镜」（`CROP_512`，坐标基准是原画缩到 512×512 时） |
| 48 / 64 / 128 / 256 | 整张原画 |

小尺寸必须用裁切图：整幅原画缩到 16~32px 只剩色块，裁到脸和护目镜之后还能看出两个镜片和头带。换裁切框就改 `CROP_512`，改完重新生成并**逐级目视**（16/24/32 是重点，48 以上原画本来就够清楚）。

### 13.1 三个落点，别只改一个

| 文件 | 谁在用 |
| ---- | ------ |
| `resource/base/image/logo.ico` | `interface.json` 的 `icon`，运行时窗口 / 任务栏 / 托盘图标（生产环境走的就是这条：安装目录根**没有** `Assets/`） |
| `G:/MFAAvalonia工作区/MFAAvalonia/Assets/logo.ico` | exe 的 `<ApplicationIcon>` 内嵌图标（Explorer 里看到的，也是 IconHelper 的兜底来源） |
| `G:/MFAAvalonia工作区/MFAUpdater/logo.ico` | 更新器的 exe 图标 |

三个用同一份字节。内嵌资源（`avares://MFAAvalonia.Core/Assets/logo.ico`）取的也是它，所以 **exe 图标要重新构建 fork 才生效**（编译期资源）；`resource/` 那个是运行时读文件，换完即时生效——前提是 fork 侧 `IconHelper` 已按 §13.2 修好。

### 13.2 两个坑（2026-10-10 实测）

- **只有一帧 256 的 ICO 一定糊**，而且目录标注必须与实际像素一致。事故原样：`resource/base/image/logo.ico` 曾是一个目录项写 256×256、内里却是 512×512 的 PNG——运行时窗口图标真的就是一张 512 位图被 Windows 缩到 16（用 `WM_GETICON` 实测印证：`ICON_SMALL=512x512`）。现在固定产出 7 帧，`--check` 会报出任何「目录标注与实际像素不符」。
- **多尺寸帧只有走原始字节才用得上**。Avalonia 的 `IPlatformIconLoader.LoadIcon(IBitmapImpl)` 会把位图重新编码成 PNG 再交给 `Win32Icon`；`Win32Icon` 读到非 ICO 数据就退化成「按位图原尺寸建 HICON」，尺寸信息全丢。所以 fork 的 `IconHelper` 必须留住 `.ico` 原字节、用 `new WindowIcon(new MemoryStream(bytes))`，**不要**先解成 `Bitmap` 再传。

### 13.3 自检

- `python tools/build-icon.py --check <三个文件>` 全绿，且三者 md5 相同。
- 实测窗口真正设上去的图标尺寸（新旧对比最直观）：

  ```powershell
  powershell -ExecutionPolicy Bypass -File G:/MFAAvalonia工作区/bin/query-icon.ps1 -Id <pid>
  ```

  修好后应是 `ICON_SMALL=16x16  ICON_BIG=32x32`（按 DPI 取最近帧）；**再出现 `512x512` 就说明又退回单帧、或 IconHelper 被改回传 Bitmap 了**。
- 这些 ico 不参与 pipeline，**不用**跑 §8 的 JSON 校验。


## 14. 秘盟兑换任务（`密盟兑换.json`）

**入口**：`interface.json` 的 task「秘盟兑换」→ 节点 `密盟兑换`。任务**不做导航**，要求用户先手动打开「采购办 → 玩法兑换 → 秘盟兑换」（停在哪个档位都行，同「抽卡记录」的套路）。白名单由 option `兑换物资`（`type: "checkbox"`）勾选，**初阶/中阶/高阶三档会自动依次走一遍**。

### 14.1 交互闭环（2026-10-11 首验；2026-10-14 补三档与横滑翻屏）

点卡片**不会直接买**，会开详情弹窗，所以每种物资的流程是：

```
密盟兑换_确认页面  OCR「秘盟兑换」确认停在兑换页（不在就收尾，不会乱点）
密盟兑换_换下一档  按顺序挑下一步：去初阶 → 初阶右滑 → 去中阶 → 中阶右滑 → 去高阶 → 高阶右滑 → 结束
密盟兑换_去初阶/去中阶/去高阶  点档位页签；每档只能进一次（max_hit: 1 当状态机）
密盟兑换_初阶右滑/中阶右滑/高阶右滑  每档横滑一屏，看列表后半段；也是每档一次
密盟兑换_兑换循环  当前屏没有可换物资 → on_error → 换下一档
密盟兑换_物资_X   图标模板命中 → 点该图标 → 开详情弹窗
密盟兑换_数量拉满  TemplateMatch「数量减号.png」确认弹窗已开 → Swipe 把数量拉条拖到最右
密盟兑换_购买     Click 红按钮 → 弹窗自动关闭 + 全屏「获得物资」遮罩（不会自动消失）
密盟兑换_获得物资 OCR「获得物资」→ 点掉遮罩（链尾，JumpBack 负责回循环）
```

- **切档/翻屏用 `max_hit: 1` 当状态机**：`密盟兑换_换下一档.next` 是一张有序清单（去初阶 → 初阶右滑 → … → 结束），节点被用掉一次后自动被跳过，所以顺序天然成立。改档位数、档位顺序、每档要滑几屏，都只改这一条 next 与相应节点。
- **列表是横向可滚动的**（2026-10-14 纠正：早先"列表不滚动"的结论是拿**纵向**滑动测的，测错了）。一屏放 3 列 6 格，物资多于一屏就得横滑；**切档位会把该档的滚动位置重置回最左**（实测），所以每档"起始一屏 + 右滑一屏"两屏就能覆盖该档全部物资（最长的高阶 9 件正好两屏）。滑完不要当它回到原位——所以每档只有一个右滑节点。
- **切档/翻屏后都要等画面静止**（`post_wait_freezes: 1000` / `800`），否则会拿旧画面去点新画面上的卡。

- **循环是 `[JumpBack]` 驱动的**（§4.5）：`密盟兑换_兑换循环.next` 里「获得物资」与每个物资引用都写成 `[JumpBack]密盟兑换_物资_X`，链路走完自动回父节点重扫；**链尾节点（获得物资/关闭详情弹窗）不写 `next`**，不要再加 `next: [密盟兑换_兑换循环]` 这类手动回边。实测**走 `on_error` 的失败链同样会回跳**（v5.9+ 行为，5.12.3 上用三场景离线验证过）；物资节点自己的 `timeout: 4000` 兜"点卡后弹窗没开"。
- **滑条拖到最右 = 自动钳到本月剩余限购**，所以一种物资一次买满，不需要循环买。
- 点购买**没有二次确认弹窗**（多数量也没有）；价格显示的是**总价**（单价 × 数量）。
- 购买失败（弹窗没关、没出遮罩）由 `密盟兑换_购买` 的 `timeout` 兜：超时进 `on_error` → `密盟兑换_关闭详情弹窗`（点弹窗外即可关闭），链尾交给 JumpBack 回循环。

### 14.2 四条不能改错的约束

- **阈值 0.90，别再往下调**。真框架（MaaFW 5.12.3）实测：真值最低 **0.964**（狄斯币在 9 物资全量矩阵里），假值最高 **0.827**（高阶材料补给箱模板误命中中阶材料补给箱图标——三种补给箱几何相同、只有颜色不同，而 MaaFW 的 `TemplateMatch` 走**灰度**，颜色区分不了）。0.90 是这两者中间。
- **ROI 必须是整片列表区 `[425,220,770,395]`，不要按卡位收窄**。列表按「列优先」填格，**售罄的物资会沉到列表末尾**（兑换后卡位会变：实测买空狄斯币后它从左上跑到右下），按卡位切 ROI 会在重排后漏掉物资。
- **白名单是「每种物资一个节点 + `enabled` 开关」，不是 `expected`/`template` 数组**。理由见 §6：PI V2 的 checkbox 是把各 case 的 `pipeline_override` 按 cases 顺序合并、**同名节点同字段后者覆盖前者**，写成一个节点上的列表会互相覆盖。
- **物资节点的 `max_hit: 6` 是按节点计、三档共用的**（`6 = 三档各买一次 + 三档各重试一次`）。改档位数、或让某物资多档重复兑换时要一起调，**调小了会让中/高阶整档漏换**。`max_hit` 每次任务运行独立计数（实测同一 Tasker 连跑两次不累积），重复跑任务不受影响。

### 14.3 素材与识别

- 模板全在 `resource/base/image/密盟兑换/`：9 个物资图标（`<物资名>.png`，连图标底部的品质光条一起裁，约 92×94）+ `数量减号.png`（弹窗判据，语言无关，比 OCR「购买数量」更稳）。
- **物资清单按档递增**（2026-10-14 实测）：初阶 4 件（狂乱精粹/狄斯币/低阶材料补给箱/技能模组Ⅰ）、中阶 7 件（再加记忆碎片/中阶材料补给箱/技能模组Ⅱ）、高阶 9 件（再加高阶材料补给箱/技能模组Ⅲ）。要补物资就从**该物资所在档的那一屏截图**上裁（技能模组Ⅱ/Ⅲ 只在横滑后的第二屏可见）。
- 图标必须从 **1280×720 原始截图**上原样裁（§4.6），不要缩放或重画。
- 剪影判据：**已售罄的卡会被灰带盖住图标中段**，同一模板分数掉到 0.34~0.45（实测），所以"买空 → 图标不再命中 → 循环自然收尾"成立；不需要单独做「已售罄」识别。三个技能模组（Ⅰ 白卡/Ⅱ 绿条/Ⅲ 蓝卡）灰度下**互不误认**（实测最高 0.757），不用额外区分手段。
- 要加新物资：截一张该物资正常态的图 → 裁图标进 `image/密盟兑换/` → 在 `密盟兑换.json` 里复制一个物资节点（`enabled: false`）→ 把节点名加进 `密盟兑换_兑换循环.next`（带 `[JumpBack]`）→ 在 `interface.json` 的 `兑换物资` 里加一个 case。**别忘了一套要在阈值 0.9 下复测**（拿真框架跑，见下）。

### 14.4 离线自测（不用开模拟器、不花功绩点）

`maa` Python 绑定可以直接对静态图跑真识别：

```python
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JTemplateMatch
tasker.post_recognition("TemplateMatch", JTemplateMatch(template=[...], threshold=[0.9], roi=[...]), img720p)
```

要点：`RecognitionDetail.best_result` **不是最高分**，而是按 `order_by`（默认 `Horizontal`）排序后取的那个；要看真分数请读 `raw_detail["all"]` 里各条，或在节点里显式写 `order_by: "Score"`。跑整条流程可用 `CustomController` 配一张固定截图当"游戏"（注意 `get_features()` 默认会让框架走 `touch_down/up` 而不是 `click`）。现成的离线环境在 `.scratch/maafw5123/`（MaaFw 5.12.3 解包 + `tools/pipeline.schema.json`，gitignored，删了可重下；昔日测试脚本样例也散在 `.scratch/` 下）。

### 14.5 未验证 / 待办

- `密盟兑换_功绩点不足`（OCR「功绩点不足」）**从未在实机见过**：功绩点够不够买满时游戏到底弹不弹框、弹在哪都未知。该节点目前只做 DoNothing 后收尾，属防御性占位。
- **没做导航**：进入兑换页仍是手动（**三档切换已自动**）。补导航时注意（2026-10-11 实测）：**采购办左侧栏可滚动、滚动位置不固定**，同一个 y 不同时刻指向不同条目（`(137,498)` 一会儿是「秘盟兑换」、滚一下就变成「兑换中心」），所以切子页必须 OCR 侧栏文字再点，不能写死坐标。路径：主菜单 → 采购办 `(1037,588)` → 侧栏「玩法兑换」→ 其子栏「秘盟兑换」→ 档位页签（这一排不随侧栏滚：y≈131，初阶 x≈432 / 中阶 x≈625 / 高阶 x≈842，任务已在用）。另注意「兑换中心」是另一个商店（追踪认证，卖狂乱精粹×6000 等、另一种货币），别和秘盟兑换搞混。
- 国际服：弹窗判据走模板所以不受语言影响，但「获得物资」「功绩点不足」两个 OCR 是中文；国际服要另建 `resource/global/pipeline/密盟兑换.json` overlay 补本地化文案。
