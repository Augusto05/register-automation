import sys
import time
import random
import logging
from datetime import datetime
from config import (
    BASE_DIR,
    INTERVAL_BETWEEN_LEADS,
    INTERVAL_JITTER,
    IDLE_KEEP_ALIVE_INTERVAL
)
from db import (
    init_db,
    is_cnpj_processed,
    record_lead,
    update_heartbeat,
    get_stats_today,
    is_bot_paused,
    consume_force_check
)
from sheets import fetch_pending_leads, update_sheet_status
from rpa import SalesforceRPA
from license import LicenseController, TokenLogSanitizer

_sanitizer = TokenLogSanitizer()
_stream_handler = logging.StreamHandler()
_stream_handler.addFilter(_sanitizer)
_file_handler = logging.FileHandler(str(BASE_DIR / "bot_execution.log"), encoding="utf-8")
_file_handler.addFilter(_sanitizer)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_stream_handler, _file_handler]
)

def prevent_windows_sleep():
    """Impede que o Windows suspenda ou durma por inatividade enquanto o robô roda."""
    if sys.platform == "win32":
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            logging.info("[Sistema] Modo anti-suspensão do Windows ativado.")
        except Exception as e:
            logging.warning(f"[Sistema] Aviso ao configurar anti-suspensão: {e}")

def wait_with_heartbeat(seconds: int, action_prefix: str, license_ctrl: LicenseController = None) -> bool:
    """
    Aguarda o intervalo atualizando o batimento a cada 2 segundos.
    Respeita pausas, sinal de verificação imediata e checagem periódica de licença.
    Retorna True se pode prosseguir, ou False se o robô foi bloqueado pela LeadSale.
    """
    start = time.time()
    while time.time() - start < seconds:
        if license_ctrl is not None:
            liberado, _ = license_ctrl.verificar_se_necessario()
            if not liberado:
                return False

        # Se o usuário clicou em forçar verificação
        if consume_force_check():
            logging.info("[Controle] Verificação imediata solicitada pelo usuário.")
            return True

        # Se o usuário pausou o robô
        while is_bot_paused():
            update_heartbeat("PAUSADO", "Robô pausado pelo usuário. Clique em Retomar para continuar.")
            time.sleep(1)

        remaining = int(seconds - (time.time() - start))
        update_heartbeat("AGUARDANDO_INTERVALO", f"{action_prefix} (próximo em {remaining}s)")
        time.sleep(min(2, max(1, remaining)))
    return True

