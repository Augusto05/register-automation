@echo off
setlocal
cd /d "%~dp0"

title Automacao Leads Salesforce C6

echo ===================================================================
echo     AUTOMACAO DE LEADS SALESFORCE C6 BANK
echo ===================================================================
echo.

REM Verifica se python ou py esta disponivel
set PYTHON_CMD=
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PYTHON_CMD=python
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERRO] Python nao foi encontrado nesta maquina!
    echo.
    echo Por favor, instale o Python:
    echo 1. Baixe em: https://www.python.org/downloads/
    echo 2. ATENCAO: Marque a opcao "Add python.exe to PATH" ao instalar!
    echo.
    pause
    exit /b 1
)

echo Usando: %PYTHON_CMD%

REM Cria venv se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Criando ambiente virtual Python...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo Falha ao criar venv. Tentando continuar...
    )
)

REM Ativa venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Instala dependencias na primeira vez
if not exist "venv\.installed" (
    echo [2/3] Instalando dependencias (Playwright, Streamlit, Pandas)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo Instalando navegador Playwright Chromium...
    playwright install chromium
    echo ok > "venv\.installed"
)

REM Inicia o painel e o robo
echo [3/3] Iniciando o Painel de Controle e o Robo...
python gui.py

pause
