@echo off
title Screenshot Discord Bot Dependencies Installer
color 0A

echo Installing Python dependencies for Screenshot Discord Bot...
echo.

pip install --upgrade requests pyautogui psutil Pillow pygetwindow pywin32

if %errorlevel%==0 (
    echo.
    echo ✅ All dependencies installed successfully!
) else (
    echo.
    echo ❌ Installation failed. Please check errors above.
)

echo.
pause
