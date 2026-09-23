set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
python := if os() == "windows" { ".venv/Scripts/python" } else { ".venv/bin/python" }

venv:
    @echo "Preparing python environment"
    python -m venv .venv

run mode="tui":
    @echo "Running the application"
    bash scripts/run.sh {{mode}}

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
