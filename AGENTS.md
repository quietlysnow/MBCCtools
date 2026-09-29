# MBCCtools — Agent 规则

本文件是给 AI 编码助手的项目约束。规则来自**当前仓库里实际观察到的写法**，不是 MaaFramework 通用教程。
协议细节一律以本地文档副本 `docs/zh_cn/` 为准（见文末索引），本文只写「本项目怎么写」。

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
    "child_exec": "python",                 // CWD = interface.json 所在目录
    "child_args": ["./agent/main.py"],
    "identifier": "MBCCtools"               // 可选；填了就用它建通信套接字
}
```

- UI 会向子进程注入 `PI_*` 环境变量（`PI_CLIENT_NAME`、`PI_CONTROLLER`、`PI_RESOURCE` 等，全表见 `3.3`）。**多服项目必须读 `PI_RESOURCE`** 来判断当前选中的是官服/B服/国际服，再加载对应资源。
- 多个 Agent 可写成数组形式。

### 2.4 当前落地状态

已接（2026-09-19 第一步）。连通性已实测：MFAAvalonia 会按 `agent` 段自动执行 `python "G:\MBCCtools\agent\main.py" MBCCtools_default`，AgentServer 起来并注册了 `CloseButton`，握手响应里 `recognitions:["CloseButton"]` —— 除协议版本外全链路通，协议问题见 §7.3。**识别逻辑本身（找关闭按钮并点击）仍未实机验证。**

- `agent/main.py`：注册识别器 `CloseButton`，用 `context.run_recognition_direct` 调框架自带的 `TemplateMatch` 逐个模板匹配，再按「离 `corner` 指定的屏幕角最近」择优 —— 这一步是 JSON 表达不了的（`order_by` 只有 Horizontal/Vertical/Score/Area/Length/Random，不能按到某个角的距离排序）。未命中返回 `None`，不抛异常。
- `interface.json` 顶层新增 `agent` 段（`child_exec: "python"` / `child_args: ["./agent/main.py"]` / `identifier: "MBCCtools"`）。
- `resource/base/pipeline/项目名.json` 新增公共节点 `通用关闭弹窗`（`Custom` + `Click`，`target` 默认 true 即命中框本身）。
- `resource/base/pipeline/启动.json`：`登录前处理` 与 `登录后处理` 的 `next` **末尾**各挂了一个 `[JumpBack]通用关闭弹窗`。

两点设计取舍，改的时候别破坏：

- **只放在原有专用处理器之后**。`关闭公告`/`一般弹窗` 等带写死坐标的节点全部保留，所以 Agent 没起来时行为和改动前一致（退化成本不受影响），Agent 起来时它只兜住"没枚举到的新弹窗"。等实机确认 `CloseButton` 稳定后，才谈得上删掉那些写死坐标。
- **不要把它插到 `首页` 之前**。那样任何带"关闭"图样的正常页面都会被提前点掉，属于新增误操作风险。
- `bilibili/`、`global/` 的 `启动.json` **还没接**，节点因定义在 `base` 而对三服可见但未被引用。
- **它的适用面比预想的窄**（2026-09-19 实机结论）：启动期最常见的两类弹窗 —— 空投「点击领取今日补给」和「情绪检测」台词窗 —— **画面上根本没有 X 按钮**，`CloseButton` 对它们必然未命中（未命中是正确返回，不是故障）。这类"点某句文案"的弹窗一律用 `OCR + Click` 解决，已落地的例子见 `base/pipeline/启动.json` 的 `今日补给`。别再把"找关闭按钮"当成启动流程的万能兜底。

未做/待办：

- **AgentServer 的 Python 绑定版本必须与 AgentClient 的协议代一致**。实测：MFAAvalonia 实际加载的是 `runtimes/win-x64/native/MaaFramework.dll` = **v5.12.3**（协议 protocol=7），而不是根目录那份 v5.13.0。装 5.13.1 会被拒：`Protocol version mismatch client: v5.12.3 kProtocolVersion=7 server: v5.13.1 protocol=8` + `Please update AgentClient`。当前已钉 `pip install MaaFw==5.12.3`（其自带的 `MaaAgentServer.dll` 同为 v5.12.3，与客户端逐版本一致）。
- 换 MaaFramework / MFAAvalonia 版本时，要同步重选 `MaaFw` 版本，否则 Custom 节点直接连不上。
- 自定义代码放 `agent/`，**不要**放进 `resource/`（会被当资源包扫描）。

## 3. 目录与 bundle 结构

```
interface.json                 # ProjectInterface V2 清单，见 §6
resource/
├── default_pipeline.json      # ⚠ 见 §7 已知问题
├── mfa_layout.json            # MFAAvalonia 界面布局，与算法无关
├── base/                      # 官服 bundle（主资源包）
│   ├── image/                 # 模板图片（含 材料/ 子目录）
│   ├── model/ocr/             # det.onnx / rec.onnx / keys.txt（PP-OCRv5_mobile）
│   └── pipeline/              # 19 个 JSON
├── bilibili/                  # B服 overlay：仅 pipeline/，3 个 JSON
└── global/                    # 国际服 overlay：仅 pipeline/，20 个 JSON
```

- bundle 根必须同时具备 `pipeline/`、`image/`、`model/ocr/` 才能被完整加载；框架**只**在 bundle 根目录下查找 `default_pipeline.json`（见 §7）。
- MaaFW 递归读取 `pipeline/` 下所有 `.json`；**路径中任一段以 `.` 开头的文件/目录会被跳过**（`_` 前缀不跳过）；JSON 顶层 key 以 `$` 开头的不解析。
- 仓库里原有一批编辑器画布元数据（`$__mpe_config_*` / `$__mpe_external_*` 根键、节点内 `$__mpe_code`，共 46 处，仅存在于 `base` 的 `启动.json` 与 `刷取材料.json`），**已于 2026-09-19 全部清除**。现在 `pipeline/` 里不应再出现任何 `$` 开头的键；若某工具回写后又把它们带回来，删掉即可，不影响运行。
- `bilibili/`、`global/` 没有自己的 `image/`，但 `template` 仍能引用 `base/image/` 下的图：**模板图管理器跨 bundle 累积**，因此差异包只放需要不同的 pipeline。

## 4. Pipeline 节点写法（核心）

### 4.1 统一使用 Pipeline v2（对象式）

**全仓 359 个节点已于 2026-09-19 全部转为 v2 形式**（120 个原 v1 扁平节点被机械转换，逐节点通过「槽位归一化后键值完全相等」校验）。新节点一律照 v2 写：

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

- `recognition`：`OCR`、`TemplateMatch`、`ColorMatch`、`DirectHit`
- `action`：`Click`、`Swipe`、`DoNothing`、`StartApp`、`StopTask`、`LongPress`
- 以上为现状。方案二（§2）另外**允许** `recognition: Custom` / `action: Custom`，但必须配套 AgentServer 实现与 `interface.json` 的 `agent` 段，且引入前先与用户对齐理由。
- 其余仍未使用：`FeatureMatch`、`NeuralNetworkClassify`、`NeuralNetworkDetect`、`And`/`Or`、`Command`、`Shell`、`Scroll`、`InputText`、`MultiSwipe`。需要引入前先与用户确认。
- 不使用 `model` 字段（OCR 走 `base/model/ocr` 根目录默认模型）。
- `is_sub` / `interrupt` 在 v5.1 已废弃，**禁止使用**，用 `[JumpBack]` 替代。

### 4.3 字段使用约定（按仓库出现频次）

高频（统计范围 `resource/base/pipeline/`）：`next`(128) `roi`(99) `expected`(84) `post_wait_freezes`(70) `focus`(138) `target`(51) `timeout`(41) `post_delay`(41) `template`(38) `on_error`(21) `begin`/`end`(13) `max_hit`(5) `order_by`/`index`(3) `threshold`(2) `pre_delay`(2) `package`(1)

- **`focus` 约定（2026-09-19 批量补齐后）**：凡是**真的执行动作**的节点（`Click`/`Swipe`/`LongPress`/`StartApp`）都带一条进度通知，写在 `action` 成员之后，只用 `Node.Action.Succeeded` 这一个键：

  ```jsonc
  "focus": {
      "Node.Action.Succeeded": "进入浊暗之阱"
  }
  ```

  全仓 352 个节点中 **257 个**带 focus（`Node.Action.Succeeded` 242、`Node.Recognition.Succeeded` 13、`Node.Recognition.Starting` 2）。**不加** focus 的两类：① 纯分发节点、只有 `DoNothing`/`StopTask` 的节点（没有动作结果可上报）；② 纯手势与通用 UI 辅助节点（`左滑`/`右滑`/`上滑`/`第一次滑动`/`点击`/`侧边点击`/`返回按钮`/`点击关闭按钮`/`关闭界面` 等），它们在循环里被反复触发、名字又不含业务对象，只会刷日志。
- 文案默认取节点名本身，仅以下几类按规则改写：`X入口` → `进入X`；`X_异常处理` → `处理X异常`；`X_SecondClick` → `X二次点击`；`X_副本N` → 去掉 `_副本N` 后缀；`StartApp` 节点 → `启动游戏`。新增节点时照这套走，别写英文或留空。

- **延迟策略**：优先 `post_wait_freezes`（等画面静止），其次才用 `post_delay`。官方建议"增加中间节点，少用 delay"（`3.1` §等待画面静止）。
- **`timeout` / `on_error` 归属上一节点**：想控制"等某个节点出现多久"，改它**父节点**的 `timeout`；想超时后兜底，改父节点 `on_error`。这是本项目最常踩的坑，务必参考 `3.1` §属性字段的原文提示。
- **阈值靠兜底**：pipeline 里几乎不写 `threshold`（仅 2 处），默认值意图由 `default_pipeline.json` 提供（但该文件当前不生效，见 §7）——改阈值时先确认它写在节点上。
- 每个 task 的入口节点（`interface.json` 里的 `entry`）必须真实存在于合并后的 pipeline 中。MaaFW **按键名查找**，与键序无关；仓库惯例是入口节点写在文件开头、新增节点追加在末尾。

### 4.4 坐标

- 一律 4 元绝对像素 `[x, y, w, h]`，基准 **1280×720**（`README.md:45-48`，MuMu5 2560×1440 开发）。
- 纯点击点写成 `[x, y, 1, 1]`。
- `roi` = 识别范围，`box` = 命中的位置，`target` = 动作落点；`roi_offset` / `target_offset` 在其上叠加（`3.1` §roi/box/target 区分）。
- `target` / `begin` / `end` 可用 `true`（用本节点 `box`）、节点名字符串、`[Anchor]名`、`[x, y]` 或 `[x,y,w,h]`。
- 不要在节点里写 `"coordinateMode"`、`"pipeline_version"` 之类自造字段：MaaFW 只按协议字段名取值，多余 key 一律静默忽略、不报错，所以写错了只会表现为"节点行为莫名其妙"。

### 4.5 流程控制惯例

- 入口节点常写成只做分发的纯 `next` 节点（`派遣.json:2-11`、`体力.json:2-12`）。
- **弹窗/异常恢复用 `[JumpBack]`**（三个 bundle 合计 280 处，是唯一用到的节点属性），挂在父节点 `next`/`on_error` 上，处理完自动回到父节点重新识别：`"[JumpBack]关闭界面"`。
- `next` 数组**顺序即优先级**：命中第一个就中断后续。把专有的、易误判的分支放前面，兜底分支放最后。
- 流程终止条件只有三种（`3.1` §终止条件）：`next` 为空、`next` 未命中且超时、外部 `StopTask`。所以链尾必须以 `DoNothing` 或明确终点收尾，否则会靠超时结束。

### 4.6 图片引用

- **`template` 相对 `image/` 根目录解析**，可写裸文件名，也可写带子目录的相对路径（如 `"材料/坚韧.png"`），还可整目录（递归加载其中所有图片）。
- 本项目现状：26 个 `template` 引用全部是裸文件名，0 处带路径前缀；`resource/base/image/材料/` 下 24 张图当前**只被 `interface.json` 的 `icon` 使用**，pipeline 未引用。要引用它们就写 `材料/xxx.png` —— 带子目录的相对路径是协议支持的写法，M9A 里 `Psychube/xxx.png` 就是这么写的（只借它的写法，图片素材不通用）。
- 图片必须是**无损原图缩放到 720p 后裁剪**（`1.1` §图像素材）。用 VSCode maa-support / MFA 工具箱 / ImageCropper 截取，不要手工缩放压缩过的截图。

### 4.7 命名与风格

- **节点名和文件名全部用中文**（`密盟`、`浊暗之阱`、`扫荡完成`、`职业选择`），不用驼峰/下划线英文。
- 变体后缀惯例：`_SecondClick`、`_异常处理`、`回主页`、数字后缀（`首页检查2`、`危机管理2`）、`_副本4`（历史遗留，勿模仿新增）。
- **通用/共享节点集中放在 `resource/base/pipeline/项目名.json`**（`主菜单`、`返回按钮`、`点击关闭按钮`、`左滑/右滑/上滑`、`扫荡完成`、`扫荡调令不足`、`难度选择`、`副本未开放` 等）。新增跨任务复用的节点放这里，不要在各业务文件里复制。文件名"项目名"是脚手架遗留，含义即"公共节点池"。
- 占位待办用空对象节点：`"TODO设置自动战斗": {}`（`破碎防线.json:61`）。
- **pipeline JSON 一律不写注释**（`//` 与 `_comment` 都不要）：全仓 42 个 pipeline 文件严格无注释，可直接用 `json.loads` 校验；只有 `resource/default_pipeline.json` 是 JSONC 允许注释。中文 key 直写，不做 `\uXXXX` 转义。
- **格式已于 2026-09-19 全量归一化**（30 个文件，逐文件通过「解析后对象与改前完全相等」校验）：`resource/**/*.json` + `interface.json` 统一为 **4 空格缩进、LF、UTF-8 无 BOM、无行尾空格、文件末尾单个换行、`"key": value` 冒号后一个空格**。写新代码就照这套。
- **坐标数组允许单行紧凑写法**（`"target": [185,330,1,1]`），这是本项目既有习惯且更省行数；不要为了"美观"把它拆成多行，也不要改动任何已有的换行位置 —— 归一化只动了行首缩进和单位宽度，没有重排换行。
- **禁止**再对整个文件做 reformat / 重新 `json.dump`（会把紧凑数组全部炸开成多行，产生上百行无意义 diff）。只改你真正要改的那几行。

