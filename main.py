import sys


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "tui"

    if modo == "tui":
        from interfaces.tui.app import run

        run()
    else:
        print(f"Interface '{modo}' ainda não implementada.")


if __name__ == "__main__":
    main()
