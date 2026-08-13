import sys


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "terminal"

    if modo == "terminal":
        from interfaces.terminal.app import run

        run()
    else:
        print(f"Interface '{modo}' ainda não implementada.")


if __name__ == "__main__":
    main()
