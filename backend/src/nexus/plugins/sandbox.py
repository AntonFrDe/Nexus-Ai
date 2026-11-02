import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
RUNNER = Path(__file__).with_name("runner.py").resolve()
MAX_RESPONSE_BYTES = 5_000_000
DEFAULT_TIMEOUT = 30


class PluginFailure(Exception):
    pass


def sandbox_available() -> bool:
    return shutil.which(SANDBOX_EXEC) is not None


def python_paths() -> tuple[Path, Path]:
    return Path(os.path.realpath(sys.executable)), Path(sys.base_prefix).resolve()


def _quoted(path: Path) -> str:
    return json.dumps(str(path))


def build_profile(
    plugin_dir: Path, data_dir: Path, private_dir: Path, permissions: list[str]
) -> str:
    """Denies by area, then opens only what this plugin needs. Later rules win. Reads must be
    denied broadly: a plain subprocess could otherwise read the master key and API token."""
    python, prefix = python_paths()
    plugin, data, private = plugin_dir.resolve(), data_dir.resolve(), private_dir.resolve()
    rules = [
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        f'(allow file-write* (subpath {_quoted(data)}) (literal "/dev/null"))',
        '(deny file-read* (subpath "/Users") (subpath "/Volumes") (subpath "/private/var/root")'
        f" (subpath {_quoted(private)}))",
        f"(allow file-read* (subpath {_quoted(prefix)}) (subpath {_quoted(plugin)})"
        f" (subpath {_quoted(data)}) (literal {_quoted(RUNNER)}))",
        "(allow file-read-metadata)",
        r'(deny mach-lookup (global-name-regex "^com\\.apple\\.(secur|Security|trustd)"))',
    ]
    if "network" not in permissions:
        rules.append("(deny network*)")
    if "shell" not in permissions:
        rules += ["(deny process-exec*)", f"(allow process-exec (literal {_quoted(python)}))"]
    return "".join(rules)


def plugin_environment(permissions: list[str], data_dir: Path) -> dict[str, str]:
    """Starts empty. Only variables the user granted by name reach the plugin."""
    environment = {"HOME": str(data_dir), "TMPDIR": str(data_dir), "PATH": "/usr/bin:/bin"}
    for permission in permissions:
        if permission.startswith("env:"):
            name = permission.removeprefix("env:")
            if name in os.environ:
                environment[name] = os.environ[name]
    return environment


async def call_plugin(
    plugin_dir: Path,
    entry: str,
    data_dir: Path,
    private_dir: Path,
    permissions: list[str],
    kind: str,
    name: str,
    payload: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """One isolated call. Without a sandbox nothing runs: a bare process could read every key."""
    if not sandbox_available():
        raise PluginFailure("Plugins need the macOS sandbox, which this system does not have")
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    profile = build_profile(plugin_dir, data_dir, private_dir, permissions)
    python, _ = python_paths()
    process = await asyncio.create_subprocess_exec(
        SANDBOX_EXEC,
        "-p",
        profile,
        str(python),
        "-I",
        "-S",
        str(RUNNER),
        str(plugin_dir.resolve()),
        entry,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=data_dir,
        env=plugin_environment(permissions, data_dir),
    )
    request = json.dumps({"kind": kind, "name": name, "payload": payload}).encode() + b"\n"
    try:
        async with asyncio.timeout(timeout):
            output, _ = await process.communicate(request)
    except TimeoutError:
        raise PluginFailure(f"The plugin did not answer within {timeout} seconds") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    if len(output) > MAX_RESPONSE_BYTES:
        raise PluginFailure("The plugin returned too much data")
    try:
        reply = json.loads(output)
    except ValueError:
        raise PluginFailure("The plugin ended without a valid answer") from None
    if "error" in reply:
        raise PluginFailure(reply["error"])
    return reply["result"]
