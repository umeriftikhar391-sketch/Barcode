import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def desktop():
    path = Path(__file__).resolve().parents[1] / "scripts/desktop.pyw"
    loader = importlib.machinery.SourceFileLoader("barcode_desktop_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_existing_service_opens_browser_without_starting_another_process(monkeypatch):
    module = desktop()
    opened = []
    monkeypatch.setattr(module, "running", lambda: True)
    monkeypatch.setattr(module.webbrowser, "open", opened.append)
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("already running")),
    )
    module.main()
    assert opened == [module.URL]


def test_new_service_has_log_and_background_launcher(monkeypatch, tmp_path):
    module = desktop()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    sequence = iter([False, True])
    monkeypatch.setattr(module, "running", lambda: next(sequence))
    monkeypatch.setattr(
        module.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False
    )
    started, opened = [], []
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *args, **kw: started.append((args, kw))
    )
    monkeypatch.setattr(module.webbrowser, "open", opened.append)
    module.main()
    assert "--background" in started[0][0][0]
    assert started[0][1]["creationflags"] == 0x08000000
    assert (tmp_path / "BarcodeStudio/service.log").is_file()
    assert opened == [module.URL]
