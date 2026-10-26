set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
python := if os() == "windows" { ".venv/Scripts/python" } else { ".venv/bin/python" }
# No PowerShell, `bash` resolve pra C:\Windows\System32\bash.exe (WSL), não pro Git Bash — e
# com WSL sem distro/quebrado o `run` morre antes de começar. Acha o bash do Git a partir do
# próprio git (exec-path = <Git>/mingw64/libexec/git-core), sem caminho fixo por máquina.
bash := if os() == "windows" { "& '" + `Join-Path (Split-Path (Split-Path (Split-Path (git --exec-path)))) 'bin\bash.exe'` + "'" } else { "bash" }

venv:
    @echo "Preparing python environment"
    python -m venv .venv

run mode="tui":
    @echo "Running the application"
    {{bash}} scripts/run.sh {{mode}}

# API em modo local/demo: sem auth, tudo resolve pro primeiro usuário do Postgres (o que tem estoque).
# Não altera o .env; vale só pra este processo. O painel abre direto no chat, sem login.
api-local:
    $env:API__KEY_AUTH_ENABLED = "false"; just run api

web:
    @echo "Starting API (modo local) and frontend in separate terminals"
    Start-Process powershell -WorkingDirectory '{{justfile_directory()}}' -ArgumentList '-NoExit', '-Command', 'just api-local'
    Start-Process powershell -WorkingDirectory '{{justfile_directory()}}/web' -ArgumentList '-NoExit', '-Command', 'npm run dev'

obs:
    @echo "Subindo Prometheus (9090)"
    {{python}} scripts/prometheus_token.py
    docker compose --profile observability up -d --force-recreate prometheus

check:
    @echo "Running pre-commit checks"
    {{python}} -m ruff check

fix:
    @echo "Running pre-commit fixes"
    {{python}} -m ruff check --fix

test:
    @echo "Running tests"
    {{python}} -m pytest

deploy:
    @echo "Deploy manual no FastAPI Cloud (precisa de fastapi cloud login)"
    uvx "fastapi[standard]" deploy --app-id 1d76fa27-f906-4699-85cb-aa1a5e730341
