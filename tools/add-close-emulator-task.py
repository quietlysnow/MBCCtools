#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
在实例任务队列末尾追加「收工」特殊任务（幂等，可撤销）。

它做什么
--------
在队列**最后一项**跑一条命令，顺序做两件事：

    1) ldconsole.exe quit --index N            —— 关掉模拟器（与 MFA 自己关模拟器同一条命令）
    2) 等几秒后 taskkill /IM MFAAvalonia.exe /F —— 关掉 MFAAvalonia 本体（--emulator-only 可关掉这步）

**默认不弹黑框**：MFA 调外部程序时写死 `UseShellExecute = true`，直接跑 cmd.exe 一定会有控制台窗口。
所以默认改成 `wscript.exe //B //Nologo <本目录>\close-sim-and-mfa.vbs`——
wscript 是 GUI 子系统程序、根本不创建控制台，VBS 里用
`WScript.Shell.Run(cmd, 0, True)`（窗口样式 0 = 隐藏）执行上面两条命令。
想回到会弹框的 cmd 方式：`--window cmd`。

为什么必须合成一条命令（2026-10-01 实测教训）
--------------------------------------------
关模拟器会让 MFAAvalonia 断开控制器并销毁 tasker。此后**队列里再放任何任务**，
MaaFramework 都直接报 `[ERR][Tasker.cpp] Tasker not inited`，任务立刻失败
（UI 日志：`任务失败：结束进程`；框架日志：`Tasker not inited`）。
所以「关模拟器」和「结束进程」写成两个任务项时，第二个必然失败、整轮队列被判 FAILED。
本脚本把两件事塞进同一个 cmd 进程，避开这个坑。

为什么用特殊任务而不是「任务完成后」开关
----------------------------------------
MFAAvalonia 的 AfterTask 对**单独运行**同样生效（右键任务项 -> 单独运行走的也是同一条收尾路径；
已核对 v2.16.1 源码，上游最新版同样没有区分单任务/全队列的开关）。放在队列尾部就不会影响单独运行。

效果
----
* 右键「单独运行」任意任务 -> 不触发（碰不到队尾这一项）
* 只勾一个任务点「开始任务」 -> 不触发
* 跑完整队列且真的走到最后一项 -> 关模拟器 + 关 MFAAvalonia
* 队列里勾着「切换实例」-> 不触发：SwitchInstanceAction 会停掉当前队列并把控制权交给下一个实例，
  它后面的项不会执行（MFA 既有行为）

用法
----
    python add-close-emulator-task.py --config-dir "<安装目录>/config" --check          # 预览
    python add-close-emulator-task.py --config-dir "<安装目录>/config"                  # 应用（自动备份 config/instances）
    python add-close-emulator-task.py --config-dir "<安装目录>/config" --emulator-only  # 只关模拟器，不结束 MFA
    python add-close-emulator-task.py --config-dir "<安装目录>/config" --window cmd     # 不用 VBS，直接跑 cmd（会弹黑框）
    python add-close-emulator-task.py --config-dir "<安装目录>/config" --remove         # 撤销（移除本脚本加的任务项）
    python add-close-emulator-task.py --config-dir "<安装目录>/config" --remove-named "结束进程"

    `<安装目录>` 就是放 MFAAvalonia.exe 的目录，`config/instances` 在它下面。
    模拟器控制台程序（ldconsole.exe 等）的路径默认按实例配置里的 SoftwarePath 同目录推导；
    推导不出来时用 `--console` 显式指定。

    其它开关：--instances / --index / --delay / --mfa-exe / --name / --vbs / --no-backup

隐藏窗口依赖同目录生成的 `close-sim-and-mfa.vbs`（脚本产物，机器相关，不入库；换机器重跑本脚本即可）。

