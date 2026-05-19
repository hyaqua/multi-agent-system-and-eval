#!/usr/bin/env python3
"""
Command-line password generator with REPL interface.
Generates random passwords with configurable length, character sets,
strength rating, passphrase support, and ambiguous character exclusion.
"""

import secrets
import string
import sys
import math
import re


# A small built-in word list for passphrase generation (common English words, 4-7 letters)
WORD_LIST = [
    "apple", "blue", "cat", "dog", "eagle", "fish", "green", "happy", "ice",
    "jungle", "kite", "lion", "moon", "night", "ocean", "piano", "queen",
    "rain", "sun", "tree", "umbrella", "violet", "water", "xray", "yellow",
    "zebra", "bridge", "cloud", "dragon", "earth", "forest", "garden", "house",
    "island", "jazz", "king", "lake", "mountain", "north", "orange", "purple",
    "river", "stone", "tiger", "valley", "wind", "star", "dawn", "field",
    "glass", "honey", "iron", "jade", "knife", "lemon", "music", "noble",
    "olive", "paper", "quiet", "rose", "silver", "table", "unity", "voice",
    "winter", "amber", "blaze", "coral", "delta", "ember", "flame", "grace",
    "harvest", "ivy", "jasper", "koala", "lilac", "maple", "nest", "onyx",
    "pearl", "quartz", "raven", "sage", "thorn", "willow", "acorn", "birch",
    "cedar", "dove", "elm", "fern", "grove", "hawk", "iris", "lotus",
]


# Ambiguous characters
AMBIGUOUS_CHARS = "0O1lI"


def get_uppercase():
    """Return uppercase letters, optionally excluding ambiguous ones."""
    return string.ascii_uppercase


def get_lowercase():
    """Return lowercase letters, optionally excluding ambiguous ones."""
    return string.ascii_lowercase


def get_digits():
    """Return digits, optionally excluding ambiguous ones."""
    return string.digits


def get_symbols():
    """Return symbol characters."""
    return "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"


