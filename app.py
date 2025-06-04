import streamlit as st
import pandas as pd
import datetime
import pytz
import os
import smtplib
import random
import threading
import time
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from streamlit.components.v1 import html
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import uuid

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
       
       # Create indexes for better performance
       conn.execute('CREATE INDEX IF NOT EXISTS idx_email ON attendance(email)')
       conn.execute('CREATE INDEX IF NOT EXISTS idx_session ON attendance(session_id)')
       conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON attendance(created_at)')
       
       conn.commit()
   except sqlite3.Error as e:
       st.error(f"Database initialization error: {e}")
   finally:
       conn.close()

def get_browser_fingerprint():
   """Generate unique browser fingerprint using JavaScript."""
   fingerprint_js = """
   <div id="browser-fingerprint" style="display: none;"></div>
   <script>
       function generateFingerprint() {
           const canvas = document.createElement('canvas');
           const ctx = canvas.getContext('2d');
           ctx.textBaseline = 'top';
           ctx.font = '14px Arial';
           ctx.fillText('Browser fingerprint', 2, 2);
           
           const fingerprint = [
               navigator.userAgent,
               navigator.language,
               screen.width + 'x' + screen.height,
               new Date().getTimezoneOffset(),
               canvas.toDataURL(),
               navigator.hardwareConcurrency || 0,
               navigator.deviceMemory || 0
           ].join('|');
           
           // Simple hash function
           let hash = 0;
           for (let i = 0; i < fingerprint.length; i++) {
               const char = fingerprint.charCodeAt(i);
               hash = ((hash << 5) - hash) + char;
               hash = hash & hash;
           }
           
           const fingerprintElement = document.getElementById('browser-fingerprint');
           if (fingerprintElement) {
               fingerprintElement.textContent = Math.abs(hash).toString();
           }
           
           // Dispatch event
           const event = new CustomEvent('fingerprint_ready', { 
               detail: Math.abs(hash).toString() 
           });
           document.dispatchEvent(event);
       }
       
       if (document.readyState === 'loading') {
           document.addEventListener('DOMContentLoaded', generateFingerprint);
       } else {
           generateFingerprint();
       }
   </script>
   """
   html(fingerprint_js, height=0)
   return "generating..."

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
   """Initialize all session state variables with thread safety."""
   if 'session_id' not in st.session_state:
       st.session_state.session_id = str(uuid.uuid4())
   
   if 'registros' not in st.session_state:
       st.session_state.registros = load_attendance_data()

   if 'timer_started' not in st.session_state:
       st.session_state.timer_started = False
       
   if 'timer_end_time' not in st.session_state:
       st.session_state.timer_end_time = load_timer_state()
       if st.session_state.timer_end_time and st.session_state.timer_end_time > datetime.datetime.now():
           st.session_state.timer_started = True
       else:
           st.session_state.timer_end_time = None
       
   # FIX: Always reload class state from database to ensure consistency across sessions
   st.session_state.aula_iniciada = load_class_state()

   if 'mostrando_senha' not in st.session_state:
       st.session_state.mostrando_senha = False

   if 'senha_correta' not in st.session_state:
       st.session_state.senha_correta = False
       
   if 'senha_professor' not in st.session_state:
       st.session_state.senha_professor = st.secrets.get("senha_professor", "professor@aws")

   if 'ip_professor' not in st.session_state:
       st.session_state.ip_professor = load_professor_ip()
           
   if 'botao_clicado' not in st.session_state:
       st.session_state.botao_clicado = None

   if 'captcha_pergunta' not in st.session_state:
       st.session_state.captcha_pergunta = None

   if 'captcha_resposta' not in st.session_state:
       st.session_state.captcha_resposta = None
       
   if 'browser_fingerprint' not in st.session_state:
       st.session_state.browser_fingerprint = None

def load_attendance_data():
   """Load attendance data from database with error handling."""
   try:
       conn = get_db_connection()
       df = pd.read_sql_query("SELECT nome as Nome, email as Email, data_hora as Data_Hora FROM attendance ORDER BY created_at", conn)
       conn.close()
       return df
   except Exception as e:
       st.error(f"Error loading attendance data: {e}")
       return pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora'])

def load_class_state():
   """Load class state from database with proper error handling."""
   try:
       conn = get_db_connection()
       cursor = conn.execute("SELECT aula_iniciada FROM class_state WHERE id = 1")
       result = cursor.fetchone()
       conn.close()
       # FIX: Ensure we return the actual database state
       if result is not None:
           return bool(result[0])
       else:
           # If no record exists, class is not started
           return False
   except Exception as e:
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

def load_professor_ip():
   """Load professor IP from database."""
   try:
       conn = get_db_connection()
       cursor = conn.execute("SELECT ip_professor FROM class_state WHERE id = 1")
       result = cursor.fetchone()
       conn.close()
       return result[0] if result else None
   except Exception:
       return None

