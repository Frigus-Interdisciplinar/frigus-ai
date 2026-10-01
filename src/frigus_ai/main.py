import sys


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "tui"

    if modo == "tui":
        from frigus_ai.tui.app import run

        run()
    elif modo == "api":
        import uvicorn

        from frigus_ai.settings import settings

        uvicorn.run("frigus_ai.api.app:app", host="0.0.0.0", port=8000, reload=settings.api.reload)
    else:
        print(f"Interface '{modo}' ainda não implementada.")


if __name__ == "__main__":
    main()
