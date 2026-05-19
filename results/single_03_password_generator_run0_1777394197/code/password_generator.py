#!/usr/bin/env python3
"""Command-line password generator with REPL interface."""

import secrets
import string
import sys
from typing import Set


# Ambiguous characters that can be excluded
AMBIGUOUS_CHARS: Set[str] = {"0", "O", "1", "l", "I"}

# Character sets
UPPERCASE_CHARS = string.ascii_uppercase
LOWERCASE_CHARS = string.ascii_lowercase
DIGIT_CHARS = string.digits
SYMBOL_CHARS = "!@#$%^&*()-_=+[]{}|;:,.<>?/~`"


class PasswordGenerator:
    """Password generator with configurable settings."""

    def __init__(self):
        # Default configuration
        self.length: int = 16
        self.use_uppercase: bool = True
        self.use_lowercase: bool = True
        self.use_digits: bool = True
        self.use_symbols: bool = True
        self.exclude_ambiguous: bool = False

    def _get_allowed_chars(self) -> str:
        """Build the character pool based on current settings."""
        chars = ""
        if self.use_uppercase:
            chars += UPPERCASE_CHARS
        if self.use_lowercase:
            chars += LOWERCASE_CHARS
        if self.use_digits:
            chars += DIGIT_CHARS
        if self.use_symbols:
            chars += SYMBOL_CHARS

        if self.exclude_ambiguous:
            chars = "".join(c for c in chars if c not in AMBIGUOUS_CHARS)

        return chars

    def _count_char_types(self, password: str) -> int:
        """Count how many character types appear in the password."""
        types = 0
        if any(c in UPPERCASE_CHARS for c in password):
            types += 1
        if any(c in LOWERCASE_CHARS for c in password):
            types += 1
        if any(c in DIGIT_CHARS for c in password):
            types += 1
        if any(c in SYMBOL_CHARS for c in password):
            types += 1
        return types

    def rate_strength(self, password: str) -> str:
        """Rate password strength as weak, medium, strong, or very strong."""
        length = len(password)
        char_types = self._count_char_types(password)

        # Scoring system
        score = 0

        # Length contributes significantly
        if length >= 16:
            score += 4
        elif length >= 12:
            score += 3
        elif length >= 8:
            score += 2
        else:
            score += 1

        # Character variety
        score += char_types

        # Final rating
        if score >= 7:
            return "very strong"
        elif score >= 5:
            return "strong"
        elif score >= 3:
            return "medium"
        else:
            return "weak"

    def generate(self) -> str:
        """Generate a single password from the current settings."""
        chars = self._get_allowed_chars()
        if not chars:
            raise ValueError("All character sets are disabled. Enable at least one.")
        return "".join(secrets.choice(chars) for _ in range(self.length))

    def generate_multiple(self, count: int) -> list:
        """Generate multiple passwords."""
        return [self.generate() for _ in range(count)]

    def show_config(self) -> str:
        """Return a string describing the current configuration."""
        lines = [
            "=" * 50,
            "Current Configuration",
            "=" * 50,
            f"  Length:              {self.length}",
            f"  Uppercase (A-Z):     {'ON' if self.use_uppercase else 'OFF'}",
            f"  Lowercase (a-z):     {'ON' if self.use_lowercase else 'OFF'}",
            f"  Digits (0-9):        {'ON' if self.use_digits else 'OFF'}",
            f"  Symbols (!@#$...):   {'ON' if self.use_symbols else 'OFF'}",
            f"  Exclude ambiguous:   {'ON' if self.exclude_ambiguous else 'OFF'}",
            "=" * 50,
        ]
        return "\n".join(lines)


def print_help() -> None:
    """Print the help/command list."""
    help_text = """
Available commands:
  generate [N]     - Generate password(s). Default 1, or specify N for multiple.
  length <N>       - Set password length to N (default: 16).
  uppercase        - Toggle uppercase letters (A-Z).
  lowercase        - Toggle lowercase letters (a-z).
  digits           - Toggle digits (0-9).
  symbols          - Toggle symbols (!@#$%^&*-_=+ etc.).
  ambiguous        - Toggle exclusion of ambiguous characters (0/O, 1/l/I).
  config           - Show current configuration.
  help             - Show this help message.
  quit / exit      - Exit the program.
"""
    print(help_text)


