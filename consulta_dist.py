# ============================================================
# PAINEL DE DISTRIBUIÇÃO – CORA
# Versão 3.3 – Sem busca livre, sem auto-refresh,
# Distribuição deduplicada por PDV + Produto
# (data de entrega MAIS PRÓXIMA DE HOJE)
# Autor: Ricardo Marchette Sabino
# ============================================================

import streamlit as st
import pandas as pd
import os
from datetime import datetime

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
    padding: 28px 32px; border-radius: 12px; color: white;
    margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.header h1 { color: white; font-size: 26px; margin: 0; font-weight: 600; }
.header p  { color: #D9E2EC; margin: 4px 0 0 0; font-size: 14px; }

[data-testid="stMetric"] {
    background-color: white; padding: 16px 20px; border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #0B2545;
}
[data-testid="stMetricLabel"] { color: #5C6B7A !important; font-size: 13px !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { color: #0B2545 !important; font-size: 28px !important; }

.stButton>button {
    background-color: #0B2545; color: white; border-radius: 8px;
    border: none; padding: 8px 18px; font-weight: 500;
}
.stButton>button:hover { background-color: #13315C; color: white; }

.pedido-status {
    display: inline-block; padding: 4px 10px; border-radius: 6px;
    font-size: 12px; font-weight: 500; margin-right: 6px;
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
ARQUIVO_TIMESTAMP = "ultima_atualizacao.txt"
ABA_CORA = "CORA"
CARDS_POR_PAGINA = 20

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

FILTROS_PADRAO = ["CDD", "Setor", "PDV", "Nome PDV"]

# ------------------------------------------------------------
# FUNÇÕES COM CACHE
# ------------------------------------------------------------
@st.cache_data(show_spinner="Carregando base...")
def carregar_base_cache(timestamp_arquivo):
    if not os.path.exists(ARQUIVO_BASE):
        return None
    df = pd.read_parquet(ARQUIVO_BASE)
    for col in ["CDD", "Setor", "Tipo pedido", "Situação pedido", "Situação atendimento"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df

@st.cache_data(show_spinner=False)
def calcular_resumos(hash_filtros, df):
    if "Número pedido" not in df.columns:
        return pd.DataFrame()

    resumo = df.groupby(["Nome PDV", "PDV"], observed=True).agg(
        qtd_pedidos=("Número pedido", "nunique"),
    ).reset_index()

    if "Distribuição" in df.columns:
        pedidos_distrib = df.groupby(
            ["Nome PDV", "PDV", "Número pedido"], observed=True
        )["Distribuição"].max().reset_index()
        distrib_cliente = pedidos_distrib.groupby(
            ["Nome PDV", "PDV"], observed=True
        )["Distribuição"].sum().reset_index().rename(columns={"Distribuição": "qtd_distrib"})
        resumo = resumo.merge(distrib_cliente, on=["Nome PDV", "PDV"], how="left")
    else:
        resumo["qtd_distrib"] = 0

    return resumo

# ------------------------------------------------------------
# REGRA DE DISTRIBUIÇÃO (data de entrega MAIS PRÓXIMA DE HOJE)
# ------------------------------------------------------------
def aplicar_regra_distribuicao(df):
    """
    Regra:
    - Mesmo produto vendido várias vezes pro mesmo PDV → aparece TODAS as vezes
    - Mas só a linha com a DATA DE ENTREGA MAIS PRÓXIMA DE HOJE
      conta como Distribuição = 1
    - As outras viram Distribuição = 0 (evita duplicidade)
    """
    if "Distribuição" not in df.columns:
        return df
    if not all(c in df.columns for c in ["PDV", "Cód. produto", "Data entrega"]):
        return df

    df_dist = df[df["Distribuição"] == 1].copy()
    if df_dist.empty:
        return df

    df_dist_validas = df_dist.dropna(subset=["Data entrega"])
    if df_dist_validas.empty:
        return df

    # ⚡ Calcula a distância (em dias) de cada data até HOJE
    hoje = pd.Timestamp(datetime.now().date())
    df_dist_validas = df_dist_validas.assign(
        _dist_dias=(df_dist_validas["Data entrega"] - hoje).abs()
    )

    # Para cada (PDV, Cód. produto), pega o índice da menor distância
    idx_manter = df_dist_validas.groupby(
        ["PDV", "Cód. produto"], observed=True
    )["_dist_dias"].idxmin().values

    df["Distribuição"] = 0
    df.loc[idx_manter, "Distribuição"] = 1
    df["Distribuição"] = df["Distribuição"].astype("int8")

    return df

# ------------------------------------------------------------
# LEITURA E SALVAMENTO
# ------------------------------------------------------------
def ler_arquivo_upload(arquivo):
    df = pd.read_excel(arquivo, sheet_name=ABA_CORA)
    df.columns = df.columns.str.strip()
    renomear = {k: v for k, v in COLUNAS_MAP.items() if k in df.columns}
    df = df.rename(columns=renomear)

    for col in ["Data entrada", "Data entrega"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "Distribuição" in df.columns:
        df["Distribuição"] = pd.to_numeric(df["Distribuição"], errors="coerce").fillna(0).astype("int8")

    for col in ["Qtd venda (cx)", "Volume (hl)", "Valor líquido (R$)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")

    df = aplicar_regra_distribuicao(df)
    return df

def salvar_base(df):
    df.to_parquet(ARQUIVO_BASE, index=False, compression="snappy")
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(ARQUIVO_TIMESTAMP, "w", encoding="utf-8") as f:
        f.write(agora)
    st.cache_data.clear()

def ler_timestamp():
    if os.path.exists(ARQUIVO_TIMESTAMP):
        with open(ARQUIVO_TIMESTAMP, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "—"

# ------------------------------------------------------------
# AUXILIARES VISUAIS
# ------------------------------------------------------------
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
    <p>Consulta de pedidos – Operação Comercial</p>
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
# ÁREA DO ADMIN (upload)
# ------------------------------------------------------------
if st.session_state.admin_logado:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚙️ Atualizar base")
        upload = st.file_uploader("Selecione o arquivo CORA (.xlsx):", type=["xlsx"])
        if upload is not None:
            try:
                with st.spinner("Processando..."):
                    df_novo = ler_arquivo_upload(upload)
                    salvar_base(df_novo)
                st.success(f"Base atualizada! {len(df_novo)} linhas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

# ------------------------------------------------------------
# CARREGA BASE
# ------------------------------------------------------------
if not os.path.exists(ARQUIVO_BASE):
    st.info("⏳ Base ainda não disponível.")
    st.stop()

timestamp_arquivo = os.path.getmtime(ARQUIVO_BASE)
df = carregar_base_cache(timestamp_arquivo)
ultima_atualizacao = ler_timestamp()

if df is None or df.empty:
    st.info("⏳ Base vazia.")
    st.stop()

st.markdown(
    f"<p style='color:#5C6B7A;font-size:13px;'>🔄 Base atualizada em <b>{ultima_atualizacao}</b> "
    f"&nbsp;|&nbsp; Total de linhas: <b>{len(df):,}</b>".replace(",", ".") + "</p>",
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# FILTROS
# ------------------------------------------------------------
st.markdown("#### 🔎 Filtros")

df_filtrado = df
filtros_disponiveis = [c for c in FILTROS_PADRAO if c in df.columns]

cols = st.columns(min(len(filtros_disponiveis), 4) or 1)
for i, coluna in enumerate(filtros_disponiveis):
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
            faixa = st.date_input("Data entrada:", value=(min_d, max_d),
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
            faixa = st.date_input("Data entrega:", value=(min_d, max_d),
                                  min_value=min_d, max_value=max_d, key="f_entrega")
            if isinstance(faixa, tuple) and len(faixa) == 2:
                d1, d2 = faixa
                df_filtrado = df_filtrado[
                    (df_filtrado["Data entrega"].dt.date >= d1) &
                    (df_filtrado["Data entrega"].dt.date <= d2)
                ]

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
st.markdown("---")

if "Número pedido" in df_filtrado.columns:
    total_pedidos = df_filtrado["Número pedido"].nunique()
else:
    total_pedidos = len(df_filtrado)

if "Distribuição" in df_filtrado.columns:
    distribuidos = int(df_filtrado["Distribuição"].sum())
else:
    distribuidos = 0

nao_distribuidos = max(0, total_pedidos - distribuidos)
taxa = (distribuidos / total_pedidos * 100) if total_pedidos else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Pedidos", f"{total_pedidos:,}".replace(",", "."))
k2.metric("✅ Distribuição", f"{distribuidos:,}".replace(",", "."))
k3.metric("❌ Não distribuição", f"{nao_distribuidos:,}".replace(",", "."))
k4.metric("📈 Taxa", f"{taxa:.1f}%")

st.markdown("---")

# ------------------------------------------------------------
# RESUMO POR CLIENTE
# ------------------------------------------------------------
st.markdown("### 🏪 Clientes")

if "Nome PDV" not in df_filtrado.columns:
    st.warning("Base sem coluna 'Nome fantasia'.")
    st.stop()

hash_filtros = hash((len(df_filtrado),
                     str(df_filtrado.index.min()),
                     str(df_filtrado.index.max())))
resumo_clientes = calcular_resumos(hash_filtros, df_filtrado)

if resumo_clientes.empty:
    st.info("Nenhum pedido encontrado com os filtros atuais.")
    st.stop()

resumo_clientes = resumo_clientes.sort_values("qtd_pedidos", ascending=False).reset_index(drop=True)

# ------------------------------------------------------------
# PAGINAÇÃO
# ------------------------------------------------------------
total_clientes = len(resumo_clientes)
total_paginas = max(1, (total_clientes - 1) // CARDS_POR_PAGINA + 1)

col_info, col_pag = st.columns([3, 1])
with col_info:
    st.caption(f"Exibindo até **{CARDS_POR_PAGINA}** clientes por página • Total: **{total_clientes}** clientes")
with col_pag:
    pagina = st.number_input("Página:", min_value=1, max_value=total_paginas, value=1, step=1)

inicio = (pagina - 1) * CARDS_POR_PAGINA
fim = inicio + CARDS_POR_PAGINA
clientes_pagina = resumo_clientes.iloc[inicio:fim]

# ------------------------------------------------------------
# CARDS POR CLIENTE
# ------------------------------------------------------------
for _, linha in clientes_pagina.iterrows():
    nome  = str(linha["Nome PDV"]) if pd.notna(linha["Nome PDV"]) else "—"
    pdv   = str(linha["PDV"])      if pd.notna(linha["PDV"])      else "—"
    qtd_p = int(linha["qtd_pedidos"])
    qtd_d = int(linha.get("qtd_distrib", 0))

    titulo = (f"🏪  {nome}   •   PDV: {pdv}   "
              f"|   📦 {qtd_p} pedidos   "
              f"|   ✅ {qtd_d} distribuições")

    with st.expander(titulo, expanded=False):
        dados_cliente = df_filtrado[
            (df_filtrado["Nome PDV"] == linha["Nome PDV"]) &
            (df_filtrado["PDV"] == linha["PDV"])
        ]

        if "Número pedido" in dados_cliente.columns:
            for num_pedido, itens in dados_cliente.groupby("Número pedido", observed=True):
                primeira = itens.iloc[0]

                tipo  = str(primeira.get("Tipo pedido", "—"))
                sit_p = str(primeira.get("Situação pedido", "—"))
                sit_a = str(primeira.get("Situação atendimento", "—"))

                pedido_eh_distrib = int(itens["Distribuição"].max()) if "Distribuição" in itens.columns else 0

                badge_distrib = (
                    '<span class="pedido-status status-ok">✅ Distribuição</span>'
                    if pedido_eh_distrib == 1 else
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

                colunas_itens = [c for c in [
                    "Cód. produto", "Desc. produto",
                    "Qtd venda (cx)", "Volume (hl)", "Valor líquido (R$)",
                    "Distribuição"
                ] if c in itens.columns]

                itens_exibir = itens[colunas_itens].copy().reset_index(drop=True)
                if "Distribuição" in itens_exibir.columns:
                    itens_exibir["Distribuição"] = itens_exibir["Distribuição"].map(
                        {1: "✅", 0: "❌"}
                    ).fillna("❌")

                st.dataframe(itens_exibir, use_container_width=True, hide_index=True)
                st.markdown("---")
