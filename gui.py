import os
import re
import sys
import time
import threading
import subprocess
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

from config import BASE_DIR
from db import (
    init_db,
    get_heartbeat,
    get_license_state,
    get_stats_today,
    set_bot_paused,
    is_bot_paused,
    trigger_force_check
)
from license import (
    token_esta_configurado,
    salvar_token
)

_TOKEN_REGEX = re.compile(r"lri_[A-Za-z0-9_\-]+")


class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Painel de Controle - Robô de Indicação LeadSale (Salesforce C6)")
        self.root.geometry("760x600")
        self.root.minsize(700, 550)
        self.root.configure(bg="#0F172A")

        self.bot_thread = None
        self.dashboard_process = None
        self.token_modal = None
        self.last_manual_retry_ts = 0.0

        self._setup_style()
        self._build_ui()
        self._start_background_services()
        self._poll_status()

        # Se o escritório ainda não configurou o leadsale_token.txt, abre a janela de configuração automaticamente
        if not token_esta_configurado():
            self.root.after(600, self._open_token_modal)

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0F172A")
        style.configure("TLabel", background="#0F172A", foreground="#F8FAFC", font=("Helvetica", 10))

    def _build_ui(self):
        # 1. Top Header
        header_frame = tk.Frame(self.root, bg="#1E293B", padx=20, pady=14)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        top_title_row = tk.Frame(header_frame, bg="#1E293B")
        top_title_row.pack(fill="x")

        title_lbl = tk.Label(
            top_title_row,
            text="🤖 Robô de Indicação LeadSale — Salesforce C6",
            font=("Helvetica", 14, "bold"),
            bg="#1E293B",
            fg="#FFFFFF"
        )
        title_lbl.pack(side="left", anchor="w")

        # Status Badge & License Badge Row
        status_sub_frame = tk.Frame(header_frame, bg="#1E293B")
        status_sub_frame.pack(fill="x", pady=(10, 0))

        tk.Label(
            status_sub_frame,
            text="Status do Robô:",
            font=("Helvetica", 10),
            bg="#1E293B",
            fg="#94A3B8"
        ).pack(side="left")

        self.status_badge = tk.Label(
            status_sub_frame,
            text="INICIANDO...",
            font=("Helvetica", 9, "bold"),
            bg="#3B82F6",
            fg="#FFFFFF",
            padx=10,
            pady=2
        )
        self.status_badge.pack(side="left", padx=(6, 18))

        tk.Label(
            status_sub_frame,
            text="Assinatura LeadSale:",
            font=("Helvetica", 10),
            bg="#1E293B",
            fg="#94A3B8"
        ).pack(side="left")

        self.license_badge = tk.Label(
            status_sub_frame,
            text="VERIFICANDO...",
            font=("Helvetica", 9, "bold"),
            bg="#64748B",
            fg="#FFFFFF",
            padx=10,
            pady=2
        )
        self.license_badge.pack(side="left", padx=6)

        self.activity_label = tk.Label(
            header_frame,
            text="Carregando serviços...",
            font=("Helvetica", 9, "italic"),
            bg="#1E293B",
            fg="#CBD5E1"
        )
        self.activity_label.pack(anchor="w", pady=(8, 0))

        self.license_detail_label = tk.Label(
            header_frame,
            text="🔐 Verificando liberação do escritório na LeadSale...",
            font=("Helvetica", 9),
            bg="#1E293B",
            fg="#94A3B8"
        )
        self.license_detail_label.pack(anchor="w", pady=(3, 0))

        # 2. Metrics Cards
        metrics_frame = tk.Frame(self.root, bg="#0F172A")
        metrics_frame.pack(fill="x", padx=15, pady=5)

        self.card_cadastrados = self._create_card(metrics_frame, "Cadastrados Hoje", "0", "#10B981")
        self.card_indisponiveis = self._create_card(metrics_frame, "Indisponíveis", "0", "#EF4444")
        self.card_total = self._create_card(metrics_frame, "Total Processado", "0", "#3B82F6")

        self.card_cadastrados.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.card_indisponiveis.pack(side="left", fill="both", expand=True, padx=3)
        self.card_total.pack(side="left", fill="both", expand=True, padx=(6, 0))

        # 3. Action Buttons Bar
        btn_frame = tk.Frame(self.root, bg="#0F172A", pady=10)
        btn_frame.pack(fill="x", padx=15)

        self.pause_btn = tk.Button(
            btn_frame,
            text="⏸️ Pausar Robô",
            font=("Helvetica", 10, "bold"),
            bg="#F59E0B",
            fg="#000000",
            activebackground="#D97706",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._toggle_pause
        )
        self.pause_btn.pack(side="left", padx=(0, 6))

        self.login_done_btn = tk.Button(
            btn_frame,
            text="✅ Já fiz o Login!",
            font=("Helvetica", 10, "bold"),
            bg="#10B981",
            fg="#FFFFFF",
            activebackground="#059669",
            padx=10,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._confirm_login
        )
        self.login_done_btn.pack(side="left", padx=4)

        self.check_now_btn = tk.Button(
            btn_frame,
            text="🔄 Verificar Planilha",
            font=("Helvetica", 10),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            padx=10,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._force_check
        )
        self.check_now_btn.pack(side="left", padx=4)

        self.token_btn = tk.Button(
            btn_frame,
            text="🔑 Configurar Token",
            font=("Helvetica", 10, "bold"),
            bg="#6366F1",
            fg="#FFFFFF",
            activebackground="#4F46E5",
            padx=10,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._open_token_modal
        )
        self.token_btn.pack(side="left", padx=4)

        self.dashboard_btn = tk.Button(
            btn_frame,
            text="🌐 Dashboard Web",
            font=("Helvetica", 10),
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            padx=10,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._open_dashboard
        )
        if not getattr(sys, "frozen", False):
            self.dashboard_btn.pack(side="right")

        # 4. Live Logs Console
        log_frame = tk.LabelFrame(
            self.root,
            text=" Logs de Execução em Tempo Real ",
            font=("Helvetica", 9, "bold"),
            bg="#0F172A",
            fg="#94A3B8",
            padx=10,
            pady=5
        )
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.log_text = ScrolledText(
            log_frame,
            bg="#020617",
            fg="#E2E8F0",
            insertbackground="#FFFFFF",
            font=("Courier", 9),
            relief="flat"
        )
        self.log_text.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_card(self, parent, title, initial_val, color):
        f = tk.Frame(parent, bg="#1E293B", padx=15, pady=12, relief="flat")
        t = tk.Label(f, text=title, font=("Helvetica", 9), bg="#1E293B", fg="#94A3B8")
        t.pack(anchor="w")
        v = tk.Label(f, text=initial_val, font=("Helvetica", 18, "bold"), bg="#1E293B", fg=color)
        v.pack(anchor="w", pady=(4, 0))
        f.val_label = v
        return f

    def _start_background_services(self):
        init_db()

        # Inicia o Dashboard Streamlit em segundo plano apenas quando executado via ambiente Python completo
        if not getattr(sys, "frozen", False):
            try:
                self.dashboard_process = subprocess.Popen(
                    [sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.headless=true", "--server.port=8501"],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"Erro ao iniciar dashboard: {e}")

        self._start_bot_thread_if_needed()

    def _start_bot_thread_if_needed(self):
        if self.bot_thread and self.bot_thread.is_alive():
            return
        from main import run_automation_loop
        self.bot_thread = threading.Thread(target=run_automation_loop, daemon=True)
        self.bot_thread.start()

    def _open_token_modal(self):
        if self.token_modal and self.token_modal.winfo_exists():
            self.token_modal.lift()
            self.token_modal.focus_force()
            return

        modal = tk.Toplevel(self.root)
        modal.title("🔑 Configurar Token de Assinatura — LeadSale")
        modal.geometry("520x340")
        modal.resizable(False, False)
        modal.configure(bg="#0F172A")
        modal.transient(self.root)
        modal.grab_set()
        self.token_modal = modal

        container = tk.Frame(modal, bg="#1E293B", padx=20, pady=18)
        container.pack(fill="both", expand=True, padx=15, pady=15)

        tk.Label(
            container,
            text="🔑 Token do Escritório (LeadSale)",
            font=("Helvetica", 12, "bold"),
            bg="#1E293B",
            fg="#FFFFFF"
        ).pack(anchor="w")

        status_atual = "Configurado (oculto por segurança)" if token_esta_configurado() else "Não configurado"
        cor_status = "#10B981" if token_esta_configurado() else "#F59E0B"

        tk.Label(
            container,
            text=f"Arquivo leadsale_token.txt: {status_atual}",
            font=("Helvetica", 9, "bold"),
            bg="#1E293B",
            fg=cor_status
        ).pack(anchor="w", pady=(6, 10))

        tk.Label(
            container,
            text="Cole abaixo o token recebido da LeadSale (começa com lri_):",
            font=("Helvetica", 9),
            bg="#1E293B",
            fg="#CBD5E1"
        ).pack(anchor="w")

        entry_row = tk.Frame(container, bg="#1E293B")
        entry_row.pack(fill="x", pady=(6, 10))

        token_var = tk.StringVar()
        entry = tk.Entry(
            entry_row,
            textvariable=token_var,
            show="•",
            font=("Courier", 11),
            bg="#020617",
            fg="#F8FAFC",
            insertbackground="#FFFFFF",
            relief="flat"
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        def _colar_unico(_event=None):
            try:
                clip = self.root.clipboard_get().strip()
                token_var.set(clip)
                entry.icursor(tk.END)
            except Exception:
                pass
            return "break"

        # Evita colagem duplicada no Tkinter (comum no macOS ao usar Cmd+V)
        entry.bind("<Command-v>", _colar_unico)
        entry.bind("<Control-v>", _colar_unico)

        paste_btn = tk.Button(
            entry_row,
            text="📋 Colar",
            font=("Helvetica", 9, "bold"),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            padx=10,
            pady=5,
            relief="flat",
            cursor="hand2",
            command=_colar_unico
        )
        paste_btn.pack(side="right")
        entry.focus_set()

        aviso_txt = (
            "🔒 Cuidados importantes:\n"
            "• O token é uma senha secreta: nunca aparece na tela nem nos logs.\n"
            "• Se aparecer 'Robô não liberado' na 1ª vez, avise a LeadSale para liberar a internet.\n"
            "• Não tente tokens errados várias vezes seguidas (bloqueia a internet por 1 hora)."
        )
        tk.Label(
            container,
            text=aviso_txt,
            justify="left",
            font=("Helvetica", 8),
            bg="#1E293B",
            fg="#94A3B8"
        ).pack(anchor="w", pady=(0, 14))

        btn_row = tk.Frame(container, bg="#1E293B")
        btn_row.pack(fill="x")

        def _salvar_e_validar():
            sucesso, msg = salvar_token(token_var.get())
            if not sucesso:
                messagebox.showwarning("Token Inválido", msg, parent=modal)
                return

            agora = time.time()
            if agora - self.last_manual_retry_ts < 15:
                messagebox.showinfo(
                    "Token Salvo",
                    "Token gravado em leadsale_token.txt! Aguarde alguns segundos antes de uma nova consulta à LeadSale.",
                    parent=modal
                )
                modal.destroy()
                return

            self.last_manual_retry_ts = agora
            modal.destroy()
            self.activity_label.configure(text="Token atualizado! Validando assinatura na LeadSale...")
            self._start_bot_thread_if_needed()

        save_btn = tk.Button(
            btn_row,
            text="💾 Salvar Token e Validar",
            font=("Helvetica", 10, "bold"),
            bg="#10B981",
            fg="#FFFFFF",
            activebackground="#059669",
            padx=14,
            pady=6,
            relief="flat",
            cursor="hand2",
            command=_salvar_e_validar
        )
        save_btn.pack(side="left")

        cancel_btn = tk.Button(
            btn_row,
            text="Cancelar",
            font=("Helvetica", 10),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
            command=modal.destroy
        )
        cancel_btn.pack(side="right")

    def _toggle_pause(self):
        currently_paused = is_bot_paused()
        set_bot_paused(not currently_paused)
        if not currently_paused:
            self.pause_btn.configure(text="▶️ Retomar Robô", bg="#10B981")
        else:
            self.pause_btn.configure(text="⏸️ Pausar Robô", bg="#F59E0B")

    def _force_check(self):
        trigger_force_check()
        self.activity_label.configure(text="Solicitando verificação antecipada da planilha...")

    def _confirm_login(self):
        from db import confirm_manual_login
        confirm_manual_login()
        self.activity_label.configure(text="Login confirmado! Robô acessando os Leads...")
        self.login_done_btn.configure(state="disabled", text="✅ Login OK")

    def _open_dashboard(self):
        webbrowser.open("http://localhost:8501")

    def _poll_status(self):
        try:
            hb = get_heartbeat() or {}
            lic = get_license_state() or {}

            state = hb.get("state", "OCIOSO")
            action = hb.get("current_action", "")

            lic_status = lic.get("license_status", "VERIFICANDO")
            lic_msg = lic.get("license_message", "")
            last_ok = lic.get("last_license_ok", 0.0)

            # Atualiza Badge de Status do Robô
            state_styles = {
                "DESLIGADO": ("#EF4444", "🔴 OFFLINE / DESLIGADO"),
                "INICIANDO": ("#3B82F6", "INICIANDO..."),
                "AGUARDANDO_LOGIN": ("#8B5CF6", "🔑 FAÇA LOGIN NO CHROME"),
                "PROCESSANDO": ("#3B82F6", "⚡ CADASTRANDO LEAD"),
                "AGUARDANDO_INTERVALO": ("#F59E0B", "⏱️ AGUARDANDO INTERVALO"),
                "CONSULTANDO_PLANILHA": ("#3B82F6", "🔍 CONSULTANDO PLANILHA"),
                "OCIOSO": ("#10B981", "🟢 EM OPERAÇÃO (OCIOSO)"),
                "PAUSADO": ("#F59E0B", "⏸️ PAUSADO"),
                "BLOQUEADO": ("#EF4444", "🚫 NÃO LIBERADO (PARADO)"),
                "TOKEN_AUSENTE": ("#EF4444", "🔑 CONFIGURE O TOKEN"),
                "ERRO": ("#EF4444", "⚠️ ERRO")
            }
            bg_color, display_text = state_styles.get(state, ("#64748B", state))
            self.status_badge.configure(text=display_text, bg=bg_color)
            self.activity_label.configure(text=f"📌 {action}")

            # Atualiza Badge da Assinatura LeadSale
            license_styles = {
                "ATIVA": ("#10B981", "🟢 LIBERADO"),
                "CONTINGENCIA": ("#F59E0B", "🟡 RECONECTANDO (1H)"),
                "BLOQUEADO": ("#EF4444", "🔴 NÃO LIBERADO"),
                "TOKEN_AUSENTE": ("#EF4444", "🔑 TOKEN AUSENTE"),
                "VERIFICANDO": ("#64748B", "⏳ VERIFICANDO...")
            }
            lic_bg, lic_text = license_styles.get(lic_status, ("#64748B", lic_status))
            self.license_badge.configure(text=lic_text, bg=lic_bg)

            detail_suffix = ""
            if last_ok and last_ok > 0:
                dt_str = datetime.fromtimestamp(last_ok).strftime("%d/%m às %H:%M")
                detail_suffix = f" (Última confirmação: {dt_str})"
            self.license_detail_label.configure(
                text=f"🔐 {lic_msg}{detail_suffix}",
                fg="#FCA5A5" if lic_status in ("BLOQUEADO", "TOKEN_AUSENTE") else "#94A3B8"
            )

            # Habilita/desabilita botões operacionais caso bloqueado pela LeadSale
            bloqueado = state in ("BLOQUEADO", "TOKEN_AUSENTE") or lic_status in ("BLOQUEADO", "TOKEN_AUSENTE")
            btn_state = "disabled" if bloqueado else "normal"
            self.pause_btn.configure(state=btn_state)
            self.check_now_btn.configure(state=btn_state)
            if bloqueado:
                self.login_done_btn.configure(state="disabled")

            # Atualiza Botão de Pausa se sincronizado
            if is_bot_paused():
                self.pause_btn.configure(text="▶️ Retomar Robô", bg="#10B981")
            else:
                self.pause_btn.configure(text="⏸️ Pausar Robô", bg="#F59E0B")

            # Atualiza Métricas
            stats = get_stats_today()
            self.card_cadastrados.val_label.configure(text=str(stats["cadastrados"]))
            self.card_indisponiveis.val_label.configure(text=str(stats["indisponiveis"]))
            self.card_total.val_label.configure(text=str(stats["total"]))

            # Atualiza Logs (garantindo que nenhum token apareça na tela)
            log_file = BASE_DIR / "bot_execution.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-30:]
                    safe_content = _TOKEN_REGEX.sub("lri_[OCULTO]", "".join(lines))
                    self.log_text.delete("1.0", tk.END)
                    self.log_text.insert(tk.END, safe_content)
                    self.log_text.see(tk.END)

        except Exception:
            pass

        # Repete a cada 1.5s
        self.root.after(1500, self._poll_status)

    def _on_close(self):
        if messagebox.askokcancel("Encerrar Robô", "Deseja realmente encerrar a automação 24/7?"):
            if self.dashboard_process:
                self.dashboard_process.terminate()
            self.root.destroy()
            sys.exit(0)


def main():
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
