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
        
        # --- SEÇÃO DE EXPORTAÇÃO UNIFICADA ---
        st.markdown("---")
        st.subheader("📥 Exportar Registros Otimizados")
        
        total_linhas = len(df)
        st.markdown(f"Baixe os registros exibidos acima em formatos de alta compatibilidade. *(Total de **{total_linhas}** linhas estruturadas por ordem cronológica de inclusão)*.")
        
        col_csv, col_txt, col_pdf = st.columns(3)
        
        # Variáveis auxiliares para evitar quebras de sintaxe no interpretador
        data_atual_slug = datetime.today().strftime('%Y-%m-%d')
        data_atual_pt = datetime.today().strftime('%d/%m/%Y %H:%M:%S')
        nome_usuario_atual = st.session_state.username
        role_usuario_atual = st.session_state.role.upper()
        
        with col_csv:
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Baixar em CSV (Excel / Sheets)",
                data=csv_data,
                file_name=f"PDCEAF_Export_{data_atual_slug}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_txt:
            txt_data = df.to_csv(index=False, sep='\t', encoding='utf-8')
            st.download_button(
                label="📥 Baixar em TXT (Tabulado)",
                data=txt_data,
                file_name=f"PDCEAF_Export_{data_atual_slug}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        with col_pdf:
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
                <p><strong>Emitido por:</strong> {nome_usuario_atual}</p>
                <p><strong>Nível de Acesso:</strong> {role_usuario_atual}</p>
                <p><strong>Data de Exportação:</strong> {data_atual_pt}</p>
                {html_table}
            </body>
            </html>
            """
            st.download_button(
                label="📄 Baixar Layout de Impressão (PDF)",
                data=html_content.encode('utf-8'),
                file_name=f"PDCEAF_Export_{data_atual_slug}.html",
                mime="text/html",
                use_container_width=True
            )
            st.caption("💡 *Dica do PDF:* Ao abrir o arquivo baixado, pressione **Ctrl + P** no teclado e selecione **'Salvar como PDF'**!")

# --- ABA 2: INSERIR NOVO REGISTRO ---
elif menu_opcao == "Inserir Novo Registro":
    st.header("📝 Cadastrar Nova Solicitação")
    
    with st.form("insert_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.session_state.username in MUNICIPIOS_SRS:
                idx_padrao_municipio = MUNICIPIOS_SRS.index(st.session_state.username)
            else:
                idx_padrao_municipio = 0
                
            municipio = st.selectbox("Município", MUNICIPIOS_SRS, index=idx_padrao_municipio)
            nome = st.text_input("Nome do Paciente")
            cpf = st.text_input("CPF")
        with col2:
            num_sigaf = st.text_input("N° SIGAF")
            num_sei = st.text_input("N° SEI")
            medicamento = st.text_input("Medicamento")
        with col3:
            status_sigaf = st.selectbox("Status SIGAF", ["Deferido", "Indeferido", "Em análise", "Em certificação"])
            data_envio = st.date_input("Data de Envio", datetime.today()).strftime('%Y-%m-%d')
            situacao_caf = st.selectbox("Situação (Preenchimento CAF)", ["Monitoramento", "Processo Novo", "Reavaliação", "Via Rápida", "Via Urgente"])
            
        analisado_por = st.text_input("Analisado por:")
        resolvido = st.checkbox("Resolvido")
        
        submit_btn = st.form_submit_button("Salvar Registro")
        if submit_btn:
            insert_sql = """
                INSERT INTO registros (usuario_criador, municipio, nome, cpf, num_sigaf, num_sei, medicamento, status_sigaf, data_envio, situacao_caf, analisado_por, resolvido)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            run_query(insert_sql, (st.session_state.username, municipio, nome, cpf, num_sigaf, num_sei, medicamento, status_sigaf, data_envio, situacao_caf, analisado_por, 1 if resolvido else 0))
            st.success("Registro inserido com sucesso!")

# --- ABA 3: GERENCIAR EXISTENTES ---
elif menu_opcao == "Gerenciar Existentes":
    st.header("⚙️ Editar ou Remover Registros")
    df_edit = run_query(view_query, params, is_select=True)
    
    if df_edit.empty:
        st.warning("Não há dados disponíveis para edição.")
    else:
        registro_opcoes = df_edit.apply(lambda r: f"ID: {r['id']} | Paciente: {r['nome']} ({r['municipio']})", axis=1).tolist()
        selecionado = st.selectbox("Escolha o registro que deseja modificar:", registro_opcoes)
        id_selecionado = int(selecionado.split(" | ")[0].replace("ID: ", ""))
        row = df_edit[df_edit['id'] == id_selecionado].iloc[0]
        
        st.markdown("---")
        st.subheader(f"Modificando Registro ID: {id_selecionado}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            idx_mun = MUNICIPIOS_SRS.index(row['municipio']) if row['municipio'] in MUNICIPIOS_SRS else 0
            edit_municipio = st.selectbox("Município", MUNICIPIOS_SRS, index=idx_mun)
            edit_nome = st.text_input("Nome do Paciente", value=row['nome'])
            edit_cpf = st.text_input("CPF", value=row['cpf'])
        with col2:
            edit_num_sigaf = st.text_input("N° SIGAF", value=row['num_sigaf'])
            edit_num_sei = st.text_input("N° SEI", value=row['num_sei'])
            edit_medicamento = st.text_input("Medicamento", value=row['medicamento'])
        with col3:
            opcoes_sigaf = ["Deferido", "Indeferido", "Em análise", "Em certificação"]
            idx_sigaf = opcoes_sigaf.index(row['status_sigaf']) if row['status_sigaf'] in opcoes_sigaf else 0
            edit_status_sigaf = st.selectbox("Status SIGAF", opcoes_sigaf, index=idx_sigaf)
            try:
                dt_obj = datetime.strptime(row['data_envio'], '%Y-%m-%d')
            except:
                dt_obj = datetime.today()
            edit_data_envio = st.date_input("Data de Envio", dt_obj).strftime('%Y-%m-%d')
            opcoes_caf = ["Monitoramento", "Processo Novo", "Reavaliação", "Via Rápida", "Via Urgente"]
            idx_caf = opcoes_caf.index(row['situacao_caf']) if row['situacao_caf'] in opcoes_caf else 0
            edit_situacao_caf = st.selectbox("Situação (Preenchimento CAF)", opcoes_caf, index=idx_caf)
            
        edit_analisado_por = st.text_input("Analisado por:", value=row['analisado_por'])
        edit_resolvido = st.checkbox("Resolvido", value=bool(row['resolvido']))
        
        btn_atualizar, btn_deletar = st.columns(2)
        with btn_atualizar:
            if st.button("💾 Gravar Alterações", use_container_width=True):
                update_sql = """
                    UPDATE registros SET 
                    municipio=?, nome=?, cpf=?, num_sigaf=?, num_sei=?, medicamento=?, status_sigaf=?, data_envio=?, situacao_caf=?, analisado_por=?, resolvido=?
                    WHERE id=?
                """
                run_query(update_sql, (edit_municipio, edit_nome, edit_cpf, edit_num_sigaf, edit_num_sei, edit_medicamento, edit_status_sigaf, edit_data_envio, edit_situacao_caf, edit_analisado_por, 1 if edit_resolvido else 0, id_selecionado))
                st.success("Alterações gravadas com sucesso!")
                st.rerun()
        with btn_deletar:
            if st.button("❌ Excluir Registro Permanente", use_container_width=True):
                run_query("DELETE FROM registros WHERE id=?", (id_selecionado,))
                st.warning("Registro excluído!")
                st.rerun()