def is_student_registered(email, fingerprint=None):
   """Check if a student is already registered with improved duplicate detection."""
   try:
       conn = get_db_connection()
       
       # Check by email first (primary duplicate prevention)
       cursor = conn.execute("SELECT COUNT(*) FROM attendance WHERE email = ?", (email,))
       email_count = cursor.fetchone()[0]
       
       conn.close()
       
       if email_count > 0:
           return True
           
       # Additional check with browser fingerprint if available
       if fingerprint and hasattr(st.session_state, 'used_fingerprints'):
           if fingerprint in st.session_state.used_fingerprints:
               return True
               
       return False
   except Exception as e:
       st.error(f"Error checking registration: {e}")
       return True  # Fail safe - prevent registration on error

def send_attendance_email():
   """Send attendance list via email with improved error handling."""
   try:
       df = load_attendance_data()
       if df.empty:
           st.warning("Não há alunos registrados para enviar por email.")
           return False
           
       recipient = st.secrets.get("email_destinatario", "default@example.com")
       subject = "Lista de Presença - " + get_brazil_datetime()
       
       email_body = "<h2>Lista de Presença</h2>"
       email_body += f"<p>Data e hora: {get_brazil_datetime()}</p>"
       email_body += f"<p>Total de alunos: {len(df)}</p>"
       email_body += "<p>Segue a lista de alunos presentes:</p>"
       email_body += df.to_html(index=False)
       
       message = MIMEMultipart()
       message['From'] = "sistema@listadechamada.com"
       message['To'] = recipient
       message['Subject'] = subject
       message.attach(MIMEText(email_body, 'html'))
       
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
       
       # Create backup
       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       backup_filename = f'lista_presenca_{timestamp}.csv'
       df.to_csv(backup_filename, index=False)
       st.info(f"Backup da lista salvo em: {backup_filename}")
       return True
       
   except Exception as e:
       st.error(f"Erro ao enviar email: {str(e)}")
       # Still create backup on email failure
       try:
           df = load_attendance_data()
           timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
           backup_filename = f'lista_presenca_{timestamp}.csv'
           df.to_csv(backup_filename, index=False)
           st.info(f"Backup da lista salvo em: {backup_filename}")
       except Exception:
           pass
       return False

def start_timer():
   """Start the 1-hour timer with database persistence."""
   if st.session_state.aula_iniciada:
       st.session_state.timer_started = True
       st.session_state.timer_end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
       
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
   if 'captcha_resposta' not in st.session_state:
       return False
   try:
       return (password == st.session_state.senha_professor and 
               int(captcha_response) == st.session_state.captcha_resposta)
   except ValueError:
       return False

def reset_attendance_list():
   """Reset the attendance list and related state with database cleanup."""
   send_attendance_email()
   
   try:
       conn = get_db_connection()
       conn.execute("DELETE FROM attendance")
       conn.execute("DELETE FROM class_state")
       conn.commit()
       conn.close()
       
       # Reset session state
       st.session_state.registros = pd.DataFrame(columns=['Nome', 'Email', 'Data_Hora'])
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
       
       if hasattr(st.session_state, 'used_fingerprints'):
           st.session_state.used_fingerprints.clear()
       
       st.success("Lista de presença finalizada e enviada por email com sucesso!")
       st.rerun()
       
   except Exception as e:
       st.error(f"Error resetting attendance list: {e}")

def start_class():
   """Start the class with database persistence."""
   try:
       conn = get_db_connection()
       # FIX: Use INSERT OR REPLACE to ensure the record is properly created/updated
       conn.execute("""
           INSERT OR REPLACE INTO class_state (id, aula_iniciada, session_id) 
           VALUES (1, 1, ?)
       """, (st.session_state.session_id,))
       conn.commit()
       conn.close()
       
       # FIX: Update session state immediately after database update
       st.session_state.aula_iniciada = True
       st.session_state.senha_correta = True
       
       if not hasattr(st.session_state, 'used_fingerprints'):
           st.session_state.used_fingerprints = set()
       
       start_timer()
       
   except Exception as e:
       st.error(f"Error starting class: {e}")

def add_attendance_record(name, email, fingerprint=None):
   """Add a new attendance record with improved duplicate prevention and concurrency handling."""
   timestamp = get_brazil_datetime()
   
   # Check for duplicates with thread safety
   if is_student_registered(email, fingerprint):
       return False
   
   try:
       conn = get_db_connection()
       
       # Double-check within transaction to prevent race conditions
       cursor = conn.execute("SELECT COUNT(*) FROM attendance WHERE email = ?", (email,))
       if cursor.fetchone()[0] > 0:
           conn.close()
           return False
       
       # Insert new record
       conn.execute("""
           INSERT INTO attendance (nome, email, data_hora, session_id) 
           VALUES (?, ?, ?, ?)
       """, (name, email, timestamp, st.session_state.session_id))
       
       conn.commit()
       conn.close()
       
       # Update session state
       new_record = pd.DataFrame({
           'Nome': [name],
           'Email': [email],
           'Data_Hora': [timestamp]
       })
       
       st.session_state.registros = pd.concat([st.session_state.registros, new_record], ignore_index=True)
       
       # Track fingerprint if available
       if fingerprint and hasattr(st.session_state, 'used_fingerprints'):
           st.session_state.used_fingerprints.add(fingerprint)
       
       return True
       
   except sqlite3.IntegrityError:
       # Handle duplicate email constraint
       return False
   except Exception as e:
       st.error(f"Error adding attendance record: {e}")
       return False

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
       st.markdown("<div style='text-align: right;'><h3>01:00:00</h3></div>", unsafe_allow_html=True)

