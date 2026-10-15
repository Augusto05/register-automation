import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    print("=" * 65)
    print("   AUTOMAÇÃO 24/7 SALESFORCE C6 BANK + DASHBOARD STREAMLIT")
    print("=" * 65)
    print("\n[1/3] Verificando dependências...")

    # Garante que as dependências estão instaladas
    req_file = BASE_DIR / "requirements.txt"
    if req_file.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)], check=False)

    # Garante o chromium do playwright
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    except Exception:
        pass

    print("[2/3] Iniciando o Dashboard Streamlit...")
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.headless=true", "--server.port=8501"],
        cwd=str(BASE_DIR)
    )

    time.sleep(3)
    # Abre o Dashboard no navegador padrão do usuário
    webbrowser.open("http://localhost:8501")

    print("[3/3] Iniciando o Robô 24/7 (Chrome abrirá para o Salesforce)...")
    print("-> Se for a primeira vez, faça o login normalmente na janela do Chrome.")
    print("-> A sessão ficará salva permanentemente no perfil local.\n")

    try:
        # Executa o loop principal da automação
        from main import run_automation_loop
        run_automation_loop()
    except KeyboardInterrupt:
        print("\nFinalizando processos...")
    finally:
        dashboard_process.terminate()
        print("Finalizado com sucesso.")

if __name__ == "__main__":
    main()
