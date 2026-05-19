"""REPL loop for the password generator."""

from config import Config
from password_engine import generate, assess_strength, generate_multiple


HELP_TEXT = (
    "Unknown command. Available commands:\n"
    "  length <num>         - Set password length\n"
    "  words <num>          - Set passphrase word count\n"
    "  uppercase on|off     - Toggle uppercase letters\n"
    "  lowercase on|off     - Toggle lowercase letters\n"
    "  digits on|off        - Toggle digits\n"
    "  symbols on|off       - Toggle symbols\n"
    "  ambiguous on|off     - Toggle ambiguous character exclusion\n"
    "  mode password|passphrase  - Switch generation mode\n"
    "  generate [N]         - Generate N passwords (default 1)\n"
    "  config               - Show current settings\n"
    "  quit / exit          - Exit the program\n"
)


def _print_config(config: Config) -> None:
    """Display the current configuration."""
    print(f"Mode: {config.mode}")
    if config.mode == "passphrase":
        print(f"Word count: {config.wordcount}")
    else:
        print(f"Length: {config.length}")
    print(f"Uppercase: {'on' if config.uppercase else 'off'}")
    print(f"Lowercase: {'on' if config.lowercase else 'off'}")
    print(f"Digits: {'on' if config.digits else 'off'}")
    print(f"Symbols: {'on' if config.symbols else 'off'}")
    print(f"Exclude ambiguous: {'on' if config.exclude_ambiguous else 'off'}")


def _on_off(value: str) -> bool | None:
    """Parse on/off string into a bool; returns None if invalid."""
    v = value.strip().lower()
    if v == "on":
        return True
    elif v == "off":
        return False
    return None


def start() -> None:
    """Start the REPL loop."""
    config = Config()

    print("Password Generator")
    print("Type 'config' to see settings, 'generate' to create a password, "
          "'quit' to exit.")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        # ---- length ----
        if cmd == "length":
            if len(parts) < 2:
                print("Usage: length <number>")
                continue
            try:
                val = int(parts[1])
                if val <= 0:
                    print("Invalid value, must be a positive integer.")
                    continue
                config.length = val
                print(f"Password length set to {val}.")
            except ValueError:
                print("Invalid value, must be a positive integer.")

        # ---- words ----
        elif cmd == "words":
            if len(parts) < 2:
                print("Usage: words <number>")
                continue
            try:
                val = int(parts[1])
                if val <= 0:
                    print("Invalid value, must be a positive integer.")
                    continue
                config.wordcount = val
                print(f"Passphrase word count set to {val}.")
            except ValueError:
                print("Invalid value, must be a positive integer.")

        # ---- uppercase ----
        elif cmd == "uppercase":
            if len(parts) < 2:
                print("Usage: uppercase on|off")
                continue
            val = _on_off(parts[1])
            if val is None:
                print("Usage: uppercase on|off")
                continue
            config.uppercase = val
            print(f"Uppercase: {'on' if val else 'off'}")

        # ---- lowercase ----
        elif cmd == "lowercase":
            if len(parts) < 2:
                print("Usage: lowercase on|off")
                continue
            val = _on_off(parts[1])
            if val is None:
                print("Usage: lowercase on|off")
                continue
            config.lowercase = val
            print(f"Lowercase: {'on' if val else 'off'}")

        # ---- digits ----
        elif cmd == "digits":
            if len(parts) < 2:
                print("Usage: digits on|off")
                continue
            val = _on_off(parts[1])
            if val is None:
                print("Usage: digits on|off")
                continue
            config.digits = val
            print(f"Digits: {'on' if val else 'off'}")

        # ---- symbols ----
        elif cmd == "symbols":
            if len(parts) < 2:
                print("Usage: symbols on|off")
                continue
            val = _on_off(parts[1])
            if val is None:
                print("Usage: symbols on|off")
                continue
            config.symbols = val
            print(f"Symbols: {'on' if val else 'off'}")

        # ---- ambiguous ----
        elif cmd == "ambiguous":
            if len(parts) < 2:
                print("Usage: ambiguous on|off")
                continue
            val = _on_off(parts[1])
            if val is None:
                print("Usage: ambiguous on|off")
                continue
            config.exclude_ambiguous = val
            print(f"Exclude ambiguous: {'on' if val else 'off'}")

        # ---- mode ----
        elif cmd == "mode":
            if len(parts) < 2:
                print("Usage: mode password|passphrase")
                continue
            m = parts[1].lower()
            if m not in ("password", "passphrase"):
                print("Usage: mode password|passphrase")
                continue
            config.mode = m
            print(f"Mode set to {m}.")

        # ---- generate ----
        elif cmd == "generate":
            count = 1
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                    if count <= 0:
                        print("Invalid value, must be a positive integer.")
                        continue
                except ValueError:
                    print("Invalid value, must be a positive integer.")
                    continue

            try:
                results = generate_multiple(config, count)
            except ValueError as e:
                print(f"Error: {e}")
                continue

            for i, pw in enumerate(results, start=1):
                strength = assess_strength(pw, config)
                print(f"{i}. {pw} ({strength})")

        # ---- config ----
        elif cmd == "config":
            _print_config(config)

        # ---- quit / exit ----
        elif cmd in ("quit", "exit"):
            print("Goodbye.")
            break

        else:
            print(HELP_TEXT)
