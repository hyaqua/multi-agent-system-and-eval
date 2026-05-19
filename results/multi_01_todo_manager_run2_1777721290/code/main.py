"""Entry point for the Task Manager application."""

from manager import Manager
from cli import CLI


def main() -> None:
    manager = Manager()
    cli = CLI(manager)
    cli.run()


if __name__ == "__main__":
    main()
