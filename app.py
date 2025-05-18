import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from streamlit.components.v1 import html

# Page configuration
st.set_page_config(
    page_title="List Web App!",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit footer
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, 
    unsafe_allow_html=True
)

def get_public_ip():
    """
    Fetch the visitor's public IP address on the client-side using JavaScript.
    Returns an HTML placeholder that gets updated with the IP.
    """
    ip_html_code = """
    <div id="visitor-ip-container" style="display: none;">
        <span id="user-ip-address">Carregando IP...</span>
    </div>

    <script>
        var globalUserIP = "Carregando IP...";
        
        async function fetchAndDisplayUserIP() {
            const ipElement = document.getElementById('user-ip-address');
            try {
                let response = await fetch('https://ipinfo.io/json', {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' }
                });
                
                if (!response.ok) {
                    console.warn('ipinfo.io failed. Trying api.ipify.org...');
                    response = await fetch('https://api.ipify.org?format=json', {
                        method: 'GET',
                        headers: { 'Accept': 'application/json' }
                    });
                }

                if (!response.ok) {
                    throw new Error('All IP services failed');
                }

                const data = await response.json();
                const ip = data.ip || 'Não disponível';
                
                globalUserIP = ip;
                if (ipElement) {
                    ipElement.textContent = ip;
                }
                
                const displayElements = window.parent.document.getElementsByClassName('display-ip');
                for (let i = 0; i < displayElements.length; i++) {
                    displayElements[i].textContent = ip;
                }
                
                const ipStorage = window.parent.document.getElementById('ip-storage');
                if (ipStorage) {
                    ipStorage.textContent = ip;
                }
                
                const event = new CustomEvent('ip_ready', { detail: ip });
                window.parent.document.dispatchEvent(event);
            } catch (error) {
                console.error('Error fetching IP:', error);
                globalUserIP = 'Não disponível';
                if (ipElement) {
                    ipElement.textContent = 'Não disponível';
                }
                
                const displayElements = window.parent.document.getElementsByClassName('display-ip');
                for (let i = 0; i < displayElements.length; i++) {
                    displayElements[i].textContent = 'Não disponível';
                }
                
                const ipStorage = window.parent.document.getElementById('ip-storage');
                if (ipStorage) {
                    ipStorage.textContent = 'Não disponível';
                }
                
                const event = new CustomEvent('ip_ready', { detail: 'Não disponível' });
                window.parent.document.dispatchEvent(event);
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fetchAndDisplayUserIP);
        } else {
            fetchAndDisplayUserIP();
        }
        
        window.getUserIP = function() {
            return globalUserIP;
        };
    </script>
    """
    
    st.markdown('<div id="ip-storage" style="display:none;">Carregando IP...</div>', unsafe_allow_html=True)
    html(ip_html_code, height=0)
    return '<span class="display-ip">Carregando IP...</span>'

def get_brazil_datetime():
    """Get current date and time in Brazilian format."""
    brazil_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.datetime.now(brazil_tz)
    weekdays = {
        0: 'Segunda-feira',
        1: 'Terça-feira',
        2: 'Quarta-feira',
        3: 'Quinta-feira',
        4: 'Sexta-feira',
        5: 'Sábado',
        6: 'Domingo'
    }
    weekday = weekdays[now.weekday()]
    return f"{weekday}, {now.strftime('%d/%m/%Y %H:%M:%S')}"

