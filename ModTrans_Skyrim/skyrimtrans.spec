# PyInstaller spec: un solo eseguibile SkyrimTrans (apre l'interfaccia nel browser).
#   pip install pyinstaller .[anthropic,7z]
#   pyinstaller --noconfirm ModTrans_Skyrim/skyrimtrans.spec
# Resta una finestra console aperta: serve per chiudere il programma (chiudila o premi Ctrl+C).
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)  # cartella ModTrans_Skyrim

datas, binaries, hiddenimports = [], [], []
for pkg in ("py7zr", "anthropic"):  # librerie con import dinamici: si include tutto
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="SkyrimTrans",
    debug=False, strip=False, upx=False,
    console=True,
)
