# PyInstaller spec: builds a single windowed ModTrans executable.
#   pip install pyinstaller
#   pyinstaller --noconfirm ModTrans_Source/modtrans.spec
from pathlib import Path

ROOT = Path(SPECPATH)   # the ModTrans_Source folder

a = Analysis(
    [str(ROOT / "start.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "modtrans_pub" / "presets"), "modtrans_pub/presets"),   # game presets + glossary
        (str(ROOT / "config.example.toml"), "."),                           # copied to config.toml on first run
    ],
    hiddenimports=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="ModTrans",
    debug=False, strip=False, upx=False,
    console=False,          # GUI app: no console window
)
