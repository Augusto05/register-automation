import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Salesforce C6 Partner Portal URL
SALESFORCE_LEADS_URL = "https://c6bank.my.site.com/partners/s/lead/Lead/00B5A000008HZEOUA4"

# Google Sheets Config
# Pode ser o ID da planilha ou a URL pública completa
# Exemplo: https://docs.google.com/spreadsheets/d/SEU_SPREADSHEET_ID/edit
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "SEU_SPREADSHEET_ID_AQUI")
SHEET_GID = os.getenv("SHEET_GID", "0") # ID da aba (aba 1 costuma ser 0)

# URL do Webhook do Google Apps Script (opcional, para gravar Status CADASTRADO/INDISPONIVEL na planilha pública sem auth)
APPS_SCRIPT_WEBHOOK_URL = os.getenv("APPS_SCRIPT_WEBHOOK_URL", "")

# Configurações de Delays (em segundos)
INTERVAL_BETWEEN_LEADS = 180  # 3 minutos entre leads com fila acumulada
INTERVAL_JITTER = 10          # Variação aleatória (+/- 10s) para humanização
IDLE_KEEP_ALIVE_INTERVAL = 240 # 4 minutos para ping anti-logoff quando a fila estiver vazia

# Diretório de perfil persistente do Chrome (salva login/cookies no Windows)
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", str(BASE_DIR / "chrome_user_data"))

# Banco SQLite local para deduplicação e histórico
DB_PATH = str(BASE_DIR / "leads_history.db")
