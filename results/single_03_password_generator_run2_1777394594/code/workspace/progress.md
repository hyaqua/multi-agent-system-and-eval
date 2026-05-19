STATUS: COMPLETE

## Password Generator - Progress Report

### Features Implemented and Verified

All required features have been implemented and tested:

1. **REPL loop accepting commands** — Works. The program presents a `passgen>` prompt and processes commands interactively.

2. **Random password generation with configurable length (default 16)** — Works. `generate` produces a 16-character password by default. All characters are selected using `secrets.choice()` for cryptographic-quality randomness.

3. **'length' command** — Works. `length 8` sets the password length, validated to be >= 1.

4. **Toggle character sets on/off** — Works. `uppercase on|off`, `lowercase on|off`, `digits on|off`, `symbols on|off` all toggle individual character classes.

5. **Generates passwords using only enabled character sets** — Works. When only digits are enabled, only digit characters appear in output.

6. **Strength rating for each password** — Works. Ratings are `weak`, `medium`, `strong`, `very strong` based on length and character class diversity. Displayed next to each generated password.

7. **Generate multiple passwords** — Works. `generate N` produces N passwords in one command.

8. **'config' command shows current configuration** — Works. Displays all settings including length, toggles, ambiguous filter, separator, and the active character set.

9. **Refuses generation when all sets are disabled** — Works. Prints "ERROR: All character sets are disabled. Enable at least one." when every character class is off.

10. **Exclude ambiguous characters toggle** — Works. `ambiguous on` excludes `0`, `O`, `1`, `l`, `I` from the character pool. Verified that with only digits + ambiguous on, the charset reduces to `23456789`.

11. **'quit' / 'exit' commands** — Works. Both terminate the program cleanly with a goodbye message.

### Bonus Features

- **Passphrase generation** — `passphrase [N] [count]` generates passphrases of N random words (default 4), optionally multiple. Uses system word list (`/usr/share/dict/words`) if available, otherwise falls back to an embedded list of ~200 common words.
- **Passphrase separator** — `sep <char>` sets the word separator for passphrases (default `-`).
- **'help' command** — Displays all available commands.

### Testing

- Unit tests for core functions (`build_charset`, `rate_strength`, `generate_password`, `generate_passphrase`) all pass.
- REPL integration tests with piped input verify all command flows work correctly.
- Edge cases tested: all charsets disabled, ambiguous filtering with single charset, minimum length, large generation counts.

### Files

- `password_generator.py` — Complete, self-contained application. No external dependencies (standard library only).
