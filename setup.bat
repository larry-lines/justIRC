@echo off
REM Setup script for JustIRC on Windows

echo ===================================
echo JustIRC - Secure IRC Setup
echo ===================================
echo.

REM Check Python version
echo Checking Python version...
python --version
if %errorlevel% neq 0 (
    echo Error: Python 3 is required but not found
    exit /b 1
)

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ===================================
echo Setup complete!
echo ===================================
echo.
echo To start using JustIRC:
echo.
echo 1. Activate the virtual environment:
echo    venv\Scripts\activate.bat
echo.
echo 2. Start the server:
echo    python server.py
echo.
echo 3. Start a client (in another terminal):
echo    python client.py --nickname YourName
echo    OR
echo    python client_gui.py
echo.
echo For more information, see README.md
echo.

pause
