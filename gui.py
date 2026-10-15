import os
import sys
import time
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

from db import (
    init_db,
    get_heartbeat,
    get_stats_today,
    set_bot_paused,
    is_bot_paused,
    trigger_force_check
)

BASE_DIR = Path(__file__).resolve().parent

class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Painel de Controle - Automação Salesforce C6")
        self.root.geometry("700x560")
        self.root.minsize(650, 520)
        self.root.configure(bg="#0F172A")

        self.bot_thread = None
        self.dashboard_process = None

        self._setup_style()
        self._build_ui()
        self._start_background_services()
        self._poll_status()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0F172A")
        style.configure("TLabel", background="#0F172A", foreground="#F8FAFC", font=("Helvetica", 10))

    def _build_ui(self):
        # 1. Top Header
        header_frame = tk.Frame(self.root, bg="#1E293B", padx=20, pady=15)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = tk.Label(
            header_frame,
            text="🤖 Robô de Cadastro de Leads - Salesforce C6",
            font=("Helvetica", 14, "bold"),
            bg="#1E293B",
            fg="#FFFFFF"
        )
        title_lbl.pack(anchor="w")

        # Status Badge & Subtext
        status_sub_frame = tk.Frame(header_frame, bg="#1E293B")
        status_sub_frame.pack(fill="x", pady=(8, 0))

        tk.Label(status_sub_frame, text="Status Atual:", font=("Helvetica", 10), bg="#1E293B", fg="#94A3B8").pack(side="left")
        
        self.status_badge = tk.Label(
            status_sub_frame,
            text="INICIANDO...",
            font=("Helvetica", 10, "bold"),
            bg="#3B82F6",
            fg="#FFFFFF",
            padx=10,
            pady=2
        )
        self.status_badge.pack(side="left", padx=10)

        self.activity_label = tk.Label(
            header_frame,
            text="Carregando serviços...",
            font=("Helvetica", 9, "italic"),
            bg="#1E293B",
            fg="#CBD5E1"
        )
        self.activity_label.pack(anchor="w", pady=(6, 0))

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
            padx=15,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._toggle_pause
        )
        self.pause_btn.pack(side="left", padx=(0, 8))

        self.check_now_btn = tk.Button(
            btn_frame,
            text="🔄 Verificar Planilha Agora",
            font=("Helvetica", 10),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._force_check
        )
        self.check_now_btn.pack(side="left", padx=4)

        self.dashboard_btn = tk.Button(
            btn_frame,
            text="🌐 Abrir Dashboard Web",
            font=("Helvetica", 10),
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            padx=12,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=self._open_dashboard
        )
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

        # Inicia o Dashboard Streamlit em segundo plano
        try:
            self.dashboard_process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.headless=true", "--server.port=8501"],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Erro ao iniciar dashboard: {e}")

        # Inicia a thread do robô
        from main import run_automation_loop
        self.bot_thread = threading.Thread(target=run_automation_loop, daemon=True)
        self.bot_thread.start()

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

    def _open_dashboard(self):
        webbrowser.open("http://localhost:8501")

    def _poll_status(self):
        try:
            hb = get_heartbeat() or {}
            state = hb.get("state", "OCIOSO")
            action = hb.get("current_action", "")
            
            # Atualiza Badge de Status
            state_styles = {
                "DESLIGADO": ("#EF4444", "🔴 OFFLINE / DESLIGADO"),
                "INICIANDO": ("#3B82F6", "INICIANDO..."),
                "AGUARDANDO_LOGIN": ("#8B5CF6", "🔑 FAÇA LOGIN NO CHROME"),
                "PROCESSANDO": ("#3B82F6", "⚡ CADASTRANDO LEAD"),
                "AGUARDANDO_INTERVALO": ("#F59E0B", "⏱️ AGUARDANDO INTERVALO"),
                "OCIOSO": ("#10B981", "🟢 EM OPERAÇÃO (OCIOSO)"),
                "PAUSADO": ("#EF4444", "⏸️ PAUSADO"),
                "ERRO": ("#EF4444", "⚠️ ERRO")
            }
            bg_color, display_text = state_styles.get(state, ("#64748B", state))
            self.status_badge.configure(text=display_text, bg=bg_color)
            self.activity_label.configure(text=f"📌 {action}")

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

            # Atualiza Logs
            log_file = BASE_DIR / "bot_execution.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-30:] # Últimas 30 linhas
                    self.log_text.delete("1.0", tk.END)
                    self.log_text.insert(tk.END, "".join(lines))
                    self.log_text.see(tk.END)

        except Exception as e:
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
