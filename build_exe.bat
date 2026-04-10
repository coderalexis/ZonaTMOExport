@echo off
setlocal

cd /d "%~dp0"

echo ============================================
echo  Build GUI EXE - ZonaTMO/LectorManga Export
echo ============================================

echo.
echo [1/4] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python no esta instalado o no esta en PATH.
  echo Instala Python 3.9+ y marca "Add Python to PATH".
  pause
  exit /b 1
)

echo.
echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install requests beautifulsoup4 browser-cookie3 pyinstaller
if errorlevel 1 (
  echo ERROR: No se pudieron instalar dependencias.
  pause
  exit /b 1
)

echo.
echo [3/4] Generando ejecutable...
python -m PyInstaller --noconfirm --onefile --windowed --name ZonaTMOExportGUI gui_windows.py
if errorlevel 1 (
  echo ERROR: Fallo la compilacion del .exe.
  pause
  exit /b 1
)

echo.
echo [4/4] Listo.
echo EXE generado en: dist\ZonaTMOExportGUI.exe
echo.
echo IMPORTANTE:
echo - Instala la extension "Get cookies.txt LOCALLY" en tu navegador.
echo - Exporta cookies.txt y selecciona ese archivo en la GUI.

echo.
pause
exit /b 0