## 5. 多服差异（overlay 规则）

`interface.json` 的 `resource` 决定加载顺序，**后加载的同名 task 与先加载的按顶层 key 合并覆盖**（列表整体替换、不逐项合并；`3.3` §资源覆盖）：

- 官服 `[base]` / B服 `[base, bilibili]` / 国际服 `[base, global]`，路径统一写 `{PROJECT_DIR}/resource/...`。
- 因此差异包里**只写需要改的节点**，未出现的节点继续由 `base` 提供。示例：
  - `package`：base `com.zy.wqmt.cn` / bilibili `com.zy.wqmt.bilibili` / global `com.zy.wqmt.global`（各 `启动.json` 的 `StartApp`）。
  - `友情点.json`：base 用 `OCR "领取"`，bilibili 同名节点改为 `TemplateMatch "一键领取.png"`。
  - `global/pipeline/密盟.json`、`浊暗之阱.json` 故意**删掉入口节点**（沿用 base 的），并新增 base 没有的 `专案密令.json`、`时尚巡游.json`。
- 改 `base` 里的共享节点会同时影响三个服 —— 只该服需要的改动，一律放进 `bilibili/` 或 `global/`。

## 6. `interface.json` 规则

- 结构（实测字段清单）：`name/title/icon/version/mirrorchyan_rid/mirrorchyan_multiplatform/url/controller/resource/task/option/github`。
- 目前没有 `agent`、`custom`、`account`、`preset`；`controller` 只有一个 Adb（`"安卓端"`）。不要凭空添加 `custom`/`account`/`preset`；**方案二落地时按 §2.3 新增 `agent` 段**，这是唯一预期内的顶层字段扩展。
- 13 个 `task`，每项 `{name, entry, option?, doc?}`；`entry` 必须能在（合并后的）pipeline 中找到顶层节点。
- 参数化用 `option.<组名>.cases[]`，`case` 通过 `pipeline_override` 覆盖同名节点的 `next` / `expected` / `on_error` 实现分支，例如：
  - `"每日体力用途": { "next": "狄斯币" }`
  - `"派遣区域选择": { "expected": "..." }`、`"职业选择": { "expected": "坚韧" }`
