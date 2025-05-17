# Aplicativo de Lista de Chamada

Este é um aplicativo web desenvolvido com Streamlit para registrar a presença de alunos. O aplicativo permite que os alunos registrem sua presença fornecendo nome e e-mail, e automaticamente captura a data/hora no formato brasileiro e o IP público do usuário.

## Funcionalidades

- Formulário centralizado para registro de presença
- Captura automática de data e hora no formato brasileiro
- Captura do IP público do usuário
- Lista de alunos presentes exibida em ordem alfabética na lateral direita
- Armazenamento dos registros em arquivo CSV

## Requisitos

- Python 3.7 ou superior
- Bibliotecas listadas no arquivo `requirements.txt`

## Instalação

1. Clone este repositório ou baixe os arquivos
2. Instale as dependências necessárias:

```
pip install -r requirements.txt
```

## Como executar

Para iniciar o aplicativo, execute o seguinte comando no terminal:

```
streamlit run app.py
```

O aplicativo será aberto automaticamente no seu navegador padrão. Se não abrir, acesse `http://localhost:8501`.

## Estrutura do projeto

- `app.py`: Arquivo principal contendo o código do aplicativo
- `requirements.txt`: Lista de dependências necessárias
- `registros.csv`: Arquivo gerado automaticamente para armazenar os registros de presença