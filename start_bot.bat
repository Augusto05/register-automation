@echo off
setlocal
cd /d "%~dp0"
title Robo Leads Salesforce C6

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python main.py
pause
