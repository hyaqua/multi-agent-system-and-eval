# Implementation Plan: Command-Line Password Generator

## 1. Files to Create

- **`main.py`** – Entry point; starts the REPL loop.
- **`config.py`** – Holds configuration state (length, active sets, mode, etc.).
- **`password_engine.py`** – Logic for password/passphrase generation and strength rating.
- **`repl.py`** – REPL loop with command parsing, configuration toggling, and generation output.
- **`words.py`** – Contains a Python list of ~2000 common English words for passphrase generation.

All files reside in the same package. Only the standard library is used (no external dependencies).

## 2. Architecture

```
main.py
  └── repl.start()
        ├── config.Config (shared state)
        ├── password_engine (generate, assess_strength)
        └── words.WORD_LIST (only if passphrase mode)
```

- **`config.Config`** is a simple class/data structure storing:
  - `length` (int, default 16)
  - `uppercase`, `lowercase`, `digits`, `symbols` (bool flags)
  - `exclude_ambiguous` (bool)
  - `mode` (`'password'` or `'passphrase'`)
  - `wordcount` (int, default 4)
- **`repl`** reads commands, updates `Config`, and calls engine functions.
- **`password_engine`** builds character pools, uses `secrets.choice()`, and computes strength.

## 3. Implementation Order

1. **`words.py`** – Prepare the word list (hardcoded list of common, lower-case words without punctuation).
2. **`config.py`** – Define the `Config` class with default values.
3. **`password_engine.py`** – Implement:
   - `generate_password(config)` – builds charset, picks random chars.
   - `generate_passphrase(config)` – picks random words, joins with `-`.
   - `assess_strength(password, config)` – returns one of `weak`, `medium`, `strong`, `very strong`.
   - `generate_multiple(config, count)` – returns list of passwords/passphrases.
4. **`repl.py`** – Build the REPL: command parser, configuration toggles, generate with rating display, `config` display.
5. **`main.py`** – Simply call `repl.start()`.

## 4. Libraries

- **`secrets`** – For cryptographically secure randomness.
- **`sys`**, **`os`** – Not strictly needed; only standard input/output.
- **`re`** could be used for simple command matching, but string methods suffice.

## 5. Feature Implementation Details

### REPL loop (`repl.py`)
- Prompt `> ` waits for input.
- Commands parsed case-insensitively.
- Supported commands:
  - `length <num>` – Sets password length (must be >0).
  - `words <num>` – Sets passphrase word count (used only in passphrase mode).
  - `uppercase on|off`, `lowercase on|off`, `digits on|off`, `symbols on|off` – Toggles corresponding flags.
  - `ambiguous on|off` – Toggles exclusion of `0 O 1 l I`.
  - `mode password|passphrase` – Switches generation mode.
  - `generate [N]` – Produces N passwords/passphrases, prints each with strength.
  - `config` – Prints all current settings.
  - `quit` / `exit` – Exits loop.
- Invalid input prints a brief help message.

### Password generation (`password_engine.py`)
- Build character pool by concatenating active sets:
  - uppercase: `ABCDEFGHIJKLMNOPQRSTUVWXYZ`
  - lowercase: `abcdefghijklmnopqrstuvwxyz`
  - digits: `0123456789`
  - symbols: `!@#$%^&*()_+-=[]{}|;:',.<>?/`~`` (standard set)
- If `exclude_ambiguous`, remove `0`, `O`, `1`, `l`, `I` from the pool (before concatenation).
- If pool is empty, raise a `ValueError` with message "All character sets are disabled. Enable at least one set."
- Use `secrets.choice(pool)` for each character until length reached.

### Passphrase generation
- If `mode == 'passphrase'`, generate by randomly sampling `config.wordcount` words from `words.WORD_LIST` using `secrets.choice` (or `random.sample` for uniqueness – but `secrets.choice` repeated is fine; "sample" would guarantee uniqueness, but spec does not require). Use `secrets.choice` repeatedly; fine.
- Join words with `-` (e.g., `"correct-horse-battery-staple"`).
- Strength rating for passphrase based on word count:
  - `<3` words → `weak`
  - `3-4` → `medium`
  - `5` → `strong`
  - `>=6` → `very strong`
  (Alternatively, compute entropy `log2(len(WORD_LIST)**wordcount)` but simple rule suffices.)

### Strength rating for passwords
- Score based on:
  - Length categories: `<8` weak regardless of charset; `8-11` medium baseline; `12-15` strong; `>=16` very strong.
  - Upgrade if multiple character types used. A simple mapping:
    - `weak`: length < 8 or single charset used.
    - `medium`: length 8-11 and at least two char types.
    - `strong`: length 12-15 and at least three char types OR length >=16 with at least two.
    - `very strong`: length >=16 and all four types present.
  - Adjustments if only one charset: always weak.

### Multiple passwords (`generate N`)
- If `N` is not given, default to 1.
- Loop N times, call appropriate generation function, display each with strength label:
  - Example: `1. P@ssw0rd (weak)`

### Configuration display (`config` command)
- Show:
  - `Mode: password / passphrase`
  - `Length: 16` (if password) or `Word count: 4` (if passphrase)
  - `Uppercase: on/off`
  - `Lowercase: on/off`
  - `Digits: on/off`
  - `Symbols: on/off`
  - `Exclude ambiguous: on/off`

### Error handling
- All disallowed state: when generating and no charset active, print the error message and do not generate.
- Invalid numeric input: print “Invalid value, must be a positive integer.”
- Unknown command: print “Unknown command. Type 'config' to see settings, or 'generate' to get a password.”

### Exit
- Typing `quit` or `exit` breaks the loop and terminates the program.

This plan yields a single‑run script with clear separation of concerns, easily testable and extendable.