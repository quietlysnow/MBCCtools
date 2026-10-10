from pathlib import Path

import shutil
import sys
import json

from configure import configure_ocr_model
from prepare_agent_runtime import interpreter_relpath, prepare_runtime, resolve_platform, use_utf8_console


working_dir = Path(__file__).parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print("Please download the MaaFramework to \"deps\" first.")
        print("请先下载 MaaFramework 到 \"deps\"。")
        sys.exit(1)

    shutil.copytree(
        working_dir / "deps" / "bin",
        install_path,
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*",
            "*MaaThriftControlUnit*",
            "*MaaRpc*",
            "*MaaHttp*",
        ),
        dirs_exist_ok=True,
    )
    shutil.copytree(
        working_dir / "deps" / "share" / "MaaAgentBinary",
        install_path / "MaaAgentBinary",
        dirs_exist_ok=True,
    )


def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = json.load(f)

    interface["version"] = version

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )

def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

def _read_interface():
    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        return json.load(f)

def _agent_entries(interface):
    """agent 段允许对象或数组（PI 协议两种都收），统一成列表。"""
    agents = interface.get("agent")
    if isinstance(agents, dict):
        return [agents]
    if isinstance(agents, list):
        return [item for item in agents if isinstance(item, dict)]
    return []

def install_agent_runtime():
    """把解释器与依赖打进包，并把发布用 interface.json 的 child_exec 指向它。

    源码 interface.json 里 child_exec 是开发用的裸命令名 python（走宿主 PATH）；
    发布包必须指向包内解释器，否则用户机器上有没有 python 全凭运气。
    """
    platform = resolve_platform()
    relpath = interpreter_relpath(platform)
    prepare_runtime(install_path / "agent" / "python", platform, working_dir / "requirements.txt")

    interface = _read_interface()
    for agent in _agent_entries(interface):
        agent["child_exec"] = f"./agent/python/{relpath}"
    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)
    print(f"agent 运行时：{platform} -> ./agent/python/{relpath}")

def check_agent():
    """构建期守卫：声明了 agent 就必须真的带上脚本与解释器，否则别发包。"""
    agents = _agent_entries(_read_interface())
    if not agents:
        return
    missing = []
    for agent in agents:
        fields = [agent.get("child_exec"), *(agent.get("child_args") or [])]
        for value in fields:
            if isinstance(value, str) and value.startswith("./") and not (install_path / value[2:]).exists():
                missing.append(value)
    if missing:
        print(f"interface.json 声明了 agent，但包内缺文件：{', '.join(missing)}")
        sys.exit(1)


if __name__ == "__main__":
    use_utf8_console()
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    install_agent_runtime()
    check_agent()

    print(f"Install to {install_path} successfully.")