def initialize_session_state():
    """Initialize all session state variables."""
    if 'registros' not in st.session_state:
        if os.path.exists('registros.csv'):
            st.session_state.registros = pd.read_csv('registros.csv')
        else:
            st.session_state.registros = pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora', 'IP'])

    if 'timer_started' not in st.session_state:
        st.session_state.timer_started = False
        
    if 'timer_end_time' not in st.session_state:
        if os.path.exists('timer_end.txt'):
            with open('timer_end.txt', 'r') as f:
                end_time_str = f.read().strip()
                st.session_state.timer_end_time = datetime.datetime.fromisoformat(end_time_str)
                if st.session_state.timer_end_time > datetime.datetime.now():
                    st.session_state.timer_started = True
                else:
                    st.session_state.timer_end_time = None
        else:
            st.session_state.timer_end_time = None
        
    if 'aula_iniciada' not in st.session_state:
        if os.path.exists('aula_estado.txt'):
            with open('aula_estado.txt', 'r') as f:
                st.session_state.aula_iniciada = (f.read().strip() == 'iniciada')
        else:
            st.session_state.aula_iniciada = False

    if 'mostrando_senha' not in st.session_state:
        st.session_state.mostrando_senha = False

    if 'senha_correta' not in st.session_state:
        st.session_state.senha_correta = False
        
    if 'senha_professor' not in st.session_state:
        st.session_state.senha_professor = st.secrets.get("senha_professor", "professor@aws")

    if 'ip_professor' not in st.session_state:
        if os.path.exists('ip_professor.txt'):
            with open('ip_professor.txt', 'r') as f:
                st.session_state.ip_professor = f.read().strip()
        else:
            st.session_state.ip_professor = None
            
    if 'botao_clicado' not in st.session_state:
        st.session_state.botao_clicado = None

    if 'captcha_pergunta' not in st.session_state:
        st.session_state.captcha_pergunta = None

    if 'captcha_resposta' not in st.session_state:
        st.session_state.captcha_resposta = None

def is_student_registered(email, ip):
    """Check if a student is already registered based on email or IP."""
    if st.session_state.registros.empty:
        return False
    return ((st.session_state.registros['Email'] == email) | 
            (st.session_state.registros['IP'] == ip)).any()