实现说明
--------
配置文件的读写走 json 解析 + `json.dumps(indent=2, ensure_ascii=False)` 回写（CRLF、无 BOM、
文件末尾不加空行）—— 已验证与 MFAAvalonia 自己写出来的字节完全一致，不会产生噪声 diff。
"""

import argparse
import io
import json
import os
import shutil
import sys
import time

# 本脚本管理/清理的任务项名（历史变体都认）
TASK_NAMES = ["关闭模拟器并退出", "关闭模拟器"]
DEFAULT_NAME = "关闭模拟器并退出"
ENTRY = "CustomProgramAction"
VBS_NAME = "close-sim-and-mfa.vbs"


def load_json(path):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        return json.loads(f.read())


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2).replace("\r\n", "\n").replace("\n", "\r\n")


def save_json(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(dump_json(obj))


def make_item(name, program, arguments):
    return {
        "name": name,
        "entry": ENTRY,
        "default_check": True,
        "description": "SpecialTask_CustomProgramDesc",
        "pipeline_override": {
            ENTRY: {
                "action": "Custom",
                "custom_action": ENTRY,
                "custom_action_param": {
                    "program": program,
                    "arguments": arguments,
                    "wait_for_exit": True,
                },
            }
        },
    }


def add_item(cfg, name, program, arguments):
    items = cfg.setdefault("TaskItems", [])
    if any(i.get("name") == name for i in items):
        return "already"
    items.append(make_item(name, program, arguments))

    queue = cfg.setdefault("CurrentTasks", [])
    key = "%s<|||>%s" % (name, ENTRY)
    if key not in queue:
        queue.append(key)
    return "added"


def remove_items(cfg, names):
    """删掉名字在 names 里的任务项及其队列项，返回实际删掉的名字。"""
    removed = []
    items = cfg.get("TaskItems", [])
    keep = []
    for it in items:
        if it.get("name") in names:
            removed.append(it.get("name"))
        else:
            keep.append(it)
    cfg["TaskItems"] = keep

    queue = cfg.get("CurrentTasks", [])
    new_queue = []
    for entry in queue:
        head = entry.split("<|||>")[0]
        if head in names:
            removed.append(head)
        else:
            new_queue.append(entry)
    cfg["CurrentTasks"] = new_queue
    return sorted(set(removed))


def build_arguments(console, index, delay, mfa_exe):
    """拼出 cmd.exe /c ... 的命令行（--window cmd 时使用）。

    延时不使用 `timeout`：实测在部分宿主环境里它会以
    `ERROR: Input redirection is not supported` 立刻返回（stdin 被重定向时），
    改用 `ping -n`（每跳约 1 秒，不依赖输入输出，稳）。
    """
    quit_cmd = '"%s" quit --index %d' % (console, index) if " " in console else "%s quit --index %d" % (console, index)
    parts = [quit_cmd]
    if mfa_exe:
        if delay > 0:
            parts.append("ping -n %d 127.0.0.1 >nul" % (delay + 1))
        parts.append("taskkill /IM %s /F >nul" % mfa_exe)
    return " /c " + " & ".join(parts)


def write_vbs(vbs_path, console, index, delay, mfa_exe, dry=False):
    """生成隐藏窗口的 VBS（wscript 是 GUI 子系统程序，不会创建控制台窗口）。

    MFA 调用外部程序时写死 UseShellExecute = true，用 cmd.exe 跑必然弹黑框；
    wscript.exe + WScript.Shell.Run(..., 0, ...) 则是彻底无窗口。
    """
    lines = [
        "' 由 tools/add-close-emulator-task.py 生成，请勿手改",
        "' Generated by tools/add-close-emulator-task.py -- do not edit by hand.",
        "Option Explicit",
        "Dim sh",
        'Set sh = CreateObject("WScript.Shell")',
        'sh.Run """%s"" quit --index %d", 0, True' % (console, index),
    ]
    if mfa_exe:
        if delay > 0:
            lines.append("WScript.Sleep %d" % (delay * 1000))
        lines.append('sh.Run "taskkill /IM %s /F", 0, False' % mfa_exe)
    if not dry:
        parent = os.path.dirname(os.path.abspath(vbs_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        # 必须用 UTF-16(带 BOM)：实测 WSH 不认 UTF-8 BOM，会静默解析失败（脚本完全不执行）
        with io.open(vbs_path, "w", encoding="utf-16", newline="") as f:
            f.write("\r\n".join(lines) + "\r\n")
    return vbs_path


def resolve_cmd():
    default = r"C:\Windows\System32\cmd.exe"
    if os.path.exists(default):
        return default
    return os.environ.get("COMSPEC") or default


def resolve_wscript():
    default = r"C:\Windows\System32\wscript.exe"
    if os.path.exists(default):
        return default
    return default


def resolve_console(instance_cfg, explicit, instance_name=""):
    """模拟器控制台程序路径：优先 --console，其次按实例 SoftwarePath 同目录推导。"""
    if explicit:
        return explicit
    sw = (instance_cfg.get("SoftwarePath") or "").strip()
    if sw:
        return os.path.join(os.path.dirname(sw), "ldconsole.exe")
    return ""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--config-dir", required=True,
                    help="MFAAvalonia 的 config 目录（<安装目录>/config），里面要有 instances/*.json")
    ap.add_argument("--instances", default="", help="逗号分隔，留空=全部")
    ap.add_argument("--index", type=int, default=0, help="模拟器序号（ldconsole --index）")
    ap.add_argument("--console", default="", help="ldconsole.exe 完整路径，留空按实例 SoftwarePath 推导")
    ap.add_argument("--emulator-only", action="store_true", help="只关模拟器，不结束 MFA")
    ap.add_argument("--mfa-exe", default="MFAAvalonia.exe", help="要结束的进程名，默认 MFAAvalonia.exe")
    ap.add_argument("--delay", type=int, default=3, help="关模拟器后等几秒再结束 MFA，默认 3")
    ap.add_argument("--name", default="", help="任务项名字，默认「关闭模拟器并退出」/「关闭模拟器」")
    ap.add_argument("--window", choices=["hidden", "cmd"], default="hidden",
                    help="hidden=用 wscript 跑 VBS，全程无窗口（默认）；cmd=直接跑 cmd.exe，会弹黑框")
    ap.add_argument("--vbs", default="", help="VBS 落地路径，默认 <本脚本目录>\\%s" % VBS_NAME)
    ap.add_argument("--check", action="store_true", help="只预览不写文件")
    ap.add_argument("--remove", action="store_true", help="移除本脚本添加的任务项")
    ap.add_argument("--remove-named", default="", help="额外删除的任务项名（逗号分隔）")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    cfg_dir = os.path.abspath(args.config_dir)
    inst_dir = os.path.join(cfg_dir, "instances")
    if not os.path.isdir(inst_dir):
        raise SystemExit("找不到实例目录：%s" % inst_dir)

    if args.instances.strip():
        names = [n.strip() for n in args.instances.split(",") if n.strip()]
        files = [os.path.join(inst_dir, n + ".json") for n in names]
    else:
        files = sorted(os.path.join(inst_dir, f) for f in os.listdir(inst_dir) if f.endswith(".json"))

    missing = [f for f in files if not os.path.exists(f)]
    if missing:
        raise SystemExit("实例文件不存在：%s" % ", ".join(missing))

    if not args.check and not args.no_backup:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(os.path.dirname(cfg_dir), "backup", "instances-" + stamp)
        os.makedirs(backup, exist_ok=True)
        for f in files:
            shutil.copy2(f, os.path.join(backup, os.path.basename(f)))
        print("已备份 %d 个实例文件到 %s" % (len(files), backup))

    extra = [n.strip() for n in args.remove_named.split(",") if n.strip()]
    task_name = args.name or ("关闭模拟器" if args.emulator_only else DEFAULT_NAME)
    vbs_path = args.vbs or os.path.join(os.path.dirname(os.path.abspath(__file__)), VBS_NAME)
    mfa_exe = "" if args.emulator_only else args.mfa_exe

    changed = 0
    for f in files:
        cfg = load_json(f)
        console = resolve_console(cfg, args.console)
        actions = []
        dirty = False

        if args.remove:
            removed = remove_items(cfg, TASK_NAMES)
            if removed:
                dirty = True
                actions.append("移除 %s" % ",".join(removed))
            else:
                actions.append("无可移除")
        else:
            if not console:
                raise SystemExit(
                    "%s 里没有 SoftwarePath（或为空），推导不出模拟器控制台路径。\n"
                    "两种解法：① 在 MFAAvalonia 的「启动设置」里填好模拟器程序路径（SoftwarePath）；"
                    "② 用 --console 显式指定控制台程序，例如 --console \"C:/LDPlayer9/ldconsole.exe\"。"
                    % os.path.basename(f))
            if extra:
                removed = remove_items(cfg, extra)
                if removed:
                    dirty = True
                    actions.append("删除 %s" % ",".join(removed))
            if args.window == "hidden":
                write_vbs(vbs_path, console, args.index, args.delay, mfa_exe, dry=args.check)
                program = resolve_wscript()
                arguments = '//B //Nologo "%s"' % vbs_path
                target = "%s -> %s" % (vbs_path, arguments)
            else:
                program = resolve_cmd()
                arguments = build_arguments(console, args.index, args.delay, mfa_exe)
                target = arguments
            result = add_item(cfg, task_name, program, arguments)
            if result == "added":
                dirty = True
                actions.append("添加 %s -> %s" % (task_name, target))
            else:
                actions.append("已存在(跳过)")

        if dirty:
            changed += 1
            if not args.check:
                save_json(f, cfg)

        print("[%s] %s%s" % (os.path.basename(f), "将 " if args.check else "", "；".join(actions)))

    print("")
    print("%s %d 个实例文件。" % ("预览：将修改" if args.check else "实际修改", changed))
    print("提醒：MFAAvalonia 需重启（或重载实例）后队列才会显示新任务项。")


if __name__ == "__main__":
    main()
