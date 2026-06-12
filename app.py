import streamlit as st
import sqlite3
import pandas as pd
import unicodedata
from datetime import datetime

# Configuração da página do Streamlit
st.set_page_config(page_title="Sistema PDCEAF - SRS Passos", layout="wide")

# 1. LISTA OFICIAL DE MUNICÍPIOS DA SRS PASSOS MG
MUNICIPIOS_SRS = [
    "Alpinópolis", "Alterosa", "Arceburgo", "Areado", "Bom Jesus da Penha", 
    "Carmo do Rio Claro", "Cássia", "Claraval", "Conceição da Aparecida", 
    "Delfinópolis", "Fortaleza de Minas", "Guaranésia", "Guaxupé", "Ibiraci", 
    "Itamogi", "Itaú de Minas", "Jacuí", "Monte Santo de Minas", "Nova Resende", 
    "Passos", "Pimenta", "Pratápolis", "São João Batista do Glória", 
    "São José da Barra", "São Roque de Minas", "São Sebastião do Paraíso", 
    "São Tomás de Aquino"
]

def gerar_senha_municipio(nome_cidade):
    nfkd_form = unicodedata.normalize('NFKD', nome_cidade)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    limpo = "".join([c for c in only_ascii if c.isalpha()]).lower()
    return f"{limpo[:3]}12345"

# 2. CONFIGURAÇÃO E CRIAÇÃO DO BANCO DE DADOS
def init_db():
    conn = sqlite3.connect('pdceaf_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_criador TEXT,
            municipio TEXT,
            nome TEXT,
            cpf TEXT,
            num_sigaf TEXT,
            num_sei TEXT,
            medicamento TEXT,
            status_sigaf TEXT,
            data_envio TEXT,
            situacao_caf TEXT,
            analisado_por TEXT,
            resolvido INTEGER
        )
    ''')
    cursor.execute("INSERT OR REPLACE INTO usuarios VALUES ('srsmedpassos@gmail.com', 'srs123456', 'admin')")
    
    for cidade in MUNICIPIOS_SRS:
        senha = gerar_senha_municipio(cidade)
        nivel_acesso = 'admin' if cidade == "Passos" else 'user'
        cursor.execute("INSERT OR REPLACE INTO usuarios VALUES (?, ?, ?)", (cidade, senha, nivel_acesso))
        
    conn.commit()
    conn.close()

init_db()

# 3. SESSÃO DE AUTENTICAÇÃO
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

def login_user(username, password):
    conn = sqlite3.connect('pdceaf_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM usuarios WHERE username = ? AND password = ?", (username, password))
    result = cursor.fetchone()
    conn.close()
    if result:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.role = result[0]
        return True
    return False

def logout_user():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

# --- TELA DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Sistema de Alimentação Planilha PDCEAF</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>SRS Passos - MG</h4>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Usuário (E-mail ou Município)")
            pass_input = st.text_input("Senha", type="password")
            submit_login = st.form_submit_button("Entrar no Sistema")
            
            if submit_login:
                if login_user(user_input, pass_input):
                    st.success(f"Bem-vindo, {user_input}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# --- ÁREA LOGADA ---
st.sidebar.title("📌 Menu de Navegação")
st.sidebar.info(f"**Usuário:**\n{st.session_state.username}")
menu_opcao = st.sidebar.radio("Selecione uma ação:", ["Visualizar Registros", "Inserir Novo Registro", "Gerenciar Existentes"])

if st.sidebar.button("🚪 Sair do Sistema"):
    logout_user()

def run_query(query, params=(), is_select=False):
    conn = sqlite3.connect('pdceaf_database.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    if is_select:
        data = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        conn.close()
        return pd.DataFrame(data, columns=columns)
    conn.commit()
    conn.close()

# Regra de Segurança com Ordenação obrigatória por ordem de Inclusão (id ASC)
if st.session_state.role == "admin":
    view_query = "SELECT * FROM registros ORDER BY id ASC"
    params = ()
else:
    view_query = "SELECT * FROM registros WHERE usuario_criador = ? ORDER BY id ASC"
    params = (st.session_state.username,)

# --- ABA 1: VISUALIZAÇÃO E EXPORTAÇÃO DE REGISTROS ---
if menu_opcao == "Visualizar Registros":
    st.header("📋 Banco de Dados Atual (Modo Administrador)" if st.session_state.role == "admin" else "📋 Banco de Dados Atual")
    df = run_query(view_query, params, is_select=True)
    
    if df.empty:
        st.warning("Nenhum registro encontrado.")
    else:
        # Cria uma cópia formatada apenas para exibição em tela
        df_visualizacao = df.copy()
        df_visualizacao['resolvido'] = df_visualizacao['resolvido'].apply(lambda x: "✅ Sim" if x == 1 else "❌ Não")
        st.dataframe(df_visualizacao, use_container_width=True)
        
        # --- NOVA SEÇÃO DE EXPORTAÇÃO UNIFICADA (Disponível para TODOS os usuários) ---
        st.markdown("---")
        st.subheader("📥 Exportar Registros Otimizados")
        st.markdown(
            f"Baixe os registros exibidos acima em formatos de alta compatibilidade. "
            f"*(Total de **{len(df)}** linhas estruturadas por ordem cronológica de inclusão)*."
        )
        
        col_csv, col_txt, col_pdf = st.columns(3)
        
        with col_csv:
            # utf-8-sig garante que acentos abram perfeitamente direto no Excel ou Google Sheets brasileiro
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Baixar em CSV (Excel / Sheets)",
                data=csv_data,
                file_name=f"PDCEAF_Export_{datetime.today().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_txt:
            # Formato de texto separado por tabulação (Tab), ideal para relatórios limpos no Bloco de Notas
            txt_data = df.to_csv(index=False, sep='\t', encoding='utf-8')
            st.download_button(
                label="📥 Baixar em TXT (Tabulado)",
                data=txt_data,
                file_name=f"PDCEAF_Export_{datetime.today().strftime('%Y-%m-%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        with col_pdf:
            # Estrutura HTML limpa para geração nativa de PDF direto pelas ferramentas do navegador
            html_table = df.to_html(index=False, classes='table')
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>Relatório Oficial PDCEAF</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 30px; color: #333; }}
                    h2 {{ color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 8px; }}
                    p {{ font-size: 14px; margin: 4px 0; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 11px; }}
                    th {{ background-color: #f5f5f5; font-weight: bold; }}
                    tr:nth-child(even) {{ background-color: #fafafa; }}
                </style>
            </head>
            <body>
                <h2>Relatório de Solicitações PDCEAF - SRS Passos</h2>
                <p><strong>Emitido por:</strong> {st.session_state.username}</p>
                <p><strong>Nível de Acesso:</strong> {st.session_state.role.upper()}</p>
                <p><strong>Data de Exportação:</strong> {datetime.today().strftime('%d/%m/%Y %H:%M:%S')}</p>
                {html_table}
            </body>
            </html>
            """
            st.download_button(
