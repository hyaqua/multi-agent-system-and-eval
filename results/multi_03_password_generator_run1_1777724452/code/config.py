"""Configuration state for the password generator."""


class Config:
    """Holds all configuration for password/passphrase generation."""

    def __init__(self):
        self.mode: str = "password"  # 'password' or 'passphrase'
        self.length: int = 16        # password character length
        self.wordcount: int = 4      # passphrase word count

        # Character set toggles
        self.uppercase: bool = True
        self.lowercase: bool = True
        self.digits: bool = True
        self.symbols: bool = True

        self.exclude_ambiguous: bool = False
