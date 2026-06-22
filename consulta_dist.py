# ======================================================
# APP DE CONSULTA DE PEDIDOS - DISTRIBUIÇÃO
# Autor: Ricardo Marchette Sabino
# Descrição: Permite que vendedores consultem se seus
# pedidos estão contabilizando como distribuição.
# ======================================================

import streamlit as st
import pandas as pd

# ------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------
st.set_page_config(
    page_title="Consulta de Pedidos - Distribuição",
    page_icon="📦",
    layout="wide"
)

# ------------------------------------------------------
# TÍTULO E DESCRIÇÃO
# ------------------------------------------------------
st.title("📦 Consulta de Pedidos - Distribuição")
st.caption("Consulte em tempo real se seu pedido está contabilizando como distribuição.")

# ------------------------------------------------------
# UPLOAD DA BASE (somente você precisa fazer isso)
# ------------------------------------------------------
st.sidebar.header("⚙️ Área do Administrador")
arquivo = st.sidebar.file_uploader(
    "Carregue a base de pedidos (Excel ou CSV):",
    type=["xlsx", "csv"]
)

# ------------------------------------------------------
# FUNÇÃO PARA LER O ARQUIVO
# ------------------------------------------------------
@st.cache_data
def carregar_base(arquivo):
    if arquivo.name.endswith(".csv"):
        df = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig")
    else:
        df = pd.read_excel(arquivo)
    # Remove espaços extras nos nomes das colunas
    df.columns = df.columns.str.strip()
    return df

# ------------------------------------------------------
# SE A BASE FOI CARREGADA, MOSTRA O APP
# ------------------------------------------------------
if arquivo is not None:
    df = carregar_base(arquivo)

    st.success(f"Base carregada com sucesso! Total de registros: {len(df)}")

    # ------------------------------------------------------
    # FILTROS NA LATERAL
    # ------------------------------------------------------
    st.sidebar.header("🔎 Filtros")

    # Detecta colunas automaticamente (case-insensitive)
    colunas = {c.lower(): c for c in df.columns}

    col_vendedor = colunas.get("vendedor")
    col_cliente = colunas.get("cliente")
    col_pedido = colunas.get("pedido")
    col_sku = colunas.get("sku")
    col_status = colunas.get("status")

    # Filtro por vendedor
    if col_vendedor:
        vendedores = ["Todos"] + sorted(df[col_vendedor].dropna().unique().tolist())
        filtro_vendedor = st.sidebar.selectbox("Vendedor:", vendedores)
        if filtro_vendedor != "Todos":
            df = df[df[col_vendedor] == filtro_vendedor]

    # Filtro por status
    if col_status:
        status_opcoes = ["Todos"] + sorted(df[col_status].dropna().unique().tolist())
        filtro_status = st.sidebar.selectbox("Status da distribuição:", status_opcoes)
        if filtro_status != "Todos":
            df = df[df[col_status] == filtro_status]

    # Busca livre por pedido / cliente / SKU
    busca = st.text_input("🔍 Buscar por nº do pedido, cliente ou SKU:")
    if busca:
        mascara = pd.Series([False] * len(df))
        for c in [col_pedido, col_cliente, col_sku]:
            if c:
                mascara |= df[c].astype(str).str.contains(busca, case=False, na=False)
        df = df[mascara]

    # ------------------------------------------------------
    # INDICADORES (cards no topo)
    # ------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de pedidos", len(df))

    if col_status:
        contabilizando = df[df[col_status].astype(str).str.lower().str.contains("sim|ok|contabiliz", na=False)]
        nao_contabilizando = df[df[col_status].astype(str).str.lower().str.contains("não|nao|erro|fora", na=False)]
        col2.metric("✅ Contabilizando", len(contabilizando))
        col3.metric("❌ Não contabilizando", len(nao_contabilizando))

    # ------------------------------------------------------
    # TABELA DE RESULTADOS
    # ------------------------------------------------------
    st.subheader("📋 Resultados")
    st.dataframe(df, use_container_width=True, height=500)

    # ------------------------------------------------------
    # BOTÃO PARA BAIXAR O RESULTADO
    # ------------------------------------------------------
    csv_export = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ Baixar resultado filtrado",
        data=csv_export,
        file_name="resultado_filtrado.csv",
        mime="text/csv"
    )

else:
    st.info("👈 Carregue uma base no menu lateral para começar.")
    st.markdown("""
    ### Como usar:
    1. O administrador carrega a base de pedidos no menu lateral.
    2. O vendedor escolhe seu nome no filtro.
    3. Pode buscar por número do pedido, cliente ou SKU.
    4. O status mostra se o pedido **contabiliza distribuição** ou não.
    """)