- `case.icon` 写 `image/材料/xxx.png`（相对所选资源目录），而顶层 `icon` 写 `resource/base/image/logo.jpg`（相对项目根）——两种基准并存，新增时照抄同类字段的写法，不要"顺手统一"。
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

`timeout` 是**节点级**字段，`DoNothing`/`Click` 没有这个动作参数。曾有 24 个节点写成 `"action": { "type": "DoNothing", "param": { "timeout": N } }`，MaaFW 按键名取值 → **这个 N 从来没起过作用**，节点实际一直用框架默认 20000ms。

已处理：三个 `启动.json` 的 **16 处**已于 2026-09-19 搬到节点级（`base` 6、`bilibili` 4、`global` 6），逐文件通过「除该项外节点完全相等」校验。依据是实机日志：`首页` 想等 3 秒却实等 20 秒，弹窗轮询每轮白等约 17 秒。

**仍未处理**：`resource/global/pipeline/采购办.json` 的 8 处（`采购办网络恢复_*` 5000 共 7 处、`采购办滑动前等待` 2000）+ 2 处节点级与 param 里各有一个 `timeout`（`确认养成补给选中`、`确认免费礼包详情`，param 里那个 500 是废值）。

约束：
- 这 16 处属于**行为变更**（20000 → 3000/5000/15000/30000，超时路径会更早触发），**必须实机回归**；回退用 `G:/MBCCtools_backup_20260919/pre_step2/` 里的三个 `启动.json`。
- 搬之前先确认该节点没有同时存在节点级 `timeout`；若两边都有，param 里那个是废值，直接删，别覆盖。
- 新增节点时 `timeout` 一律写在**节点级**，不要再塞进 `action.param`（历史遗留写法，`采购办.json` 里还残留若干处，别照着抄）。

