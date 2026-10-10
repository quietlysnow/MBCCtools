"""给发布包准备 agent 子进程要用的便携解释器（落到 install/agent/python/）。

版式照 M9A（MAA1999/M9A 的 tools/sync-runtime.mjs）：包内自带解释器，用户机器上
有没有 python 都不影响 agent 启动。

- Windows：官方 embed zip（python.org）+ 补 python*._pth；
- macOS：python-build-standalone 的 install_only_stripped（按资产 sha256 校验）；
- 依赖：用宿主 pip `--target` 装进包里那份解释器的 site-packages。

宿主平台必须等于目标平台：pip 只按 --platform 解析 wheel、不执行目标解释器，跨平台
构建会把包装坏，所以这里直接报错（M9A 同样如此），CI 按平台选 runner。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as host_platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

EMBED_VERSION = "3.13.16"  # Windows embed zip；python.org/ftp 实测 amd64、arm64 都在
STANDALONE_MINOR = "3.13"  # macOS 取 python-build-standalone 3.13 线的最新补丁
STANDALONE_REPO = "astral-sh/python-build-standalone"
STANDALONE_TRIPLES = {
    "macos-x64": "x86_64-apple-darwin",
    "macos-arm64": "aarch64-apple-darwin",
}
# pip --platform 取的是 wheel 文件名里的平台标签
WHEEL_PLATFORMS = {
    "win-x64": "win_amd64",
    "win-arm64": "win_arm64",
    "macos-x64": "macosx_13_0_x86_64",
    "macos-arm64": "macosx_13_0_arm64",
}

_ARCH_ALIASES = {
    "x64": "x64", "x86_64": "x64", "x86-64": "x64", "amd64": "x64",
    "arm64": "arm64", "aarch64": "arm64",
}
_OS_ALIASES = {
    "win": "win", "windows": "win",
    "macos": "macos", "mac": "macos", "osx": "macos", "darwin": "macos",
}


def normalize_platform(text: str) -> str | None:
    """把各种写法归一成 win-x64 / win-arm64 / macos-x64 / macos-arm64。"""
    parts = text.strip().lower().replace("_", "-").split("-")
    if len(parts) < 2:
        return None
    os_name = _OS_ALIASES.get(parts[0])
    arch = next((_ARCH_ALIASES[p] for p in reversed(parts) if p in _ARCH_ALIASES), None)
    if os_name is None or arch is None:
        return None
    platform_name = f"{os_name}-{arch}"
    return platform_name if platform_name in WHEEL_PLATFORMS else None


def detect_host_platform() -> str:
    system = host_platform.system()
    machine = host_platform.machine()
    os_name = {"Windows": "win", "Darwin": "macos"}.get(system)
    arch = _ARCH_ALIASES.get(machine.lower())
    if os_name is None or arch is None:
        raise SystemExit(f"不认识的宿主平台：{system} {machine}")
    return f"{os_name}-{arch}"


def resolve_platform() -> str:
    """目标平台：显式 env AGENT_RUNTIME_PLATFORM 优先，CI 里必须显式给。"""
    explicit = os.environ.get("AGENT_RUNTIME_PLATFORM", "").strip()
    if explicit:
        platform_name = normalize_platform(explicit)
        if platform_name is None:
            raise SystemExit(f"AGENT_RUNTIME_PLATFORM 不认识：{explicit}")
        return platform_name
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise SystemExit(
            "CI 里必须显式指定目标平台：由 workflow 的 matrix 传 AGENT_RUNTIME_PLATFORM"
            "（win-x64 / win-arm64 / macos-x64 / macos-arm64）"
        )
    return detect_host_platform()


def interpreter_relpath(platform_name: str) -> str:
    """包内解释器相对 agent/python/ 的路径，install.py 的 child_exec 也用它。"""
    return "python.exe" if platform_name.startswith("win-") else "bin/python3"


def site_packages_path(dest: Path, platform_name: str) -> Path:
    if platform_name.startswith("win-"):
        return dest / "Lib" / "site-packages"
    return dest / "lib" / f"python{STANDALONE_MINOR}" / "site-packages"


def preflight_platform(platform_name: str) -> None:
    """宿主与目标必须一致 —— 跨平台构建只会做出装错 wheel 的包，宁可构建失败。"""
    host = detect_host_platform()
    if host != platform_name:
        raise SystemExit(
            f"目标平台 {platform_name} 与宿主 {host} 不一致：本步骤不执行目标解释器，"
            "跨平台构建会把 wheel 装错。CI 请按平台选 runner（见 install.yml）。"
        )


def prepare_runtime(dest: Path, platform_name: str, requirements: Path) -> None:
    """把解释器与依赖装进 dest（会被清空重建）。"""
    if platform_name not in WHEEL_PLATFORMS:
        raise SystemExit(f"不支持的平台：{platform_name}")
    if not requirements.exists():
        raise SystemExit(f"缺少依赖清单：{requirements}")
    preflight_platform(platform_name)

    dest = Path(dest)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)

    print(f"准备 agent 解释器：{platform_name} -> {dest}")
    if platform_name.startswith("win-"):
        _prepare_windows(dest, platform_name)
    else:
        _prepare_macos(dest, platform_name)
    _install_requirements(dest, platform_name, requirements)

    executable = dest / interpreter_relpath(platform_name)
    if not executable.exists():
        raise SystemExit(f"解释器没落地：{executable}")
    print(f"agent 解释器就绪：{executable}")


def _cache_dir() -> Path:
    return Path(__file__).parent / "deps" / ".agent-runtime-cache"


def _download(url: str, filename: str, sha256: str | None = None) -> Path:
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / filename
    if target.exists():
        if sha256 is None or _sha256_file(target) == sha256:
            print(f"缓存命中：{target.name}")
            return target
        target.unlink()
    print(f"下载 {filename} …")
    request = urllib.request.Request(url, headers={"User-Agent": "MBCCtools-packaging"})
    with urllib.request.urlopen(request, timeout=600) as response, open(target, "wb") as out:
        shutil.copyfileobj(response, out)
    if sha256 is not None and _sha256_file(target) != sha256:
        target.unlink()
        raise SystemExit(f"{filename} 的 sha256 校验失败")
    return target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _github_json(url: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "MBCCtools-packaging"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return json.load(response)


def _prepare_windows(dest: Path, platform_name: str) -> None:
    arch = "arm64" if platform_name.endswith("arm64") else "amd64"
    filename = f"python-{EMBED_VERSION}-embed-{arch}.zip"
    archive = _download(f"https://www.python.org/ftp/python/{EMBED_VERSION}/{filename}", filename)
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(dest)
    _patch_python_pth(dest)


def _patch_python_pth(dest: Path) -> None:
    """embed 版的 python*._pth 不含 site-packages 且注释掉了 import site，补上。"""
    candidates = [p for p in dest.iterdir() if p.name.lower().endswith("._pth")]
    if not candidates:
        raise SystemExit(f"embed 运行时里没找到 python*._pth：{dest}")
    pth = candidates[0]
    lines = [line for line in pth.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")]
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines = ["import site" if line.strip() in ("#import site", "# import site") else line for line in lines]
    if not any(line.strip() == "import site" for line in lines):
        lines.append("import site")
    for item in (".", "Lib", "Lib\\site-packages", "DLLs"):
        if not any(line.strip() == item for line in lines):
            lines.append(item)
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已补 {pth.name}")


def _prepare_macos(dest: Path, platform_name: str) -> None:
    triple = STANDALONE_TRIPLES[platform_name]
    release = _github_json(f"https://api.github.com/repos/{STANDALONE_REPO}/releases/latest")
    tag = release.get("tag_name", "")
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        prefix = f"cpython-{STANDALONE_MINOR}."
        suffix = f"+{tag}-{triple}-install_only_stripped.tar.gz"
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        digest = asset.get("digest", "")
        if not digest.startswith("sha256:"):
            raise SystemExit(f"{name} 没带 sha256 校验值")
        archive = _download(asset["browser_download_url"], name, digest.removeprefix("sha256:"))
        _extract_tar_strip_root(archive, dest)
        break
    else:
        raise SystemExit(f"python-build-standalone 的 {tag} 里没有 {platform_name} 的 {STANDALONE_MINOR} 资产")

    executable = dest / interpreter_relpath(platform_name)
    if not executable.exists():
        # 解压丢符号链接时（跨文件系统/权限），用带版本号的真身补上
        real = next(dest.glob(f"bin/python{STANDALONE_MINOR}"), None)
        if real is None:
            raise SystemExit(f"解压后没找到解释器：{dest}/bin/")
        shutil.copy2(real, executable)
    executable.chmod(0o755)


def _extract_tar_strip_root(archive: Path, dest: Path) -> None:
    """python-build-standalone 的顶层是单个 python/ 目录，取出来铺到 dest。"""
    with tempfile.TemporaryDirectory() as staging:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(staging)
        roots = [entry for entry in Path(staging).iterdir() if entry.is_dir()]
        if len(roots) != 1:
            raise SystemExit(f"{archive.name} 顶层不是单目录：{[r.name for r in roots]}")
        for entry in roots[0].iterdir():
            shutil.move(str(entry), str(dest / entry.name))


def _install_requirements(dest: Path, platform_name: str, requirements: Path) -> None:
    site_packages = site_packages_path(dest, platform_name)
    site_packages.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "pip", "install",
        "--target", str(site_packages),
        "--upgrade",
        # 不生成宿主版本的 .pyc（宿主 python 未必是 3.13）
        "--no-compile",
        "--only-binary", ":all:",
        "--implementation", "cp",
        "--python-version", STANDALONE_MINOR,
        "--abi", f"cp{STANDALONE_MINOR.replace('.', '')}",
        "--platform", WHEEL_PLATFORMS[platform_name],
        "-r", str(requirements),
    ]
    print("安装依赖：" + " ".join(command[3:]))
    subprocess.run(command, check=True)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="准备发布包内的 agent 解释器")
    parser.add_argument("--dest", default="install/agent/python", help="解释器落盘位置")
    parser.add_argument("--platform", default=None, help="目标平台，默认读 AGENT_RUNTIME_PLATFORM 或宿主")
    parser.add_argument("--requirements", default="requirements.txt", help="依赖清单")
    args = parser.parse_args()

    platform_name = normalize_platform(args.platform) if args.platform else resolve_platform()
    if platform_name is None:
        raise SystemExit(f"不认识的目标平台：{args.platform}")
    prepare_runtime(Path(args.dest), platform_name, Path(args.requirements))
    return 0


if __name__ == "__main__":
    sys.exit(main())
