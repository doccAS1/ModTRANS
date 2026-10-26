@echo off
rem Builds ModTrans.exe on Windows. Requires Python 3.11+ (with tkinter) on PATH.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :err
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build ModTrans_Source\modtrans.spec || goto :err
copy /Y ModTrans_Source\config.example.toml dist\config.toml >nul
echo.
echo Done: dist\ModTrans.exe  (config.toml next to it is ready to edit)
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
