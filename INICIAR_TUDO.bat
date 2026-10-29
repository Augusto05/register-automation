@echo off
setlocal
cd /d "%~dp0"

title Automacao Leads Salesforce C6 - LeadSale

echo ===================================================================
echo     AUTOMACAO DE LEADS SALESFORCE C6 BANK (LEADSALE)
echo ===================================================================
echo.

REM 1. Verifica se python ou py esta disponivel e funcional
set PYTHON_CMD=
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py --version >nul 2>nul
    if %ERRORLEVEL% equ 0 set PYTHON_CMD=py
)

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        python --version >nul 2>nul
        if %ERRORLEVEL% equ 0 set PYTHON_CMD=python
    )
)

REM 2. Se o Python nao foi encontrado, faz download e instala silenciosamente
if "%PYTHON_CMD%"=="" (
    echo [INFO] Python nao foi detectado nesta maquina.
    echo Baixando e instalando o Python oficial automaticamente...
    echo Aguarde cerca de 1 a 2 minutos...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$url = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe\; $out = "$env:TEMP\python_installer.exe"; Write-Host 'Baixando Python do site oficial...' ; Invoke-WebRequest -Uri $url -OutFile $out ; Write-Host 'Instalando silenciosamente...' ; Start-Process -FilePath $out -ArgumentList '/quiet PrependPath=1 Include_test=0' -Wait ; Remove-Item $out -ErrorAction SilentlyContinue"

    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    set "PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;%PATH%"

    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PYTHON_CMD=py
    ) else (
        where python >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            set PYTHON_CMD=python
        ) else (
            echo.
            echo [SUCESSO] Python foi instalado com sucesso!
            echo Por favor, FECHE esta janela e de duplo clique novamente em INICIAR_TUDO.bat
            echo para que o Windows reconheca o novo Python instalado.
            echo.
            pause
            exit /b 0
        )
    )
)

echo [OK] Python detectado: %PYTHON_CMD%

REM 3. Cria venv se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Criando ambiente virtual isolado...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo Falha ao criar venv. Tentando continuar com Python global...
    )
)

REM 4. Ativa venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM 5. Instala dependencias na primeira execucao
if not exist "venv\.installed" (
    echo [2/3] Instalando dependencias (Playwright, Streamlit, Pandas)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo Instalando navegador Playwright Chromium...
    playwright install chromium
    echo ok > "venv\.installed"
)

REM 6. Verifica lembrete de token da LeadSale e inicia o painel de controle e o robo
if not exist "leadsale_token.txt" (
    echo [AVISO] Arquivo leadsale_token.txt ainda nao configurado.
    echo Voce podera colar o seu token lri_ diretamente na janela do Painel de Controle!
    echo.
)

echo [3/3] Iniciando o Painel de Controle e o Robo...
python gui.py

pause
