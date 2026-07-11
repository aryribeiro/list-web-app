import streamlit as st
import pandas as pd
import base64
import datetime
import pytz
import re
import smtplib
import random
import threading
import time
import uuid
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from streamlit.components.v1 import html

# Page configuration
st.set_page_config(
   page_title="List Web App!",
   page_icon="📝",
   layout="wide",
   initial_sidebar_state="expanded"
)

# Global styles: hide Streamlit menu/footer but keep the sidebar toggle visible
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
    /* Esconde o menu principal e footer, MAS mantém o botão do sidebar */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}

    /* Mantém o botão de toggle do sidebar visível */
    button[kind="header"] {
        display: block !important;
        visibility: visible !important;
    }

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

    /* Garante que o header com o botão do sidebar fique visível */
    header[data-testid="stHeader"] {
        display: block !important;
        visibility: visible !important;
        background-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

EMAIL_REGEX = re.compile(r'^[\w.+-]+@[\w-]+(\.[\w-]+)+$')
_APP_SEED = "YWRtaW4xMjM="

def get_secret(key, default=""):
   """Read a secret without crashing when no secrets.toml exists at all."""
   try:
       return st.secrets.get(key, default)
   except Exception:
       return default

# Database connection with thread safety
def get_db_connection():
   """Get database connection with proper configuration for concurrent access."""
   conn = sqlite3.connect('attendance.db', check_same_thread=False, timeout=30.0)
   conn.execute('PRAGMA journal_mode=WAL')
   conn.execute('PRAGMA synchronous=NORMAL')
   conn.execute('PRAGMA cache_size=10000')
   conn.execute('PRAGMA temp_store=memory')
   return conn

def init_database():
   """Initialize database with proper indexes for performance."""
   conn = get_db_connection()
   try:
       conn.execute('''
           CREATE TABLE IF NOT EXISTS attendance (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               nome TEXT NOT NULL,
               email TEXT NOT NULL UNIQUE,
               data_hora TEXT NOT NULL,
               session_id TEXT,
               ip TEXT,
               registrado_por TEXT DEFAULT 'aluno',
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       ''')

       conn.execute('''
           CREATE TABLE IF NOT EXISTS class_state (
               id INTEGER PRIMARY KEY,
               aula_iniciada INTEGER DEFAULT 0,
               timer_end_time TEXT,
               ip_professor TEXT,
               session_id TEXT UNIQUE
           )
       ''')

       # Fila persistente de comprovantes de presença (estilo SQS):
       # o registro apenas enfileira; um worker em background envia
       conn.execute('''
           CREATE TABLE IF NOT EXISTS email_queue (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               destinatario TEXT NOT NULL,
               nome TEXT NOT NULL,
               data_hora TEXT NOT NULL,
               status TEXT DEFAULT 'pendente',
               tentativas INTEGER DEFAULT 0,
               criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               enviado_em TEXT
           )
       ''')
       conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON email_queue(status)")

       # Migração para bancos criados por versões antigas do app
       for ddl in (
           "ALTER TABLE attendance ADD COLUMN ip TEXT",
           "ALTER TABLE attendance ADD COLUMN registrado_por TEXT DEFAULT 'aluno'",
       ):
           try:
               conn.execute(ddl)
           except sqlite3.OperationalError:
               pass  # coluna já existe

       # Create indexes for better performance
       conn.execute('CREATE INDEX IF NOT EXISTS idx_email ON attendance(email)')
       conn.execute('CREATE INDEX IF NOT EXISTS idx_session ON attendance(session_id)')
       conn.execute('CREATE INDEX IF NOT EXISTS idx_ip ON attendance(ip)')
       conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON attendance(created_at)')

       conn.commit()
   except sqlite3.Error as e:
       st.error(f"Database initialization error: {e}")
   finally:
       conn.close()

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
   """Initialize session state and sync class/timer state from the database."""
   if 'session_id' not in st.session_state:
       st.session_state.session_id = str(uuid.uuid4())

   if 'timer_started' not in st.session_state:
       st.session_state.timer_started = False

   if 'timer_end_time' not in st.session_state:
       st.session_state.timer_end_time = None

   # A aula pode ser iniciada/finalizada por outra sessão (professor),
   # então o estado é sempre relido do banco a cada execução.
   st.session_state.aula_iniciada = load_class_state()

   if st.session_state.aula_iniciada:
       if not st.session_state.timer_started:
           timer_state = load_timer_state()
           if timer_state and timer_state > datetime.datetime.now():
               st.session_state.timer_end_time = timer_state
               st.session_state.timer_started = True
   else:
       st.session_state.timer_started = False
       st.session_state.timer_end_time = None

   # Timer expirado: limpa o estado para o JS não recarregar a página em loop
   if st.session_state.timer_end_time and st.session_state.timer_end_time <= datetime.datetime.now():
       st.session_state.timer_started = False
       st.session_state.timer_end_time = None

   if 'professor_autenticado' not in st.session_state:
       st.session_state.professor_autenticado = False

   if 'senha_professor' not in st.session_state:
       # Senha padrão (ofuscada); em produção é sobrescrita pelo secrets
       st.session_state.senha_professor = get_secret(
           "senha_professor", base64.b64decode(_APP_SEED).decode())

   if 'captcha_pergunta' not in st.session_state:
       st.session_state.captcha_pergunta = None

   if 'captcha_resposta' not in st.session_state:
       st.session_state.captcha_resposta = None

def load_attendance_data():
   """Load attendance data from database with error handling."""
   try:
       conn = get_db_connection()
       df = pd.read_sql_query(
           "SELECT nome as Nome, email as Email, ip as IP, data_hora as Data_Hora FROM attendance ORDER BY created_at",
           conn)
       conn.close()
       df['IP'] = df['IP'].fillna('registro manual')
       return df
   except Exception as e:
       st.error(f"Error loading attendance data: {e}")
       return pd.DataFrame(columns=['Nome', 'Email', 'IP', 'Data_Hora'])

def sort_alunos(df):
   """Sort attendance alphabetically by name, ignoring case and accents."""
   return df.sort_values(
       by='Nome',
       key=lambda s: (s.str.normalize('NFKD')
                       .str.encode('ascii', errors='ignore')
                       .str.decode('ascii')
                       .str.lower())
   )

def load_class_state():
   """Load class state from database with proper error handling."""
   try:
       conn = get_db_connection()
       cursor = conn.execute("SELECT aula_iniciada FROM class_state WHERE id = 1")
       result = cursor.fetchone()
       conn.close()
       if result is not None:
           return bool(result[0])
       return False
   except Exception:
       # On error, assume class is not started for safety
       return False

def load_timer_state():
   """Load timer state from database."""
   try:
       conn = get_db_connection()
       cursor = conn.execute("SELECT timer_end_time FROM class_state WHERE id = 1")
       result = cursor.fetchone()
       conn.close()
       if result and result[0]:
           return datetime.datetime.fromisoformat(result[0])
       return None
   except Exception:
       return None

def flash(kind, text):
   """Queue a message ('success', 'error', 'warning', 'info') to survive the next st.rerun()."""
   st.session_state.setdefault('flash_messages', []).append((kind, text))

def show_flash_messages():
   """Display and clear messages queued before the last st.rerun()."""
   for kind, text in st.session_state.pop('flash_messages', []):
       getattr(st, kind)(text)

def save_backup_csv(csv_content, filename):
   """Save the attendance CSV backup locally (UTF-8 with BOM for Excel)."""
   with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
       f.write(csv_content)
   flash('info', f"Backup da lista salvo em: {filename}")

def build_email_message(df, sender, recipient, csv_filename, csv_content):
   """Build the email: HTML body with the sorted list + CSV attachment."""
   message = MIMEMultipart()
   message['From'] = sender
   message['To'] = recipient
   message['Subject'] = "Lista de Presença - " + get_brazil_datetime()

   email_body = "<h2>Lista de Presença</h2>"
   email_body += f"<p>Data e hora: {get_brazil_datetime()}</p>"
   email_body += f"<p>Total de alunos: {len(df)}</p>"
   email_body += "<p>Segue a lista de alunos presentes (em ordem alfabética):</p>"
   email_body += df.to_html(index=False)
   email_body += f"<p>A lista completa segue em anexo: {csv_filename}</p>"
   message.attach(MIMEText(email_body, 'html'))

   attachment = MIMEApplication(csv_content.encode('utf-8-sig'), Name=csv_filename)
   attachment['Content-Disposition'] = f'attachment; filename="{csv_filename}"'
   message.attach(attachment)

   return message

def send_attendance_email():
   """Send the sorted attendance list via email (CSV attached) and save a local backup."""
   df = load_attendance_data()
   if df.empty:
       flash('warning', "Não há alunos registrados para enviar por email.")
       return False

   df = sort_alunos(df)
   timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
   csv_filename = f'lista_presenca_{timestamp}.csv'
   csv_content = df.to_csv(index=False)

   sender_email = get_secret("email")
   app_password = get_secret("senha_email")
   recipient = get_secret("email_destinatario")

   enviado = False
   try:
       if sender_email and app_password and recipient:
           message = build_email_message(df, sender_email, recipient, csv_filename, csv_content)
           with smtplib.SMTP('smtp.gmail.com', 587) as server:
               server.starttls()
               server.login(sender_email, app_password)
               server.send_message(message)
           flash('success', "Email enviado com sucesso, com a lista em anexo (CSV)!")
           enviado = True
       else:
           flash('warning', "Configuração de email não encontrada. Simulação: Email enviado.")
   except Exception as e:
       flash('error', f"Erro ao enviar email: {str(e)}")

   # O backup local é salvo mesmo se o envio falhar
   try:
       save_backup_csv(csv_content, csv_filename)
   except Exception as e:
       flash('error', f"Erro ao salvar backup: {str(e)}")

   return enviado

def build_receipt_email(sender, destinatario, nome, data_hora):
   """Build the student's attendance receipt email."""
   message = MIMEMultipart()
   message['From'] = sender
   message['To'] = destinatario
   message['Subject'] = f"Comprovante de Presença - {nome}"

   body = "<h2>✅ Comprovante de Presença</h2>"
   body += f"<p>Olá, <strong>{nome}</strong>!</p>"
   body += "<p>Sua presença foi registrada com sucesso no <strong>List Web App!</strong></p>"
   body += f"<p><strong>Data e hora do registro:</strong> {data_hora}</p>"
   body += f"<p><strong>E-mail registrado:</strong> {destinatario}</p>"
   body += "<p>Guarde este e-mail como comprovante do seu registro de presença.</p>"
   message.attach(MIMEText(body, 'html'))
   return message

def send_receipt_email(creds, destinatario, nome, data_hora):
   """Send one receipt email via SMTP (runs in the background worker)."""
   message = build_receipt_email(creds['email'], destinatario, nome, data_hora)
   with smtplib.SMTP('smtp.gmail.com', 587) as server:
       server.starttls()
       server.login(creds['email'], creds['senha_email'])
       server.send_message(message)

def process_email_queue(creds):
   """Consume pending receipts from the queue (producer/consumer, SQS-style).

   Roda fora do fluxo de registro: falha de SMTP nunca afeta a presença já
   gravada. Cada item tem até 5 tentativas antes de ser marcado como 'falhou'.
   """
   conn = get_db_connection()
   rows = conn.execute(
       """SELECT id, destinatario, nome, data_hora FROM email_queue
          WHERE status = 'pendente' AND tentativas < 5 ORDER BY id LIMIT 20"""
   ).fetchall()

   if not rows:
       conn.close()
       return 0

   agora = datetime.datetime.now().isoformat()
   configured = bool(creds.get('email') and creds.get('senha_email'))

   if not configured:
       # Sem credenciais: marca como simulado para a fila não crescer
       conn.executemany(
           "UPDATE email_queue SET status = 'simulado', enviado_em = ? WHERE id = ?",
           [(agora, r[0]) for r in rows])
       conn.commit()
       conn.close()
       return len(rows)

   for row_id, destinatario, nome, data_hora in rows:
       try:
           send_receipt_email(creds, destinatario, nome, data_hora)
           conn.execute(
               "UPDATE email_queue SET status = 'enviado', enviado_em = ? WHERE id = ?",
               (datetime.datetime.now().isoformat(), row_id))
       except Exception:
           conn.execute(
               """UPDATE email_queue SET tentativas = tentativas + 1,
                  status = CASE WHEN tentativas + 1 >= 5 THEN 'falhou' ELSE 'pendente' END
                  WHERE id = ?""", (row_id,))
       conn.commit()

   conn.close()
   return len(rows)

def email_worker_loop(creds):
   """Background daemon: polls the receipt queue every 2 seconds."""
   while True:
       try:
           process_email_queue(creds)
       except Exception:
           pass  # o worker nunca pode morrer por erro transitório
       time.sleep(2)

@st.cache_resource
def start_email_worker():
   """Start the receipt queue worker once per server process.

   As credenciais são lidas aqui (thread do Streamlit) porque o worker,
   rodando fora do contexto de sessão, não pode acessar st.secrets.
   """
   creds = {
       'email': get_secret("email"),
       'senha_email': get_secret("senha_email"),
   }
   worker = threading.Thread(target=email_worker_loop, args=(creds,), daemon=True)
   worker.start()
   return worker

def formatar_duracao(minutos):
   """Format a duration in minutes as '15 minutos', '1 hora', '2 horas'..."""
   if minutos < 60:
       return f"{minutos} minutos"
   horas = minutos // 60
   return f"{horas} hora" if horas == 1 else f"{horas} horas"

def start_timer(duracao_minutos=60):
   """Start the countdown timer with database persistence."""
   if st.session_state.aula_iniciada:
       st.session_state.timer_started = True
       st.session_state.timer_end_time = datetime.datetime.now() + datetime.timedelta(minutes=duracao_minutos)

       try:
           conn = get_db_connection()
           conn.execute("""
               UPDATE class_state SET timer_end_time = ? WHERE id = 1
           """, (st.session_state.timer_end_time.isoformat(),))
           conn.commit()
           conn.close()
       except Exception as e:
           st.error(f"Error saving timer state: {e}")

def generate_captcha():
   """Generate a simple CAPTCHA math question."""
   num1 = random.randint(1, 10)
   num2 = random.randint(1, 10)
   question = f"Quanto é {num1} + {num2}?"
   answer = num1 + num2
   return question, answer

def verify_password_and_captcha(password, captcha_response):
   """Verify the professor's password and CAPTCHA answer."""
   if st.session_state.captcha_resposta is None:
       return False
   try:
       return (password == st.session_state.senha_professor and
               int(captcha_response.strip()) == st.session_state.captcha_resposta)
   except ValueError:
       return False

def reset_captcha():
   """Clear the current CAPTCHA so a new one is generated on the next run."""
   st.session_state.captcha_pergunta = None
   st.session_state.captcha_resposta = None
   st.session_state.pop("captcha_input", None)
   st.session_state.pop("senha_input", None)

def reset_attendance_list():
   """Send the list by email, then clear the database and session state."""
   send_attendance_email()

   try:
       conn = get_db_connection()
       conn.execute("DELETE FROM attendance")
       conn.execute("DELETE FROM class_state")
       # Comprovantes pendentes continuam na fila; remove só os concluídos
       conn.execute("DELETE FROM email_queue WHERE status <> 'pendente'")
       conn.commit()
       conn.close()
   except Exception as e:
       st.error(f"Error resetting attendance list: {e}")
       return

   st.session_state.timer_started = False
   st.session_state.timer_end_time = None
   st.session_state.aula_iniciada = False
   reset_captcha()

   flash('success', "Lista de presença finalizada e enviada por email com sucesso!")
   st.rerun()

def auto_finalize_if_expired():
   """Automatically close the list and send the email when the timer expires.

   O UPDATE condicional é atômico: com vários alunos conectados no momento
   da expiração, apenas UMA sessão "vence" (rowcount == 1) e executa o envio
   do email/backup — as demais apenas veem a lista fechada.
   Returns True if THIS session performed the finalization.
   """
   try:
       conn = get_db_connection()
       cursor = conn.execute(
           """UPDATE class_state SET aula_iniciada = 0
              WHERE id = 1 AND aula_iniciada = 1
                AND timer_end_time IS NOT NULL AND timer_end_time <= ?""",
           (datetime.datetime.now().isoformat(),))
       conn.commit()
       claimed = cursor.rowcount > 0
       conn.close()
   except Exception:
       return False

   if not claimed:
       return False

   flash('warning', "⏰ Tempo encerrado! A lista de presença foi finalizada automaticamente.")
   send_attendance_email()

   try:
       conn = get_db_connection()
       conn.execute("DELETE FROM attendance")
       conn.execute("DELETE FROM class_state")
       # Comprovantes pendentes continuam na fila; remove só os concluídos
       conn.execute("DELETE FROM email_queue WHERE status <> 'pendente'")
       conn.commit()
       conn.close()
   except Exception as e:
       flash('error', f"Erro ao limpar a lista: {e}")

   st.session_state.aula_iniciada = False
   st.session_state.timer_started = False
   st.session_state.timer_end_time = None
   return True

def start_class(duracao_minutos=60):
   """Start the class with database persistence."""
   try:
       conn = get_db_connection()
       conn.execute("""
           INSERT OR REPLACE INTO class_state (id, aula_iniciada, session_id)
           VALUES (1, 1, ?)
       """, (st.session_state.session_id,))
       conn.commit()
       conn.close()

       st.session_state.aula_iniciada = True
       start_timer(duracao_minutos)
       return True

   except Exception as e:
       st.error(f"Error starting class: {e}")
       return False

def get_client_ip():
   """Public IP of the connected user (client-side), as seen by the server.

   Usa st.context.ip_address (Streamlit >= 1.45), que retorna o IP do
   USUÁRIO conectado — nunca o IP do servidor. Retorna None em execução
   local (localhost).
   """
   try:
       return st.context.ip_address
   except Exception:
       return None

def student_already_registered(ip):
   """True if this browser session or this public IP already self-registered."""
   try:
       conn = get_db_connection()
       cursor = conn.execute(
           """SELECT COUNT(*) FROM attendance
              WHERE registrado_por = 'aluno'
                AND (session_id = ? OR (? IS NOT NULL AND ip = ?))""",
           (st.session_state.session_id, ip, ip))
       count = cursor.fetchone()[0]
       conn.close()
       return count > 0
   except Exception:
       return False

def add_attendance_record(name, email, ip=None, registrado_por='aluno'):
   """Add a new attendance record. Returns (ok, error_message).

   Alunos ('aluno') só podem registrar a própria presença uma única vez:
   bloqueia e-mail, sessão e IP público repetidos. O registro manual do
   professor ('professor') só valida e-mail duplicado.
   """
   timestamp = get_brazil_datetime()

   try:
       conn = get_db_connection()

       cursor = conn.execute("SELECT COUNT(*) FROM attendance WHERE email = ?", (email,))
       if cursor.fetchone()[0] > 0:
           conn.close()
           return False, "Este e-mail já está registrado."

       if registrado_por == 'aluno':
           cursor = conn.execute(
               """SELECT COUNT(*) FROM attendance
                  WHERE registrado_por = 'aluno'
                    AND (session_id = ? OR (? IS NOT NULL AND ip = ?))""",
               (st.session_state.session_id, ip, ip))
           if cursor.fetchone()[0] > 0:
               conn.close()
               return False, "Você já registrou presença nesta lista. Cada aluno pode registrar apenas a própria presença, uma única vez."

       conn.execute("""
           INSERT INTO attendance (nome, email, data_hora, session_id, ip, registrado_por)
           VALUES (?, ?, ?, ?, ?, ?)
       """, (name, email, timestamp, st.session_state.session_id, ip, registrado_por))

       # Enfileira o comprovante na MESMA transação: ele só existe se a
       # presença foi de fato gravada (e o envio nunca bloqueia o registro)
       conn.execute("""
           INSERT INTO email_queue (destinatario, nome, data_hora)
           VALUES (?, ?, ?)
       """, (email, name, timestamp))

       conn.commit()
       conn.close()
       return True, None

   except sqlite3.IntegrityError:
       # Handle duplicate email constraint (race between check and insert)
       return False, "Este e-mail já está registrado."
   except Exception as e:
       return False, f"Erro ao registrar presença: {e}"

def display_timer():
   """Display the countdown timer with improved JavaScript."""
   if st.session_state.timer_started and st.session_state.timer_end_time:
       end_time_ms = int(st.session_state.timer_end_time.timestamp() * 1000)
       timer_html = f"""
       <div style='text-align: right;'>
           <h3 id="cronometro">Carregando...</h3>
       </div>
       <script>
           (function() {{
               const endTime = {end_time_ms};
               let timerInterval;

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

                       const cronometroElement = document.getElementById("cronometro");
                       if (cronometroElement) {{
                           cronometroElement.textContent = timeString;
                       }}
                   }} else {{
                       const cronometroElement = document.getElementById("cronometro");
                       if (cronometroElement) {{
                           cronometroElement.textContent = "00:00:00";
                       }}
                       if (timerInterval) {{
                           clearInterval(timerInterval);
                       }}
                       setTimeout(() => {{
                           if (window.location) {{
                               window.location.reload();
                           }}
                       }}, 2000);
                   }}
               }}

               updateTimer();
               timerInterval = setInterval(updateTimer, 1000);

               // Cleanup on page unload
               window.addEventListener('beforeunload', function() {{
                   if (timerInterval) {{
                       clearInterval(timerInterval);
                   }}
               }});
           }})();
       </script>
       """
       html(timer_html, height=50)
   else:
       if st.session_state.aula_iniciada:
           placeholder = "00:00:00"
       else:
           minutos = st.session_state.get('duracao_minutos', 60)
           placeholder = f"{minutos // 60:02d}:{minutos % 60:02d}:00"
       st.markdown(f"<div style='text-align: right;'><h3>{placeholder}</h3></div>", unsafe_allow_html=True)

@st.fragment(run_every=5)
def render_attendance_list():
   """Attendance list, auto-refreshed every 5 seconds without a full page reload.

   Este fragment também serve de "relógio" do app: a cada execução verifica
   se o cronômetro expirou (finalizando a lista automaticamente) e se o
   estado da aula mudou em outra sessão, recarregando a página inteira.
   """
   finalized = auto_finalize_if_expired()
   if finalized or (st.session_state.aula_iniciada and not load_class_state()):
       st.rerun(scope="app")

   current_registros = load_attendance_data()

   if not current_registros.empty:
       st.subheader(f"Total: {len(current_registros)}")
       alunos_ordenados = sort_alunos(current_registros)

       for _, aluno in alunos_ordenados.iterrows():
           st.write(f"**{aluno['Nome']}**")
           st.write(f"<small>{aluno['Data_Hora']}</small>", unsafe_allow_html=True)
           st.divider()
   else:
       st.write("Nenhum aluno registrado!")

def main():
   """Main application function."""
   init_database()
   start_email_worker()
   # Fecha a lista automaticamente se o cronômetro expirou (ex.: página
   # recarregada pelo JS do timer ao chegar em 00:00:00)
   auto_finalize_if_expired()
   initialize_session_state()

   st.markdown("<h1 style='text-align: center;'>📝List Web App!</h1>", unsafe_allow_html=True)

   header_col1, header_col2 = st.columns([3, 1])
   with header_col2:
       display_timer()

   st.markdown("---")
   prof_col1, prof_col2, prof_col3 = st.columns([1, 1, 1])
   with prof_col2:
       # Mensagens enfileiradas antes de um st.rerun() são exibidas aqui
       show_flash_messages()

       if not st.session_state.professor_autenticado:
           # Alunos veem apenas este expander discreto; os controles do
           # professor só aparecem após autenticar a sessão
           with st.expander("🔑 Área do professor"):
               if st.session_state.captcha_pergunta is None:
                   pergunta, resposta = generate_captcha()
                   st.session_state.captcha_pergunta = pergunta
                   st.session_state.captcha_resposta = resposta

               with st.form(key="senha_form"):
                   st.write(st.session_state.captcha_pergunta)
                   resposta_captcha = st.text_input("Resposta do CAPTCHA:", key="captcha_input")
                   senha = st.text_input("Digite a senha do professor:", type="password", key="senha_input")
                   submit_senha = st.form_submit_button("Entrar")

                   if submit_senha:
                       if not senha or not resposta_captcha:
                           st.error("Preencha todos os campos.")
                       elif verify_password_and_captcha(senha, resposta_captcha):
                           st.session_state.professor_autenticado = True
                           reset_captcha()
                           flash('success', "Acesso do professor liberado!")
                           st.rerun()
                       else:
                           # Gera novo CAPTCHA e re-executa para exibir a nova pergunta
                           reset_captcha()
                           flash('error', "Senha ou CAPTCHA incorreto!")
                           st.rerun()
       else:
           if not st.session_state.aula_iniciada:
               duracao = st.selectbox(
                   "⏱️ Duração da lista:",
                   options=[15, 30, 60, 120, 240],
                   index=2,
                   format_func=formatar_duracao,
                   key="duracao_minutos",
               )
               if st.button("Iniciar Lista", key="btn_start", use_container_width=True):
                   if start_class(duracao):
                       flash('success', f"Aula iniciada com sucesso! Duração da lista: {formatar_duracao(duracao)}.")
                   st.rerun()
           else:
               if st.button("Finalizar Lista", key="btn_reset", use_container_width=True):
                   reset_attendance_list()

               # Registro manual: para alunos presentes que tiveram problema
               # técnico (travamento, rede, dispositivo) ao registrar presença
               with st.expander("👨‍🏫 Registro manual pelo professor"):
                   st.caption("Use apenas para alunos presentes que não conseguiram registrar por problemas técnicos.")
                   with st.form(key="registro_manual_form"):
                       nome_manual = st.text_input("Nome Completo do aluno", key="manual_nome_input")
                       email_manual = st.text_input("E-mail do aluno", key="manual_email_input")
                       submit_manual = st.form_submit_button("Registrar aluno")

                       if submit_manual:
                           nome_manual = nome_manual.strip()
                           email_manual = email_manual.strip().lower()

                           if not nome_manual or not email_manual:
                               st.error("Preencha todos os campos.")
                           elif not EMAIL_REGEX.match(email_manual):
                               st.error("Digite um e-mail válido.")
                           else:
                               ok, erro = add_attendance_record(nome_manual, email_manual, registrado_por='professor')
                               if ok:
                                   st.session_state.pop("manual_nome_input", None)
                                   st.session_state.pop("manual_email_input", None)
                                   flash('success', f"Presença de {nome_manual} registrada manualmente pelo professor! "
                                                    "Um comprovante será enviado ao e-mail do aluno.")
                                   st.rerun()
                               else:
                                   st.error(erro)

   # Student registration section
   col1, col2, col3 = st.columns([1, 1, 1])
   with col2:
       if st.session_state.aula_iniciada:
           client_ip = get_client_ip()

           nome_registrado = st.session_state.pop('msg_presenca_registrada', None)
           if nome_registrado:
               st.success(f"Presença de {nome_registrado} registrada com sucesso! "
                          "Um comprovante será enviado para o seu e-mail.")

           if student_already_registered(client_ip):
               st.info("Sua presença já foi registrada nesta lista. Cada aluno pode registrar apenas a própria presença, uma única vez.")
           else:
               st.subheader("Registre sua presença preenchendo o formulário abaixo")

               with st.form(key="registro_form"):
                   nome = st.text_input("Nome Completo", key="registro_form_nome_input")
                   email = st.text_input("E-mail", key="registro_form_email_input")
                   submit_button = st.form_submit_button(label="Registrar Presença")

                   if submit_button:
                       nome = nome.strip()
                       email = email.strip().lower()

                       if not nome or not email:
                           st.error("Preencha todos os campos.")
                       elif not EMAIL_REGEX.match(email):
                           st.error("Digite um e-mail válido.")
                       else:
                           ok, erro = add_attendance_record(nome, email, ip=client_ip)
                           if ok:
                               # Limpa os campos do formulário antes de re-executar
                               st.session_state.pop("registro_form_nome_input", None)
                               st.session_state.pop("registro_form_email_input", None)
                               st.session_state.msg_presenca_registrada = nome
                               st.rerun()
                           else:
                               st.error(erro)
       else:
           st.info("Aguarde o professor iniciar a lista para registrar sua presença.")

   # Sidebar with attendance list
   with st.sidebar:
       st.header("👨🏻‍🎓 Alunos Presentes")
       render_attendance_list()

   st.markdown("---")
   st.markdown(f"<div style='text-align: center;'>{get_brazil_datetime()}</div>", unsafe_allow_html=True)

   # Footer
   st.markdown("""
   <hr>
   <div style="text-align: center;">
       <h4>List Web App! - Lista de presença digital</h4>
       <p>Por Ary Ribeiro. Contato: <a href="mailto:aryribeiro@gmail.com">aryribeiro@gmail.com</a></p>
   </div>
   """, unsafe_allow_html=True)

if __name__ == "__main__":
   main()
