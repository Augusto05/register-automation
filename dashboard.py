import streamlit as st
import pandas as pd
from datetime import datetime
import time
from db import get_heartbeat, get_all_leads, get_stats_today

# Configuração da página
st.set_page_config(
    page_title="Monitor de Cadastro de Leads - Salesforce C6",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS para visual moderno e profissional
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border-radius: 10px;
        padding: 18px 24px;
        border-left: 5px solid #0052FF;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-success { background-color: #10B98122; color: #10B981; border: 1px solid #10B981; }
    .badge-error { background-color: #EF444422; color: #EF4444; border: 1px solid #EF4444; }
    .badge-warning { background-color: #F59E0B22; color: #F59E0B; border: 1px solid #F59E0B; }
</style>
""", unsafe_allow_html=True)

# Barra Lateral
st.sidebar.title("⚡ Painel de Controle")
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto-atualizar a cada 10s", value=True)
if auto_refresh:
    time.sleep(1)
    st.sidebar.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

# Header
st.title("🤖 Monitor de Automação de Leads - C6 Bank")
st.markdown("Acompanhamento em tempo real da RPA de indicação de leads no Salesforce.")

# Heartbeat e Status do Robô
hb = get_heartbeat() or {}
bot_state = hb.get("state", "DESCONHECIDO")
current_action = hb.get("current_action", "Aguardando informações...")
last_ping = hb.get("last_ping", "N/A")

status_colors = {
    "PROCESSANDO": "#3B82F6",
    "AGUARDANDO_INTERVALO": "#F59E0B",
    "OCIOSO": "#10B981",
    "AGUARDANDO_LOGIN": "#8B5CF6",
    "PAUSADO": "#F59E0B",
    "ERRO": "#EF4444",
    "DESLIGADO": "#EF4444",
    "PARADO": "#6B7280"
}
state_color = status_colors.get(bot_state, "#6B7280")

st.markdown(f"""
<div style="background-color: #111827; border: 1px solid #374151; border-radius: 12px; padding: 16px 20px; margin-bottom: 25px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span style="color: #9CA3AF; font-size: 0.9rem;">Status do Robô:</span>
            <span style="background-color: {state_color}22; color: {state_color}; border: 1px solid {state_color}; padding: 3px 10px; border-radius: 6px; font-weight: bold; margin-left: 8px;">
                {bot_state}
            </span>
        </div>
        <div style="color: #9CA3AF; font-size: 0.85rem;">
            Último batimento: <strong>{last_ping}</strong>
        </div>
    </div>
    <div style="margin-top: 10px; font-size: 1.05rem; color: #F3F4F6;">
        📌 <strong>Atividade atual:</strong> {current_action}
    </div>
</div>
""", unsafe_allow_html=True)

# KPIs do Dia
stats = get_stats_today()
total = stats["total"]
cadastrados = stats["cadastrados"]
indisponiveis = stats["indisponiveis"]
taxa_sucesso = f"{(cadastrados / total * 100):.1f}%" if total > 0 else "0%"

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Hoje", total)
with col2:
    st.metric("Cadastrados com Sucesso", cadastrados, delta="Ativos")
with col3:
    st.metric("Indisponíveis / Erros", indisponiveis, delta_color="inverse")
with col4:
    st.metric("Taxa de Conversão", taxa_sucesso)

st.markdown("---")

# Tabela e Histórico
st.subheader("📋 Leads e Histórico de Processamento")
leads = get_all_leads()

if not leads:
    # Se não houver histórico local (ex: no Streamlit Cloud), carrega os leads diretamente da Planilha Online
    from sheets import fetch_pending_leads
    pending = fetch_pending_leads()
    if pending:
        leads = [{
            "processed_at": "Pendente",
            "cnpj": p["cnpj"],
            "razao_social": p["razao_social"],
            "telefone": p["telefone"],
            "email": p["email"],
            "status": "PENDENTE",
            "error_message": "Aguardando processamento pelo robô"
        } for p in pending]

if leads:
    df = pd.DataFrame(leads)
    
    # Filtros
    f_col1, f_col2 = st.columns([1, 2])
    with f_col1:
        status_options = ["Todos"] + sorted(list(df["status"].dropna().unique()))
        status_filter = st.selectbox("Filtrar por Status", status_options)
    with f_col2:
        search_query = st.text_input("Buscar por CNPJ ou Razão Social", "")

    if status_filter != "Todos":
        df = df[df["status"] == status_filter]

    if search_query:
        query = search_query.lower()
        df = df[df["cnpj"].str.lower().str.contains(query, na=False) | df["razao_social"].str.lower().str.contains(query, na=False)]

    # Exibição da tabela formatada
    cols_to_show = ["processed_at", "cnpj", "razao_social", "telefone", "email", "status", "error_message"]
    display_df = df[cols_to_show].rename(columns={
        "processed_at": "Data/Hora",
        "cnpj": "CNPJ",
        "razao_social": "Razão Social",
        "telefone": "Telefone",
        "email": "E-mail",
        "status": "Status",
        "error_message": "Detalhes / Motivo"
    })

    st.dataframe(display_df, use_container_width=True, height=420)

    # Botão de exportação
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Relatório em CSV",
        data=csv_data,
        file_name=f"relatorio_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
else:
    st.info("Nenhum lead encontrado na planilha online.")
