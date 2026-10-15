@echo off
title RPA Leads Salesforce C6
chcp 65001 > nul
echo ========================================================
echo   Iniciando Robo de Cadastro de Leads - Salesforce C6
echo ========================================================

:: Verifica se o ambiente virtual existe, se nao, cria
if not exist "venv" (
    echo Criando ambiente virtual Python...
    python -m venv venv
)

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo Instalando / Atualizando dependencias...
pip install -r requirements.txt

echo Garantindo os navegadores do Playwright...
playwright install chromium

echo.
echo Iniciando o robo 24/7...
python main.py

pause
