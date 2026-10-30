from types import SimpleNamespace
from scripts import online_printer as module


def test_queue_selection_requires_exact_model_name():
    found = module.te200_queues(
        lambda: [
            (0, "", "Epson Receipt", ""),
            (0, "", "TSC TE200", ""),
            (0, "", "TSC TE2000", ""),
        ]
    )
    assert found == ["TSC TE200"]


def test_existing_working_driver_is_reused_without_update_or_setting_changes(
    monkeypatch,
):
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module, "te200_queues", lambda: ["TSC TE200"])
    monkeypatch.setattr(
        module.printer, "workspace", lambda: SimpleNamespace(geometry="confirmed")
    )
    initialized = []
    monkeypatch.setattr(
        module.printer, "initialize", lambda *args: initialized.append(args)
    )
    monkeypatch.setattr(module.printer, "check_page", lambda *args: None)
    monkeypatch.setattr(
        module,
        "configure_standard_page",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("working page must not change")
        ),
    )
    monkeypatch.setattr(
        module.printer,
        "admin_action",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("working driver must not update")
        ),
    )
    assert module.ensure() is True
    assert initialized == [(), ("TSC TE200", "confirmed")]


def test_unavailable_driver_is_reported_without_claiming_printer_ready(
    monkeypatch, capsys
):
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module, "te200_queues", lambda: [])
    monkeypatch.setattr(module.printer, "initialize", lambda *args: None)

    def unavailable(*args):
        raise RuntimeError("No compatible hardware driver available")

    monkeypatch.setattr(module.printer, "admin_action", unavailable)
    assert module.ensure() is False
    assert "PRINTER PENDING" in capsys.readouterr().out
