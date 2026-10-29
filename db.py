import sqlite3
from datetime import datetime
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de histórico de leads processados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj TEXT UNIQUE,
        razao_social TEXT,
        email TEXT,
        telefone TEXT,
        status TEXT, -- 'CADASTRADO', 'INDISPONIVEL', 'ERRO'
        error_message TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabela de status e controle do robô (Heartbeat para GUI e Dashboard)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_heartbeat (
        id INTEGER PRIMARY KEY,
        last_ping TIMESTAMP,
        state TEXT, -- 'INICIANDO', 'AGUARDANDO_LOGIN', 'PROCESSANDO', 'AGUARDANDO_INTERVALO', 'OCIOSO', 'PAUSADO', 'ERRO', 'BLOQUEADO', 'TOKEN_AUSENTE'
        current_action TEXT,
        total_cadastrados_hoje INTEGER DEFAULT 0,
        total_indisponiveis_hoje INTEGER DEFAULT 0,
        is_paused INTEGER DEFAULT 0,
        force_check INTEGER DEFAULT 0,
        manual_login INTEGER DEFAULT 0,
        license_status TEXT DEFAULT 'VERIFICANDO',
        license_message TEXT DEFAULT 'Verificando assinatura na LeadSale...',
        last_license_ok REAL DEFAULT 0,
        next_license_check REAL DEFAULT 0
    )
    """)

    # Migrações seguras caso a tabela já exista na máquina do usuário
    migrations = [
        ("is_paused", "INTEGER DEFAULT 0"),
        ("force_check", "INTEGER DEFAULT 0"),
        ("manual_login", "INTEGER DEFAULT 0"),
        ("license_status", "TEXT DEFAULT 'VERIFICANDO'"),
        ("license_message", "TEXT DEFAULT 'Verificando assinatura na LeadSale...'"),
        ("last_license_ok", "REAL DEFAULT 0"),
        ("next_license_check", "REAL DEFAULT 0")
    ]
    for col, col_def in migrations:
        try:
            cursor.execute(f"ALTER TABLE bot_heartbeat ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    cursor.execute("SELECT COUNT(*) FROM bot_heartbeat WHERE id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO bot_heartbeat (
            id, last_ping, state, current_action,
            total_cadastrados_hoje, total_indisponiveis_hoje,
            is_paused, force_check, manual_login,
            license_status, license_message, last_license_ok, next_license_check
        )
        VALUES (
            1, CURRENT_TIMESTAMP, 'INICIANDO', 'Robô inicializado',
            0, 0, 0, 0, 0,
            'VERIFICANDO', 'Verificando assinatura na LeadSale...', 0, 0
        )
        """)

    conn.commit()
    conn.close()

def is_cnpj_processed(cnpj: str) -> bool:
    """Verifica se o CNPJ já foi cadastrado ou marcado anteriormente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM processed_leads WHERE cnpj = ?", (cnpj,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_lead(cnpj: str, razao_social: str, email: str, telefone: str, status: str, error_message: str = ""):
    """Registra ou atualiza o status do lead no banco local."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO processed_leads (cnpj, razao_social, email, telefone, status, error_message, processed_at)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(cnpj) DO UPDATE SET
        status = excluded.status,
        error_message = excluded.error_message,
        processed_at = CURRENT_TIMESTAMP
    """, (cnpj, razao_social, email, telefone, status, error_message))
    conn.commit()
    conn.close()

def update_heartbeat(state: str, action: str):
    """Atualiza o batimento do robô e computa totais de hoje."""
    conn = get_connection()
    cursor = conn.cursor()

    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    SELECT 
        SUM(CASE WHEN status = 'CADASTRADO' THEN 1 ELSE 0 END) as cadastrados,
        SUM(CASE WHEN status = 'INDISPONIVEL' THEN 1 ELSE 0 END) as indisponiveis
    FROM processed_leads
    WHERE date(processed_at) = ?
    """, (today_str,))
    row = cursor.fetchone()
    cadastrados = row["cadastrados"] or 0
    indisponiveis = row["indisponiveis"] or 0

    cursor.execute("""
    UPDATE bot_heartbeat
    SET last_ping = CURRENT_TIMESTAMP,
        state = ?,
        current_action = ?,
        total_cadastrados_hoje = ?,
        total_indisponiveis_hoje = ?
    WHERE id = 1
    """, (state, action, cadastrados, indisponiveis))
    conn.commit()

    cursor.execute("SELECT license_status, license_message, last_license_ok FROM bot_heartbeat WHERE id = 1")
    lic_row = cursor.fetchone()
    lic_status = lic_row["license_status"] if lic_row and "license_status" in lic_row.keys() else "VERIFICANDO"
    lic_msg = lic_row["license_message"] if lic_row and "license_message" in lic_row.keys() else ""
    lic_ok = lic_row["last_license_ok"] if lic_row and "last_license_ok" in lic_row.keys() else 0
    conn.close()

    # Sincroniza em segundo plano com a nuvem (Streamlit Cloud)
    _push_cloud_heartbeat(state, action, cadastrados, indisponiveis, lic_status, lic_msg, lic_ok)

