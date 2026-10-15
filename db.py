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
        state TEXT, -- 'INICIANDO', 'AGUARDANDO_LOGIN', 'PROCESSANDO', 'AGUARDANDO_INTERVALO', 'OCIOSO', 'PAUSADO', 'ERRO'
        current_action TEXT,
        total_cadastrados_hoje INTEGER DEFAULT 0,
        total_indisponiveis_hoje INTEGER DEFAULT 0,
        is_paused INTEGER DEFAULT 0,
        force_check INTEGER DEFAULT 0
    )
    """)

    cursor.execute("SELECT COUNT(*) FROM bot_heartbeat WHERE id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO bot_heartbeat (id, last_ping, state, current_action, total_cadastrados_hoje, total_indisponiveis_hoje, is_paused, force_check)
        VALUES (1, CURRENT_TIMESTAMP, 'INICIANDO', 'Robô inicializado', 0, 0, 0, 0)
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
    conn.close()

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
    """Retorna o estado do heartbeat do robô."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bot_heartbeat WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

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
    cursor.execute("UPDATE bot_heartbeat SET force_check = 1 WHERE id = 1")
    conn.commit()
    conn.close()

def consume_force_check() -> bool:
    """Verifica e consome o sinal de verificação imediata."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT force_check FROM bot_heartbeat WHERE id = 1")
    row = cursor.fetchone()
    needed = bool(row["force_check"]) if row else False
    if needed:
        cursor.execute("UPDATE bot_heartbeat SET force_check = 0 WHERE id = 1")
        conn.commit()
    conn.close()
    return needed
