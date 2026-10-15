import time
import random
import logging
from datetime import datetime
from config import (
    INTERVAL_BETWEEN_LEADS,
    INTERVAL_JITTER,
    IDLE_KEEP_ALIVE_INTERVAL
)
from db import init_db, is_cnpj_processed, record_lead, update_heartbeat, get_stats_today
from sheets import fetch_pending_leads, update_sheet_status
from rpa import SalesforceRPA

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_execution.log", encoding="utf-8")
    ]
)

def wait_with_heartbeat(seconds: int, action_prefix: str):
    """Aguarda o intervalo atualizando o batimento a cada 5 segundos."""
    start = time.time()
    while time.time() - start < seconds:
        remaining = int(seconds - (time.time() - start))
        update_heartbeat("AGUARDANDO_INTERVALO", f"{action_prefix} (próximo em {remaining}s)")
        time.sleep(min(5, max(1, remaining)))

def run_automation_loop():
    logging.info("Iniciando Automação de Leads Salesforce C6 Bank (24/7)...")
    init_db()
    update_heartbeat("INICIANDO", "Carregando navegador Chrome com perfil persistente...")

    rpa = SalesforceRPA(headless=False)
    rpa.start()

    logging.info("Navegador iniciado. Verificando sessão...")
    rpa.navigate_to_leads()
    
    if not rpa.is_logged_in():
        logging.warning("ATENÇÃO: Efetue o login no Salesforce na janela do Chrome aberta.")
        update_heartbeat("AGUARDANDO_LOGIN", "Aguardando login manual na janela do Chrome...")
        while not rpa.is_logged_in():
            time.sleep(5)
        logging.info("Login detectado com sucesso!")

    last_keep_alive = time.time()

    while True:
        try:
            update_heartbeat("CONSULTANDO_PLANILHA", "Buscando novos leads na planilha online...")
            pending_leads = fetch_pending_leads()
            
            # Filtra leads que já foram cadastrados no banco local
            unprocessed_leads = [l for l in pending_leads if not is_cnpj_processed(l["cnpj"])]

            if unprocessed_leads:
                logging.info(f"Encontrados {len(unprocessed_leads)} leads pendentes para cadastro.")
                
                for idx, lead in enumerate(unprocessed_leads):
                    cnpj = lead["cnpj"]
                    razao = lead["razao_social"]
                    logging.info(f"[{idx+1}/{len(unprocessed_leads)}] Processando: {cnpj} - {razao}")
                    
                    update_heartbeat("PROCESSANDO", f"Cadastrando: {cnpj} ({razao[:25]})")
                    
                    result = rpa.register_lead(lead)
                    status = result["status"]
                    error = result["error"]

                    # Grava no banco SQLite local
                    record_lead(
                        cnpj=cnpj,
                        razao_social=razao,
                        email=lead["email"],
                        telefone=lead["telefone"],
                        status=status,
                        error_message=error
                    )

                    # Atualiza status na planilha online
                    update_sheet_status(cnpj, status, error)

                    stats = get_stats_today()
                    logging.info(f"Resultado: {status} | Erro: {error or 'Nenhum'}")
                    logging.info(f"Hoje -> Cadastrados: {stats['cadastrados']} | Indisponíveis: {stats['indisponiveis']}")

                    last_keep_alive = time.time()

                    # Se ainda restam leads acumulados nesta rodada, aguarda o intervalo de 3 minutos
                    if idx < len(unprocessed_leads) - 1:
                        delay = INTERVAL_BETWEEN_LEADS + random.randint(-INTERVAL_JITTER, INTERVAL_JITTER)
                        logging.info(f"Aguardando {delay}s (3 min) antes do próximo lead para evitar bloqueios...")
                        wait_with_heartbeat(delay, f"Lead anterior: {status}. Aguardando rate-limit")

            else:
                # Fila vazia: momento de ociosidade
                update_heartbeat("OCIOSO", "Fila zerada. Aguardando novos leads na planilha online...")
                time.sleep(15)

                # Se passou do intervalo anti-logoff (4 min), faz keep-alive na página
                if time.time() - last_keep_alive >= IDLE_KEEP_ALIVE_INTERVAL:
                    logging.info("[Keep-Alive] Realizando interação periódica anti-logoff...")
                    update_heartbeat("OCIOSO", "Anti-logoff: atualizando sessão da página...")
                    rpa.keep_alive_interaction()
                    last_keep_alive = time.time()

        except KeyboardInterrupt:
            logging.info("Encerrando automação por solicitação do usuário...")
            update_heartbeat("PARADO", "Robô finalizado manualmente")
            rpa.stop()
            break
        except Exception as e:
            logging.error(f"Erro inesperado no loop principal: {e}", exc_info=True)
            update_heartbeat("ERRO", f"Recuperando de erro: {str(e)[:40]}")
            time.sleep(10)

if __name__ == "__main__":
    run_automation_loop()