def update_license_state(status: str, message: str, last_ok: float = None, next_check: float = None):
    """Atualiza o status de validação da assinatura LeadSale no banco local."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if last_ok is not None and next_check is not None:
            cursor.execute("""
                UPDATE bot_heartbeat
                SET license_status = ?, license_message = ?, last_license_ok = ?, next_license_check = ?
                WHERE id = 1
            """, (status, message, last_ok, next_check))
        elif next_check is not None:
            cursor.execute("""
                UPDATE bot_heartbeat
                SET license_status = ?, license_message = ?, next_license_check = ?
                WHERE id = 1
            """, (status, message, next_check))
        else:
            cursor.execute("""
                UPDATE bot_heartbeat
                SET license_status = ?, license_message = ?
                WHERE id = 1
            """, (status, message))
        conn.commit()
    except Exception:
        pass
    conn.close()

def get_license_state() -> dict:
    """Retorna os metadados de validação da assinatura LeadSale."""
    conn = get_connection()
    cursor = conn.cursor()
    result = {
        "license_status": "VERIFICANDO",
        "license_message": "Verificando assinatura na LeadSale...",
        "last_license_ok": 0.0,
        "next_license_check": 0.0
    }
    try:
        cursor.execute("SELECT license_status, license_message, last_license_ok, next_license_check FROM bot_heartbeat WHERE id = 1")
        row = cursor.fetchone()
        if row:
            result = {
                "license_status": row["license_status"] or "VERIFICANDO",
                "license_message": row["license_message"] or "",
                "last_license_ok": float(row["last_license_ok"] or 0.0),
                "next_license_check": float(row["next_license_check"] or 0.0)
            }
    except Exception:
        pass
    conn.close()
    return result

def _get_cloud_url():
    try:
        from config import CLOUD_HEARTBEAT_URL
        return CLOUD_HEARTBEAT_URL
    except Exception:
        return "https://api.restful-api.dev/objects/ff808181a09d98f701a140c660376b10"

def _push_cloud_heartbeat(
    state: str,
    action: str,
    cadastrados: int,
    indisponiveis: int,
    license_status: str = "VERIFICANDO",
    license_message: str = "",
    last_license_ok: float = 0
):
    """Envia o batimento para a nuvem de forma não-bloqueante (em thread)."""
    cloud_url = _get_cloud_url()
    if not cloud_url:
        return

    import threading
    import requests
    import time

    def _worker():
        try:
            payload = {
                "name": "c6_bot_heartbeat",
                "data": {
                    "state": state,
                    "current_action": action,
                    "last_ping": time.time(),
                    "total_cadastrados_hoje": cadastrados,
                    "total_indisponiveis_hoje": indisponiveis,
                    "license_status": license_status,
                    "license_message": license_message,
                    "last_license_ok": last_license_ok
                }
            }
            requests.put(cloud_url, json=payload, timeout=4)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()

def _fetch_cloud_heartbeat():
    """Busca o batimento na nuvem se o robô estiver rodando em outra máquina."""
    cloud_url = _get_cloud_url()
    if not cloud_url:
        return None

    import requests
    import time

    try:
        resp = requests.get(cloud_url, timeout=4)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            last_ping_ts = data.get("last_ping", 0)
            diff = time.time() - last_ping_ts
            if diff < 45 or data.get("state") in ("BLOQUEADO", "TOKEN_AUSENTE"):
                return {
                    "state": data.get("state", "OCIOSO"),
                    "is_alive": diff < 45,
                    "current_action": data.get("current_action", "Ativo na nuvem"),
                    "last_ping": datetime.fromtimestamp(last_ping_ts).strftime("%Y-%m-%d %H:%M:%S") if last_ping_ts else "N/A",
                    "total_cadastrados_hoje": data.get("total_cadastrados_hoje", 0),
                    "total_indisponiveis_hoje": data.get("total_indisponiveis_hoje", 0),
                    "license_status": data.get("license_status", "VERIFICANDO"),
                    "license_message": data.get("license_message", ""),
                    "last_license_ok": data.get("last_license_ok", 0),
                    "seconds_since_ping": int(diff)
                }
    except Exception:
        pass
    return None

def get_stats_today():
    """Retorna estatísticas consolidadas do dia."""
    conn = get_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'CADASTRADO' THEN 1 ELSE 0 END) as cadastrados,
        SUM(CASE WHEN status = 'INDISPONIVEL' THEN 1 ELSE 0 END) as indisponiveis
    FROM processed_leads
    WHERE date(processed_at) = ?
    """, (today_str,))
    row = cursor.fetchone()
    stats = {
        "total": row["total"] or 0,
        "cadastrados": row["cadastrados"] or 0,
        "indisponiveis": row["indisponiveis"] or 0
    }
    conn.close()

    # Se estiver vazio localmente (ex: no Streamlit Cloud), tenta ler do cloud heartbeat
    if stats["total"] == 0:
        cloud_hb = _fetch_cloud_heartbeat()
        if cloud_hb and (cloud_hb["total_cadastrados_hoje"] > 0 or cloud_hb["total_indisponiveis_hoje"] > 0):
            cad = cloud_hb["total_cadastrados_hoje"]
            ind = cloud_hb["total_indisponiveis_hoje"]
            return {"total": cad + ind, "cadastrados": cad, "indisponiveis": ind}

    return stats