### 7.3 有两份 MaaFramework.dll，权威版本是 `runtimes/` 那份

MFAAvalonia 是 .NET 程序，按原生依赖解析规则加载的是 **`runtimes/win-x64/native/MaaFramework.dll`**；根目录那份 `MaaFramework.dll` 是给 `MaaPiCli.exe` 用的副本。**两者版本可以不一样**（实测：`runtimes/` 全部 `Maa*.dll` 为 v5.12.3，根目录那份曾是 v5.13.0）。

- 想知道"本项目运行时到底是哪个版本"，读 `runtimes/win-x64/native/MaaFramework.dll` 的版本串，或直接看 `debug/maafw.log` 里 `AgentClient::connect` 打出的 client 版本，**不要**只看根目录 dll。
- 这条直接决定 Custom 能不能用：AgentServer（Python 绑定）与 AgentClient（MFA 加载的那份）协议必须同代，5.12.x=protocol 7、5.13.x=protocol 8，跨代直接拒连（日志 `Protocol version mismatch` + `Please update AgentClient`，随后 MFA 还会抛一个自己侧的 `NullReferenceException`，那句 `Agent 'python' failed to start` 是它的连锁反应，不是真的启动命令失败）。
- 用 `MaaPiCli.exe` 调试时它是另一套版本，行为可能与 MFA 不一致 —— 出问题时先确认是谁在跑。