class PasswordGenerator:
    """Manages configuration and generation of passwords."""

    def __init__(self):
        self.length = 16
        self.use_uppercase = True
        self.use_lowercase = True
        self.use_digits = True
        self.use_symbols = True
        self.exclude_ambiguous = False
        self.running = True

    def get_charset(self):
        """Build the character set based on current configuration."""
        chars = ""
        if self.use_uppercase:
            upper = get_uppercase()
            if self.exclude_ambiguous:
                upper = "".join(c for c in upper if c not in AMBIGUOUS_CHARS)
            chars += upper
        if self.use_lowercase:
            lower = get_lowercase()
            if self.exclude_ambiguous:
                lower = "".join(c for c in lower if c not in AMBIGUOUS_CHARS)
            chars += lower
        if self.use_digits:
            digits = get_digits()
            if self.exclude_ambiguous:
                digits = "".join(c for c in digits if c not in AMBIGUOUS_CHARS)
            chars += digits
        if self.use_symbols:
            chars += get_symbols()
        return chars

    def rate_strength(self, password):
        """Rate password strength based on entropy and character diversity."""
        # Determine the charset size used to generate this password
        charset = self.get_charset()
        if not charset:
            return "none"

        charset_size = len(set(charset))
        entropy = self.length * math.log2(charset_size)

        # Additional factors: check for character class diversity
        has_upper = any(c in get_uppercase() for c in password)
        has_lower = any(c in get_lowercase() for c in password)
        has_digit = any(c in get_digits() for c in password)
        has_symbol = any(c in get_symbols() for c in password)
        class_count = sum([has_upper, has_lower, has_digit, has_symbol])

        # Adjust effective entropy based on class count
        if class_count >= 3:
            entropy *= 1.1
        if class_count == 4:
            entropy *= 1.1

        if entropy < 40:
            return "weak"
        elif entropy < 60:
            return "medium"
        elif entropy < 80:
            return "strong"
        else:
            return "very strong"

    def generate_password(self):
        """Generate a single random password."""
        charset = self.get_charset()
        if not charset:
            return None
        return "".join(secrets.choice(charset) for _ in range(self.length))

    def generate_passphrase(self, num_words=4, separator="-", capitalize=False, include_number=False):
        """Generate a memorable passphrase from random words."""
        words = [secrets.choice(WORD_LIST) for _ in range(num_words)]
        if capitalize:
            words = [w.capitalize() for w in words]
        passphrase = separator.join(words)
        if include_number:
            passphrase += str(secrets.randbelow(100))
        return passphrase

    def handle_command(self, line):
        """Parse and execute a command."""
        line = line.strip()
        if not line:
            return

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            self.running = False
            print("Goodbye!")
            return

        elif cmd == "length":
            if len(parts) < 2:
                print("Usage: length <number>")
                return
            try:
                new_length = int(parts[1])
                if new_length < 1:
                    print("Error: Length must be at least 1.")
                    return
                if new_length > 256:
                    print("Error: Length cannot exceed 256.")
                    return
                self.length = new_length
                print(f"Password length set to {self.length}.")
            except ValueError:
                print("Error: Length must be a valid integer.")

        elif cmd in ("uppercase", "upper"):
            if len(parts) < 2:
                self.use_uppercase = not self.use_uppercase
            else:
                val = parts[1].lower()
                if val in ("on", "true", "yes", "enable"):
                    self.use_uppercase = True
                elif val in ("off", "false", "no", "disable"):
                    self.use_uppercase = False
                else:
                    print("Usage: uppercase [on|off]")
                    return
            print(f"Uppercase: {'ON' if self.use_uppercase else 'OFF'}")

        elif cmd in ("lowercase", "lower"):
            if len(parts) < 2:
                self.use_lowercase = not self.use_lowercase
            else:
                val = parts[1].lower()
                if val in ("on", "true", "yes", "enable"):
                    self.use_lowercase = True
                elif val in ("off", "false", "no", "disable"):
                    self.use_lowercase = False
                else:
                    print("Usage: lowercase [on|off]")
                    return
            print(f"Lowercase: {'ON' if self.use_lowercase else 'OFF'}")

        elif cmd == "digits":
            if len(parts) < 2:
                self.use_digits = not self.use_digits
            else:
                val = parts[1].lower()
                if val in ("on", "true", "yes", "enable"):
                    self.use_digits = True
                elif val in ("off", "false", "no", "disable"):
                    self.use_digits = False
                else:
                    print("Usage: digits [on|off]")
                    return
            print(f"Digits: {'ON' if self.use_digits else 'OFF'}")

        elif cmd == "symbols":
            if len(parts) < 2:
                self.use_symbols = not self.use_symbols
            else:
                val = parts[1].lower()
                if val in ("on", "true", "yes", "enable"):
                    self.use_symbols = True
                elif val in ("off", "false", "no", "disable"):
                    self.use_symbols = False
                else:
                    print("Usage: symbols [on|off]")
                    return
            print(f"Symbols: {'ON' if self.use_symbols else 'OFF'}")

        elif cmd == "ambiguous":
            if len(parts) < 2:
                self.exclude_ambiguous = not self.exclude_ambiguous
            else:
                val = parts[1].lower()
                if val in ("on", "true", "yes", "enable"):
                    self.exclude_ambiguous = True
                elif val in ("off", "false", "no", "disable"):
                    self.exclude_ambiguous = False
                else:
                    print("Usage: ambiguous [on|off]")
                    return
            print(f"Exclude ambiguous characters (0/O, 1/l/I): {'ON' if self.exclude_ambiguous else 'OFF'}")

        elif cmd == "generate":
            count = 1
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                    if count < 1:
                        print("Error: Count must be at least 1.")
                        return
                    if count > 100:
                        print("Error: Cannot generate more than 100 passwords at once.")
                        return
                except ValueError:
                    print("Error: Count must be a valid integer.")
                    return

            charset = self.get_charset()
            if not charset:
                print("ERROR: Cannot generate password. All character sets are disabled.")
                print("Enable at least one character set (uppercase, lowercase, digits, symbols).")
                return

            print(f"\nGenerating {count} password(s)...\n")
            for i in range(count):
                pwd = self.generate_password()
                strength = self.rate_strength(pwd)
                print(f"  {i+1}. {pwd}  [{strength}]")
            print()

        elif cmd == "passphrase":
            # Parse options
            num_words = 4
            separator = "-"
            capitalize = False
            include_number = False

            # Simple parsing: passphrase [N] [-sep X] [-capitalize] [-number]
            idx = 1
            while idx < len(parts):
                arg = parts[idx].lower()
                if arg == "-sep" or arg == "-separator":
                    if idx + 1 < len(parts):
                        separator = parts[idx + 1]
                        idx += 2
                    else:
                        print("Error: -sep requires a separator string.")
                        return
                elif arg == "-capitalize":
                    capitalize = True
                    idx += 1
                elif arg == "-number":
                    include_number = True
                    idx += 1
                else:
                    try:
                        num_words = int(arg)
                        if num_words < 2:
                            print("Error: Passphrase must have at least 2 words.")
                            return
                        if num_words > 20:
                            print("Error: Passphrase cannot have more than 20 words.")
                            return
                    except ValueError:
                        print(f"Unknown option: {arg}")
                        return
                    idx += 1

            passphrase = self.generate_passphrase(
                num_words=num_words,
                separator=separator,
                capitalize=capitalize,
                include_number=include_number,
            )
            # Rate the passphrase roughly
            # Approximate entropy: each word from a list of ~100 words = ~6.6 bits
            word_entropy = num_words * math.log2(len(WORD_LIST))
            if capitalize:
                word_entropy += num_words  # each word could be capitalized or not
            if include_number:
                word_entropy += math.log2(100)  # 0-99

            if word_entropy < 40:
                strength = "weak"
            elif word_entropy < 60:
                strength = "medium"
            elif word_entropy < 80:
                strength = "strong"
            else:
                strength = "very strong"

            print(f"\n  Passphrase: {passphrase}  [{strength}]\n")

        elif cmd == "config":
            print("\n" + "=" * 50)
            print("  CURRENT CONFIGURATION")
            print("=" * 50)
            print(f"  Length:              {self.length}")
            print(f"  Uppercase:           {'ON' if self.use_uppercase else 'OFF'}")
            print(f"  Lowercase:           {'ON' if self.use_lowercase else 'OFF'}")
            print(f"  Digits:              {'ON' if self.use_digits else 'OFF'}")
            print(f"  Symbols:             {'ON' if self.use_symbols else 'OFF'}")
            print(f"  Exclude Ambiguous:   {'ON' if self.exclude_ambiguous else 'OFF'}")
            charset = self.get_charset()
            if charset:
                print(f"  Active charset size: {len(set(charset))} characters")
                entropy = self.length * math.log2(len(set(charset)))
                print(f"  Entropy per password: ~{entropy:.1f} bits")
            else:
                print(f"  Active charset:      NONE (all disabled!)")
            print("=" * 50 + "\n")

        elif cmd in ("help", "?"):
            self.print_help()

        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")

    def print_help(self):
        """Print help information."""
        print("""
Available commands:
  length <N>        Set password length (default: 16, min: 1, max: 256)
  uppercase [on|off]  Toggle or set uppercase letters
  lowercase [on|off]  Toggle or set lowercase letters
  digits [on|off]     Toggle or set digits
  symbols [on|off]    Toggle or set symbols
  ambiguous [on|off]  Toggle exclusion of ambiguous chars (0/O, 1/l/I)
  generate [N]      Generate N passwords (default: 1, max: 100)
  passphrase [N] [-sep X] [-capitalize] [-number]
                    Generate a passphrase of N words (default: 4)
  config            Display current configuration
  help, ?           Show this help message
  quit, exit        Exit the program
""")

    def run(self):
        """Run the REPL loop."""
        print("=" * 60)
        print("  PASSWORD GENERATOR")
        print("  Type 'help' for available commands, 'quit' to exit.")
        print("=" * 60)

        # If stdin is a pipe/redirect, read all lines at once
        if not sys.stdin.isatty():
            for line in sys.stdin:
                line = line.strip()
                if line:
                    print(f"> {line}")
                    self.handle_command(line)
                    if not self.running:
                        break
            return

        while self.running:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            if line:
                self.handle_command(line)


def main():
    gen = PasswordGenerator()
    gen.run()


if __name__ == "__main__":
    main()
