"""Password/passphrase generation and strength assessment."""

import secrets
from config import Config
from words import WORD_LIST

_UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"
_SYMBOLS = r"!@#$%^&*()_+-=[]{}|;:',.<>?/`~"

_AMBIGUOUS = set("0O1lI")


def _build_pool(config: Config) -> str:
    """Build the character pool based on current config."""
    parts: list[str] = []
    if config.uppercase:
        parts.append(_UPPERCASE)
    if config.lowercase:
        parts.append(_LOWERCASE)
    if config.digits:
        parts.append(_DIGITS)
    if config.symbols:
        parts.append(_SYMBOLS)

    pool = "".join(parts)

    if config.exclude_ambiguous:
        pool = "".join(ch for ch in pool if ch not in _AMBIGUOUS)

    return pool


def _active_set_count(config: Config) -> int:
    """Return the number of active character sets."""
    return sum([config.uppercase, config.lowercase, config.digits, config.symbols])


def generate_password(config: Config) -> str:
    """Generate a random password from the active character sets."""
    pool = _build_pool(config)
    if not pool:
        raise ValueError(
            "All character sets are disabled. Enable at least one set."
        )
    return "".join(secrets.choice(pool) for _ in range(config.length))


def generate_passphrase(config: Config) -> str:
    """Generate a random passphrase from the word list."""
    words = [secrets.choice(WORD_LIST) for _ in range(config.wordcount)]
    return "-".join(words)


def generate(config: Config) -> str:
    """Generate a password or passphrase based on the config mode."""
    if config.mode == "passphrase":
        return generate_passphrase(config)
    else:
        return generate_password(config)


def assess_strength_password(password: str, config: Config) -> str:
    """Assess strength of a generated password."""
    length = len(password)
    sets_used = _active_set_count(config)

    # Determine which characters are actually present
    present_upper = any(c in _UPPERCASE for c in password) and config.uppercase
    present_lower = any(c in _LOWERCASE for c in password) and config.lowercase
    present_digit = any(c in _DIGITS for c in password) and config.digits
    present_symbol = any(c in _SYMBOLS for c in password) and config.symbols
    actual_sets = sum([present_upper, present_lower, present_digit, present_symbol])

    if length < 8 or actual_sets <= 1:
        return "weak"
    if length >= 16 and actual_sets >= 4:
        return "very strong"
    if length >= 12 and actual_sets >= 3:
        return "strong"
    if length >= 16 and actual_sets >= 2:
        return "strong"
    if length >= 8 and actual_sets >= 2:
        return "medium"

    return "weak"


def assess_strength_passphrase(passphrase: str, config: Config) -> str:
    """Assess strength of a passphrase based on word count."""
    wc = config.wordcount
    if wc < 3:
        return "weak"
    elif wc <= 4:
        return "medium"
    elif wc == 5:
        return "strong"
    else:
        return "very strong"


def assess_strength(generated: str, config: Config) -> str:
    """Assess the strength of a generated password or passphrase."""
    if config.mode == "passphrase":
        return assess_strength_passphrase(generated, config)
    else:
        return assess_strength_password(generated, config)


def generate_multiple(config: Config, count: int) -> list[str]:
    """Generate multiple passwords/passphrases."""
    results: list[str] = []
    for _ in range(count):
        results.append(generate(config))
    return results
