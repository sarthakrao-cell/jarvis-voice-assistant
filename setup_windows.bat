@echo off
echo ============================================
echo   JARVIS Voice Assistant - Setup
echo ============================================
echo.

:: Check Python
python --version 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install from python.org
    pause
    exit /b 1
)

:: Install packages
echo Installing required packages...
pip install speechrecognition pyttsx3 pyaudio anthropic psutil pyautogui pillow requests pyperclip

echo.
echo ============================================
echo Setup complete! Now:
echo 1. Open assistant.py
echo 2. Replace YOUR_ANTHROPIC_API_KEY_HERE with your key
echo    (Get one at: console.anthropic.com)
echo 3. Run: python assistant.py
echo ============================================
pause
