@echo off
rem Costruisce SkyrimTrans.exe su Windows. Serve Python 3.10+ nel PATH.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :err
python -m pip install ".[anthropic,7z]" || goto :err
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build skyrimtrans.spec || goto :err
echo.
echo Fatto: dist\SkyrimTrans.exe
pause
exit /b 0
:err
echo Build fallita.
pause
exit /b 1
