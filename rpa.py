import re
import time
import random
from typing import Dict, Any, Tuple
from playwright.sync_api import sync_playwright, BrowserContext, Page
from config import SALESFORCE_LEADS_URL, CHROME_PROFILE_DIR

class SalesforceRPA:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

    def start(self):
        """Inicia o navegador com perfil persistente para manter a sessão ativa."""
        self.playwright = sync_playwright().start()
        
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-sandbox"
        ]

        try:
            # Tenta abrir o Google Chrome instalado na máquina Windows
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE_DIR,
                channel="chrome",
                headless=self.headless,
                args=launch_args,
                no_viewport=True
            )
        except Exception:
            # Fallback para o Chromium integrado do Playwright caso o Chrome padrão dê erro
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE_DIR,
                headless=self.headless,
                args=launch_args,
                no_viewport=True
            )

        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        self.page.set_default_timeout(25000)

    def stop(self):
        """Encerra a sessão do navegador com segurança."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    def navigate_to_leads(self):
        """Navega para a tela de Leads do C6 Salesforce."""
        current_url = self.page.url
        if "lead/Lead" not in current_url:
            self.page.goto(SALESFORCE_LEADS_URL, wait_until="networkidle")
        else:
            self.page.goto(SALESFORCE_LEADS_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)

    def is_logged_in(self) -> bool:
        """Verifica se a tela do parceiro está carregada ou se caiu na tela de login."""
        return "login" not in self.page.url.lower() and "partners" in self.page.url.lower()

    def split_razao_social(self, razao: str) -> Tuple[str, str]:
        """
        Divide a Razão Social em Primeiro Nome e Sobrenome.
        Garante que Sobrenome (campo obrigatório no Salesforce) nunca fique vazio.
        """
        parts = razao.strip().split()
        if not parts:
            return "Lead", "Empresa"
        if len(parts) == 1:
            return parts[0], parts[0]
        
        first_name = parts[0]
        last_name = " ".join(parts[1:])
        return first_name, last_name

    def register_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o fluxo completo de cadastro do Lead no Salesforce C6.
        """
        cnpj = lead_data.get("cnpj", "")
        razao_social = lead_data.get("razao_social", "")
        email = lead_data.get("email", "")
        telefone = lead_data.get("telefone", "")

        first_name, last_name = self.split_razao_social(razao_social)

        try:
            self.navigate_to_leads()

            # 1. Clicar no botão 'Novo Lead'
            novo_btn = self.page.locator('button:has-text("Novo Lead")')
            novo_btn.wait_for(state="visible", timeout=15000)
            novo_btn.click()

            # 2. Aguardar abertura do Modal
            modal = self.page.locator('section[role="dialog"]')
            modal.wait_for(state="visible", timeout=10000)
            self.page.wait_for_timeout(1000)

            # 3. Preenchimento dos campos mapeados
            # Primeiro Nome
            first_input = modal.locator('input[name="firstName"]')
            if first_input.count() > 0:
                first_input.fill(first_name)

            # Sobrenome (*)
            last_input = modal.locator('input[name="lastName"]')
            last_input.fill(last_name)

            # Razão Social (*)
            razao_input = modal.locator('input[name="RazaoSocial__c"]')
            razao_input.fill(razao_social)

            # CNPJ (*) - Somente números sem formatação
            cnpj_input = modal.locator('input[name="CNPJ__c"]')
            clean_digits_cnpj = re.sub(r"\D", "", cnpj)
            cnpj_input.fill(clean_digits_cnpj)

            # Telefone (*) - 55 + 11 dígitos
            phone_input = modal.locator('input[name="Phone"]')
            phone_input.fill(telefone)

            # E-mail (*)
            email_input = modal.locator('input[name="Email"]')
            email_input.fill(email)

            self.page.wait_for_timeout(800)

            # 4. Clicar em 'Confirmar'
            confirm_btn = modal.locator('button:has-text("Confirmar")')
            confirm_btn.click()

            # 5. Avaliação do resultado (Sucesso ou Erro)
            # Aguarda até 8 segundos para fechamento do modal ou mensagem de erro
            start_time = time.time()
            has_error = False
            error_message = ""

            while time.time() - start_time < 8:
                # Verifica mensagens de erro / toasts
                toast_error = self.page.locator('.slds-notify_toast.slds-theme_error, div[role="alert"], .slds-has-error')
                if toast_error.count() > 0 and toast_error.first.is_visible():
                    error_message = toast_error.first.inner_text().strip()
                    has_error = True
                    break

                # Verifica se o modal fechou com sucesso
                if not modal.is_visible():
                    break

                self.page.wait_for_timeout(500)

            # Se ainda houver modal aberto ou erro detectado
            if has_error or modal.is_visible():
                if not error_message:
                    # Tenta ler qualquer texto de ajuda ou erro dentro do modal
                    help_texts = modal.locator('.slds-form-element__help').all_inner_texts()
                    error_message = " | ".join([h.strip() for h in help_texts if h.strip()]) or "Erro ao validar campos ou lead indisponível"

                # Fecha o modal clicando em Cancelar para limpar a tela
                cancel_btn = modal.locator('button[title="Cancelar e fechar"]')
                if cancel_btn.count() > 0 and cancel_btn.is_visible():
                    cancel_btn.click()
                else:
                    self.page.reload()

                return {
                    "success": False,
                    "status": "INDISPONIVEL",
                    "error": error_message
                }

            # Modal fechou com sucesso!
            return {
                "success": True,
                "status": "CADASTRADO",
                "error": ""
            }

        except Exception as e:
            # Em caso de qualquer exceção, recarrega a página para restabelecer o estado limpo
            try:
                self.page.reload()
            except Exception:
                pass
            return {
                "success": False,
                "status": "INDISPONIVEL",
                "error": str(e)
            }

    def keep_alive_interaction(self):
        """
        Interação suave anti-logoff periódica (a cada 4 min quando ocioso).
        Recarrega a lista de leads para manter tokens e sessão vivos.
        """
        try:
            self.page.goto(SALESFORCE_LEADS_URL, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
            # Clica no botão de refresh da lista se disponível
            refresh_btn = self.page.locator('a[role="button"]:has-text("Refresh"), button[title*="Atualizar"]')
            if refresh_btn.count() > 0 and refresh_btn.first.is_visible():
                refresh_btn.first.click()
        except Exception as e:
            print(f"[KeepAlive] Aviso na interação anti-logoff: {e}")
