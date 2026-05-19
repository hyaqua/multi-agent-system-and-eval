#!/usr/bin/env python3
"""
Command-line password generator with REPL interface.

Features:
- Configurable password length (default 16)
- Toggle character sets: uppercase, lowercase, digits, symbols
- Exclude ambiguous characters (0/O, 1/l/I)
- Generate one or multiple passwords
- Strength rating for each password
- Passphrase generation
- Show current configuration
"""

import secrets
import string
import sys
import os


# ─── Character sets ───────────────────────────────────────────────────────────

UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?/"

# Ambiguous characters to exclude when filtering is enabled
AMBIGUOUS = set("0O1lI")

# A modest built-in word list for passphrase generation.
# On Unix we try to load /usr/share/dict/words; otherwise fall back to this.
FALLBACK_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
    "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
    "oscar", "papa", "quebec", "romeo", "sierra", "tango", "uniform",
    "victor", "whiskey", "xray", "yankee", "zulu", "apple", "banana",
    "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi",
    "lemon", "mango", "nectarine", "orange", "papaya", "quince",
    "raspberry", "strawberry", "tangerine", "vanilla", "watermelon",
    "apricot", "blueberry", "coconut", "dragonfruit", "guava", "lime",
    "lychee", "melon", "olive", "peach", "pear", "pineapple", "plum",
    "pumpkin", "acorn", "badger", "coyote", "dolphin", "eagle", "falcon",
    "giraffe", "hawk", "iguana", "jaguar", "koala", "llama", "meerkat",
    "narwhal", "octopus", "penguin", "raccoon", "salmon", "turtle",
    "urchin", "vulture", "walrus", "yak", "zebra", "anchor", "bridge",
    "castle", "diamond", "emerald", "forest", "garden", "harbor",
    "island", "jungle", "kettle", "lantern", "mountain", "needle",
    "ocean", "prairie", "quartz", "river", "sunset", "thunder",
    "umbrella", "valley", "willow", "zenith", "breeze", "cloud",
    "dawn", "ember", "frost", "glacier", "horizon", "iris", "jade",
    "kale", "lotus", "mist", "nova", "orbit", "petal", "rain", "stone",
    "tide", "vapor", "wave", "aurora", "basil", "canyon", "dew",
    "elk", "fern", "grove", "hazel", "ivy", "juniper", "kite",
    "lily", "maple", "north", "onyx", "pine", "reef", "sage",
    "thorn", "west", "yarrow", "ash", "birch", "cedar", "dune",
    "elm", "flint", "heath", "moss", "oak", "reed", "spruce",
    "teak", "wheat", "barn", "cabin", "dock", "forge", "hut",
    "inn", "lodge", "mill", "nest", "pier", "shed", "tent",
    "arch", "beam", "column", "dome", "gate", "hall", "keystone",
    "loft", "plaza", "spire", "tower", "vault", "wing", "yard",
]
FALLBACK_WORDS = sorted(set(w.lower() for w in FALLBACK_WORDS))


# ─── Passphrase word loader ──────────────────────────────────────────────────

def load_word_list():
    """Load a word list from the system dictionary if available, else fallback."""
    paths = ["/usr/share/dict/words", "/usr/dict/words"]
    for path in paths:
        try:
            with open(path, "r") as f:
                words = [line.strip().lower() for line in f
                         if line.strip().isalpha() and len(line.strip()) >= 3]
                if len(words) >= 100:
                    return words
        except (FileNotFoundError, PermissionError):
            continue
    return FALLBACK_WORDS


# ─── Strength rating ─────────────────────────────────────────────────────────

def rate_strength(password: str) -> str:
    """Rate password strength based on length and character diversity."""
    length = len(password)
    has_upper = any(c in string.ascii_uppercase for c in password)
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_digit = any(c in string.digits for c in password)
    has_symbol = any(c in SYMBOLS for c in password)

    char_classes = sum([has_upper, has_lower, has_digit, has_symbol])

    score = 0
    # Length scoring
    if length >= 20:
        score += 3
    elif length >= 14:
        score += 2
    elif length >= 10:
        score += 1

    # Diversity scoring
    if char_classes == 4:
        score += 3
    elif char_classes == 3:
        score += 2
    elif char_classes == 2:
        score += 1

    if score >= 5:
        return "very strong"
    elif score >= 3:
        return "strong"
    elif score >= 2:
        return "medium"
    else:
        return "weak"


# ─── Password generation ─────────────────────────────────────────────────────

def build_charset(config: dict) -> str:
    """Build the character set string based on current config."""
    chars = ""
    if config["uppercase"]:
        chars += UPPERCASE
    if config["lowercase"]:
        chars += LOWERCASE
    if config["digits"]:
        chars += DIGITS
    if config["symbols"]:
        chars += SYMBOLS

    if config["exclude_ambiguous"]:
        chars = "".join(c for c in chars if c not in AMBIGUOUS)

    return chars


def generate_password(config: dict) -> str:
    """Generate a single random password according to config."""
    charset = build_charset(config)
    if not charset:
        raise ValueError("All character sets are disabled! Enable at least one.")
    length = config["length"]
    return "".join(secrets.choice(charset) for _ in range(length))


def generate_passphrase(config: dict, word_count: int = 4) -> str:
    """Generate a passphrase of random words."""
    words = config["word_list"]
    chosen = [secrets.choice(words) for _ in range(word_count)]
    separator = config.get("passphrase_separator", "-")
    return separator.join(chosen)


