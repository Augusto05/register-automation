import io
import re
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from config import SPREADSHEET_ID, SHEET_GID, APPS_SCRIPT_WEBHOOK_URL

def clean_cnpj(val: Any) -> str:
    """Extrai apenas os números do CNPJ e garante 14 dígitos (preserva zeros à esquerda)."""
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    if 0 < len(digits) < 14:
        digits = digits.zfill(14)
    return digits

def clean_phone(val: Any) -> str:
    """Higieniza telefone garantindo o formato 55 + 11 dígitos."""
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    # Se já começar com 55 e tiver 13 dígitos
    if digits.startswith("55") and len(digits) == 13:
        return digits
    # Se tiver 11 dígitos (DDD + 9 dígitos), adiciona 55
    if len(digits) == 11:
        return f"55{digits}"
    # Se tiver 10 dígitos (DDD + 8 dígitos)
    if len(digits) == 10:
        return f"55{digits}"
    # Caso geral: adiciona 55 se ainda não tiver
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return digits

def fetch_pending_leads(spreadsheet_id: str = SPREADSHEET_ID, gid: str = SHEET_GID) -> List[Dict[str, Any]]:
    """
    Lê a planilha online (via Webhook do Apps Script ou CSV direto).
    Retorna apenas os leads pendentes de cadastro.
    """
    df = None

    # 1. Tenta via Webhook do Apps Script se configurado (ideal para planilhas corporativas restritas)
    if APPS_SCRIPT_WEBHOOK_URL:
        try:
            resp = requests.get(APPS_SCRIPT_WEBHOOK_URL, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 1:
                    headers = [str(h) for h in data[0]]
                    rows = data[1:]
                    df = pd.DataFrame(rows, columns=headers).astype(str)
        except Exception as e:
            print(f"[Sheets] Erro ao ler via Webhook: {e}")

    # 2. Se não leu via Webhook, tenta ler via CSV público direto
    if df is None:
        if not spreadsheet_id or spreadsheet_id == "SEU_SPREADSHEET_ID_AQUI":
            return []

        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
        try:
            response = requests.get(csv_url, timeout=15)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.content.decode("utf-8", errors="ignore")), dtype=str)
        except Exception as e:
            print(f"[Sheets] Erro ao carregar planilha online via CSV: {e}")
            return []

    try:
        
        # Normaliza cabeçalhos (minúsculo, sem acentos e sem espaços extras)
        col_map = {}
        for c in df.columns:
            c_norm = c.strip().lower()
            if "cnpj" in c_norm:
                col_map["cnpj"] = c
            elif "razao" in c_norm or "social" in c_norm or "empresa" in c_norm or "nome" in c_norm:
                if "cnpj" not in c_norm:
                    col_map["razao_social"] = c
            elif "mail" in c_norm:
                col_map["email"] = c
            elif "fone" in c_norm or "tel" in c_norm or "cel" in c_norm or "whatsapp" in c_norm:
                col_map["telefone"] = c
            elif "status" in c_norm:
                col_map["status"] = c

        pending = []
        for idx, row in df.iterrows():
            cnpj_raw = row.get(col_map.get("cnpj", ""), "")
            cnpj = clean_cnpj(cnpj_raw)
            if not cnpj:
                continue

            # Verifica status se houver coluna de status
            status_val = str(row.get(col_map.get("status", ""), "")).strip().upper()
            if status_val in ["CADASTRADO", "INDISPONÍVEL", "INDISPONIVEL"]:
                continue

            razao_social = str(row.get(col_map.get("razao_social", ""), "")).strip()
            email = str(row.get(col_map.get("email", ""), "")).strip()
            telefone = clean_phone(row.get(col_map.get("telefone", ""), ""))

            pending.append({
                "row_index": idx + 2, # Linha na planilha (1-indexed + cabeçalho)
                "cnpj": cnpj,
                "razao_social": razao_social,
                "email": email,
                "telefone": telefone,
                "status_atual": status_val
            })

        return pending

    except Exception as e:
        print(f"[Sheets] Erro ao carregar planilha online: {e}")
        return []

def update_sheet_status(cnpj: str, status: str, error_message: str = ""):
    """
    Envia a atualização de status para a planilha online se o Apps Script Webhook estiver configurado.
    """
    if not APPS_SCRIPT_WEBHOOK_URL:
        return

    payload = {
        "cnpj": cnpj,
        "status": status,
        "error_message": error_message
    }

    try:
        requests.post(APPS_SCRIPT_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"[Sheets] Erro ao sincronizar status na planilha online: {e}")
