# Cana Mania — sistema de gestão

Aplicação web para administrar produtos e estoque, registrar vendas no PDV e acompanhar operações da loja. Também inclui gestão de clientes, categorias, movimentações, filiais, máquinas e reservas de armários.

## Requisitos

- Python 3.10 ou superior
- `pip`
- Git (opcional, para clonar o repositório)

## Instalação local

No terminal, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No macOS ou Linux, ative o ambiente com `source .venv/bin/activate`.

O sistema usa SQLite por padrão e cria as tabelas ausentes ao iniciar. Para iniciar o servidor local:

```bash
uvicorn app.main:app --reload
```

Acesse <http://127.0.0.1:8000>. A documentação interativa da API fica em <http://127.0.0.1:8000/docs>.

## Configuração do ambiente

Crie um arquivo `.env` na raiz do projeto. Não publique esse arquivo nem coloque credenciais nele no Git. A aplicação carrega as configurações do ambiente; sem `DATABASE_URL`, usa `sqlite:///./estoque.db`.

Exemplo mínimo:

```dotenv
DATABASE_URL=sqlite:///./estoque.db
SECRET_KEY=gere-uma-chave-aleatoria-longa-para-este-ambiente
ACCESS_TOKEN_EXPIRACAO_MINUTOS=60
RESET_TOKEN_EXPIRACAO_MINUTOS=30
```

Para usar PostgreSQL, configure `DATABASE_URL` com a URL da instância, por exemplo `postgresql://usuario:senha@host:5432/banco`. Mantenha a senha fora do repositório.

### Pix

O PDV gera o código Pix a partir das credenciais da conta recebedora. Configure no `.env`:

```dotenv
PIX_CHAVE=
PIX_NOME_RECEBEDOR=
PIX_CIDADE=
```

Preencha os valores com a chave Pix cadastrada, o nome do recebedor e a cidade. O arquivo `.env.pix.example` contém os nomes dessas variáveis; ele pode servir de referência, mas não contém credenciais.

### Recuperação de senha por e-mail

Para habilitar o envio dos links de redefinição, configure as variáveis SMTP:

```dotenv
SMTP_HOST=
SMTP_PORT=587
SMTP_FROM=
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_SSL=false
SMTP_USE_TLS=true
```

Use os dados fornecidos pelo seu serviço de e-mail. Em produção, defina também uma `SECRET_KEY` forte e exclusiva; não use a chave padrão de desenvolvimento.

## Banco de dados e migrações

As revisões do Alembic ficam em `migrations/versions`. Para aplicar as migrações pendentes ao banco selecionado por `DATABASE_URL`:

```bash
alembic upgrade head
```

Para criar uma nova revisão a partir das mudanças nos modelos:

```bash
alembic revision --autogenerate -m "descreva a mudança"
```

Revise a revisão gerada antes de aplicá-la. Faça backup do banco antes de atualizar uma instalação com dados importantes.

## Testes

Os testes usam `pytest`. Instale-o no ambiente virtual e execute a suíte:

```bash
pip install pytest
python -m pytest
```

## Organização do projeto

- `app/main.py`: configuração do FastAPI e páginas principais.
- `app/controllers/`: rotas e operações dos módulos.
- `app/models/`: modelos do banco de dados.
- `app/templates/`: páginas HTML renderizadas no servidor.
- `app/static/`: CSS, JavaScript e arquivos estáticos.
- `migrations/`: configuração e revisões do Alembic.
- `tests/`: testes automatizados.
- `requirements.txt`: dependências da aplicação.

## Segurança

- Nunca versione `.env`, chaves Pix, senhas, tokens ou URLs de banco com credenciais.
- Use credenciais próprias e uma `SECRET_KEY` forte para cada ambiente.
- Em hospedagens como Render, configure as variáveis no painel de ambiente do serviço e mantenha os dados persistentes do banco em armazenamento apropriado.
