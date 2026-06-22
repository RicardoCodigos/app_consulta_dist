# ============================================================
# PAINEL DE DISTRIBUIÇÃO – CORA
# Versão 3.0 – Adaptada para a base CORA
# Autor: Ricardo Marchette Sabino
# ============================================================

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ------------------------------------------------------------
# CONFIGURAÇÃO BÁSICA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Painel de Distribuição | CORA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------
# ESTILO VISUAL
# ------------------------------------------------------------
st.markdown("""
<style>
.main { background-color: #F5F7FA; }

.header {
    background: linear-gradient(90deg, #0B2545 0%, #13315C 100%);
    padding: 28px 32px;
    border-radius: 12px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.header h1 { color: white; font-size: 26px; margin: 0; font-weight: 600; }
.header p  { color: #D9E2EC; margin: 4px 0 0 0; font-size: 14px; }

[data-testid="stMetric"] {
    background-color: white;
    padding: 16px 20px;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-left: 4px solid #0B2545;
}
[data-testid="stMetricLabel"] { color: #5C6B7A !important; font-size: 13px !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { color: #0B2545 !important; font-size: 28px !important; }

.stButton>button {
    background-color: #0B2545; color: white; border-radius: 8px;
    border: none; padding: 8px 18px; font-weight: 500;
}
.stButton>button:hover { background-color: #13315C; color: white; }

.pedido-status {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 6px;
}
.status-ok    { background-color: #DFF5E1; color: #1F7A3A; }
.status-pend  { background-color: #FFF4D6; color: #8A6D00; }
.status-erro  { background-color: #FBE3E3; color: #A12626; }

footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONSTANTES
# ------------------------------------------------------------
ARQUIVO_BASE = "base_pedidos.parquet"
INTERVALO_REFRESH_MS = 30_000
ABA_CORA = "CORA"

# Mapeamento: nome real na planilha -> nome amigável no app
COLUNAS_MAP = {
    "Cód. unidade entrega": "CDD",
    "Cód. setor": "Setor",
    "Cód. cliente": "PDV",
    "Nome fantasia": "Nome PDV",
    "Data entrada": "Data entrada",
    "Data entrega": "Data entrega",
    "Cód. produto": "Cód. produto",
    "Desc. produto": "Desc. produto",
    "Quant. venda": "Qtd venda (cx)",
    "Volume hectolitro": "Volume (hl)",
    "Valor líquido item": "Valor líquido (R$)",
    "Tipo pedido": "Tipo pedido",
    "Situação pedido": "Situação pedido",
    "Situação atend. pedido": "Situação atendimento",
    "Número pedido": "Número pedido",
    "Distribuição": "Distribuição",
}

# Filtros disponíveis pro vendedor
FILTROS_PADRAO = ["CDD", "Setor", "PDV", "Nome PDV", "Data entrada", "Data entrega"]

# ------------------------------------------------------------
# AUTO-REFRESH
# ------------------------------------------------------------
st_autorefresh(interval=INTERVALO_REFRESH_MS, key="refresh_vendedor")

# ------------------------------------------------------------
# FUNÇÕES
# ------------------------------------------------------------
def ler_arquivo_upload(arquivo):
    """Lê o Excel pegando SÓ a aba CORA."""
    df = pd.read_excel(arquivo, sheet_name=ABA_CORA)
    df.columns = df.columns.str.strip()

    # Renomeia as colunas que existem
    renomear = {k: v for k, v in COLUNAS_MAP.items() if k in df.columns}
    df = df.rename(columns=renomear)

    # Converte datas
    for col in ["Data entrada", "Data entrega"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Garante que distribuição seja numérica (0 ou 1)
    if "Distribuição" in df.columns:
        df["Distribuição"] = pd.to_numeric(df["Distribuição"], errors="coerce").fillna(0).astype(int)

    return df

def carregar_base_do_servidor():
    if os.path.exists(ARQUIVO_BASE):
        df = pd.read_parquet(ARQUIVO_BASE)
        ts = os.path.getmtime(ARQUIVO_BASE)
        atualizado = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
        return df, atualizado
    return None, None

def salvar_base(df):
    df.to_parquet(ARQUIVO_BASE, index=False)

def badge_status(texto, tipo="ok"):
    cor = {"ok": "status-ok", "pend": "status-pend", "erro": "status-erro"}.get(tipo, "status-pend")
    return f'<span class="pedido-status {cor}">{texto}</span>'

def classifica_situacao(valor):
    s = str(valor).upper()
    if "CANCEL" in s or "ANUL" in s or "ERRO" in s:
        return "erro"
    if "ATEND" in s or "FATUR" in s or "OK" in s:
        return "ok"
    return "pend"

# ------------------------------------------------------------
# CABEÇALHO
# ------------------------------------------------------------
st.markdown("""
<div class="header">
    <h1>📊 Painel de Distribuição – CORA</h1>
    <p>Consulta de pedidos em tempo real – Operação Comercial</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# LOGIN ADMIN
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
# ÁREA DO ADMIN
# ------------------------------------------------------------
if st.session_state.admin_logado:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚙️ Atualizar base")
        upload = st.file_uploader("Selecione o arquivo CORA (.xlsx):", type=["xlsx"])
        if upload is not None:
            try:
                df_novo = ler_arquivo_upload(upload)
                salvar_base(df_novo)
                st.success(f"Base atualizada! {len(df_novo)} linhas da aba CORA.")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

# ------------------------------------------------------------
# CARREGA BASE
# ------------------------------------------------------------
df, ultima_atualizacao = carregar_base_do_servidor()

if df is None:
    st.info("⏳ Base ainda não disponível. Volte em alguns instantes.")
    st.stop()

st.markdown(
    f"<p style='color:#5C6B7A;font-size:13px;'>🔄 Base atualizada em <b>{ultima_atualizacao}</b> "
    f"&nbsp;|&nbsp; Atualização automática a cada 30 segundos</p>",
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# FILTROS
# ------------------------------------------------------------
st.markdown("#### 🔎 Filtros")

df_filtrado = df.copy()
filtros_disponiveis = [c for c in FILTROS_PADRAO if c in df.columns]

cols = st.columns(min(len(filtros_disponiveis), 4) or 1)

# Filtros simples (CDD, Setor, PDV, Nome PDV)
for i, coluna in enumerate([c for c in filtros_disponiveis if "Data" not in c]):
    valores = ["Todos"] + sorted(df[coluna].dropna().astype(str).unique().tolist())
    with cols[i % len(cols)]:
        escolha = st.selectbox(coluna, valores, key=f"f_{coluna}")
        if escolha != "Todos":
            df_filtrado = df_filtrado[df_filtrado[coluna].astype(str) == escolha]

# Filtros de data
col_d1, col_d2 = st.columns(2)
if "Data entrada" in df.columns:
    with col_d1:
        datas = df["Data entrada"].dropna()
        if not datas.empty:
            min_d, max_d = datas.min().date(), datas.max().date()
            faixa = st.date_input("Data entrada (período):", value=(min_d, max_d),
                                  min_value=min_d, max_value=max_d, key="f_entrada")
            if isinstance(faixa, tuple) and len(faixa) == 2:
                d1, d2 = faixa
                df_filtrado = df_filtrado[
                    (df_filtrado["Data entrada"].dt.date >= d1) &
                    (df_filtrado["Data entrada"].dt.date <= d2)
                ]

if "Data entrega" in df.columns:
    with col_d2:
        datas = df["Data entrega"].dropna()
        if not datas.empty:
            min_d, max_d = datas.min().date(), datas.max().date()
            faixa = st.date_input("Data entrega (período):", value=(min_d, max_d),
                                  min_value=min_d, max_value=max_d, key="f_entrega")
            if isinstance(faixa, tuple) and len(faixa) == 2:
                d1, d2 = faixa
                df_filtrado = df_filtrado[
                    (df_filtrado["Data entrega"].dt.date >= d1) &
                    (df_filtrado["Data entrega"].dt.date <= d2)
                ]

# Busca livre
busca = st.text_input("🔍 Buscar por nº do pedido, PDV ou Nome PDV:")
if busca:
    mascara = pd.Series([False] * len(df_filtrado), index=df_filtrado.index)
    for c in ["Número pedido", "PDV", "Nome PDV"]:
        if c in df_filtrado.columns:
            mascara |= df_filtrado[c].astype(str).str.contains(busca, case=False, na=False)
    df_filtrado = df_filtrado[mascara]

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
st.markdown("---")

# Conta pedidos únicos (não linhas)
if "Número pedido" in df_filtrado.columns:
    total_pedidos = df_filtrado["Número pedido"].nunique()
else:
    total_pedidos = len(df_filtrado)

if "Distribuição" in df_filtrado.columns and "Número pedido" in df_filtrado.columns:
    distrib_df = df_filtrado.groupby("Número pedido")["Distribuição"].max()
    distribuidos = int((distrib_df == 1).sum())
else:
    distribuidos = 0

nao_distribuidos = total_pedidos - distribuidos
taxa = (distribuidos / total_pedidos * 100) if total_pedidos else 0

valor_total = df_filtrado["Valor líquido (R$)"].sum() if "Valor líquido (R$)" in df_filtrado.columns else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Pedidos", f"{total_pedidos:,}".replace(",", "."))
k2.metric("✅ Distribuição", f"{distribuidos:,}".replace(",", "."))
k3.metric("❌ Não distribuição", f"{nao_distribuidos:,}".replace(",", "."))
k4.metric("📈 Taxa", f"{taxa:.1f}%")

st.markdown("---")

# ------------------------------------------------------------
# CARDS POR CLIENTE
# ------------------------------------------------------------
st.markdown("### 🏪 Clientes")

if "Nome PDV" not in df_filtrado.columns:
    st.warning("A base não tem a coluna 'Nome fantasia'. Verifique o arquivo.")
    st.stop()

grupos = df_filtrado.groupby(["Nome PDV", "PDV"], dropna=False)

if len(grupos) == 0:
    st.info("Nenhum pedido encontrado com os filtros atuais.")
else:
    for (nome_pdv, cod_pdv), dados in grupos:
        nome = str(nome_pdv) if pd.notna(nome_pdv) else "—"
        pdv  = str(cod_pdv)  if pd.notna(cod_pdv)  else "—"

        # Pedidos únicos
        if "Número pedido" in dados.columns:
            pedidos_unicos = dados["Número pedido"].nunique()
            if "Distribuição" in dados.columns:
                distrib_por_pedido = dados.groupby("Número pedido")["Distribuição"].max()
                qtd_distrib = int((distrib_por_pedido == 1).sum())
            else:
                qtd_distrib = 0
        else:
            pedidos_unicos = len(dados)
            qtd_distrib = 0

        titulo = (f"🏪  {nome}   •   PDV: {pdv}   "
                  f"|   📦 {pedidos_unicos} pedidos   "
                  f"|   ✅ {qtd_distrib} distribuições")

        with st.expander(titulo):
            # Agrupa por número do pedido
            if "Número pedido" in dados.columns:
                for num_pedido, itens in dados.groupby("Número pedido"):
                    primeira = itens.iloc[0]

                    tipo  = str(primeira.get("Tipo pedido", "—"))
                    sit_p = str(primeira.get("Situação pedido", "—"))
                    sit_a = str(primeira.get("Situação atendimento", "—"))
                    distrib = int(primeira.get("Distribuição", 0)) if "Distribuição" in itens.columns else 0

                    badge_distrib = (
                        '<span class="pedido-status status-ok">✅ Distribuição</span>'
                        if distrib == 1 else
                        '<span class="pedido-status status-erro">❌ Não distribuição</span>'
                    )

                    badges = (
                        badge_distrib +
                        badge_status(tipo, "ok") +
                        badge_status(sit_p, classifica_situacao(sit_p)) +
                        badge_status(sit_a, classifica_situacao(sit_a))
                    )

                    data_entrada = primeira.get("Data entrada", "")
                    data_entrega = primeira.get("Data entrega", "")
                    data_entrada_str = data_entrada.strftime("%d/%m/%Y %H:%M") if pd.notna(data_entrada) else "—"
                    data_entrega_str = data_entrega.strftime("%d/%m/%Y") if pd.notna(data_entrega) else "—"

                    st.markdown(
                        f"**Pedido {num_pedido}** &nbsp;&nbsp; "
                        f"📅 Entrada: {data_entrada_str} &nbsp;|&nbsp; 🚚 Entrega: {data_entrega_str}<br>"
                        f"{badges}",
                        unsafe_allow_html=True
                    )

                    # Tabela de itens
                    colunas_itens = [c for c in [
                        "Cód. produto", "Desc. produto",
                        "Qtd venda (cx)", "Volume (hl)", "Valor líquido (R$)"
                    ] if c in itens.columns]

                    st.dataframe(
                        itens[colunas_itens].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True
                    )
                    st.markdown("---")
            else:
                st.dataframe(dados.reset_index(drop=True), use_container_width=True, hide_index=True)
