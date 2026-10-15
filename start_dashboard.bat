@echo off
title Dashboard de Leads - Streamlit
chcp 65001 > nul
echo ========================================================
echo   Iniciando Dashboard Web de Leads - Salesforce C6
echo ========================================================

if exist "venv\Scripts\activate" (
    call venv\Scripts\activate
)

echo Abrindo Dashboard no navegador...
streamlit run dashboard.py

pause
