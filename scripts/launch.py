"""Run the local service with a browser; never bind the printer API to a LAN."""

from pathlib import Path
import os, sys, threading, time, webbrowser
import uvicorn

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def open_browser():
    import urllib.request

    for _ in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8765/api/session", timeout=1):
                pass
            webbrowser.open("http://127.0.0.1:8765")
            return
        except OSError:
            time.sleep(0.2)


if __name__ == "__main__":
    if not (ROOT / "frontend/dist/index.html").exists():
        raise SystemExit(
            "Build the frontend first: npm ci --prefix frontend && npm run build --prefix frontend"
        )
    from backend.app import app

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8765, access_log=False)
    )
    app.state.stop_server = lambda: setattr(server, "should_exit", True)
    if "--background" not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()
    server.run()
