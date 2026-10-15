@echo off
setlocal
cd /d "%~dp0"
title Dashboard Leads - Streamlit

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

streamlit run dashboard.py
pause
