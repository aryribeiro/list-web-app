import streamlit as st
import pandas as pd
import datetime
import pytz
import requests
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from streamlit.components.v1 import html
import random

# Configuração da página
st.set_page_config(
    page_title="List Web App!",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Remover o rodapé do Streamlit
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Função para obter o IP público
def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        ip_data = response.json()
        return ip_data['ip']
    except:
        return "Não foi possível obter o IP"

# Função para obter a data e hora atual no formato brasileiro
def get_brazil_datetime():
    brazil_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.datetime.now(brazil_tz)
    dias_semana = {
        0: 'Segunda-feira',
        1: 'Terça-feira',
        2: 'Quarta-feira',
        3: 'Quinta-feira',
        4: 'Sexta-feira',
        5: 'Sábado',
        6: 'Domingo'
    }
    dia_semana = dias_semana[now.weekday()]
    return f"{dia_semana}, {now.strftime('%d/%m/%Y %H:%M:%S')}"

# Inicialização das variáveis de estado
if 'registros' not in st.session_state:
    if os.path.exists('registros.csv'):
        try:
            st.session_state.registros = pd.read_csv('registros.csv')
        except:
            st.session_state.registros = pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora', 'IP'])
    else:
        st.session_state.registros = pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora', 'IP'])

if 'timer_started' not in st.session_state:
    st.session_state.timer_started = False
    
if 'timer_end_time' not in st.session_state:
    if os.path.exists('timer_end.txt'):
        try:
            with open('timer_end.txt', 'r') as f:
                end_time_str = f.read().strip()
                st.session_state.timer_end_time = datetime.datetime.fromisoformat(end_time_str)
                if st.session_state.timer_end_time > datetime.datetime.now():
                    st.session_state.timer_started = True
                else:
                    st.session_state.timer_end_time = None
        except:
            st.session_state.timer_end_time = None
    else:
        st.session_state.timer_end_time = None
    
if 'aula_iniciada' not in st.session_state:
    try:
        if os.path.exists('aula_estado.txt'):
            with open('aula_estado.txt', 'r') as f:
                estado = f.read().strip()
                st.session_state.aula_iniciada = (estado == 'iniciada')
        else:
            st.session_state.aula_iniciada = False
    except:
        st.session_state.aula_iniciada = False

if 'mostrando_senha' not in st.session_state:
    st.session_state.mostrando_senha = False

if 'senha_correta' not in st.session_state:
    st.session_state.senha_correta = False
    
if 'senha_professor' not in st.session_state:
    st.session_state.senha_professor = st.secrets.get("senha_professor", "professor@aws")

if 'ip_professor' not in st.session_state:
    try:
        if os.path.exists('ip_professor.txt'):
            with open('ip_professor.txt', 'r') as f:
                st.session_state.ip_professor = f.read().strip()
        else:
            st.session_state.ip_professor = None
    except:
        st.session_state.ip_professor = None
        
if 'botao_clicado' not in st.session_state:
    st.session_state.botao_clicado = None

if 'captcha_pergunta' not in st.session_state:
    st.session_state.captcha_pergunta = None

if 'captcha_resposta' not in st.session_state:
    st.session_state.captcha_resposta = None

# Função para verificar se o aluno já está registrado
def aluno_ja_registrado(email, ip):
    if st.session_state.registros.empty:
        return False
    return ((st.session_state.registros['Email'] == email) | 
            (st.session_state.registros['IP'] == ip)).any()

# Função para enviar email com a lista de presença
def enviar_lista_por_email():
    try:
        if st.session_state.registros.empty:
            st.warning("Não há alunos registrados para enviar por email.")
            return False
            
        destinatario = st.secrets["email_destinatario"]
        assunto = "Lista de Presença - " + get_brazil_datetime()
        
        corpo_email = "<h2>Lista de Presença</h2>"
        corpo_email += f"<p>Data e hora: {get_brazil_datetime()}</p>"
        corpo_email += f"<p>Total de alunos: {len(st.session_state.registros)}</p>"
        corpo_email += "<p>Segue a lista de alunos presentes:</p>"
        
        tabela_html = st.session_state.registros.to_html(index=False)
        corpo_email += tabela_html
        
        mensagem = MIMEMultipart()
        mensagem['From'] = "sistema@listadechamada.com"
        mensagem['To'] = destinatario
        mensagem['Subject'] = assunto
        
        mensagem.attach(MIMEText(corpo_email, 'html'))
        
        try:
            servidor = smtplib.SMTP('smtp.gmail.com', 587)
            servidor.starttls()
            
            email_remetente = st.secrets.get("email", "seu_email@gmail.com")
            senha_app = st.secrets.get("senha_email", "sua_senha_de_app")
            
            if email_remetente != "seu_email@gmail.com" and senha_app != "sua_senha_de_app":
                servidor.login(email_remetente, senha_app)
                servidor.send_message(mensagem)
                servidor.quit()
                st.success("Email enviado com sucesso!")
            else:
                st.warning("Para enviar emails reais, configure as credenciais no arquivo secrets.toml ou diretamente no código.")
                st.info("Instruções: \n1. Crie uma senha de app no Gmail: https://support.google.com/accounts/answer/185833 \n2. Configure as credenciais no arquivo secrets.toml ou diretamente no código.")
                st.warning("Simulação: Email enviado.")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f'lista_presenca_{timestamp}.csv'
            st.session_state.registros.to_csv(backup_filename, index=False)
            st.info(f"Backup da lista salvo em: {backup_filename}")
            return True
            
        except Exception as e:
            st.error(f"Erro ao configurar servidor de email: {str(e)}")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f'lista_presenca_{timestamp}.csv'
            st.session_state.registros.to_csv(backup_filename, index=False)
            st.info(f"Backup da lista salvo em: {backup_filename}")
            return False
    except Exception as e:
        st.error(f"Erro ao preparar email: {str(e)}")
        return False

# Função para iniciar o cronômetro
def iniciar_cronometro():
    if st.session_state.aula_iniciada:
        st.session_state.timer_started = True
        st.session_state.timer_end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        try:
            with open('timer_end.txt', 'w') as f:
                f.write(st.session_state.timer_end_time.isoformat())
        except:
            st.warning("Não foi possível salvar o tempo final no arquivo.")

# Função para gerar CAPTCHA
def gerar_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    pergunta = f"Quanto é {num1} + {num2}?"
    resposta = num1 + num2
    return pergunta, resposta

# Função para verificar a senha e o CAPTCHA
def verificar_senha_e_captcha(senha_digitada, resposta_captcha):
    if 'captcha_resposta' not in st.session_state:
        return False
    try:
        return (senha_digitada == st.session_state.senha_professor and 
                int(resposta_captcha) == st.session_state.captcha_resposta)
    except ValueError:
        return False

# Função para resetar a lista de presença
def resetar_lista():
    enviar_lista_por_email()
    st.session_state.registros = pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora', 'IP'])
    st.session_state.registros.to_csv('registros.csv', index=False)
    st.session_state.timer_started = False
    st.session_state.timer_end_time = None
    st.session_state.aula_iniciada = False
    st.session_state.ip_professor = None
    st.session_state.senha_correta = False
    st.session_state.botao_clicado = None
    st.session_state.mostrando_senha = False
    st.session_state.form_submitted = False
    st.session_state.captcha_pergunta = None
    st.session_state.captcha_resposta = None
    try:
        if os.path.exists('aula_estado.txt'):
            os.remove('aula_estado.txt')
        if os.path.exists('timer_end.txt'):
            os.remove('timer_end.txt')
        if os.path.exists('ip_professor.txt'):
            os.remove('ip_professor.txt')
    except:
        st.warning("Não foi possível remover arquivos de estado.")
    st.success("Lista de presença finalizada e enviada por email com sucesso!")
    st.rerun()

# Função para iniciar a aula
def iniciar_aula():
    st.session_state.aula_iniciada = True
    ip_atual = get_public_ip()
    st.session_state.ip_professor = ip_atual
    st.session_state.senha_correta = True
    try:
        with open('ip_professor.txt', 'w') as f:
            f.write(ip_atual)
    except:
        st.warning("Não foi possível salvar o IP do professor no arquivo.")
    try:
        with open('aula_estado.txt', 'w') as f:
            f.write('iniciada')
    except:
        st.warning("Não foi possível salvar o estado da aula no arquivo.")
    iniciar_cronometro()

# Função para adicionar um novo registro
def adicionar_registro(nome, email):
    data_hora = get_brazil_datetime()
    ip = get_public_ip()
    if aluno_ja_registrado(email, ip):
        return False
    novo_registro = pd.DataFrame({
        'Nome': [nome],
        'Email': [email],
        'Data_Hora': [data_hora],
        'IP': [ip]
    })
    st.session_state.registros = pd.concat([st.session_state.registros, novo_registro], ignore_index=True)
    st.session_state.registros.to_csv('registros.csv', index=False)
    return True

# Layout principal
header_col1, header_col2 = st.columns([3, 1])
st.markdown("<h1 style='text-align: center;'>📝List Web App!</h1>", unsafe_allow_html=True)

with header_col2:
    if st.session_state.timer_started and st.session_state.timer_end_time:
        end_time_ms = int(st.session_state.timer_end_time.timestamp() * 1000)
        timer_html = f"""
        <div style='text-align: right;'>
            <h3 id="cronometro">Carregando...</h3>
        </div>
        <script>
            (function() {{
                const endTime = {end_time_ms};
                function updateTimer() {{
                    const now = new Date().getTime();
                    const distance = endTime - now;
                    if (distance > 0) {{
                        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                        const timeString = 
                            (hours < 10 ? "0" + hours : hours) + ":" + 
                            (minutes < 10 ? "0" + minutes : minutes) + ":" + 
                            (seconds < 10 ? "0" + seconds : seconds);
                        document.getElementById("cronometro").textContent = timeString;
                    }} else {{
                        document.getElementById("cronometro").textContent = "00:00:00";
                        clearInterval(timerInterval);
                        setTimeout(() => {{ window.location.reload(); }}, 2000);
                    }}
                }}
                updateTimer();
                const timerInterval = setInterval(updateTimer, 1000);
                window.addEventListener('beforeunload', () => {{
                    clearInterval(timerInterval);
                }});
            }})();
        </script>
        """
        html(timer_html, height=50)
    else:
        st.markdown("<div style='text-align: right;'><h3>01:00:00</h3></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: right;'>IP: {get_public_ip()}</div>", unsafe_allow_html=True)

ip_atual = get_public_ip()
is_professor = True

if is_professor:
    st.markdown("---")
    prof_col1, prof_col2, prof_col3 = st.columns([1, 1, 1])
    with prof_col2:
        if not st.session_state.aula_iniciada:
            if st.button("Iniciar Lista", key="btn_start", use_container_width=True):
                st.session_state.mostrando_senha = True
                st.session_state.botao_clicado = "start"
        else:
            if st.button("Finalizar Lista", key="btn_reset", use_container_width=True):
                st.session_state.mostrando_senha = True
                st.session_state.botao_clicado = "reset"
        
        if st.session_state.mostrando_senha:
            # Gerar CAPTCHA se não estiver definido ou for None
            if st.session_state.get('captcha_pergunta') is None:
                pergunta, resposta = gerar_captcha()
                st.session_state.captcha_pergunta = pergunta
                st.session_state.captcha_resposta = resposta
            
            with st.form(key="senha_form"):
                st.write(st.session_state.captcha_pergunta)
                resposta_captcha = st.text_input("Resposta do CAPTCHA:", key="captcha_input")
                senha = st.text_input("Digite a senha do professor:", type="password", key="senha_input")
                submit_senha = st.form_submit_button("Confirmar")
                
                if submit_senha and senha and resposta_captcha:
                    if verificar_senha_e_captcha(senha, resposta_captcha):
                        st.session_state.senha_correta = True
                        if st.session_state.botao_clicado == "start":
                            iniciar_aula()
                            st.success("Aula iniciada com sucesso!")
                            st.session_state.mostrando_senha = False
                            st.rerun()
                        elif st.session_state.botao_clicado == "reset":
                            resetar_lista()
                        elif st.session_state.botao_clicado == "auth":
                            st.session_state.senha_correta = True
                            st.success("Autenticado com sucesso! Você agora tem acesso aos controles do professor.")
                            st.session_state.mostrando_senha = False
                            st.rerun()
                        # Resetar CAPTCHA após uso bem-sucedido
                        del st.session_state.captcha_pergunta
                        del st.session_state.captcha_resposta
                    else:
                        st.error("Senha ou CAPTCHA incorreto!")
                        # Resetar CAPTCHA para nova tentativa
                        del st.session_state.captcha_pergunta
                        del st.session_state.captcha_resposta
                elif submit_senha:
                    st.error("Por favor, preencha todos os campos.")

if st.session_state.aula_iniciada and not is_professor and st.session_state.ip_professor is not None:
    auth_col1, auth_col2, auth_col3 = st.columns([1, 1, 1])
    with auth_col2:
        st.markdown("---")
        st.info("Se você é o professor e seu IP mudou, clique abaixo para se autenticar.")
        if st.button("Autenticar como Professor", key="btn_auth_professor", use_container_width=True):
            st.session_state.mostrando_senha = True
            st.session_state.botao_clicado = "auth"

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.session_state.aula_iniciada:
        st.subheader("Registre sua presença preenchendo o formulário abaixo")
        if 'form_submitted' not in st.session_state:
            st.session_state.form_submitted = False
        nome_inicial = "" if st.session_state.get('form_submitted', False) else st.session_state.get('registro_form_nome', "")
        email_inicial = "" if st.session_state.get('form_submitted', False) else st.session_state.get('registro_form_email', "")
        if st.session_state.get('form_submitted', False):
            st.session_state.form_submitted = False
        with st.form(key="registro_form"):
            nome = st.text_input("Nome Completo", value=nome_inicial, key="registro_form_nome")
            email = st.text_input("E-mail", value=email_inicial, key="registro_form_email")
            submit_button = st.form_submit_button(label="Registrar Presença")
            if submit_button:
                if nome and email:
                    if adicionar_registro(nome, email):
                        st.success(f"Presença de {nome} registrada com sucesso!")
                        st.session_state.form_submitted = True
                        st.rerun()
                    else:
                        st.error(f"Não foi possível registrar {nome}. Este email ou IP já está registrado.")
                else:
                    st.error("Por favor, preencha todos os campos.")
    else:
        st.info("Aguarde o professor iniciar a lista para registrar sua presença.")

with st.sidebar:
    st.header("👨🏻‍🎓 Alunos Presentes")
    if not st.session_state.registros.empty:
        st.subheader(f"Total: {len(st.session_state.registros)}")
        alunos_ordenados = st.session_state.registros.sort_values(by='Nome')
        for i, aluno in alunos_ordenados.iterrows():
            st.write(f"**{aluno['Nome']}**")
            st.write(f"<small>{aluno['Data_Hora']}</small>", unsafe_allow_html=True)
            st.divider()
    else:
        st.write("Nenhum aluno registrado!")

st.markdown("---")
st.markdown(f"<div style='text-align: center;'>{get_brazil_datetime()}</div>", unsafe_allow_html=True)

# Estilo personalizado
st.markdown("""
<style>
    .main {
        background-color: #ffffff;
        color: #333333;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    /* Esconde completamente todos os elementos da barra padrão do Streamlit */
    header {display: none !important;}
    footer {display: none !important;}
    #MainMenu {display: none !important;}
    /* Remove qualquer espaço em branco adicional */
    div[data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    /* Remove quaisquer margens extras */
    .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# Informações de contato
st.markdown("""
<hr>
<div style="text-align: center;">
    <h4>List Web App! - Lista de presença digital</h4>
    <p>Por Ary Ribeiro. Contato, através do email <a href="mailto:aryribeiro@gmail.com">aryribeiro@gmail.com</a></p>
</div>
""", unsafe_allow_html=True)
