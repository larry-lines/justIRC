@echo off
REM Build script for Windows (.exe packages)

echo ========================================
echo JustIRC Windows Package Builder
echo ========================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.8 or higher
    exit /b 1
)

echo Checking dependencies...

REM Create virtual environment
echo.
echo Setting up build environment...
python -m venv build-env
call build-env\Scripts\activate.bat

REM Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install pyinstaller

echo Build environment ready
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec
echo Cleaned
echo.

REM Build GUI client
echo ========================================
echo Building GUI client...
echo ========================================
pyinstaller --name "JustIRC-GUI" ^
    --onefile ^
    --windowed ^
    --icon=JUSTIRC-logo.png ^
    --add-data "JUSTIRC-logo.png;." ^
    --add-data "README.md;." ^
    --add-data "THEMES.md;." ^
    client_gui.py

if errorlevel 1 (
    echo Error building GUI client
    exit /b 1
)

echo GUI client built successfully
echo.

REM Build CLI client
echo ========================================
echo Building CLI client...
echo ========================================
pyinstaller --name "JustIRC-CLI" ^
    --onefile ^
    --console ^
    --add-data "README.md;." ^
    --exclude-module tkinter ^
    --exclude-module PIL ^
    client.py

if errorlevel 1 (
    echo Error building CLI client
    exit /b 1
)

echo CLI client built successfully
echo.

REM Build server
echo ========================================
echo Building server...
echo ========================================
pyinstaller --name "JustIRC-Server" ^
    --onefile ^
    --console ^
    --add-data "README.md;." ^
    --exclude-module tkinter ^
    --exclude-module PIL ^
    --exclude-module colorama ^
    server.py

if errorlevel 1 (
    echo Error building server
    exit /b 1
)

echo Server built successfully
echo.

echo ========================================
echo SUCCESS! All packages built
echo ========================================
echo.
echo Executables are in the 'dist' folder:
dir /b dist\*.exe
echo.
echo You can now distribute these .exe files.
echo They don't require Python or any dependencies!
echo.

REM Deactivate virtual environment
deactivate

pause
