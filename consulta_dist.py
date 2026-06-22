# ============================================================
# PAINEL DE DISTRIBUICAO - DIRETORIA EIXO ATLANTICO
# Versao 4.4 - Otimizado para 30k+ linhas
# Autor: Ricardo Marchette Sabino
# ============================================================

import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ------------------------------------------------------------
# CONFIGURACAO BASICA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Painel de Distribuicao | Diretoria Eixo Atlantico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------
# ESTILO VISUAL
# ------------------------------------------------------------
st.markdown("""
<style>
.main { background-color: #F4F6FA; }

.header {
    background: linear-gradient(135deg, #0B2545 0%, #13315C 50%, #1B4080 100%);
    padding: 28px 32px;
    border-radius: 14px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 4px 14px rgba(11,37,69,0.18);
}
.header h1 {
    color: white; font-size: 26px; margin: 0;
    font-weight: 600; letter-spacing: 0.3px;
}
.header p {
    color: #D9E2EC; margin: 6px 0 0 0;
    font-size: 14px; font-weight: 400;
}

[data-testid="stMetric"] {
    background-color: white; padding: 16px 20px;
    border-radius: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    border-left: 4px solid #0B2545;
}
[data-testid="stMetricLabel"] {
    color: #5C6B7A !important; font-size: 13px !important;
    font-weight: 500 !important; text-transform: uppercase;
    letter-spacing: 0.4px;
}
[data-testid="stMetricValue"] {
    color: #0B2545 !important;
    font-size: 28px !important; font-weight: 700 !important;
}

.stButton>button {
    background-color: #0B2545; color: white;
    border-radius: 8px; border: none;
    padding: 8px 18px; font-weight: 500;
}
.stButton>button:hover {
    background-color: #13315C; color: white;
}

.pedido-status {
    display: inline-block; padding: 4px 10px;
    border-radius: 6px; font-size: 12px;
    font-weight: 500; margin-right: 6px; margin-bottom: 4px;
}
.status-ok    { background-color: #DFF5E1; color: #1F7A3A; }
.status-pend  { background-color: #FFF4D6; color: #8A6D00; }
.status-erro  { background-color: #FBE3E3; color: #A12626; }

.section-title {
    color: #0B2545; font-size: 17px; font-weight: 600;
    margin: 20px 0 10px 0; padding-bottom: 8px;
    border-bottom: 2px solid #E5E9F0;
}

.info-bar {
    background: white; padding: 10px 16px;
    border-radius: 8px; border-left: 3px solid #0B2545;
    margin-bottom: 16px;
}

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

COLUNAS_PRODUTO = [
    "Nome do Produto", "Categoria Agrupado", "Categoria", "Família",
    "Marca", "Marca Consolidada", "Tamanho Embalagem", "Retornável",
    "Segmento", "Cerveja sem Álcool", "Refrigerante Zero", "Marketplace",
]

COLUNAS_IGNORAR = ["Feito antes?", "Chave"]
FILTROS_PADRAO = ["CDD", "Setor", "PDV", "Nome PDV"]

# ------------------------------------------------------------
# FUNCAO DE LEITURA DA BASE (CACHE)
# ------------------------------------------------------------
@st.cache_data(show_spinner="Carregando base...")
def carregar_base_cache(timestamp_arquivo):
    if not os.path.exists(ARQUIVO_BASE):
        return None
    df = pd.read_parquet(ARQUIVO_BASE)
    cols_categorizar = (
        ["CDD", "Setor", "Tipo pedido", "Situação pedido", "Situação atendimento"]
        + COLUNAS_PRODUTO
    )
    for col in cols_categorizar:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df

# ------------------------------------------------------------
# REGRA DE DISTRIBUICAO (mais proxima de hoje)
# ------------------------------------------------------------
def aplicar_regra_distribuicao(df):
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

    hoje = pd.Timestamp(datetime.now().date())
    df_dist_validas = df_dist_validas.assign(
        _dist_dias=(df_dist_validas["Data entrega"] - hoje).abs()
    )
    idx_manter = df_dist_validas.groupby(
        ["PDV", "Cód. produto"], observed=True
    )["_dist_dias"].idxmin().values

    df["Distribuição"] = 0
    df.loc[idx_manter, "Distribuição"] = 1
    df["Distribuição"] = df["Distribuição"].astype("int8")
    return df

# ------------------------------------------------------------
# UPLOAD OTIMIZADO (com calamine + barra de progresso)
# ------------------------------------------------------------
def ler_arquivo_upload(arquivo, progress_bar=None, status_text=None):
    """Le o Excel da aba CORA de forma otimizada."""

    if status_text:
        status_text.text("📖 Lendo arquivo Excel (pode levar alguns segundos)...")
    if progress_bar:
        progress_bar.progress(10)

    # OTIMIZACAO 1: tenta calamine (muito mais rapido), fallback para openpyxl
    try:
        df = pd.read_excel(arquivo, sheet_name=ABA_CORA, engine="calamine")
    except Exception:
        df = pd.read_excel(arquivo, sheet_name=ABA_CORA)

    if progress_bar:
        progress_bar.progress(50)
    if status_text:
        n = f"{len(df):,}".replace(",", ".")
        status_text.text(f"⚙️ Processando {n} linhas...")

    df.columns = df.columns.str.strip()

    cols_remover = [c for c in COLUNAS_IGNORAR if c in df.columns]
    if cols_remover:
        df = df.drop(columns=cols_remover)

    renomear = {k: v for k, v in COLUNAS_MAP.items() if k in df.columns}
    if renomear:
        df = df.rename(columns=renomear)

    if progress_bar:
        progress_bar.progress(65)

    # Datas
    for col in ["Data entrada", "Data entrega"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Distribuicao
    if "Distribuição" in df.columns:
        df["Distribuição"] = pd.to_numeric(
            df["Distribuição"], errors="coerce"
        ).fillna(0).astype("int8")

    # Numericos
    for col in ["Qtd venda (cx)", "Volume (hl)", "Valor líquido (R$)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")

    if progress_bar:
        progress_bar.progress(75)

    # OTIMIZACAO 2: converte colunas texto em batch
    colunas_texto = (
        COLUNAS_PRODUTO +
        ["CDD", "Setor", "PDV", "Nome PDV", "Cód. produto", "Desc. produto",
         "Tipo pedido", "Situação pedido", "Situação atendimento", "Número pedido"]
    )
    colunas_texto_existentes = [c for c in colunas_texto if c in df.columns]
    if colunas_texto_existentes:
        df[colunas_texto_existentes] = df[colunas_texto_existentes].astype(str)
        df[colunas_texto_existentes] = df[colunas_texto_existentes].replace(
            {"nan": "", "None": "", "NaT": ""}
        )

    if progress_bar:
        progress_bar.progress(90)
    if status_text:
        status_text.text("🎯 Aplicando regra de distribuicao...")

    df = aplicar_regra_distribuicao(df)

    if progress_bar:
        progress_bar.progress(100)
    if status_text:
        status_text.text("✅ Processamento concluido!")

    return df

def salvar_base(df):
    # ⚡ CORREÇÃO FINAL: força TODAS as colunas object para string
    # Isso garante que o parquet não falhe com tipos mistos
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).replace(
            {"nan": "", "None": "", "NaT": "", "<NA>": ""}
        )

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
    cor_map = {"ok": "status-ok", "pend": "status-pend", "erro": "status-erro"}
    cor = cor_map.get(tipo, "status-pend")
    return f'<span class="pedido-status {cor}">{texto}</span>'

def classifica_situacao(valor):
    s = str(valor).upper()
    if "CANCEL" in s or "ANUL" in s or "ERRO" in s:
        return "erro"
    if "ATEND" in s or "FATUR" in s or "OK" in s:
        return "ok"
    return "pend"

# ------------------------------------------------------------
# CABECALHO
# ------------------------------------------------------------
st.markdown("""
<div class="header">
    <h1>📊 Painel de Distribuição – Diretoria Eixo Atlântico</h1>
    <p>Consulta de pedidos e acompanhamento de distribuição</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------
if "admin_logado" not in st.session_state:
    st.session_state.admin_logado = False

# ------------------------------------------------------------
# SIDEBAR - LOGIN E UPLOAD
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔐 Acesso restrito")
    if not st.session_state.admin_logado:
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar"):
            try:
                senha_correta = st.secrets["admin_password"]
            except Exception:
                senha_correta = None
            if senha_correta and senha == senha_correta:
                st.session_state.admin_logado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        st.success("✅ Modo administrador")
        if st.button("Sair"):
            st.session_state.admin_logado = False
            st.rerun()

   if st.session_state.admin_logado:
        st.markdown("---")
        st.markdown("### ⚙️ Atualizar base")

        # Chave dinâmica do uploader (muda após upload bem-sucedido)
        if "upload_key" not in st.session_state:
            st.session_state.upload_key = 0

        upload = st.file_uploader(
            "Arquivo CORA (.xlsx):",
            type=["xlsx"],
            key=f"uploader_{st.session_state.upload_key}"
        )

        if upload is not None:
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()

                df_novo = ler_arquivo_upload(upload, progress_bar, status_text)

                status_text.text("💾 Salvando base...")
                salvar_base(df_novo)

                progress_bar.empty()
                status_text.empty()

                n = f"{len(df_novo):,}".replace(",", ".")
                st.success(f"✅ Base atualizada! {n} linhas.")

                # ⚡ Incrementa a chave pra "resetar" o uploader
                st.session_state.upload_key += 1
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
# ------------------------------------------------------------
# CARREGA BASE
# ------------------------------------------------------------
if not os.path.exists(ARQUIVO_BASE):
    st.info("⏳ Base ainda nao disponivel.")
    st.stop()

timestamp_arquivo = os.path.getmtime(ARQUIVO_BASE)
df = carregar_base_cache(timestamp_arquivo)
ultima_atualizacao = ler_timestamp()

if df is None or df.empty:
    st.info("⏳ Base vazia.")
    st.stop()

total_linhas_str = f"{len(df):,}".replace(",", ".")
st.markdown(
    f"<div class='info-bar'>🔄 Base atualizada em <b>{ultima_atualizacao}</b> "
    f"&nbsp;|&nbsp; Total de linhas: <b>{total_linhas_str}</b></div>",
    unsafe_allow_html=True
)

# ------------------------------------------------------------
# FILTROS PRINCIPAIS
# ------------------------------------------------------------
st.markdown('<div class="section-title">🔎 Filtros principais</div>', unsafe_allow_html=True)

df_filtrado = df
filtros_disponiveis = [c for c in FILTROS_PADRAO if c in df.columns]

n_principais = min(len(filtros_disponiveis), 4) or 1
cols = st.columns(n_principais)
for i, coluna in enumerate(filtros_disponiveis):
    valores = ["Todos"] + sorted(df[coluna].dropna().astype(str).unique().tolist())
    with cols[i % n_principais]:
        escolha = st.selectbox(coluna, valores, key=f"f_{coluna}")
        if escolha != "Todos":
            df_filtrado = df_filtrado[df_filtrado[coluna].astype(str) == escolha]

# Datas
col_d1, col_d2 = st.columns(2)
if "Data entrada" in df.columns:
    with col_d1:
        datas = df["Data entrada"].dropna()
        if not datas.empty:
            min_d = datas.min().date()
            max_d = datas.max().date()
            faixa = st.date_input(
                "Data entrada:",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                key="f_entrada"
            )
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
            min_d = datas.min().date()
            max_d = datas.max().date()
            faixa = st.date_input(
                "Data entrega:",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                key="f_entrega"
            )
            if isinstance(faixa, tuple) and len(faixa) == 2:
                d1, d2 = faixa
                df_filtrado = df_filtrado[
                    (df_filtrado["Data entrega"].dt.date >= d1) &
                    (df_filtrado["Data entrega"].dt.date <= d2)
                ]

# ------------------------------------------------------------
# FILTRO PRODUTO (expander simples)
# ------------------------------------------------------------
with st.expander("🍺 Filtro Produto (clique para abrir)", expanded=False):
    colunas_produto_existentes = [c for c in COLUNAS_PRODUTO if c in df.columns]
    filtros_produto_escolhidos = {}

    n_cols_prod = 3
    for i in range(0, len(colunas_produto_existentes), n_cols_prod):
        cols_filtro = st.columns(n_cols_prod)
        bloco = colunas_produto_existentes[i:i + n_cols_prod]
        for j, coluna in enumerate(bloco):
            with cols_filtro[j]:
                valores = ["Todos"] + sorted(df[coluna].dropna().astype(str).unique().tolist())
                escolha = st.selectbox(coluna, valores, key=f"fp_{coluna}")
                filtros_produto_escolhidos[coluna] = escolha

    for coluna, valor in filtros_produto_escolhidos.items():
        if valor != "Todos":
            df_filtrado = df_filtrado[df_filtrado[coluna].astype(str) == valor]

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
st.markdown('<div class="section-title">🏪 Clientes</div>', unsafe_allow_html=True)

if "Nome PDV" not in df_filtrado.columns or df_filtrado.empty:
    st.info("Nenhum pedido encontrado com os filtros atuais.")
    st.stop()

resumo_clientes = df_filtrado.groupby(["Nome PDV", "PDV"], observed=True).agg(
    qtd_pedidos=("Número pedido", "nunique"),
    qtd_distrib=("Distribuição", "sum")
).reset_index()

resumo_clientes["qtd_distrib"] = resumo_clientes["qtd_distrib"].fillna(0).astype(int)
resumo_clientes = resumo_clientes.sort_values("qtd_pedidos", ascending=False).reset_index(drop=True)

# ------------------------------------------------------------
# PAGINACAO
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
    nome = str(linha["Nome PDV"]) if pd.notna(linha["Nome PDV"]) else "—"
    pdv = str(linha["PDV"]) if pd.notna(linha["PDV"]) else "—"
    qtd_p = int(linha["qtd_pedidos"])
    qtd_d = int(linha["qtd_distrib"])

    titulo = (
        f"🏪  {nome}   •   PDV: {pdv}   "
        f"|   📦 {qtd_p} pedidos   "
        f"|   ✅ {qtd_d} distribuições"
    )

    with st.expander(titulo, expanded=False):
        dados_cliente = df_filtrado[
            (df_filtrado["Nome PDV"] == linha["Nome PDV"]) &
            (df_filtrado["PDV"] == linha["PDV"])
        ]

        if "Número pedido" in dados_cliente.columns:
            for num_pedido, itens in dados_cliente.groupby("Número pedido", observed=True):
                primeira = itens.iloc[0]

                tipo = str(primeira.get("Tipo pedido", "—"))
                sit_p = str(primeira.get("Situação pedido", "—"))
                sit_a = str(primeira.get("Situação atendimento", "—"))

                if "Distribuição" in itens.columns:
                    pedido_eh_distrib = int(itens["Distribuição"].max())
                else:
                    pedido_eh_distrib = 0

                if pedido_eh_distrib == 1:
                    badge_distrib = '<span class="pedido-status status-ok">✅ Distribuição</span>'
                else:
                    badge_distrib = '<span class="pedido-status status-erro">❌ Não distribuição</span>'

                badges = (
                    badge_distrib +
                    badge_status(tipo, "ok") +
                    badge_status(sit_p, classifica_situacao(sit_p)) +
                    badge_status(sit_a, classifica_situacao(sit_a))
                )

                data_entrada = primeira.get("Data entrada", "")
                data_entrega = primeira.get("Data entrega", "")

                if pd.notna(data_entrada):
                    data_entrada_str = data_entrada.strftime("%d/%m/%Y %H:%M")
                else:
                    data_entrada_str = "—"

                if pd.notna(data_entrega):
                    data_entrega_str = data_entrega.strftime("%d/%m/%Y")
                else:
                    data_entrega_str = "—"

                st.markdown(
                    f"**Pedido {num_pedido}** &nbsp;&nbsp; "
                    f"📅 Entrada: {data_entrada_str} &nbsp;|&nbsp; 🚚 Entrega: {data_entrega_str}<br>"
                    f"{badges}",
                    unsafe_allow_html=True
                )

                colunas_disponiveis_itens = [
                    "Cód. produto", "Desc. produto",
                    "Qtd venda (cx)", "Volume (hl)", "Valor líquido (R$)",
                    "Distribuição"
                ]
                colunas_itens = [c for c in colunas_disponiveis_itens if c in itens.columns]

                itens_exibir = itens[colunas_itens].copy().reset_index(drop=True)
                if "Distribuição" in itens_exibir.columns:
                    itens_exibir["Distribuição"] = itens_exibir["Distribuição"].map(
                        {1: "✅", 0: "❌"}
                    ).fillna("❌")

                st.dataframe(itens_exibir, use_container_width=True, hide_index=True)
                st.markdown("---")