def get_all_leads():
    """Retorna todos os leads para o Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processed_leads ORDER BY processed_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_heartbeat():
    """Retorna o estado do heartbeat do robô, validando local e em nuvem."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *, (strftime('%s', 'now') - strftime('%s', last_ping)) as seconds_since_ping 
        FROM bot_heartbeat 
        WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        cloud = _fetch_cloud_heartbeat()
        if cloud:
            return cloud
        return {
            "state": "DESLIGADO",
            "is_alive": False,
            "current_action": "Robô não iniciado",
            "last_ping": "N/A",
            "total_cadastrados_hoje": 0,
            "total_indisponiveis_hoje": 0
        }
    
    d = dict(row)
    seconds_since = d.get("seconds_since_ping")
    if seconds_since is None or seconds_since > 40:
        # Se o robô parou por bloqueio de licença ou falta de token, preserva esse estado na tela
        if d.get("state") in ("BLOQUEADO", "TOKEN_AUSENTE"):
            d["is_alive"] = False
            return d

        # Tenta verificar se há batimento ativo na nuvem (quando o dashboard roda no Streamlit Cloud)
        cloud = _fetch_cloud_heartbeat()
        if cloud and (cloud.get("is_alive") or cloud.get("state") in ("BLOQUEADO", "TOKEN_AUSENTE")):
            return cloud

        d["is_alive"] = False
        d["state"] = "DESLIGADO"
        d["current_action"] = "Robô desligado / offline (aguardando inicialização)"
    else:
        d["is_alive"] = True
        
    return d

def set_bot_paused(paused: bool):
    """Pausa ou retoma a execução do robô."""
    conn = get_connection()
    cursor = conn.cursor()
    val = 1 if paused else 0
    new_state = "PAUSADO" if paused else "OCIOSO"
    cursor.execute("UPDATE bot_heartbeat SET is_paused = ?, state = ? WHERE id = 1", (val, new_state))
    conn.commit()
    conn.close()

def is_bot_paused() -> bool:
    """Verifica se o robô foi pausado pelo usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_paused FROM bot_heartbeat WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return bool(row["is_paused"]) if row else False

def trigger_force_check():
    """Sinaliza ao robô para verificar a planilha imediatamente."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE bot_heartbeat SET force_check = 1 WHERE id = 1")
        conn.commit()
    except Exception:
        pass
    conn.close()

def consume_force_check() -> bool:
    """Verifica e consome o sinal de verificação imediata."""
    conn = get_connection()
    cursor = conn.cursor()
    needed = False
    try:
        cursor.execute("SELECT force_check FROM bot_heartbeat WHERE id = 1")
        row = cursor.fetchone()
        needed = bool(row["force_check"]) if row and "force_check" in row.keys() else False
        if needed:
            cursor.execute("UPDATE bot_heartbeat SET force_check = 0 WHERE id = 1")
            conn.commit()
    except Exception:
        pass
    conn.close()
    return needed

def confirm_manual_login():
    """Confirma que o usuário já fez o login no Chrome."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE bot_heartbeat SET manual_login = 1 WHERE id = 1")
        conn.commit()
    except Exception:
        pass
    conn.close()

def is_manual_login_confirmed() -> bool:
    """Verifica se o usuário confirmou o login manualmente."""
    conn = get_connection()
    cursor = conn.cursor()
    val = False
    try:
        cursor.execute("SELECT manual_login FROM bot_heartbeat WHERE id = 1")
        row = cursor.fetchone()
        val = bool(row["manual_login"]) if row and "manual_login" in row.keys() else False
    except Exception:
        pass
    conn.close()
    return val