## 8. 修改后自检

没有本地单测，也没有 CI（且**没有 git 兜底**，动手前先自查、必要时自行复制一份备份）。可行的最小验证：

0. 2026-09-19 那次全量格式归一化前的原始副本备份在 `G:/MBCCtools_backup_20260919/`（项目外，119 个文件校验一致）。确认无误后可自行删除。
1. **语义等价校验**（改格式/重构时的硬标准）：逐个文件 `json.loads(改前) == json.loads(改后)`，不等就回退。
2. JSON 语法必须合法。pipeline 文件不允许注释，可直接校验：
   `python -c "import json,pathlib;[json.loads(p.read_text(encoding='utf-8')) for b in ('base','bilibili','global') for p in pathlib.Path('resource',b,'pipeline').rglob('*.json')]"`
   （`resource/default_pipeline.json` 是 JSONC，不能用这条校验。）
3. 引用完整性：新增/改动的 `next` / `on_error` / `target` / `template` 字符串必须指向真实存在的节点名，或 `image/` 下真实存在的相对路径。
4. `interface.json` 每个 `task.entry`、每个 `pipeline_override` 的 key，都能在（对应服的）合并后 pipeline 中找到节点。
5. 坐标不得超出 1280×720 基准（`roi`/`target`/`begin`/`end` 的 `x+w`、`y+h`）。
6. 实机验证由用户完成：需要 Adb 连接的模拟器（1280×720）+ `MaaPiCli.exe` 或 MFAAvalonia。无法实机验证时，**明确说"未验证"**，不要声称功能正确。

推荐工具（写进你的判断依据，不强制）：VSCode 插件 `nekosu.maa-support`（跳转/引用/按 MaaPiCli 运行/截图裁剪）、JSON Schema `tools/pipeline.schema.json`。

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
- 两边靠**文件契约**连接：本仓库往 `record/` 写（`抽卡记录.jsonl`、`活动.json`），fork 的页面只读文件、不联网。这样抓取/解析规则变了只需更新本仓库，用户不用重下 GUI。
- 想"不动 GUI 就发布内容"时用 `resource/Announcement/*.md`：MFAAvalonia 原生展示公告。
- fork 侧的约定（页面注册点、构建部署、截图核对）见 `G:/MFAAvalonia工作区/AGENTS.md`。
