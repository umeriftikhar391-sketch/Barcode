from pathlib import Path
import struct
import pytest
from scripts.windows_sfx import SLOTS, fill_stub, build, pe_checksum

ROOT = Path(__file__).resolve().parents[1]


def test_native_host_is_x64_windows_gui_with_icon_and_empty_resources():
    stub = (ROOT / "assets/windows/SetupStub.exe").read_bytes()
    pe = struct.unpack_from("<I", stub, 0x3C)[0]
    assert stub[pe : pe + 4] == b"PE\0\0"
    assert struct.unpack_from("<H", stub, pe + 4)[0] == 0x8664
    assert struct.unpack_from("<H", stub, pe + 24 + 68)[0] == 2  # GUI subsystem
    assert pe_checksum(stub) == struct.unpack_from("<I", stub, pe + 24 + 64)[0]
    result = fill_stub(stub, b"GUI", b"CORE", b"ICON")
    assert pe_checksum(result) == struct.unpack_from("<I", result, pe + 24 + 64)[0]
    for marker, expected in [
        (b"BCGUI001", b"GUI"),
        (b"BCCMD001", b"CORE"),
        (b"BCICO001", b"ICON"),
    ]:
        start = result.index(marker) + 8
        length = struct.unpack_from("<I", result, start)[0]
        assert result[start + 4 : start + 4 + length] == expected
    with pytest.raises(ValueError, match="already populated"):
        fill_stub(result, b"GUI", b"CORE", b"ICON")


def test_real_gui_and_core_fit_slots_and_preserve_native_size(tmp_path):
    stub = (ROOT / "assets/windows/SetupStub.exe").read_bytes()
    core = (ROOT / "scripts/Setup-New-PC.template.cmd").read_bytes()
    result = build(ROOT, core, tmp_path / "Setup.exe")
    assert len(result) == len(stub)
    assert b"Windows Update" in result and b"Barcode Studio" in result
    assert result == (tmp_path / "Setup.exe").read_bytes()


@pytest.mark.parametrize("stub,gui", [(b"invalid", b"a"), (b"MZ", b"a")])
def test_bad_host_cannot_be_packaged(stub, gui):
    with pytest.raises(ValueError):
        fill_stub(stub, gui, b"a", b"a")


def test_oversized_resources_refused():
    stub = (ROOT / "assets/windows/SetupStub.exe").read_bytes()
    with pytest.raises(ValueError, match="capacity"):
        fill_stub(stub, b"a" * (SLOTS[b"BCGUI001"] + 1), b"a", b"a")


def test_packaged_exe_has_exact_same_pinned_engine_as_cmd(tmp_path):
    from scripts.package_windows import build as package
    import shutil

    for name in [
        "assets/windows/SetupStub.exe",
        "assets/windows/BarcodeStudio.ico",
        "scripts/Setup-GUI.ps1",
        "scripts/Setup-New-PC.template.cmd",
    ]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (tmp_path / "frontend/dist").mkdir(parents=True)
    (tmp_path / "frontend/dist/index.html").write_text("fixture")
    checksum = package(tmp_path, "a" * 40)
    exe = (tmp_path / "downloads/Setup.exe").read_bytes()
    start = exe.index(b"BCCMD001") + 8
    size = struct.unpack_from("<I", exe, start)[0]
    core = exe[start + 4 : start + 4 + size]
    assert core == (tmp_path / "Setup-Barcode-Studio.cmd").read_bytes()
    assert checksum.encode() in core
    assert (b"/" + b"a" * 40 + b"/downloads/Barcode-Studio.zip") in core
