#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "==================================================================="
echo "    AUTOMAÇÃO DE LEADS SALESFORCE C6 BANK + DASHBOARD ONLINE"
echo "==================================================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python 3 não encontrado!"
    echo "Instale o Python 3 para Mac em: https://www.python.org/downloads/"
    read -p "Pressione enter para sair..."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[1/3] Criando ambiente virtual Python pela primeira vez..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[2/3] Instalando dependências (Playwright, Streamlit, etc.)..."
    pip install -r requirements.txt
    playwright install chromium
else
    source venv/bin/activate
fi

echo "[3/3] Iniciando painel de controle e robô..."
python3 gui.py
