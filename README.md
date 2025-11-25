Obs.: caso o app esteja no modo "sleeping" (dormindo) ao entrar, basta clicar no botão que estará disponível e aguardar, para ativar o mesmo.
![print](https://github.com/user-attachments/assets/ee3db758-7dc9-4b41-a263-ccd8c6687be4)

# 📝 List Web App - Sistema de Lista de Presença Digital

List Web App é uma aplicação web desenvolvida em Python e Streamlit para o gerenciamento digital e simplificado de listas de presença. Ideal para aulas, eventos ou qualquer situação que necessite de um controle de participação ágil e com registro automatizado. A aplicação permite que um professor inicie e finalize a coleta de presenças, enquanto os participantes podem registrar sua presença de forma individual. Ao final, a lista é enviada por e-mail e um backup é salvo..

## ✨ Funcionalidades Principais

* **Autenticação do Professor:** Acesso seguro às funções administrativas (iniciar/finalizar lista) através de senha e um sistema de CAPTCHA simples para maior segurança.
* **Registro de Alunos/Participantes:** Formulário intuitivo para os participantes registrarem Nome Completo e E-mail.
* **Identificação Única:** Evita duplicidade de registros verificando E-mail e/IP do participante.
* **Temporizador (Cronômetro):** Um cronômetro de 1 hora é iniciado quando a lista é aberta, indicando o tempo restante para registro.
* **Notificação por E-mail:** Ao finalizar a lista, um e-mail com a relação de presentes (em formato HTML) é enviado para um destinatário configurado.
* **Backup Automático:** Uma cópia da lista de presença em formato CSV é gerada e salva localmente ao finalizar e enviar o e-mail.
* **Persistência de Dados:**
    * Registros de presença são salvos em `registros.csv`.
    * O estado da aula (iniciada/não iniciada), o IP do professor e o tempo final do cronômetro são persistidos em arquivos de texto (`aula_estado.txt`, `ip_professor.txt`, `timer_end.txt`) para permitir a recuperação do estado em caso de reinicialização da aplicação.
* **Interface Limpa e Responsiva:** Layout organizado utilizando colunas e a barra lateral do Streamlit para visualização dos presentes. Estilos personalizados para uma experiência de usuário aprimorada.
* **Informações em Tempo Real:** Exibição do IP público do usuário e data/hora atual formatada para o padrão brasileiro (com fuso horário de São Paulo).
* **Configuração Segura:** Utiliza o sistema de `secrets` do Streamlit para gerenciar credenciais sensíveis (senha do professor, dados de e-mail).

## 🚀 Tecnologias Utilizadas

* **Python 3.x**
* **Streamlit:** Framework principal para a construção da interface web.
* **Pandas:** Para manipulação e armazenamento dos dados da lista de presença.
* **Requests:** Para obter o endereço IP público.
* **Pytz:** Para manipulação de fusos horários.
* **SMTPLib & Email Mime:** Para o envio de e-mails.
* **HTML/CSS/JavaScript:** Para customizações de interface e o cronômetro.

## 🔧 Pré-requisitos

* Python 3.7 ou superior
* pip (gerenciador de pacotes Python)

## ⚙️ Configuração e Instalação

1.  **Clone o repositório (ou copie os arquivos):**
    ```bash
    # Se estiver usando git
    git clone <url_do_seu_repositorio>
    cd <nome_do_seu_repositorio>
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências do requirements.txt:**
    
    streamlit
    pandas
    requests
    pytz
    
4.  **Configure os Segredos (`secrets.toml`):**
    Crie um arquivo chamado `.secrets.toml` na pasta `.streamlit` dentro do diretório do seu projeto (`seu_projeto/.streamlit/secrets.toml`). Adicione o seguinte conteúdo, substituindo pelos seus dados:

    ```toml
    # .streamlit/secrets.toml

    # Senha para o professor acessar as funcionalidades de iniciar/finalizar lista
    senha_professor = "sua_senha_super_secreta"

    # E-mail para onde a lista de presença será enviada
    email_destinatario = "professor@exemplo.com"

    # Configurações para envio de e-mail via Gmail
    # E-mail do remetente (conta Gmail que enviará a lista)
    email = "seu_email_gmail@gmail.com"
    # Senha de aplicativo gerada para o e-mail acima.
    # Veja como gerar: [https://support.google.com/accounts/answer/185833](https://support.google.com/accounts/answer/185833)
    senha_email = "sua_senha_de_aplicativo_do_gmail"
    ```
    *Se você não configurar `email` e `senha_email`, a aplicação irá simular o envio e alertar sobre a necessidade de configuração para envios reais.*

## ▶️ Como Usar

1.  **Execute a aplicação:**
    Navegue até o diretório raiz do projeto no terminal e execute:
    ```bash
    streamlit run seu_arquivo_python.py
    ```
    (Substitua `seu_arquivo_python.py` pelo nome do seu arquivo principal, ex: `app.py`).

2.  **Para o Professor:**
    * Ao acessar a aplicação, se a lista não estiver iniciada, clique em "Iniciar Lista".
    * Digite a `senha_professor` configurada no `secrets.toml` e resolva o CAPTCHA.
    * Após a autenticação, a lista é iniciada, o cronômetro começa, e os alunos podem registrar a presença.
    * O IP do professor é registrado para ajudar na identificação em sessões futuras (embora a senha seja o principal fator de autenticação).
    * Para encerrar, clique em "Finalizar Lista", autentique-se novamente. A lista de presença será enviada por e-mail, um backup salvo, e os dados da sessão atual serão limpos.

3.  **Para o Aluno/Participante:**
    * Acesse a URL da aplicação.
    * Se a lista estiver iniciada pelo professor, um formulário para "Nome Completo" e "E-mail" estará disponível.
    * Preencha os dados e clique em "Registrar Presença".
    * Uma mensagem de sucesso ou erro (caso já registrado ou campos vazios) será exibida.
    * Os nomes dos alunos presentes são exibidos na barra lateral, ordenados alfabeticamente.

## 🗂️ Persistência de Dados

A aplicação utiliza arquivos locais para persistir dados entre sessões:

* `registros.csv`: Armazena os dados de todos os alunos que registraram presença (Nome, Email, Data/Hora do registro).
* `aula_estado.txt`: Indica se a aula está 'iniciada' ou não.
* `timer_end.txt`: Guarda a data e hora exatas em que o cronômetro de presença deve terminar.
* `ip_professor.txt`: Armazena o IP público do professor que iniciou a aula.
* Backups: Arquivos CSV com timestamp (ex: `lista_presenca_20240517_103000.csv`) são criados na pasta da aplicação cada vez que uma lista é finalizada e enviada por e-mail.

## 💡 Possíveis Melhorias e Próximos Passos

* **Tratamento de Exceções Mais Específico:** Refinar os blocos `try-except` para capturar exceções mais granulares, facilitando o debug.
* **Banco de Dados:** Para maior robustez e escalabilidade, substituir o uso de arquivos CSV e TXT por um banco de dados simples (ex: SQLite).
* **Lógica de Identificação do Professor:** Aprimorar a lógica `is_professor` para depender menos do IP e mais da autenticação ativa na sessão.
* **Finalização Automática Real:** Implementar uma lógica no backend para finalizar a lista e enviar o e-mail automaticamente quando o timer expirar, mesmo sem interação do professor.
* **CAPTCHA Mais Robusto:** Considerar bibliotecas de CAPTCHA mais avançadas se a segurança contra bots se tornar uma preocupação maior.
* **Interface de Gerenciamento:** Uma área para o professor visualizar/editar/exportar listas antigas.
* **Personalização do Tempo do Cronômetro:** Permitir que o professor defina a duração do registro.

## 👤 Autor

* **Ary Ribeiro**
* Contato: [aryribeiro@gmail.com](mailto:aryribeiro@gmail.com)
