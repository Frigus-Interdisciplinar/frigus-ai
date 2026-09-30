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

web:
    @echo "Starting API and frontend in separate terminals"
    Start-Process powershell -WorkingDirectory '{{justfile_directory()}}' -ArgumentList '-NoExit', '-Command', 'just run api'
    Start-Process powershell -WorkingDirectory '{{justfile_directory()}}/web' -ArgumentList '-NoExit', '-Command', 'npm run dev'

check:
    @echo "Running pre-commit checks"
    {{python}} -m ruff check

fix:
    @echo "Running pre-commit fixes"
    {{python}} -m ruff check --fix

test:
    @echo "Running tests"
    {{python}} -m pytest
