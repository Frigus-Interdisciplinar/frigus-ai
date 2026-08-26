import sys


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "tui"

    if modo == "tui":
        from interfaces.tui.app import run

        run()
    elif modo == "api":
        import uvicorn

        from config.docker import garantir_banco

        garantir_banco()
        uvicorn.run("interfaces.api.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        print(f"Interface '{modo}' ainda não implementada.")


if __name__ == "__main__":
    main()
