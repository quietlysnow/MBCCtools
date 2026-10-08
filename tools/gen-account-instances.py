#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「多账号轮换」的实例配置（方案 A：每个账号一个实例，互相接龙）。

每个实例的队列形如：
    切换账号(账号i) → 倒计时(20s) → 日常任务… → 切换实例(下一个实例)
最后一个实例的「切换实例」指回第一个，形成闭环，可以一直轮换。

用法：
    python gen-account-instances.py --config-dir "<安装目录>/config" \
        --accounts 13800000000 13800000001 13800000002

    `<安装目录>` 就是放 MFAAvalonia.exe 的目录，`config/instances` 在它下面。

说明：
    * 上面三个号码只是占位示例，请替换成你自己的账号；不要把真实手机号写进本文件或提交到仓库
    * 账号必须已经在游戏登录界面的账号列表里（本工具不会帮你去登录新账号）
    * 会先备份整个 config 目录，再改写 config/instances/*.json 与 config/config.json
    * 队列里的「切换账号」账号值建议之后在 MFA 界面里按需微调
"""

import argparse
import io
import json
import os
import shutil
import time


def load(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, obj):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def switch_item(template, account):
    return {
        "name": "切换账号",
        "entry": "切换账号",
        "default_check": True,
        "doc": template["doc"],
        "option": [{"name": "账号切换", "index": 0, "data": {"账号": account}}],
    }


def countdown(seconds):
    """切换账号后等首页渲染完，避免右侧菜单还没出来就去识别"""
    return {
        "name": "倒计时",
        "entry": "CountdownAction",
        "default_check": True,
        "description": "SpecialTask_CountdownDesc",
        "pipeline_override": {
            "CountdownAction": {
                "action": "Custom",
                "custom_action": "CountdownAction",
                "custom_action_param": {"seconds": seconds},
            }
        },
    }


def switch_instance(target):
    return {
        "name": "切换实例",
        "entry": "SwitchInstanceAction",
        "default_check": True,
        "description": "SpecialTask_SwitchInstanceDesc",
        "pipeline_override": {
            "SwitchInstanceAction": {
                "action": "Custom",
                "custom_action": "SwitchInstanceAction",
                "custom_action_param": {"target_instance": target},
            }
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config-dir", required=True, help="MFA 的 config 目录")
    ap.add_argument("--accounts", nargs="+", required=True, help="要轮换的账号（手机号），按顺序")
    ap.add_argument("--settle-seconds", type=int, default=20, help="切号后等待首页渲染的秒数")
    args = ap.parse_args()

    cfg_dir = os.path.abspath(args.config_dir)
    inst_dir = os.path.join(cfg_dir, "instances")
    default_path = os.path.join(inst_dir, "default.json")
    if not os.path.exists(default_path):
        raise SystemExit("找不到 %s，请先让 MFA 至少启动过一次" % default_path)

    accounts = args.accounts
    ids = ["default"] + ["acc%d" % (i + 1) for i in range(1, len(accounts))]
    names = ["配置 %d" % (i + 1) for i in range(len(accounts))]

    backup = os.path.join(os.path.dirname(cfg_dir), "backup",
                          "config-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copytree(cfg_dir, backup)
    print("已备份 config 到 %s" % backup)

    base = load(default_path)
    items = base["TaskItems"]
    switch_tpl = next(t for t in items if t["name"] == "切换账号")
    # 日常清单：去掉切换账号/切换实例/倒计时，并去掉「进入游戏」（切号流程已经完成重启+进游戏）
    daily = [t for t in items
             if t["name"] not in ("切换账号", "切换实例", "倒计时", "进入游戏")]

    for i, (iid, name, account) in enumerate(zip(ids, names, accounts)):
        nxt = names[(i + 1) % len(names)]
        queue = [switch_item(switch_tpl, account), countdown(args.settle_seconds)]
        queue += [json.loads(json.dumps(t)) for t in daily]
        queue.append(switch_instance(nxt))

        cfg = dict(base)
        cfg["InstanceName"] = name
        cfg["TaskItems"] = queue
        cfg["CurrentTasks"] = ["%s<|||>%s" % (t["name"], t["entry"]) for t in queue]
        # 切实例后目标实例的连接目标是空的，靠这两个开关自动重新扫描设备
        cfg["RetryOnDisconnected"] = True
        cfg["AutoDetectOnConnectionFailed"] = True
        cfg["RememberAdb"] = True
        save(os.path.join(inst_dir, iid + ".json"), cfg)
        print("[实例] %-8s %-6s 账号=%s -> %s  队列 %d 项"
              % (iid, name, account, nxt, len(queue)))

    gpath = os.path.join(cfg_dir, "config.json")
    g = load(gpath)
    g["Instances.List"] = ",".join(ids)
    g["Instances.Order"] = ",".join(ids)
    g["Instances.LastActive"] = ids[0]
    g["Instances.LastActiveName"] = names[0]
    save(gpath, g)
    print("Instances.List = %s" % g["Instances.List"])


if __name__ == "__main__":
    main()