def main():
   """Main application function with improved error handling and performance."""
   try:
       # Initialize database first
       init_database()
       
       # Initialize session state
       initialize_session_state()
       
       # FIX: Force refresh of class state on each page load to ensure consistency
       current_class_state = load_class_state()
       if current_class_state != st.session_state.aula_iniciada:
           st.session_state.aula_iniciada = current_class_state
           # Also reload timer state if class is active
           if current_class_state:
               timer_state = load_timer_state()
               if timer_state and timer_state > datetime.datetime.now():
                   st.session_state.timer_end_time = timer_state
                   st.session_state.timer_started = True
       
       # Generate browser fingerprint for duplicate prevention
       fingerprint = get_browser_fingerprint()
       
       st.markdown("<h1 style='text-align: center;'>📝List Web App!</h1>", unsafe_allow_html=True)

       header_col1, header_col2 = st.columns([3, 1])
       with header_col2:
           display_timer()

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
                                   # FIX: Add small delay to ensure database write completes
                                   time.sleep(0.1)
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

       # Student registration section
       col1, col2, col3 = st.columns([1, 1, 1])
       with col2:
           # FIX: Check class state directly from database for real-time status
           current_class_active = load_class_state()
           
           if current_class_active:
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
                   submit_button = st.form_submit_button(label="Registrar Presença")

                   # JavaScript to get browser fingerprint
                   js_code = """
                   <div id="fingerprint-storage" style="display:none;"></div>
                   <script>
                       document.addEventListener('fingerprint_ready', function(e) {
                           const storage = document.getElementById('fingerprint-storage');
                           if (storage) {
                               storage.textContent = e.detail;
                           }
                       });
                   </script>
                   """
                   html(js_code, height=0)

                   if submit_button:
                       st.session_state.registro_form_nome = nome
                       st.session_state.registro_form_email = email

                       if nome and email:
                           # Get browser fingerprint for duplicate prevention
                           browser_fp = st.session_state.get('browser_fingerprint')
                           
                           if add_attendance_record(nome, email, browser_fp):
                               st.success(f"Presença de {nome} registrada com sucesso!")
                               st.session_state.form_submitted_success = True
                               st.session_state.registro_form_nome = ""
                               st.session_state.registro_form_email = ""
                               st.rerun()
                           else:
                               st.error(f"Não foi possível registrar {nome}. Este email já está registrado ou você já votou neste dispositivo.")
                       else:
                           st.error("Preencha todos os campos.")
           else:
               st.info("Aguarde o professor iniciar a lista para registrar sua presença.")

       # Sidebar with attendance list
       with st.sidebar:
           st.header("👨🏻‍🎓 Alunos Presentes")
           
           # Refresh data periodically
           current_registros = load_attendance_data()
           
           if not current_registros.empty:
               st.subheader(f"Total: {len(current_registros)}")
               alunos_ordenados = current_registros.sort_values(by='Nome')
               
               # Use container for better performance with large lists
               with st.container():
                   for _, aluno in alunos_ordenados.iterrows():
                       st.write(f"**{aluno['Nome']}**")
                       st.write(f"<small>{aluno['Data_Hora']}</small>", unsafe_allow_html=True)
                       st.divider()
           else:
               st.write("Nenhum aluno registrado!")

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

   except Exception as e:
       st.error(f"Application error: {e}")
       st.info("Recarregue a página se o problema persistir.")

# Custom CSS for better performance and appearance
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
   header {display: none !important;}
   footer {display: none !important;}
   #MainMenu {display: none !important;}
   div[data-testid="stAppViewBlockContainer"] {
       padding-top: 0 !important;
       padding-bottom: 0 !important;
   }
   div[data-testid="stVerticalBlock"] {
       gap: 0 !important;
       padding-top: 0 !important;
       padding-bottom: 0 !important;
   }
   .element-container {
       margin-top: 0 !important;
       margin-bottom: 0 !important;
   }
   /* Improve form performance */
   .stForm {
       border: none !important;
   }
   /* Better mobile responsiveness */
   @media (max-width: 768px) {
       .block-container {
           padding-left: 1rem;
           padding-right: 1rem;
       }
   }
</style>
""", unsafe_allow_html=True)

if __name__ == "__main__":
   main()