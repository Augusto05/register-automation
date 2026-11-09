import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Salesforce C6 Partner Portal URL
SALESFORCE_LEADS_URL = "https://c6bank.my.site.com/partners/s/lead/Lead/00B5A000008HZEOUA4"

# Google Sheets Config
# Pode ser o ID da planilha ou a URL pública completa
# Exemplo: https://docs.google.com/spreadsheets/d/SEU_SPREADSHEET_ID/edit
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1lxFL4Rh9rxvRYn0IXA634dowZZeBeNeEQ6VsTcWZB9E")
SHEET_GID = os.getenv("SHEET_GID", "0") # ID da aba (aba 1 costuma ser 0)

# URL do Webhook do Google Apps Script (opcional, para gravar Status CADASTRADO/INDISPONIVEL na planilha pública sem auth)
APPS_SCRIPT_WEBHOOK_URL = os.getenv("APPS_SCRIPT_WEBHOOK_URL", "https://script.google.com/macros/s/AKfycbyZ0ZkCwCIhiJZOHaC_wufoGGSkndZlrnMx7v_EHNv1NxYruK38fKK7On5ugzwNzIW1/exec")

# Configurações de Delays (em segundos)
INTERVAL_BETWEEN_LEADS = 140  # 2 minutos e 20 segundos entre leads com fila acumulada
INTERVAL_JITTER = 8           # Variação aleatória (+/- 8s) para humanização
IDLE_KEEP_ALIVE_INTERVAL = 240 # 4 minutos para ping anti-logoff quando a fila estiver vazia

# Identificação do Robô (para operação paralela multi-máquina: 'Robô 1' ou 'Robô 2')
ROBOT_ID_FILE = BASE_DIR / "robot_id.txt"

def get_robot_id() -> str:
    """Retorna a identificação deste robô ('Robô 1' ou 'Robô 2')."""
    if ROBOT_ID_FILE.exists():
        try:
            val = ROBOT_ID_FILE.read_text(encoding="utf-8").strip()
            if val in ("1", "Robô 1", "Robo 1", "Robo1"):
                return "Robô 1"
            if val in ("2", "Robô 2", "Robo 2", "Robo2"):
                return "Robô 2"
            if val:
                return val
        except Exception:
            pass
    return os.getenv("ROBOT_ID", "Robô 1")

def set_robot_id(new_id: str):
    """Salva a identificação deste robô em robot_id.txt."""
    try:
        ROBOT_ID_FILE.write_text(new_id.strip(), encoding="utf-8")
    except Exception:
        pass


# Diretório de perfil persistente do Chrome (salva login/cookies no Windows)
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", str(BASE_DIR / "chrome_user_data"))

# Banco SQLite local para deduplicação e histórico
DB_PATH = str(BASE_DIR / "leads_history.db")

# Endpoint em nuvem para sincronização do Heartbeat com o Streamlit Cloud
CLOUD_HEARTBEAT_URL = os.getenv("CLOUD_HEARTBEAT_URL", "https://api.restful-api.dev/objects/ff808181a09d98f701a140c660376b10")

# LeadSale API - Controle e Validação de Assinatura (v2.0)
LEADSALE_API_URL = "https://leadsale.com.br/api/robo_indicacao/status"
LEADSALE_TOKEN_PATH = str(BASE_DIR / "leadsale_token.txt")