# ─── REPL ────────────────────────────────────────────────────────────────────

HELP_TEXT = """
Commands:
  generate [N]          Generate N passwords (default 1)
  passphrase [N]        Generate a passphrase of N words (default 4)
  length <number>       Set password length
  uppercase on|off      Toggle uppercase letters
  lowercase on|off      Toggle lowercase letters
  digits on|off         Toggle digits
  symbols on|off        Toggle symbols
  ambiguous on|off      Toggle exclusion of ambiguous characters (0/O/1/l/I)
  sep <char>            Set passphrase word separator (default '-')
  config                Show current configuration
  help                  Show this help
  quit | exit           Exit the program
"""


def print_config(config: dict):
    """Display current configuration."""
    print()
    print("=" * 42)
    print("  Current Configuration")
    print("=" * 42)
    print(f"  Password length:      {config['length']}")
    print(f"  Uppercase:            {'ON' if config['uppercase'] else 'OFF'}")
    print(f"  Lowercase:            {'ON' if config['lowercase'] else 'OFF'}")
    print(f"  Digits:               {'ON' if config['digits'] else 'OFF'}")
    print(f"  Symbols:              {'ON' if config['symbols'] else 'OFF'}")
    print(f"  Exclude ambiguous:    {'ON' if config['exclude_ambiguous'] else 'OFF'}")
    print(f"  Passphrase separator: '{config['passphrase_separator']}'")
    active = build_charset(config)
    print(f"  Active charset ({len(active)} chars): {active[:60]}{'...' if len(active) > 60 else ''}")
    print("=" * 42)
    print()


def repl():
    """Main REPL loop."""
    word_list = load_word_list()

    config = {
        "length": 16,
        "uppercase": True,
        "lowercase": True,
        "digits": True,
        "symbols": True,
        "exclude_ambiguous": False,
        "passphrase_separator": "-",
        "word_list": word_list,
    }

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║        🔐 Password Generator 🔐             ║")
    print("║  Type 'help' for commands, 'quit' to exit.  ║")
    print("╚══════════════════════════════════════════════╝")
    print_config(config)

    while True:
        try:
            raw = input("passgen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        # ── quit / exit ──
        if cmd in ("quit", "exit"):
            print("Goodbye!")
            break

        # ── help ──
        elif cmd == "help":
            print(HELP_TEXT)

        # ── config ──
        elif cmd == "config":
            print_config(config)

        # ── length ──
        elif cmd == "length":
            if len(parts) < 2:
                print("Usage: length <number>")
                continue
            try:
                val = int(parts[1])
                if val < 1:
                    print("Length must be at least 1.")
                else:
                    config["length"] = val
                    print(f"Password length set to {val}.")
            except ValueError:
                print(f"Invalid number: {parts[1]}")

        # ── uppercase / lowercase / digits / symbols ──
        elif cmd in ("uppercase", "lowercase", "digits", "symbols"):
            if len(parts) < 2 or parts[1].lower() not in ("on", "off"):
                print(f"Usage: {cmd} on|off")
                continue
            state = parts[1].lower() == "on"
            config[cmd] = state
            status = "ON" if state else "OFF"
            print(f"{cmd.capitalize()}: {status}")

        # ── ambiguous ──
        elif cmd == "ambiguous":
            if len(parts) < 2 or parts[1].lower() not in ("on", "off"):
                print("Usage: ambiguous on|off")
                continue
            state = parts[1].lower() == "on"
            config["exclude_ambiguous"] = state
            status = "ON" if state else "OFF"
            print(f"Exclude ambiguous characters: {status}")

        # ── sep ──
        elif cmd == "sep":
            if len(parts) < 2:
                print("Usage: sep <character>")
                continue
            config["passphrase_separator"] = parts[1]
            print(f"Passphrase separator set to '{parts[1]}'.")

        # ── generate ──
        elif cmd == "generate":
            count = 1
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                    if count < 1:
                        print("Count must be at least 1.")
                        continue
                except ValueError:
                    print(f"Invalid count: {parts[1]}")
                    continue

            # Check that at least one charset is enabled
            charset = build_charset(config)
            if not charset:
                print("ERROR: All character sets are disabled. Enable at least one.")
                continue

            print()
            for i in range(count):
                try:
                    pwd = generate_password(config)
                    strength = rate_strength(pwd)
                    print(f"  [{strength:>11}]  {pwd}")
                except ValueError as e:
                    print(f"  ERROR: {e}")
                    break
            print()

        # ── passphrase ──
        elif cmd == "passphrase":
            count = 1
            words_per = 4
            if len(parts) >= 2:
                try:
                    words_per = int(parts[1])
                    if words_per < 1:
                        print("Word count must be at least 1.")
                        continue
                except ValueError:
                    print(f"Invalid word count: {parts[1]}")
                    continue
            if len(parts) >= 3:
                try:
                    count = int(parts[2])
                    if count < 1:
                        print("Count must be at least 1.")
                        continue
                except ValueError:
                    print(f"Invalid count: {parts[2]}")
                    continue

            print()
            for i in range(count):
                pp = generate_passphrase(config, words_per)
                strength = rate_strength(pp)
                print(f"  [{strength:>11}]  {pp}")
            print()

        # ── unknown ──
        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")


if __name__ == "__main__":
    repl()
