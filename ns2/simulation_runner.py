import os
import shlex
import shutil
import subprocess
from pathlib import Path


def _find_trace(tcl_path):
    p = Path(tcl_path)
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("set tracefile [open "):
                return p.parent / line.split('"')[1]
    except (OSError, IndexError):
        pass
    return p.parent / "out.tr"


def run_ns2(tcl_path, timeout=90):
    p = Path(tcl_path).resolve()

    if not p.is_file():
        return {
            "ok": False,
            "message": f"Tcl script not found: {p}",
            "trace_path": None,
        }

    trace = _find_trace(p)
    exe = shutil.which("ns")

    try:
        if exe:
            result = subprocess.run(
                [exe, p.name],
                cwd=str(p.parent),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        elif os.name == "nt" and shutil.which("wsl.exe"):
            wsl = shutil.which("wsl.exe")
            converted = subprocess.run(
                [wsl, "-d", "Ubuntu", "--", "wslpath", "-a", str(p.parent)],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if converted.returncode != 0:
                return {
                    "ok": False,
                    "message": "WSL path conversion failed: "
                    + (converted.stderr or converted.stdout).strip(),
                    "trace_path": None,
                }

            linux_dir = converted.stdout.strip()
            command = (
                f"cd {shlex.quote(linux_dir)} && "
                f"ns {shlex.quote(p.name)}"
            )
            result = subprocess.run(
                [wsl, "-d", "Ubuntu", "--", "bash", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            return {
                "ok": False,
                "message": "NS2 was not found on PATH and WSL2 is unavailable.",
                "trace_path": None,
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "message": f"NS2 timed out after {timeout} seconds.",
            "trace_path": None,
        }
    except OSError as exc:
        return {
            "ok": False,
            "message": f"Could not start NS2: {exc}",
            "trace_path": None,
        }

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown NS2 error").strip()
        return {
            "ok": False,
            "message": f"NS2 failed (exit {result.returncode}): {detail}",
            "trace_path": None,
        }

    if not trace.is_file():
        return {
            "ok": False,
            "message": f"NS2 ran, but trace file was not created: {trace}",
            "trace_path": None,
        }

    return {
        "ok": True,
        "message": "NS2 simulation completed successfully.",
        "trace_path": str(trace),
    }
