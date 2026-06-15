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

# 2. FUNÇÕES AUXILIARES E CONEXÃO COM BANCO DE DADOS
def gerar_senha_municipio(nome_cidade):
    nfkd_form = unicodedata.normalize('NFKD', nome_cidade)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    limpo = "".join([c for c in only_ascii if c.isalpha()]).lower()
    return f"{limpo[:3]}12345"

def run_query(query, params=(), is_select=False):
    conn = sqlite3.connect("pdceaf_database.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    if is_select:
        data = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        conn.close()
        return pd.DataFrame(data, columns=columns)
    conn.commit()
    conn.close()

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

# --- CAIXA DE DIÁLOGO DE CONFIRMAÇÃO DE EXCLUSÃO ---
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

# Define as opções do menu de acordo com o nível de privilégio do usuário
menu_opcoes = ["Visualizar Registros", "Inserir Novo Registro", "Gerenciar Existentes"]
if st.session_state.role == "admin":
    menu_opcoes.append("Backup e Restauração")

menu_opcao = st.sidebar.radio("Selecione uma ação:", menu_opcoes)

if st.sidebar.button("🚪 Sair do Sistema"):
    logout_user()

if st.session_state.role == "admin":
    view_query = "SELECT * FROM registros ORDER BY id ASC"
    params = ()
else:
    view_query = "SELECT * FROM registros WHERE usuario_criador = ? ORDER BY id ASC"
    params = (st.session_state.username,)

# --- ABA 1: VISUALIZAÇÃO COM FILTROS DE BUSCA POR CAMPO ---
if menu_opcao == "Visualizar Registros":
    st.header("📋 Banco de Dados Atual (Modo Administrador)" if st.session_state.role == "admin" else "📋 Banco de Dados Atual")
    df_base = run_query(view_query, params, is_select=True)
    
    if df_base.empty:
        st.warning("Nenhum registro cadastrado no sistema.")
    else:
        st.markdown("### 🔍 Filtros de Busca Avançada")
        
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            f_nome = st.text_input("👤 Nome do Paciente", key="filter_nome")
        with f_col2:
            f_cpf = st.text_input("🪪 CPF", key="filter_cpf")
        with f_col3:
            f_municipio = st.text_input("📍 Município", key="filter_municipio")
        with f_col4:
            f_medicamento = st.text_input("💊 Medicamento", key="filter_med")
            
        f_col5, f_col6, f_col7, f_col8 = st.columns(4)
        with f_col5:
            f_sigaf = st.text_input("🔢 N° SIGAF", key="filter_sigaf")
        with f_col6:
            f_sei = st.text_input("📂 N° SEI", key="filter_sei")
        with f_col7:
            f_status = st.selectbox("📊 Status SIGAF", ["Todos", "Deferido", "Indeferido", "Em análise", "Em certificação"], key="filter_status")
        with f_col8:
            f_resolvido = st.selectbox("✅ Resolvido", ["Todos", "Sim", "Não"], key="filter_resolvido")

        df = df_base.copy()
        if f_nome:
            df = df[df['nome'].astype(str).str.contains(f_nome, case=False, na=False)]
        if f_cpf:
            df = df[df['cpf'].astype(str).str.contains(f_cpf, case=False, na=False)]
        if f_municipio:
            df = df[df['municipio'].astype(str).str.contains(f_municipio, case=False, na=False)]
        if f_medicamento:
            df = df[df['medicamento'].astype(str).str.contains(f_medicamento, case=False, na=False)]
        if f_sigaf:
            df = df[df['num_sigaf'].astype(str).str.contains(f_sigaf, case=False, na=False)]
        if f_sei:
            df = df[df['num_sei'].astype(str).str.contains(f_sei, case=False, na=False)]
        if f_status != "Todos":
            df = df[df['status_sigaf'] == f_status]
        if f_resolvido != "Todos":
            val_res_check = 1 if f_resolvido == "Sim" else 0
            df = df[df['resolvido'] == val_res_check]

        st.markdown("---")
        
        if df.empty:
            st.info("Nenhum registro corresponde aos critérios dos filtros aplicados.")
        else:
            df_visualizacao = df.copy()
            df_visualizacao["resolvido"] = df_visualizacao["resolvido"].apply(lambda x: "✅ Sim" if x == 1 else "❌ Não")
            st.dataframe(df_visualizacao, use_container_width=True)
            
            st.markdown("---")
            st.subheader("📥 Exportar Registros Otimizados")
            
            total_linhas = len(df)
            st.markdown(f"Baixe os registros exibidos acima em formatos de alta compatibilidade. *(Total de **{total_linhas}** linhas estruturadas de acordo com a sua busca atual)*.")
            
            col_csv, col_txt, col_pdf = st.columns(3)
            
            data_atual_slug = datetime.today().strftime("%Y-%m-%d")
            data_atual_pt = datetime.today().strftime("%d/%m/%Y %H:%M:%S")
            nome_usuario_atual = st.session_state.username
            role_usuario_atual = st.session_state.role.upper()
            
            with col_csv:
                csv_data = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 Baixar em CSV (Excel / Sheets)",
                    data=csv_data,
                    file_name=f"PDCEAF_Export_{data_atual_slug}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            with col_txt:
                txt_data = df.to_csv(index=False, sep="\t", encoding="utf-8")
                st.download_button(
                    label="📥 Baixar em TXT (Tabulado)",
                    data=txt_data,
                    file_name=f"PDCEAF_Export_{data_atual_slug}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
                
            with col_pdf:
                html_table = df.to_html(index=False, classes="table")
                html_content = "<html><head><meta charset='utf-8'><title>Relatório Oficial PDCEAF</title><style>body { font-family: Arial, sans-serif; margin: 30px; color: #333; } h2 { color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 8px; } p { font-size: 14px; margin: 4px 0; } table { width: 100%; border-collapse: collapse; margin-top: 20px; } th, td { border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 11px; } th { background-color: #f5f5f5; font-weight: bold; } tr:nth-child(even) { background-color: #fafafa; }</style></head><body><h2>Relatório de Solicitações PDCEAF - SRS Passos</h2>"
                html_content += f"<p><strong>Emitido por:</strong> {nome_usuario_atual}</p>"
                html_content += f"<p><strong>Nível de Acesso:</strong> {role_usuario_atual}</p>"
                html_content += f"<p><strong>Data de Exportação:</strong> {data_atual_pt}</p>"
                html_content += f"{html_table}</body></html>"
                
                st.download_button(
                    label="📄 Baixar Layout de Impressão (PDF)",
                    data=html_content.encode("utf-8"),
                    file_name=f"PDCEAF_Export_{data_atual_slug}.html",
                    mime="text/html",
                    use_container_width=True
                )
                st.caption("💡 *Dica do PDF:* Ao abrir o arquivo baixado, pressione **Ctrl + P** no teclado e selecione **'Salvar como PDF'**!")

# --- ABA 2: INSERIR NOVO REGISTRO ---
elif menu_opcao == "Inserir Novo Registro":
    st.header("📝 Cadastrar Nova Solicitação")
    
    if st.session_state.username in MUNICIPIOS_SRS:
        idx_padrao_municipio = MUNICIPIOS_SRS.index(st.session_state.username)
    else:
        idx_padrao_municipio = 0

    with st.form("insert_form", clear_on_submit=True):
        r1_c1, r1_c2, r1_c3 = st.columns([2, 1, 1])
        with r1_c1:
            nome = st.text_input("1. Nome do Paciente")
        with r1_c2:
            cpf = st.text_input("2. CPF")
        with r1_c3:
            municipio = st.selectbox("3. Município", MUNICIPIOS_SRS, index=idx_padrao_municipio)
            
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        with r2_c1:
            num_sigaf = st.text_input("4. N° SIGAF")
        with r2_c2:
            num_sei = st.text_input("5. N° SEI")
        with r2_c3:
            data_envio = st.date_input("6. Data de Envio", datetime.today()).strftime("%Y-%m-%d")
            
        r3_c1, r3_c2, r3_c3 = st.columns([2, 1, 1])
        with r3_c1:
            medicamento = st.text_input("7. Medicamento")
        with r3_c2:
            status_sigaf = st.selectbox("8. Status SIGAF", ["Deferido", "Indeferido", "Em análise", "Em certificação"])
        with r3_c3:
            situacao_caf = st.selectbox("9. Situação (Preenchimento CAF)", ["Monitoramento", "Processo Novo", "Reavaliação", "Via Rápida", "Via Urgente"])
            
        r4_c1, r4_c2 = st.columns([3, 1])
        with r4_c1:
            analisado_por = st.text_input("10. Analisado por:")
        with r4_c2:
            st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            resolvido = st.checkbox("11. Resolvido")
            
        st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("💾 Salvar Registro")
        
        if submit_btn:
            insert_sql = "INSERT INTO registros (usuario_criador, municipio, nome, cpf, num_sigaf, num_sei, medicamento, status_sigaf, data_envio, situacao_caf, analisado_por, resolvido) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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
        
        r1_c1, r1_c2, r1_c3 = st.columns([2, 1, 1])
        with r1_c1:
            edit_nome = st.text_input("1. Nome do Paciente", value=row["nome"])
        with r1_c2:
            edit_cpf = st.text_input("2. CPF", value=row["cpf"])
        with r1_c3:
            idx_mun = MUNICIPIOS_SRS.index(row["municipio"]) if row["municipio"] in MUNICIPIOS_SRS else 0
            edit_municipio = st.selectbox("3. Município", MUNICIPIOS_SRS, index=idx_mun)
            
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        with r2_c1:
            edit_num_sigaf = st.
