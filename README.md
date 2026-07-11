Obs.: caso o app esteja no modo "sleeping" (dormindo) ao entrar, basta clicar no botão que estará disponível e aguardar, para ativar o mesmo.
![print](https://github.com/user-attachments/assets/ee3db758-7dc9-4b41-a263-ccd8c6687be4)

# 📝 List Web App - Sistema de Lista de Presença Digital

List Web App é uma aplicação web desenvolvida em Streamlit para o gerenciamento digital de listas de presença. Ideal para aulas, eventos ou qualquer situação que necessite de controle de participação ágil, com proteção contra registros fraudulentos e envio automatizado por e-mail. O professor autentica-se, inicia a lista e um cronômetro de 1 hora começa a contar; os alunos registram a própria presença (uma única vez, validada por IP público e sessão). Ao fim do tempo — ou quando o professor finalizar manualmente — a lista é enviada por e-mail com o CSV em anexo e um backup é salvo localmente.

## ✨ Funcionalidades Principais

* **Área do professor protegida:** os controles administrativos ficam ocultos dos alunos. O professor autentica-se uma vez por sessão (senha + CAPTCHA) no expander "🔑 Área do professor" e então pode iniciar/finalizar a lista sem redigitar a senha a cada ação.
* **Registro individual com trava anti-fraude:** cada aluno registra apenas a própria presença, **uma única vez**. O bloqueio de duplicidade combina três verificações: e-mail (normalizado, insensível a maiúsculas), sessão do navegador e **IP público do aluno** (obtido via `st.context.ip_address` — o IP do cliente conectado, nunca o do servidor).
* **Registro manual pelo professor:** para alunos presentes que tiveram travamentos ou problemas de rede/dispositivo, o professor autenticado pode registrá-los manualmente (expander "👨‍🏫 Registro manual pelo professor"). Esses registros ficam auditados no banco como `registrado_por = 'professor'` e aparecem com IP "registro manual" na lista.
* **Cronômetro com duração configurável e finalização automática:** antes de iniciar a lista, o professor escolhe a duração — **15 min, 30 min, 1 hora (padrão), 2 horas ou 4 horas**. Quando o tempo termina, a lista **fecha sozinha e o e-mail é enviado automaticamente**, sem intervenção do professor. Um mecanismo atômico no banco garante que apenas uma sessão execute o envio, mesmo com vários alunos conectados no momento da expiração.
* **E-mail com CSV em anexo:** ao finalizar (manual ou automaticamente), o destinatário configurado recebe um e-mail com a lista em HTML no corpo **e o arquivo CSV em anexo** (UTF-8 com BOM, compatível com Excel). Corpo e CSV vêm em **ordem alfabética** (ignorando maiúsculas/acentos), com Nome, E-mail, **IP público** e Data/Hora de cada registro.
* **Comprovante automático para o aluno:** assim que a presença é registrada (e o nome aparece na barra lateral), o aluno recebe automaticamente um **e-mail comprovante** com nome, e-mail e data/hora do registro — um "recibo" que dá segurança de que a presença foi computada. O envio passa por uma **fila persistente no SQLite (estilo AWS SQS)** consumida por um worker em segundo plano: com vários alunos registrando ao mesmo tempo, os e-mails entram em fila (com até 5 retentativas em caso de falha de SMTP) e **nunca atrasam ou travam o registro de presença**. Registros manuais feitos pelo professor também geram comprovante ao aluno.
* **Backup automático:** o mesmo CSV é salvo localmente (`lista_presenca_YYYYMMDD_HHMMSS.csv`) a cada finalização, inclusive se o envio do e-mail falhar.
* **Sidebar em tempo real:** a lista de presentes na barra lateral atualiza automaticamente a cada 5 segundos (via `st.fragment`) para todos os conectados, em ordem alfabética, com data e hora de cada registro. O aluno vê o próprio nome imediatamente após registrar.
* **Preparado para acessos simultâneos:** SQLite em modo WAL (leituras e escritas concorrentes), verificação de duplicados dentro da transação + constraint UNIQUE (dois registros simultâneos do mesmo e-mail: só um vence), finalização automática com trava atômica (um único envio mesmo com várias sessões abertas) e fila de comprovantes fora do caminho do registro.
* **Persistência em SQLite:** todos os dados (presenças, estado da aula, cronômetro e fila de comprovantes) ficam em `attendance.db` com modo WAL. O esquema é criado/migrado automaticamente na inicialização.
* **Data/hora no fuso de São Paulo**, formatada no padrão brasileiro com dia da semana.

## 🚀 Tecnologias Utilizadas

* **Python 3.x**
* **Streamlit ≥ 1.45** — interface web, `st.context.ip_address` (IP do cliente) e `st.fragment` (atualização em tempo real)
* **SQLite (WAL)** — persistência com acesso concorrente
* **Pandas** — manipulação da lista e geração do CSV
* **Pytz** — fuso horário de São Paulo
* **SMTPLib & Email MIME** — envio do e-mail com anexo
* **HTML/CSS/JavaScript** — cronômetro e customizações de interface

## 🔧 Pré-requisitos

* Python 3.9 ou superior
* pip (gerenciador de pacotes Python)

## ⚙️ Configuração e Instalação

1.  **Clone o repositório (ou copie os arquivos):**
    ```bash
    git clone <url_do_seu_repositorio>
    cd list-web-app
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure os Segredos (`secrets.toml`):**
    Crie o arquivo `.streamlit/secrets.toml` na pasta do projeto:

    ```toml
    # .streamlit/secrets.toml

    # Senha para o professor acessar a área administrativa
    senha_professor = "sua_senha_super_secreta"

    # E-mail para onde a lista de presença será enviada
    email_destinatario = "professor@exemplo.com"

    # Conta Gmail remetente e senha de aplicativo
    # (como gerar: https://support.google.com/accounts/answer/185833)
    email = "seu_email_gmail@gmail.com"
    senha_email = "sua_senha_de_aplicativo_do_gmail"
    ```

    * **Senha padrão:** se `senha_professor` não for configurada, a senha do professor é **`admin123`**. Em produção (Streamlit Cloud), defina sempre a sua própria senha nos *secrets*/variáveis de ambiente do app — ela sobrescreve o padrão.
    * Se `email` e `senha_email` não forem configurados, a aplicação simula os envios (lista final e comprovantes) e ainda assim salva o backup CSV local.

## ▶️ Como Usar

1.  **Execute a aplicação:**
    ```bash
    streamlit run app.py
    ```

2.  **Professor:**
    * Abra o expander **"🔑 Área do professor"**, resolva o CAPTCHA e informe a senha. A autenticação vale para toda a sessão.
    * Escolha a **duração da lista** (15 min a 4 horas; padrão 1 hora) e clique em **"Iniciar Lista"** — o cronômetro começa e os alunos já podem registrar presença.
    * Se algum aluno presente não conseguir registrar (problema técnico), use o **"Registro manual pelo professor"**.
    * Para encerrar antes do prazo, clique em **"Finalizar Lista"**. Caso contrário, ao fim da 1 hora a lista fecha e envia o e-mail **automaticamente**.

3.  **Aluno/Participante:**
    * Acesse a URL da aplicação com a lista iniciada, preencha Nome Completo e E-mail e clique em **"Registrar Presença"**.
    * O registro é único: e-mail, sessão e IP público repetidos são bloqueados.
    * Seu nome aparece imediatamente na barra lateral, com data e hora, em ordem alfabética — e um **e-mail comprovante** é enviado automaticamente para você.
    * Guie-se pela contagem regressiva no topo (com a duração definida pelo professor) — ao chegar em 00:00:00 a lista fecha sozinha.

## 🗂️ Persistência de Dados

* `attendance.db` — banco SQLite (modo WAL) com as tabelas:
    * `attendance`: nome, e-mail, data/hora, sessão, **IP público** e origem do registro (`aluno` ou `professor`);
    * `class_state`: estado da aula e horário-limite do cronômetro;
    * `email_queue`: fila de comprovantes (status `pendente`/`enviado`/`falhou`, com contagem de tentativas).
* `lista_presenca_YYYYMMDD_HHMMSS.csv` — backup gerado a cada finalização (o mesmo arquivo enviado como anexo do e-mail).

## ⚠️ Limitação Conhecida

A trava por IP público bloqueia um segundo registro vindo do mesmo IP. Em turmas presenciais onde todos usam o **mesmo Wi-Fi** (um único IP público de saída), apenas o primeiro aluno conseguirá registrar por essa rede — os demais podem usar dados móveis (4G/5G) ou ser registrados manualmente pelo professor. Em uso remoto/EAD (cada aluno em sua própria rede), a trava funciona de forma transparente.

## 👤 Autor

* **Ary Ribeiro**
* Contato: [aryribeiro@gmail.com](mailto:aryribeiro@gmail.com)
