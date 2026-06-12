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
    conn = sqlite3.connect("pdceaf_database.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS registros (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_criador TEXT, municipio TEXT, nome TEXT, cpf TEXT, num_sigaf TEXT, num_sei TEXT, medicamento TEXT, status_sigaf TEXT, data_envio TEXT, situacao_caf TEXT, analisado_por TEXT, resolvido INTEGER)")
    
    cursor.execute("INSERT OR REPLACE INTO usuarios VALUES ('srsmedpassos@gmail.com', 'srs123456', 'admin')")
    
    for cidade in MUNICIPIOS_SRS:
        senha = gerar_senha_municipio(cidade)
        nivel_acesso = "admin" if cidade == "Passos" else "user"
        cursor.execute("INSERT OR REPLACE INTO usuarios VALUES (?, ?, ?)", (cidade, senha, nivel_acesso))
        
    conn.commit()
    conn.close()

init_db()

# --- CAIXA DE DIÁLOGO DE CONFIRMAÇÃO DE EXCLUSÃO (MANTIDA) ---
@st.dialog("⚠️ CONFIRMAÇÃO DE EXCLUSÃO PERMANENTE")
def confirmar_exclusao_dialog(id_registro, nome_paciente, municipio_paciente):
    st.markdown("<h3 style='color: #d9534f; margin-top: 0;'>🛑 Atenção!</h3>", unsafe_allow_html=True)
    st.write("Você tem certeza absoluta que deseja excluir permanentemente este registro?")
    
    st.error(f"**ID do Registro:** {id_registro}\n\n**Paciente:** {nome_paciente}\n\n**Município:** {municipio_paciente}")
    st.markdown("<p style='color: gray; font-size: 13px;'>*Esta ação é irreversível e o registro sumirá de todos os relatórios e exportações.</p>", unsafe_allow_html=True)
    
    col_cancelar, col_deletar = st.columns(2)
    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with col_deletar:
        if st.button("💥 Sim, Excluir Registro", use_container_width=True):
            conn = sqlite3.connect("pdceaf_database.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registros WHERE id=?", (id_registro,))
            conn.commit()
            conn.close()
            st.success("O registro foi deletado com sucesso do banco de dados!")
            st.rerun()

# 3. SESSÃO DE AUTENTICAÇÃO
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

def login_user(username, password):
    conn = sqlite3.connect("pdceaf_database.db")
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
