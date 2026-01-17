import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
import io
import base64
import time

# --- CORREÇÃO PANDAS 2.0 ---
pd.Series.iteritems = pd.Series.items

# --- 0. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Monitoração - Grandes Eventos", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- FUNÇÃO JS PARA FORÇAR FECHAMENTO DA SIDEBAR ---
def fechar_sidebar_force():
    js = """
    <script>
        var attempts = 0;
        var interval = setInterval(function() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                if (sidebar.getAttribute("aria-expanded") === "true") {
                    const closeBtn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]');
                    if (closeBtn) {
                        closeBtn.click();
                        clearInterval(interval);
                    }
                } else {
                    clearInterval(interval);
                }
            }
            attempts++;
            if (attempts > 15) clearInterval(interval);
        }, 50); 
    </script>
    """
    components.html(js, height=0, width=0)

# --- FUNÇÃO PARA CARREGAR IMAGEM DE FUNDO ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return None

bin_str = get_base64_of_bin_file('fundo.jpg')

# Lógica de Fundo e CSS Dinâmico
if "escolha_evento" not in st.session_state:
    st.session_state.escolha_evento = "Selecione o Evento..."

if st.session_state.escolha_evento == "Selecione o Evento...":
    # TELA INICIAL
    if bin_str:
        bg_css = f"""
            background-image: linear-gradient(rgba(255, 253, 231, 0.6), rgba(255, 253, 231, 0.6)), url("data:image/jpg;base64,{bin_str}");
            background-size: cover;
            background-attachment: fixed;
        """
    else:
        bg_css = "background-color: #FFFDE7;"
    
    extra_css = """
    div[data-testid="stImage"] {
        display: flex; justify-content: center; align-items: center; width: 100%; margin: 0 auto;
    }
    div[data-testid="stImage"] img { margin: 0 auto !important; display: block; }
    .stSelectbox div[data-baseweb="select"] { margin: 0 auto; }
    """
else:
    # DASHBOARD
    bg_css = """
        background: linear-gradient(135deg, #F1F8E9 0%, #DCEDC8 100%);
        background-attachment: fixed;
    """
    extra_css = ""

AZUL_ANATEL = "#003366"    
AMARELO_ANATEL = "#FFCC00" 
VERDE_OK = "#2E7D32"       
VERMELHO_ALERTA = "#CC0000"

# PALETA VIRIDIS REVERSA
VIRIDIS_REVERSED = px.colors.sequential.Viridis_r

