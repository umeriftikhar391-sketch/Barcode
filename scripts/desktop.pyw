"""Open the local app without a console; reuse an already running service."""

from pathlib import Path
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8765"


def running():
    try:
        with urllib.request.urlopen(URL + "/api/session", timeout=1) as response:
            session = json.load(response)
            return (
                isinstance(session, dict)
                and isinstance(session.get("token"), str)
                and session.get("platform") in ("nt", "posix")
            )
    except (OSError, ValueError):
        return False


def main():
    if running():
        webbrowser.open(URL)
        return
    state = Path(os.environ["LOCALAPPDATA"]) / "BarcodeStudio"
    state.mkdir(parents=True, exist_ok=True)
    log = state / "service.log"
    with log.open("ab") as output:
        subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/launch.py"),
                "--background",
            ],
            cwd=ROOT,
            stdout=output,
            stderr=output,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    for _ in range(60):
        if running():
            webbrowser.open(URL)
            return
        time.sleep(0.25)
    ctypes.windll.user32.MessageBoxW(
        None,
        "Barcode Studio could not start. Details: " + str(log),
        "Barcode Studio",
        0x10,
    )


if __name__ == "__main__":
    main()
