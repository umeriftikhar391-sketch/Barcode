# Run with PyInstaller on Windows x64 after frontend build.
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hidden = collect_submodules('backend') + collect_submodules('uvicorn') + ['keyring.backends.Windows','win32print','win32ui','win32con','PIL.ImageWin']
a = Analysis(['scripts/launch.py'], pathex=['.'], binaries=[], datas=[('frontend/dist','frontend/dist'),('samples','samples')]+collect_data_files('barcode'), hiddenimports=hidden)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='BarcodeStudio',console=True)
coll = COLLECT(exe,a.binaries,a.datas,name='BarcodeStudio')