# --- CSS GERAL ---
st.markdown(f"""
<style>
    .stApp {{ {bg_css} }}
    
    {extra_css}

    /* REDUÇÃO DRÁSTICA DO ESPAÇO SUPERIOR */
    .main .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }}

    [data-testid="stHeaderActionElements"] {{ display: none !important; }}

    .welcome-text {{
        color: {AZUL_ANATEL}; font-size: 2.2em; font-weight: bold;
        margin-top: 10px; margin-bottom: 15px; text-align: center;
        text-shadow: 1px 1px 2px white; white-space: nowrap; width: 100%; display: block;
    }}

    h1, h2, h3 {{
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2) !important;
        text-align: center;
    }}
    
    /* Subtítulos à esquerda */
    h3 {{ text-align: left !important; }}

    .kpi-box {{ 
        border-radius: 12px; padding: 20px; text-align: center; color: white !important;
        box-shadow: 0 6px 15px rgba(0,0,0,0.15); height: 140px;
        display: flex; flex-direction: column; justify-content: center; position: relative;
    }}
    
    /* FONTE DO TÍTULO DO KPI AUMENTADA (+0.05) */
    .kpi-label {{ 
        font-weight: bold; font-size: 1.10em; text-shadow: 1px 1px 3px rgba(0,0,0,0.3); 
        margin-bottom: 8px; line-height: 1.2;
    }}
    
    .kpi-value {{ 
        font-weight: bold; font-size: 2.6em; line-height: 1; text-shadow: none; color: #000000 !important; 
    }}
    
    .info-icon-container {{ position: absolute; bottom: 8px; right: 8px; }}
    .info-icon {{
        display: inline-block; width: 16px; height: 16px; line-height: 16px;
        text-align: center; border-radius: 50%; background-color: rgba(255, 255, 255, 0.5);
        color: #1A311F; font-size: 11px; font-weight: bold; cursor: pointer;
    }}
    .tooltip-text {{
        visibility: hidden; width: 200px; background-color: #333; color: #fff;
        text-align: center; border-radius: 6px; padding: 5px;
        position: absolute; z-index: 1; bottom: 125%; left: 50%;
        margin-left: -100px; opacity: 0; transition: opacity 0.3s; font-size: 0.8em; font-weight: normal;
    }}
    .info-icon-container:hover .tooltip-text {{ visibility: visible; opacity: 1; }}

    div[data-testid="stSidebarHeader"] {{
        padding-bottom: 0rem !important; padding-top: 1rem !important; height: auto !important;
    }}

    div[data-testid="stMarkdownContainer"] hr {{
        margin-top: -0.5em !important; margin-bottom: -0.5em !important;
        border-top: 1px solid rgba(49, 51, 63, 0.2);
    }}

    /* BOTÃO EXPORTAR ALINHADO À DIREITA */
    .stDownloadButton {{ display: flex; justify-content: flex-end; width: 100%; }}
    .stDownloadButton > button {{ margin-left: auto; }}
    .stDownloadButton > button:hover {{
        background-color: #E8F5E9 !important; color: #003366 !important; border-color: #2E7D32 !important;
    }}
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def tratar_colunas_duplicadas(df):
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.loc[:, (df.columns != "") & (df.columns.notna())]
    return df

@st.cache_resource
def obter_cliente_gspread():
    try:
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except: return None

def buscar_planilhas():
    client = obter_cliente_gspread()
    if not client: return {}
    arquivos = client.list_spreadsheet_files()
    return {a['name'].replace("Monitoração - ", ""): a['name'] for a in arquivos if "Monitoração" in a['name']}

@st.cache_data(ttl=60)
def carregar_dados_base(nome_planilha):
    try:
        client = obter_cliente_gspread()
        planilha = client.open(nome_planilha)
        aba_p = planilha.worksheet("PAINEL")
        dados_p = aba_p.get_all_values()
        jam = dados_p[1][20] if len(dados_p) > 1 and len(dados_p[1]) > 20 else 0
        erb = dados_p[1][21] if len(dados_p) > 1 and len(dados_p[1]) > 21 else 0

        lista_dfs = []
        coord_data = []
        for aba in planilha.worksheets():
            if aba.title not in ["PAINEL", "Escala", "Tabela UTE", "LISTAS"]:
                try:
                    lat_v = aba.cell(4, 31).value
                    lon_v = aba.cell(5, 31).value
                    if lat_v and lon_v:
                        coord_data.append({"Estação": aba.title, "lat": float(str(lat_v).replace(',', '.')), "lon": float(str(lon_v).replace(',', '.'))})
                except: pass
                raw = aba.get_all_values()
                if len(raw) >= 3:
                    temp = pd.DataFrame(raw[2:], columns=raw[1])
                    temp = temp.rename(columns={'DD/MM/AAAA': 'Data', 'HH:mm': 'Hora'})
                    temp = tratar_colunas_duplicadas(temp)
                    if 'Fiscal' in temp.columns: temp = temp[temp['Fiscal'].str.strip() != ""]
                    if not temp.empty:
                        temp['Estação_Origem'] = aba.title
                        lista_dfs.append(temp)
        df_total = pd.concat(lista_dfs, ignore_index=True, sort=False).fillna("") if lista_dfs else pd.DataFrame()
        df_coords = pd.DataFrame(coord_data)
        ute_total = len(planilha.worksheet("Tabela UTE").get_all_values()) - 1
        return df_total, jam, erb, ute_total, df_coords
    except: return None

# --- FUNÇÃO LIMPAR FILTROS ---
def limpar_filtros():
    keys_to_clear = ["sb_data", "sb_est", "sb_fx", "sb_fr", "sb_int", "sb_lic", "sb_sit", "sb_ute"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# --- FLUXO PRINCIPAL ---
dict_eventos = buscar_planilhas()
opcoes_menu = ["Selecione o Evento..."] + list(dict_eventos.keys())

# --- TELA INICIAL ---
if st.session_state.escolha_evento == "Selecione o Evento...":
    fechar_sidebar_force()
    
    c_esq, c_center, c_dir = st.columns([0.36, 0.28, 0.36])
    
    with c_center:
        st.image("logo.png", width=180)
        st.markdown(f'<div class="welcome-text">Monitoração do Espectro - Grandes Eventos 2026</div>', unsafe_allow_html=True)
        escolha = st.selectbox("Escolha o evento", opcoes_menu, key="seletor_central", label_visibility="collapsed")
        
        if escolha != "Selecione o Evento...":
            st.session_state.escolha_evento = escolha
            st.session_state.trigger_close_sidebar = True
            st.rerun()

# --- DASHBOARD ATIVO ---
else:
    if st.session_state.get("trigger_close_sidebar", False):
        fechar_sidebar_force()
        st.session_state.trigger_close_sidebar = False
    
    fechar_sidebar_force()

    evento_nome = st.session_state.escolha_evento
    dados_base = carregar_dados_base(dict_eventos[evento_nome])

    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True) 
        nova = st.selectbox("Evento Atual:", opcoes_menu, index=opcoes_menu.index(evento_nome))
        if nova != evento_nome:
            st.session_state.escolha_evento = nova
            st.session_state.trigger_close_sidebar = True
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("Filtros")

    if dados_base:
        df_full, jam, erb, ute_total, df_coords = dados_base
        df_f = df_full.copy()
        
        def get_clean_unique(df, col):
            vals = df[col].astype(str).unique()
            return sorted([x for x in vals if x.strip() != "" and x.lower() != "nan"])

        with st.sidebar:
            if not df_full.empty:
                opts_data = ["Todas"] + get_clean_unique(df_full, 'Data')
                f_data = st.selectbox("Data:", opts_data, key="sb_data")
                if f_data != "Todas": df_f = df_f[df_f['Data'].astype(str) == f_data]
                
                opts_est = ["Todas"] + get_clean_unique(df_f, 'Estação_Origem')
                f_est = st.selectbox("Estação:", opts_est, key="sb_est")
                if f_est != "Todas": df_f = df_f[df_f['Estação_Origem'] == f_est]
                
                col_fx = 'Faixa de Frequência Envolvida' if 'Faixa de Frequência Envolvida' in df_f.columns else df_f.columns[0]
                opts_fx = ["Todas"] + get_clean_unique(df_f, col_fx)
                f_fx = st.selectbox("Faixa de Frequência:", opts_fx, key="sb_fx")
                if f_fx != "Todas": df_f = df_f[df_f[col_fx].astype(str) == f_fx]
                
                if 'Frequência (MHz)' in df_f.columns:
                    opts_fr = ["Todas"] + get_clean_unique(df_f, 'Frequência (MHz)')
                    f_fr = st.selectbox("Frequência (MHz):", opts_fr, key="sb_fr")
                    if f_fr != "Todas": df_f = df_f[df_f['Frequência (MHz)'].astype(str) == f_fr]
                
                if 'Interferente?' in df_f.columns:
                    f_int = st.selectbox("Interferente?:", ["Todas", "Sim", "Não"], key="sb_int")
                    if f_int != "Todas": 
                        val_int = "SIM" if f_int == "Sim" else "NÃO"
                        df_f = df_f[df_f['Interferente?'].astype(str).str.upper() == val_int]
                
                if 'Licenciada?' in df_f.columns:
                    opts_lic = ["Todas"] + get_clean_unique(df_f, 'Licenciada?')
                    f_lic = st.selectbox("Licenciamento:", opts_lic, key="sb_lic")
                    if f_lic != "Todas": df_f = df_f[df_f['Licenciada?'].astype(str) == f_lic]
                
                if 'Situação' in df_f.columns:
                    opts_sit = ["Todas"] + get_clean_unique(df_f, 'Situação')
                    f_sit = st.selectbox("Situação da emissão:", opts_sit, key="sb_sit")
                    if f_sit != "Todas": df_f = df_f[df_f['Situação'].astype(str) == f_sit]
                
                if 'UTE?' in df_f.columns:
                    f_ute = st.selectbox("Emissões UTE:", ["Todas", "Sim", "Não"], key="sb_ute")
                    if f_ute != "Todas":
                        val_ute = "TRUE" if f_ute == "Sim" else "FALSE"
                        df_f = df_f[df_f['UTE?'].astype(str).str.upper() == val_ute]

            st.markdown("---")
            try:
                c_freq = next((c for c in df_f.columns if "Frequência (MHz)" in c), None)
                c_bw = next((c for c in df_f.columns if "Largura" in c or "BW" in c), None)
                c_id = next((c for c in df_f.columns if "Designação" in c or "Identificação" in c), None)
                if c_freq and c_bw and c_id and not df_f.empty:
                    df_app = df_f[[c_freq, c_bw, c_id]].copy()
                    df_app.columns = ["Frequência (MHz)", "Largura (KHz)", "Identificação"]
                    buffer_app = io.BytesIO()
                    with pd.ExcelWriter(buffer_app, engine='xlsxwriter') as writer:
                        df_app.to_excel(writer, index=False)
                    st.download_button(
                        label="📱 Gerar arquivo AppAnálise",
                        data=buffer_app.getvalue(),
                        file_name=f"AppAnalise_{evento_nome}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            except: pass

            st.markdown("---")
            if st.button("Limpar Filtros", on_click=limpar_filtros, use_container_width=True):
                st.rerun()
            if st.button("🔄 Sincronizar", use_container_width=True): 
                st.cache_data.clear(); st.rerun()

        st.markdown(f"<h1 style='text-align: center; color: {AZUL_ANATEL};'>Monitoração do Espectro: {evento_nome}</h1>", unsafe_allow_html=True)
        st.markdown("---")

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        
        # AJUSTE NO TÍTULO DO KPI
        pend = (df_f['Situação'].str.contains("Pendente", na=False)).sum() if 'Situação' in df_f.columns else 0
        nao_licenciadas = (df_f['Licenciada?'].str.upper().str.contains("NÃO", na=False)).sum() if 'Licenciada?' in df_f.columns else 0
        
        g_verde = "linear-gradient(135deg, #4CAF50 0%, #9CCC65 100%)"
        g_amarelo = "linear-gradient(135deg, #FFCC00, #FBC02D)"
        g_azul = "linear-gradient(to bottom, #1a3f8a, #527ac9)"
        g_vermelho = "linear-gradient(135deg, #DF1B1D 0%, #E85C5D 100%)"

        metrics = [
            ("Emissões verificadas", len(df_f), g_verde, "Total de emissões verificadas..."), 
            ("Solicitações UTE", ute_total, g_azul, "Total de frequências solicitadas..."), 
            ("Emissões pendentes", pend, g_amarelo, "Total de emissões aguardando..."), # TÍTULO ALTERADO
            ("Não licenciadas", nao_licenciadas, g_vermelho, "Total de emissões 'Não' licenciadas..."), 
            ("BSR (Jammers)", jam, g_vermelho, "Contagem total de BSRs/Jammers..."), 
            ("ERBs Fake", erb, g_vermelho, "Contagem total de ERBs Fake...")
        ]
        
        for i, (lab, val, grad, tooltip) in enumerate(metrics):
            with [k1,k2,k3,k4,k5,k6][i]:
                st.markdown(f'''
                <div class="kpi-box" style="background:{grad}">
                    <div class="info-icon-container">
                        <span class="info-icon">i</span>
                        <span class="tooltip-text">{tooltip}</span>
                    </div>
                    <div class="kpi-label">{lab}</div>
                    <div class="kpi-value">{val}</div>
                </div>''', unsafe_allow_html=True)

        if not df_f.empty:
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            bg_l = dict(paper_bgcolor="rgba(240, 240, 240, 0.8)", plot_bgcolor="rgba(0, 0, 0, 0)", margin=dict(t=40, b=20, l=20, r=20), font=dict(color=AZUL_ANATEL))
            
            with c1:
                st.subheader("Emissões por Estação")
                fig1 = px.treemap(df_f, path=['Estação_Origem'], color_discrete_sequence=VIRIDIS_REVERSED)
                fig1.update_layout(bg_l); st.plotly_chart(fig1, use_container_width=True)
            with c2:
                st.subheader("Emissões por Faixa")
                fig2 = px.pie(df_f, names=col_fx, hole=0.4, color_discrete_sequence=VIRIDIS_REVERSED)
                fig2.update_traces(textposition='inside', textinfo='label+percent')
                fig2.update_layout(bg_l, showlegend=False); st.plotly_chart(fig2, use_container_width=True)
            with c3:
                st.subheader("Emissões por Tipo")
                d_tp = df_f.iloc[:, 8].value_counts().reset_index()
                d_tp.columns = ['Tipo', 'Qtd']
                d_tp['Label'] = d_tp.apply(lambda x: f"{x['Tipo']} ({x['Qtd']})", axis=1)
                
                # GRÁFICO BARRA SEM ESCALA
                fig3 = px.bar(d_tp, y='Tipo', x='Qtd', orientation='h', color='Tipo', color_discrete_sequence=VIRIDIS_REVERSED, text='Label')
                fig3.update_traces(textposition='auto')
                fig3.update_layout(bg_l, showlegend=False)
                fig3.update_yaxes(showticklabels=False)
                # REMOÇÃO DA ESCALA INFERIOR (EIXO X)
                fig3.update_xaxes(visible=False)
                st.plotly_chart(fig3, use_container_width=True)

        st.markdown("---")
        col_t, col_b = st.columns([0.8, 0.2])
        with col_t: st.subheader("Histórico Consolidado")
        
        cols_drop = ["Alguém mais ciente?", "Ocorrência (Observações)", "Ocorrência (observações)", "Ocorrência (obsevações)"]
        df_grid = df_f.drop(columns=[c for c in cols_drop if c in df_f.columns])
        
        if 'UTE?' in df_grid.columns:
            df_grid['UTE?'] = df_grid['UTE?'].astype(str).str.upper().str.strip().map({'TRUE': 'Sim', 'FALSE': 'Não', 'SIM': 'Sim', 'NÃO': 'Não', '': ''}).fillna(df_grid['UTE?'])
        if 'Situação' in df_grid.columns:
            df_grid = df_grid.iloc[:, :df_grid.columns.get_loc('Situação') + 1]

        with col_b:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_grid.to_excel(w, index=False)
            st.download_button("📥 Exportar para Excel (.xls)", buf.getvalue(), f"Historico_{evento_nome}.xlsx")

        gb = GridOptionsBuilder.from_dataframe(df_grid.astype(str))
        gb.configure_pagination(paginationPageSize=10)
        gb.configure_default_column(resizable=True, filter=True, sortable=True)
        gb.configure_grid_options(domLayout='normal') 
        
        AgGrid(
            df_grid.astype(str), 
            gridOptions=gb.build(), 
            theme='streamlit', 
            height=400, 
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
            use_container_width=True
        )

        if not df_coords.empty:
            st.subheader("Localização das Estações")
            centro_lat = df_coords['lat'].mean()
            centro_lon = df_coords['lon'].mean()
            
            # MAPA COM SCATTER_MAP
            fig_map = px.scatter_map(
                df_coords, 
                lat="lat", 
                lon="lon", 
                text="Estação", # Nome da estação
                hover_name="Estação", 
                color_discrete_sequence=[VERMELHO_ALERTA], 
                zoom=12
            )
            # CONFIGURAÇÃO DE TEXTO DO MAPA (NEGRITO E VISÍVEL)
            fig_map.update_traces(
                textposition='top center',
                textfont=dict(family="Arial Black", size=12, color="black", weight="bold"),
                marker=dict(size=14, opacity=0.9)
            )
            fig_map.update_layout(
                map_style="carto-positron", 
                margin={"r":0,"t":0,"l":0,"b":0}, 
                map_center={"lat": centro_lat, "lon": centro_lon}
            )
            st.plotly_chart(fig_map, use_container_width=True)