# Sistema de Controle de Testes de Equipamentos

Um sistema web desenvolvido em Flask para gerenciar e registrar os resultados de testes realizados em equipamentos de rede, como ONUs e roteadores.

## Visão Geral

Esta aplicação foi criada para otimizar o processo de controle de qualidade em bancadas de teste. Ela permite que técnicos registrem equipamentos, submetam resultados de testes (aprovação/reprovação) e mantenham um histórico detalhado para cada dispositivo. O sistema também conta com gerenciamento de usuários, logs de atividade e a capacidade de exportar relatórios em PDF.

## Funcionalidades Principais

- **Autenticação de Usuários**: Sistema de login seguro com diferentes níveis de permissão.
- **Gerenciamento de Equipamentos**:
  - Cadastro de novos equipamentos (Tipo, Modelo, MAC/Serial).
  - Solicitação de re-teste para equipamentos já cadastrados.
- **Registro de Testes**:
  - Lançamento de resultados (Aprovado/Reprovado).
  - Inclusão de dados técnicos como velocidade e sinal (dBm).
  - Adição de observações.
- **Histórico Completo**: Visualização de todos os testes realizados em um equipamento específico.
- **Pesquisa Avançada**: Ferramenta de busca com filtros por MAC/Serial, status, dia ou mês do teste.
- **Painel de Administração**:
  - Gerenciamento de usuários (criar, apagar, redefinir senha).
  - Visualização de logs de atividade do sistema.
- **Exportação para PDF**: Geração de relatórios em PDF para os resultados da pesquisa e para o histórico de equipamentos.
- **Tema Escuro**: Interface com suporte a tema claro e escuro para melhor visualização.

## Tecnologias Utilizadas

- **Backend**: Python 3, Flask
- **Banco de Dados**: SQLite (com Flask-SQLAlchemy)
- **Autenticação**: Flask-Login
- **Geração de PDF**: WeasyPrint
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)

## Instalação e Configuração

Siga os passos abaixo para configurar o ambiente de desenvolvimento.

**1. Pré-requisitos:**
- Python 3.8 ou superior
- `pip` e `venv`

**2. Clone o Repositório:**
```bash
git clone <url-do-repositorio>
cd <nome-do-repositorio>
```

**3. Crie e Ative um Ambiente Virtual:**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

**4. Instale as Dependências:**
```bash
pip install -r requirements.txt
```

## Executando a Aplicação (Desenvolvimento)

**1. Inicialize o Banco de Dados:**
Execute o comando abaixo no terminal para criar o arquivo de banco de dados (`testes.db`) e as tabelas necessárias.
```bash
flask init-db
```

**2. Crie o Usuário Administrador:**
Este comando cria o usuário `master` com uma senha padrão.
```bash
flask create-master
```
- **Usuário**: `master`
- **Senha**: `105391@Lu`

**3. Inicie o Servidor:**
```bash
python app.py
```
A aplicação estará disponível em `http://127.0.0.1:5000`.

## Executando em Produção

O arquivo `main.py` é o ponto de entrada para um ambiente de produção (ex: Render, Heroku). Ele cria automaticamente o banco de dados e um usuário `admin` (`senha: admin`) na primeira execução, se não existir.

Para executar em produção, utilize um servidor WSGI como o Gunicorn:
```bash
gunicorn --bind 0.0.0.0:5000 main:app
```
Ou execute o script diretamente (não recomendado para produção real):
```bash
python main.py
```

## Estrutura do Projeto
```
├── app.py                  # Arquivo principal da aplicação Flask (rotas, modelos, etc.)
├── main.py                 # Ponto de entrada para produção
├── requirements.txt        # Lista de dependências Python
├── templates/              # Arquivos HTML (interface do usuário)
│   ├── index.html          # Página principal
│   ├── login.html          # Página de login
│   └── ...
├── static/                 # Arquivos estáticos (CSS, JS, imagens)
│   └── logo.png
├── testes.db               # Arquivo do banco de dados SQLite
└── README.md               # Este arquivo
```
