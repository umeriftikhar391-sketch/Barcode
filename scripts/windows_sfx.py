"""Fill fixed Windows PE resource slots; no compiler is needed to package releases."""

from pathlib import Path
import struct

SLOTS = {b"BCGUI001": 32768, b"BCCMD001": 65536, b"BCICO001": 65536}


def pe_checksum(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    offset = pe + 24 + 64
    total = 0
    for i in range(0, len(data), 2):
        if offset <= i < offset + 4:
            continue
        total += int.from_bytes(data[i : i + 2], "little")
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total & 0xFFFF) + len(data)


def fill_stub(stub, gui, core, icon):
    data = bytearray(stub)
    if data[:2] != b"MZ":
        raise ValueError("Windows setup stub is not a PE executable")
    for marker, content in [
        (b"BCGUI001", gui),
        (b"BCCMD001", core),
        (b"BCICO001", icon),
    ]:
        if data.count(marker) != 1:
            raise ValueError("Missing or duplicate Windows setup resource slot")
        offset = data.index(marker) + 8
        capacity = SLOTS[marker]
        if not content or len(content) > capacity:
            raise ValueError("Windows setup resource exceeds its fixed capacity")
        if (
            data[offset : offset + 4] != b"\0" * 4
            or data[offset + 4 : offset + 4 + capacity] != b"\0" * capacity
        ):
            raise ValueError("Windows setup template was already populated")
        data[offset : offset + 4] = struct.pack("<I", len(content))
        data[offset + 4 : offset + 4 + capacity] = content + b"\0" * (
            capacity - len(content)
        )
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    struct.pack_into("<I", data, pe + 24 + 64, pe_checksum(data))
    return bytes(data)


def build(root, core, output):
    root = Path(root)
    result = fill_stub(
        (root / "assets/windows/SetupStub.exe").read_bytes(),
        (root / "scripts/Setup-GUI.ps1").read_bytes(),
        core,
        (root / "assets/windows/BarcodeStudio.ico").read_bytes(),
    )
    Path(output).write_bytes(result)
    return result