def send_attendance_email():
    """Send attendance list via email."""
    if st.session_state.registros.empty:
        st.warning("Não há alunos registrados para enviar por email.")
        return False
        
    recipient = st.secrets.get("email_destinatario", "default@example.com")
    subject = "Lista de Presença - " + get_brazil_datetime()
    
    email_body = "<h2>Lista de Presença</h2>"
    email_body += f"<p>Data e hora: {get_brazil_datetime()}</p>"
    email_body += f"<p>Total de alunos: {len(st.session_state.registros)}</p>"
    email_body += "<p>Segue a lista de alunos presentes:</p>"
    email_body += st.session_state.registros.to_html(index=False)
    
    message = MIMEMultipart()
    message['From'] = "sistema@listadechamada.com"
    message['To'] = recipient
    message['Subject'] = subject
    message.attach(MIMEText(email_body, 'html'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        sender_email = st.secrets.get("email", "seu_email@gmail.com")
        app_password = st.secrets.get("senha_email", "sua_senha_de_app")
        
        if sender_email != "seu_email@gmail.com" and app_password != "sua_senha_de_app":
            server.login(sender_email, app_password)
            server.send_message(message)
            server.quit()
            st.success("Email enviado com sucesso!")
        else:
            st.warning("Configuração de email não encontrada. Simulação: Email enviado.")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f'lista_presenca_{timestamp}.csv'
        st.session_state.registros.to_csv(backup_filename, index=False)
        st.info(f"Backup da lista salvo em: {backup_filename}")
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {str(e)}")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f'lista_presenca_{timestamp}.csv'
        st.session_state.registros.to_csv(backup_filename, index=False)
        st.info(f"Backup da lista salvo em: {backup_filename}")
        return False

def start_timer():
    """Start the 1-hour timer."""
    if st.session_state.aula_iniciada:
        st.session_state.timer_started = True
        st.session_state.timer_end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
        with open('timer_end.txt', 'w') as f:
            f.write(st.session_state.timer_end_time.isoformat())

def generate_captcha():
    """Generate a simple CAPTCHA math question."""
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    question = f"Quanto é {num1} + {num2}?"
    answer = num1 + num2
    return question, answer

def verify_password_and_captcha(password, captcha_response):
    """Verify the professor's password and CAPTCHA answer."""
    if 'captcha_resposta' not in st.session_state:
        return False
    try:
        return (password == st.session_state.senha_professor and 
                int(captcha_response) == st.session_state.captcha_resposta)
    except ValueError:
        return False

def reset_attendance_list():
    """Reset the attendance list and related state."""
    send_attendance_email()
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
    for file in ['aula_estado.txt', 'timer_end.txt', 'ip_professor.txt']:
        if os.path.exists(file):
            os.remove(file)
    st.success("Lista de presença finalizada e enviada por email com sucesso!")
    st.rerun()

def start_class():
    """Start the class and record professor's IP."""
    st.session_state.aula_iniciada = True
    # Use session state IP if available, else fallback to 'Não disponível'
    current_ip = st.session_state.get('user_ip', 'Não disponível')
    st.session_state.ip_professor = current_ip
    st.session_state.senha_correta = True
    with open('ip_professor.txt', 'w') as f:
        f.write(str(current_ip))
    with open('aula_estado.txt', 'w') as f:
        f.write('iniciada')
    start_timer()

def add_attendance_record(name, email, ip):
    """Add a new attendance record with the user's real IP."""
    timestamp = get_brazil_datetime()
    
    if is_student_registered(email, ip):
        return False
    
    new_record = pd.DataFrame({
        'Nome': [name],
        'Email': [email],
        'Data_Hora': [timestamp],
        'IP': [ip]
    })
    
    st.session_state.registros = pd.concat([st.session_state.registros, new_record], ignore_index=True)
    st.session_state.registros.to_csv('registros.csv', index=False)
    return True

def display_timer():
    """Display the countdown timer."""
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
            }})();
        </script>
        """
        html(timer_html, height=50)
    else:
        st.markdown("<div style='text-align: right;'><h3>01:00:00</h3></div>", unsafe_allow_html=True)

def main():
    """Main application function."""
    initialize_session_state()
    
    ip_placeholder = get_public_ip()

    st.markdown("<h1 style='text-align: center;'>📝List Web App!</h1>", unsafe_allow_html=True)

    header_col1, header_col2 = st.columns([3, 1])
    with header_col2:
        display_timer()
        st.markdown(f"<div style='text-align: right;'>IP: {ip_placeholder}</div>", unsafe_allow_html=True)

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
                if st.session_state.get('captcha_pergunta') is None:
                    pergunta, resposta = generate_captcha()
                    st.session_state.captcha_pergunta = pergunta
                    st.session_state.captcha_resposta = resposta
                
                with st.form(key="senha_form"):
                    st.write(st.session_state.captcha_pergunta)
                    resposta_captcha = st.text_input("Resposta do CAPTCHA:", key="captcha_input")
                    senha = st.text_input("Digite a senha do professor:", type="password", key="senha_input")
                    submit_senha = st.form_submit_button("Confirmar")
                    
                    if submit_senha and senha and resposta_captcha:
                        if verify_password_and_captcha(senha, resposta_captcha):
                            st.session_state.senha_correta = True
                            if st.session_state.botao_clicado == "start":
                                start_class()
                                st.success("Aula iniciada com sucesso!")
                                st.session_state.mostrando_senha = False
                                st.rerun()
                            elif st.session_state.botao_clicado == "reset":
                                reset_attendance_list()
                            elif st.session_state.botao_clicado == "auth":
                                st.session_state.senha_correta = True
                                st.session_state.mostrando_senha = False
                                st.rerun()
                            st.session_state.captcha_pergunta = None
                            st.session_state.captcha_resposta = None
                        else:
                            st.error("Senha ou CAPTCHA incorreto!")
                            st.session_state.captcha_pergunta = None
                            st.session_state.captcha_resposta = None
                    elif submit_senha:
                        st.error("Preencha todos os campos.")

    if st.session_state.aula_iniciada and is_professor:
        auth_ip_check = st.session_state.get('user_ip', 'Não disponível')
        if st.session_state.ip_professor != auth_ip_check:
            auth_col1, auth_col2, auth_col3 = st.columns([1, 1, 1])
            with auth_col2:
                st.markdown("---")
                st.info("Seu IP pode ter mudado. Autentique-se novamente se necessário.")
                if st.button("Autenticar como Professor", key="btn_auth_professor", use_container_width=True):
                    st.session_state.mostrando_senha = True
                    st.session_state.botao_clicado = "auth"

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.session_state.aula_iniciada:
            st.subheader("Registre sua presença preenchendo o formulário abaixo")
            if 'form_submitted' not in st.session_state:
                st.session_state.form_submitted = False
            
            nome_inicial = st.session_state.get('registro_form_nome', "")
            email_inicial = st.session_state.get('registro_form_email', "")
            if st.session_state.get('form_submitted_success', False):
                nome_inicial = ""
                email_inicial = ""
                st.session_state.form_submitted_success = False

            with st.form(key="registro_form"):
                nome = st.text_input("Nome Completo", value=nome_inicial, key="registro_form_nome_input")
                email = st.text_input("E-mail", value=email_inicial, key="registro_form_email_input")
                # Hidden IP field populated by JavaScript
                ip_field = st.text_input("IP", value="", key="hidden_ip", disabled=True, help="Campo preenchido automaticamente")
                submit_button = st.form_submit_button(label="Registrar Presença")

                # JavaScript to update the hidden IP field from ip-storage
                js_code = """
                <script>
                function updateIpField() {
                    const hiddenIpInput = document.querySelector('input[data-testid="stTextInput-hidden_ip"]');
                    const ipStorage = window.parent.document.getElementById('ip-storage');
                    if (ipStorage && hiddenIpInput) {
                        hiddenIpInput.value = ipStorage.textContent;
                    }
                }
                updateIpField();
                window.parent.document.addEventListener('ip_ready', updateIpField);
                </script>
                """
                html(js_code, height=0)

                if submit_button:
                    st.session_state.registro_form_nome = nome
                    st.session_state.registro_form_email = email
                    user_ip = st.session_state.hidden_ip

                    if nome and email and user_ip != "Carregando IP...":
                        if add_attendance_record(nome, email, user_ip):
                            st.success(f"Presença de {nome} registrada com sucesso!")
                            st.session_state.form_submitted_success = True
                            st.session_state.registro_form_nome = ""
                            st.session_state.registro_form_email = ""
                            st.rerun()
                        else:
                            st.error(f"Não foi possível registrar {nome}. Este email ou IP já está registrado.")
                    else:
                        st.error("Preencha todos os campos e aguarde o IP carregar.")
        else:
            st.info("Aguarde o professor iniciar a lista para registrar sua presença.")

    with st.sidebar:
        st.header("👨🏻‍🎓 Alunos Presentes")
        if not st.session_state.registros.empty:
            st.subheader(f"Total: {len(st.session_state.registros)}")
            alunos_ordenados = st.session_state.registros.sort_values(by='Nome')
            for _, aluno in alunos_ordenados.iterrows():
                st.write(f"**{aluno['Nome']}**")
                st.write(f"<small>{aluno['Data_Hora']}</small>", unsafe_allow_html=True)
                st.write(f"<small>IP: {aluno['IP']}</small>", unsafe_allow_html=True)
                st.divider()
        else:
            st.write("Nenhum aluno registrado!")

    st.markdown("---")
    st.markdown(f"<div style='text-align: center;'>{get_brazil_datetime()}</div>", unsafe_allow_html=True)

    st.markdown("""
    <style>
        .main { background-color: #ffffff; color: #333333; }
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        div[data-testid="stAppViewBlockContainer"] { padding-top: 0rem !important; padding-bottom: 0rem !important; }
        div[data-testid="stVerticalBlock"] { gap: 0rem !important; }
        .element-container { margin-top: 0 !important; margin-bottom: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <hr>
    <div style="text-align: center;">
        <h4>List Web App! - Lista de presença digital</h4>
        <p>Por Ary Ribeiro. Contato: <a href="mailto:aryribeiro@gmail.com">aryribeiro@gmail.com</a></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

# Estilo personalizado - Remoção de elementos da interface do Streamlit
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