def parse_positive_int(token: str, max_value: int = 100, label: str = "Count") -> int:
    """Parse a token as a positive integer with an optional maximum."""
    try:
        value = int(token)
    except ValueError:
        print(f"Error: '{token}' is not a valid number.")
        return -1
    if value < 1:
        print(f"Error: {label} must be at least 1.")
        return -1
    if value > max_value:
        print(f"Error: {label} cannot exceed {max_value}.")
        return -1
    return value


def repl() -> None:
    """Run the REPL loop."""
    gen = PasswordGenerator()

    print("Password Generator")
    print('Type "help" for commands, "quit" to exit.')
    print()

    while True:
        try:
            raw = input("passgen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        parts = raw.split()
        command = parts[0].lower()

        if command in ("quit", "exit"):
            print("Goodbye!")
            break

        elif command == "help":
            print_help()

        elif command == "config":
            print(gen.show_config())

        elif command == "length":
            if len(parts) < 2:
                print("Error: 'length' requires a number. Example: length 20")
                continue
            value = parse_positive_int(parts[1], max_value=256, label="Length")
            if value < 1:
                continue
            gen.length = value
            print(f"Password length set to {gen.length}.")

        elif command == "uppercase":
            gen.use_uppercase = not gen.use_uppercase
            state = "ON" if gen.use_uppercase else "OFF"
            print(f"Uppercase letters (A-Z): {state}")

        elif command == "lowercase":
            gen.use_lowercase = not gen.use_lowercase
            state = "ON" if gen.use_lowercase else "OFF"
            print(f"Lowercase letters (a-z): {state}")

        elif command == "digits":
            gen.use_digits = not gen.use_digits
            state = "ON" if gen.use_digits else "OFF"
            print(f"Digits (0-9): {state}")

        elif command == "symbols":
            gen.use_symbols = not gen.use_symbols
            state = "ON" if gen.use_symbols else "OFF"
            print(f"Symbols: {state}")

        elif command == "ambiguous":
            gen.exclude_ambiguous = not gen.exclude_ambiguous
            state = "ON" if gen.exclude_ambiguous else "OFF"
            print(f"Exclude ambiguous characters (0/O, 1/l/I): {state}")

        elif command == "generate":
            count = 1
            if len(parts) >= 2:
                count = parse_positive_int(parts[1], max_value=100, label="Count")
                if count < 1:
                    continue

            try:
                passwords = gen.generate_multiple(count)
            except ValueError as e:
                print(f"Error: {e}")
                continue

            if count == 1:
                pwd = passwords[0]
                strength = gen.rate_strength(pwd)
                print(f"Password: {pwd}")
                print(f"Strength: {strength}")
            else:
                print(f"Generated {count} passwords:")
                print("-" * 50)
                for i, pwd in enumerate(passwords, 1):
                    strength = gen.rate_strength(pwd)
                    print(f"  {i:>3}. {pwd}  [{strength}]")
                print("-" * 50)

        else:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")


def main() -> None:
    """Entry point."""
    # If arguments are passed, handle non-interactive mode
    if len(sys.argv) > 1:
        gen = PasswordGenerator()
        try:
            arg = sys.argv[1].lower()
            if arg == "generate":
                count = 1
                if len(sys.argv) > 2:
                    try:
                        count = int(sys.argv[2])
                    except ValueError:
                        print(f"Error: Invalid count '{sys.argv[2]}'")
                        sys.exit(1)
                passwords = gen.generate_multiple(count)
                for pwd in passwords:
                    print(f"{pwd}  [{gen.rate_strength(pwd)}]")
            elif arg == "config":
                print(gen.show_config())
            else:
                print(f"Unknown argument: {arg}")
                print("Usage: python password_generator.py [generate [N] | config]")
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        repl()


if __name__ == "__main__":
    main()
