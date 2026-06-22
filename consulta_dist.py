# ============================================================
# APP DE CONSULTA DE PEDIDOS – DISTRIBUIÇÃO
# Versão 2.0 – Visual Executivo + Admin protegido + Tempo real
# Autor: Ricardo Marchette Sabino
# ============================================================

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ------------------------------------------------------------
# CONFIGURAÇÃO BÁSICA DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Painel de Distribuição | Consulta de Pedidos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------
# ESTILO VISUAL (CSS personalizado)
# ------------------------------------------------------------
st.markdown("""
<style>
/* Fundo geral */
.main { background-color: #F5F7FA; }

/* Cabeçalho */
.header {
    background: linear-gradient(90deg, #0B2545 0%, #13315C 100%);
    padding: 28px 32px;
    border-radius: 12px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.header h1 {
    color: white;
    font-size: 26px;
    margin: 0;
    font-weight: 600;
}
.header p {
    color: #D9E2EC;
    margin: 4px 0 0 0;
    font-size: 14px;
}

/* KPIs */
[data-testid="stMetric"] {
    background-color: white;
    padding: 16px 20px;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-left: 4px solid #0B2545;
}
[data-testid="stMetricLabel"] {
    color: #5C6B7A !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    color: #0B2545 !important;
    font-size: 28px !important;
}

/* Cards de cliente */
.cliente-card {
    background-color: white;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-left: 4px solid #0B2545;
}
.cliente-nome { font-size: 16px; font-weight: 600; color: #0B2545; }
.cliente-pdv  { font-size: 13px; color: #5C6B7A; margin-top: 2px; }
.cliente-info { font-size: 13px; color: #2C3E50; margin-top: 8px; }

/* Botões */
.stButton>button {
    background-color: #0B2545;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 8px 18px;
    font-weight: 500;
}
.stButton>button:hover { background-color: #13315C; color: white; }

/* Esconde footer "Made with Streamlit" */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONSTANTES
# ------------------------------------------------------------
ARQUIVO_BASE = "base_pedidos.parquet"  # base salva no servidor
ARQUIVO_CONFIG = "config_filtros.txt"  # quais colunas o vendedor filtra
INTERVALO_REFRESH_MS = 30_000          # atualiza tela a cada 30 segundos

# ------------------------------------------------------------
# AUTO-REFRESH PARA OS VENDEDORES (tempo real)
# ------------------------------------------------------------
st_autorefresh(interval=INTERVALO_REFRESH_MS, key="refresh_vendedor")

# ------------------------------------------------------------
# FUNÇÕES DE APOIO
# ------------------------------------------------------------
def carregar_base_do_servidor():
    """Lê a base salva (que o admin subiu)."""
    if os.path.exists(ARQUIVO_BASE):
        df = pd.read_parquet(ARQUIVO_BASE)
        ts = os.path.getmtime(ARQUIVO_BASE)
        atualizado = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
        return df, atualizado
    return None, None

def salvar_base(df):
    df.to_parquet(ARQUIVO_BASE, index=False)

def ler_arquivo_upload(arquivo):
    if arquivo.name.endswith(".csv"):
        df = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig")
    else:
        df = pd.read_excel(arquivo)
    df.columns = df.columns.str.strip()
    return df

def salvar_config_filtros(colunas):
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        f.write("\n".join(colunas))

def ler_config_filtros():
    if os.path.exists(ARQUIVO_CONFIG):
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            return [l.strip() for l in f.readlines() if l.strip()]
    return []

def eh_distribuido(serie_status):
    """Considera contabilizando se o texto bate com sim/ok/contabiliz/distrib."""
    return serie_status.astype(str).str.lower().str.contains(
        "sim|ok|contabiliz|distrib", na=False
    )

# ------------------------------------------------------------
# CABEÇALHO
# ------------------------------------------------------------
st.markdown("""
<div class="header">
    <h1>📊 Painel de Distribuição</h1>
    <p>Consulta de pedidos em tempo real – Operação Comercial</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# LOGIN DE ADMIN (na sidebar)
# ------------------------------------------------------------
if "admin_logado" not in st.session_state:
    st.session_state.admin_logado = False

with st.sidebar:
    st.markdown("### 🔐 Acesso restrito")
    if not st.session_state.admin_logado:
        senha = st.text_input("Senha do administrador:", type="password")
        if st.button("Entrar"):
            try:
                senha_correta = st.secrets["admin_password"]
            except Exception:
                senha_correta = None

            if senha_correta and senha == senha_correta:
                st.session_state.admin_logado = True
                st.success("Acesso liberado.")
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        st.success("✅ Modo administrador")
        if st.button("Sair"):
            st.session_state.admin_logado = False
            st.rerun()

# ------------------------------------------------------------
# ÁREA DO ADMIN (upload e configuração)
# ------------------------------------------------------------
if st.session_state.admin_logado:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚙️ Atualizar base")
        upload = st.file_uploader("Selecione o arquivo (.xlsx ou .csv):", type=["xlsx", "csv"])
        if upload is not None:
            try:
                df_novo = ler_arquivo_upload(upload)
                salvar_base(df_novo)
                st.success(f"Base atualizada! {len(df_novo)} registros.")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

        # Configuração das colunas de filtro
        df_atual, _ = carregar_base_do_servidor()
        if df_atual is not None:
            st.markdown("### 🎛️ Filtros do vendedor")
            colunas_disponiveis = df_atual.columns.tolist()
            config_atual = ler_config_filtros()
            colunas_escolhidas = st.multiselect(
                "Quais colunas o vendedor poderá filtrar?",
                options=colunas_disponiveis,
                default=config_atual if config_atual else []
            )
            if st.button("💾 Salvar configuração"):
                salvar_config_filtros(colunas_escolhidas)
                st.success("Configuração salva.")

# ------------------------------------------------------------
# ÁREA PÚBLICA (vendedor)
# ------------------------------------------------------------
df, ultima_atualizacao = carregar_base_do_servidor()

if df is None:
    st.info("⏳ Base ainda não disponível. Volte em alguns instantes.")
    st.stop()

# Info de atualização
st.markdown(
    f"<p style='color:#5C6B7A;font-size:13px;'>🔄 Base atualizada em <b>{ultima_atualizacao}</b> "
    f"&nbsp;|&nbsp; Atualização automática a cada 30 segundos</p>",
    unsafe_allow_html=True
)

# Identifica colunas-chave (case-insensitive)
colunas_map = {c.lower(): c for c in df.columns}
col_cliente = colunas_map.get("cliente")
col_pdv     = colunas_map.get("pdv") or colunas_map.get("codigo pdv") or colunas_map.get("código pdv")
col_pedido  = colunas_map.get("pedido")
col_status  = colunas_map.get("status")

# ------------------------------------------------------------
# FILTROS (somente os liberados pelo admin)
# ------------------------------------------------------------
colunas_filtro = ler_config_filtros()
df_filtrado = df.copy()

if colunas_filtro:
    st.markdown("#### 🔎 Filtros")
    n = min(len(colunas_filtro), 4)
    cols = st.columns(n)
    for i, coluna in enumerate(colunas_filtro):
        if coluna in df.columns:
            valores = ["Todos"] + sorted(df[coluna].dropna().astype(str).unique().tolist())
            with cols[i % n]:
                escolha = st.selectbox(coluna, valores, key=f"f_{coluna}")
                if escolha != "Todos":
                    df_filtrado = df_filtrado[df_filtrado[coluna].astype(str) == escolha]

# Busca livre
busca = st.text_input("🔍 Buscar por nº do pedido, cliente ou PDV:")
if busca:
    mascara = pd.Series([False] * len(df_filtrado), index=df_filtrado.index)
    for c in [col_pedido, col_cliente, col_pdv]:
        if c:
            mascara |= df_filtrado[c].astype(str).str.contains(busca, case=False, na=False)
    df_filtrado = df_filtrado[mascara]

# ------------------------------------------------------------
# KPIs DO TOPO
# ------------------------------------------------------------
st.markdown("---")
total_pedidos = len(df_filtrado)
if col_status:
    distribuidos = eh_distribuido(df_filtrado[col_status]).sum()
else:
    distribuidos = 0
nao_distribuidos = total_pedidos - distribuidos
taxa = (distribuidos / total_pedidos * 100) if total_pedidos else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de pedidos", f"{total_pedidos:,}".replace(",", "."))
k2.metric("✅ Contabilizando", f"{distribuidos:,}".replace(",", "."))
k3.metric("❌ Não contabilizando", f"{nao_distribuidos:,}".replace(",", "."))
k4.metric("📈 Taxa de distribuição", f"{taxa:.1f}%")

st.markdown("---")

# ------------------------------------------------------------
# CARDS POR CLIENTE
# ------------------------------------------------------------
st.markdown("### 🏪 Clientes")

if not col_cliente:
    st.warning("Sua base não tem uma coluna 'cliente'. Ajuste o nome da coluna e tente novamente.")
    st.stop()

# Agrupa por cliente (+ pdv se existir)
chaves = [col_cliente] + ([col_pdv] if col_pdv else [])
grupos = df_filtrado.groupby(chaves, dropna=False)

if len(grupos) == 0:
    st.info("Nenhum pedido encontrado com os filtros atuais.")
else:
    for chave, dados in grupos:
        if isinstance(chave, tuple):
            nome_cliente = str(chave[0])
            pdv = str(chave[1]) if len(chave) > 1 else "—"
        else:
            nome_cliente = str(chave)
            pdv = "—"

        qtd_pedidos = len(dados)
        if col_status:
            qtd_distrib = int(eh_distribuido(dados[col_status]).sum())
        else:
            qtd_distrib = 0

        # Bloco expansível (card)
        with st.expander(
            f"🏪  {nome_cliente}   •   PDV: {pdv}   "
            f"|   📦 {qtd_pedidos} pedidos   "
            f"|   ✅ {qtd_distrib} distribuições"
        ):
            st.dataframe(
                dados.reset_index(drop=True),
                use_container_width=True,
                hide_index=True
            )
