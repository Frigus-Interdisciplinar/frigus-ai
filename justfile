set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
cmd := "frigus-ai"
python := if os() == "windows" { ".venv/Scripts/python" } else { ".venv/bin/python" }

venv:
    @echo "Preparing python environment"
    python -m venv .venv

run mode="tui":
    @echo "Running the application"
    {{cmd}} {{mode}}

check:
    @echo "Running pre-commit checks"
    {{python}} -m ruff check

fix:
    @echo "Running pre-commit fixes"
    {{python}} -m ruff check --fix

test:
    @echo "Running tests"
    {{python}} -m pytest
