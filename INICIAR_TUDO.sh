#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "==================================================================="
echo "    AUTOMAÇÃO DE LEADS SALESFORCE C6 BANK + DASHBOARD ONLINE"
echo "==================================================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python 3 não encontrado!"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[1/3] Criando ambiente virtual..."
    python3 -m venv venv
fi

source venv/bin/activate
python3 gui.py
