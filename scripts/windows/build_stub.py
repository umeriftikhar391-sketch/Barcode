"""Build the native setup host using MinGW-w64; set MINGW_ROOT for a local toolchain."""

from pathlib import Path
import os, subprocess, tempfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
assets = ROOT / "assets/windows"
assets.mkdir(parents=True, exist_ok=True)
im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((8, 8, 248, 248), radius=52, fill="#102e35")
d.rounded_rectangle((42, 50, 214, 206), radius=16, fill="#ffffff")
x = 67
for width in [4, 2, 6, 2, 4, 6, 2, 2, 4, 2, 6, 4]:
    d.rectangle((x, 77, x + width, 163), fill="#102e35")
    x += width + 7
    if x > 196:
        break
d.rounded_rectangle((65, 179, 191, 187), radius=3, fill="#18816b")
im.save(
    assets / "BarcodeStudio.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
base = Path(os.environ["MINGW_ROOT"]) if "MINGW_ROOT" in os.environ else None
gcc = (
    str(base / "usr/bin/x86_64-w64-mingw32-gcc-win32")
    if base
    else "x86_64-w64-mingw32-gcc"
)
windres = (
    str(base / "usr/bin/x86_64-w64-mingw32-windres")
    if base
    else "x86_64-w64-mingw32-windres"
)
flags = []
if base:
    flags = [
        "-B" + str(base / "usr/lib/gcc/x86_64-w64-mingw32/14-win32") + "/",
        "--sysroot=" + str(base / "usr"),
    ]
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    from sys import path

    path.insert(0, str(ROOT))
    from scripts.windows_sfx import SLOTS

    resources = []
    for index, (marker, size) in enumerate(SLOTS.items(), 101):
        file = tmp / (str(index) + ".bin")
        file.write_bytes(marker + b"\0" * 4 + b"\0" * size)
        resources.append(f'{index} RCDATA "{file.as_posix()}"')
    manifest = tmp / "app.manifest"
    manifest.write_text(
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"><assemblyIdentity version="1.0.0.0" processorArchitecture="amd64" name="BarcodeStudio.Setup" type="win32"/><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo><compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/></application></compatibility></assembly>"""
    )
    resources += [
        f'1 ICON "{(assets / "BarcodeStudio.ico").as_posix()}"',
        f'1 24 "{manifest.as_posix()}"',
        """1 VERSIONINFO FILEVERSION 1,0,0,0 PRODUCTVERSION 1,0,0,0 FILEFLAGSMASK 0x3f FILEFLAGS 0 FILEOS 0x40004 FILETYPE 1 BEGIN BLOCK "StringFileInfo" BEGIN BLOCK "040904b0" BEGIN VALUE "FileDescription", "Barcode Studio Setup\\0" VALUE "ProductName", "Barcode Studio\\0" VALUE "FileVersion", "1.0.0\\0" END END BLOCK "VarFileInfo" BEGIN VALUE "Translation", 0x409, 1200 END END""",
    ]
    rc = tmp / "setup.rc"
    rc.write_text("\n".join(resources))
    subprocess.run(
        [
            windres,
            "--preprocessor=/usr/bin/cpp",
            "-i",
            str(rc),
            "-o",
            str(tmp / "setup.o"),
        ],
        check=True,
    )
    subprocess.run(
        [
            gcc,
            *flags,
            "-municode",
            "-mwindows",
            "-O2",
            "-s",
            "-static-libgcc",
            str(ROOT / "scripts/windows/setup_stub.c"),
            str(tmp / "setup.o"),
            "-luser32",
            "-lole32",
            "-Wl,--no-insert-timestamp",
            "-o",
            str(assets / "SetupStub.exe"),
        ],
        check=True,
    )
print("Native Windows x64 setup stub and multiresolution desktop icon built.")