def run_automation_loop():
    logging.info("Iniciando Automação de Leads Salesforce C6 Bank (24/7)...")
    prevent_windows_sleep()
    init_db()

    # 1. Conferência obrigatória da assinatura LeadSale ao abrir
    update_heartbeat("INICIANDO", "Conferindo assinatura do escritório na LeadSale...")
    license_ctrl = LicenseController(persist_db=True)
    liberado, motivo = license_ctrl.verificar_se_necessario()
    if not liberado:
        logging.error(f"Execução interrompida na validação inicial: {motivo}")
        return

    update_heartbeat("INICIANDO", "Carregando navegador Chrome com perfil persistente...")

    rpa = SalesforceRPA(headless=False)
    rpa.start()

    logging.info("Navegador iniciado. Acessando Salesforce Leads...")
    try:
        rpa.navigate_to_leads()
    except Exception as e:
        logging.warning(f"Aviso inicial ao abrir Leads: {e}")
    
    # Verificação explícita de login
    from db import is_manual_login_confirmed
    if not rpa.is_logged_in() and not is_manual_login_confirmed():
        logging.warning("ATENÇÃO: Faça o login na janela aberta do Chrome (usuário, senha e 2FA).")
        while not rpa.is_logged_in() and not is_manual_login_confirmed():
            liberado, _ = license_ctrl.verificar_se_necessario()
            if not liberado:
                rpa.stop()
                return
            update_heartbeat("AGUARDANDO_LOGIN", "Aguardando login no Chrome... (faça login na janela aberta)")
            time.sleep(2)
        logging.info("Login detectado com sucesso!")
        # Uma vez logado, navega para a tela de leads
        try:
            rpa.navigate_to_leads()
        except Exception:
            pass

    update_heartbeat("OCIOSO", "Login autenticado! Iniciando monitoramento da planilha...")
    last_keep_alive = time.time()

    while True:
        try:
            # Verifica assinatura LeadSale (1x por dia ou 1x por hora em contingência)
            liberado, _ = license_ctrl.verificar_se_necessario()
            if not liberado:
                rpa.stop()
                break

            # Verifica se o robô foi colocado em pausa pelo usuário
            while is_bot_paused():
                liberado, _ = license_ctrl.verificar_se_necessario()
                if not liberado:
                    rpa.stop()
                    return
                update_heartbeat("PAUSADO", "Robô pausado. Clique em 'Retomar' para voltar.")
                time.sleep(2)

            update_heartbeat("CONSULTANDO_PLANILHA", "Buscando novos leads na planilha online...")
            pending_leads = fetch_pending_leads()
            
            # Filtra leads já cadastrados no banco local
            unprocessed_leads = [l for l in pending_leads if not is_cnpj_processed(l["cnpj"])]

            if unprocessed_leads:
                logging.info(f"Encontrados {len(unprocessed_leads)} leads pendentes para cadastro.")
                
                for idx, lead in enumerate(unprocessed_leads):
                    # Verifica licença antes de cada lead do lote
                    liberado, _ = license_ctrl.verificar_se_necessario()
                    if not liberado:
                        rpa.stop()
                        return

                    # Verifica se o usuário pausou durante o processamento do lote
                    while is_bot_paused():
                        liberado, _ = license_ctrl.verificar_se_necessario()
                        if not liberado:
                            rpa.stop()
                            return
                        update_heartbeat("PAUSADO", "Robô pausado entre leads. Clique em Retomar.")
                        time.sleep(1)

                    cnpj = lead["cnpj"]
                    razao = lead["razao_social"]
                    logging.info(f"[{idx+1}/{len(unprocessed_leads)}] Processando: {cnpj} - {razao}")
                    
                    update_heartbeat("PROCESSANDO", f"Cadastrando: {cnpj} ({razao[:22]})")
                    
                    result = rpa.register_lead(lead)
                    status = result["status"]
                    error = result["error"]

                    # Grava no banco local
                    record_lead(
                        cnpj=cnpj,
                        razao_social=razao,
                        email=lead["email"],
                        telefone=lead["telefone"],
                        status=status,
                        error_message=error
                    )

                    # Atualiza na planilha online
                    update_sheet_status(cnpj, status, error)

                    stats = get_stats_today()
                    logging.info(f"Resultado: {status} | Erro: {error or 'Nenhum'}")
                    logging.info(f"Hoje -> Cadastrados: {stats['cadastrados']} | Indisponíveis: {stats['indisponiveis']}")

                    last_keep_alive = time.time()

                    # Se ainda restam leads nesta rodada, aguarda o intervalo de 3 minutos
                    if idx < len(unprocessed_leads) - 1:
                        delay = INTERVAL_BETWEEN_LEADS + random.randint(-INTERVAL_JITTER, INTERVAL_JITTER)
                        logging.info(f"Aguardando {delay}s (3 min) antes do próximo lead para evitar bloqueios...")
                        pode_continuar = wait_with_heartbeat(delay, f"Lead anterior: {status}. Rate-limit", license_ctrl=license_ctrl)
                        if not pode_continuar:
                            rpa.stop()
                            return

            else:
                # Fila vazia: momento de ociosidade
                update_heartbeat("OCIOSO", "Fila zerada. Aguardando novos leads na planilha online...")
                
                # Aguarda até 15s com checagem de força de verificação e pulso de batimento
                for i in range(15):
                    if consume_force_check():
                        logging.info("[Controle] Verificação antecipada solicitada!")
                        break
                    if i % 4 == 0:
                        update_heartbeat("OCIOSO", "Fila zerada. Aguardando novos leads na planilha online...")
                    time.sleep(1)

                # Anti-logoff a cada 4 minutos em momentos de ociosidade
                if time.time() - last_keep_alive >= IDLE_KEEP_ALIVE_INTERVAL:
                    logging.info("[Anti-Logoff] Interação periódica para manter a sessão ativa...")
                    update_heartbeat("OCIOSO", "Anti-logoff: mantendo sessão do C6 ativa...")
                    rpa.keep_alive_interaction()
                    last_keep_alive = time.time()

        except KeyboardInterrupt:
            logging.info("Encerrando automação por solicitação...")
            update_heartbeat("PARADO", "Robô finalizado.")
            rpa.stop()
            break
        except Exception as e:
            logging.error(f"Erro no loop principal: {e}", exc_info=True)
            update_heartbeat("ERRO", f"Recuperando de erro: {str(e)[:35]}")
            time.sleep(10)

if __name__ == "__main__":
    run_automation_loop()
