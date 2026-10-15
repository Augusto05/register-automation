@echo off
title Automação Salesforce C6 Bank
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================================
echo     AUTOMAÇÃO DE LEADS SALESFORCE C6 BANK + DASHBOARD ONLINE
echo ===================================================================
echo.

:: 1. Verifica se o Python está instalado
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Python não encontrado!
    echo Por favor, baixe e instale o Python em: https://www.python.org/downloads/
    echo ATENÇÃO: Marque a opção "Add Python to PATH" durante a instalação.
    echo.
    pause
    exit /b 1
)

:: 2. Cria o ambiente virtual na primeira execução
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Configurando ambiente virtual Python pela primeira vez...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo Falha ao criar venv. Tentando rodar com Python global...
    )
)

:: 3. Ativa o ambiente virtual
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 4. Instala dependências e navegador na primeira vez
if not exist "venv\.installed" (
    echo [2/3] Instalando dependências (Playwright, Streamlit, Pandas)...
    pip install -r requirements.txt
    echo Instalando navegador Playwright Chromium...
    playwright install chromium
    echo ok > "venv\.installed"
)

:: 5. Executa a interface gráfica e o robô
echo [3/3] Iniciando o Painel de Controle e o Robô...
python gui.py

pause
