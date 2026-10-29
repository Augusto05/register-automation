import re
import time
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple

from config import BASE_DIR, LEADSALE_API_URL, LEADSALE_TOKEN_PATH
from db import update_license_state, get_license_state, update_heartbeat

ENDERECO = LEADSALE_API_URL
TOKEN_PATH = Path(LEADSALE_TOKEN_PATH)
UMA_HORA = 60 * 60
UM_DIA = 24 * UMA_HORA

_ultimo_motivo = ""


class TokenLogSanitizer(logging.Filter):
    """Garante que nenhum token lri_ apareça acidentalmente nos logs ou no console."""
    _pattern = re.compile(r"lri_[A-Za-z0-9_\-]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._pattern.sub("lri_[OCULTO]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._pattern.sub("lri_[OCULTO]", v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._pattern.sub("lri_[OCULTO]", a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def _normalizar_arquivo_token_windows() -> Path:
    """
    Corrige automaticamente caso o usuário no Windows crie 'leadsale_token.txt.txt'
    por estar com extensões de arquivo ocultas no Explorer.
    """
    duplo_txt = BASE_DIR / "leadsale_token.txt.txt"
    if not TOKEN_PATH.exists() and duplo_txt.exists():
        try:
            conteudo = duplo_txt.read_text(encoding="utf-8").strip()
            if conteudo:
                TOKEN_PATH.write_text(conteudo, encoding="utf-8")
        except Exception:
            return duplo_txt
    return TOKEN_PATH


def _higienizar_token(raw: str) -> str:
    """
    Remove espaços/quebras de linha e corrige colagem duplicada acidental
    (ex: 'lri_abc...lri_abc...' quando o usuário aperta Ctrl+V/Cmd+V duas vezes).
    """
    if not raw:
        return ""
    limpo = raw.strip()
    if limpo.count("lri_") > 1:
        partes = [p.strip() for p in limpo.split("lri_") if p.strip()]
        if partes:
            limpo = "lri_" + partes[0]
    return limpo


def carregar_token() -> str:
    """
    Lê o token do arquivo leadsale_token.txt na pasta do robô.
    Retorna string vazia caso não exista ou não possa ser lido.
    """
    caminho = _normalizar_arquivo_token_windows()
    if not caminho.exists():
        return ""
    try:
        with open(caminho, encoding="utf-8") as f:
            conteudo = f.read().strip()
        higienizado = _higienizar_token(conteudo)
        if higienizado and higienizado != conteudo:
            caminho.write_text(higienizado, encoding="utf-8")
        return higienizado
    except Exception:
        return ""


def validar_formato_token(token: str) -> bool:
    """Verifica localmente se o token possui o prefixo oficial 'lri_'."""
    if not token:
        return False
    limpo = _higienizar_token(token)
    return limpo.startswith("lri_") and len(limpo) > 4 and " " not in limpo


def token_esta_configurado() -> bool:
    """Indica se há um token com formato válido salvo em leadsale_token.txt."""
    return validar_formato_token(carregar_token())


def salvar_token(novo_token: str) -> Tuple[bool, str]:
    """
    Salva o token do escritório no arquivo leadsale_token.txt após validar seu prefixo.
    Nunca exibe ou registra o valor do token.
    """
    limpo = _higienizar_token(novo_token or "")
    if not limpo:
        return False, "O token não pode estar vazio."
    if not validar_formato_token(limpo):
        return False, "Formato inválido. O token da LeadSale deve começar com 'lri_' e não conter espaços."
    try:
        TOKEN_PATH.write_text(limpo, encoding="utf-8")
        return True, "Token salvo com segurança em leadsale_token.txt!"
    except Exception:
        return False, "Não foi possível gravar o arquivo leadsale_token.txt na pasta do robô."


def assinatura_ativa() -> Optional[bool]:
    """True = liberado · False = não liberado · None = LeadSale não respondeu."""
    global _ultimo_motivo
    token = carregar_token()
    if not validar_formato_token(token):
        _ultimo_motivo = "TOKEN_INVALIDO"
        return False

    try:
        r = requests.get(
            ENDERECO,
            headers={"X-Api-Key": token},
            timeout=10,
            allow_redirects=False
        )
    except requests.RequestException:
        _ultimo_motivo = "SEM_RESPOSTA"
        return None

    if r.status_code == 200:
        try:
            ativo = r.json().get("ativo") == 1
            _ultimo_motivo = "LIBERADO" if ativo else "SERVICO_DESLIGADO"
            return ativo
        except ValueError:
            _ultimo_motivo = "SEM_RESPOSTA"
            return None

    if r.status_code in (401, 403):
        _ultimo_motivo = "NAO_LIBERADO"
        return False

    _ultimo_motivo = "SEM_RESPOSTA"
    return None


class LicenseController:
    """
    Controla o ciclo de verificação da assinatura LeadSale:
    - Pergunta à LeadSale ao abrir (proxima_consulta = 0) e depois 1 vez por dia (24h).
    - Se sem resposta (None), continua rodando e tenta novamente em 1 hora (por até 48h).
    - Se não liberado (False) ou sem confirmação por > 48h, para o robô imediatamente.
    """

    def __init__(self, persist_db: bool = True):
        self.persist_db = persist_db
        self.ultima_confirmacao: float = 0.0
        self.proxima_consulta: float = 0.0

        if self.persist_db:
            try:
                saved = get_license_state()
                self.ultima_confirmacao = float(saved.get("last_license_ok") or 0.0)
            except Exception:
                self.ultima_confirmacao = 0.0

    def verificar_se_necessario(self) -> Tuple[bool, str]:
        """
        Verifica a assinatura caso tenha chegado o momento de `proxima_consulta`.
        Retorna (True, mensagem) se o robô pode rodar, ou (False, motivo_parada) se deve parar.
        """
        agora = time.time()
        if agora < self.proxima_consulta:
            return True, "Assinatura ativa"

        # 1. Verifica localmente se o arquivo leadsale_token.txt existe e tem formato válido
        # (Evita enviar chamadas inválidas para a API e bloquear o IP do escritório por 1h)
        if not token_esta_configurado():
            msg = "Token LeadSale não configurado. Configure o arquivo leadsale_token.txt (ou clique em '🔑 Configurar Token')."
            logging.error(msg)
            if self.persist_db:
                update_license_state("TOKEN_AUSENTE", msg, next_check=0)
                update_heartbeat("TOKEN_AUSENTE", msg)
            return False, msg

        if self.persist_db:
            update_license_state("VERIFICANDO", "Conferindo assinatura na LeadSale...")

        resposta = assinatura_ativa()
        agora = time.time()

        if resposta is True:
            self.ultima_confirmacao = agora
            self.proxima_consulta = agora + UM_DIA
            msg = "Assinatura confirmada na LeadSale (próxima verificação em 24h)."
            logging.info(f"[LeadSale] {msg}")
            if self.persist_db:
                update_license_state(
                    "ATIVA",
                    msg,
                    last_ok=self.ultima_confirmacao,
                    next_check=self.proxima_consulta
                )
            return True, msg

        elif resposta is False:
            msg = "Robô não liberado para este escritório. Fale com a LeadSale."
            logging.error(f"[LeadSale] {msg}")
            if self.persist_db:
                update_license_state(
                    "BLOQUEADO",
                    msg,
                    next_check=agora + UMA_HORA
                )
                update_heartbeat("BLOQUEADO", msg)
            return False, msg

        else:
            # resposta is None: internet caiu ou LeadSale fora do ar
            self.proxima_consulta = agora + UMA_HORA
            if agora - self.ultima_confirmacao > 2 * UM_DIA:
                msg = "Sem confirmação da LeadSale. Robô parado."
                logging.error(f"[LeadSale] {msg}")
                if self.persist_db:
                    update_license_state(
                        "BLOQUEADO",
                        msg,
                        next_check=self.proxima_consulta
                    )
                    update_heartbeat("BLOQUEADO", msg)
                return False, msg

            msg = "Sem resposta da LeadSale — operando em contingência (nova tentativa em 1h)."
            logging.warning(f"[LeadSale] {msg}")
            if self.persist_db:
                update_license_state(
                    "CONTINGENCIA",
                    msg,
                    next_check=self.proxima_consulta
                )
            return True, msg
