# Implementation Plan: Password Generator

## 1. Files to Create

| File | Purpose |
|------|---------|
| `password_generator.py` | Single self-contained Python script implementing the entire tool. Breaks down into logical sections: configuration, generation, strength rating, REPL. |

Using one file keeps it simple; internal structure is modular via functions and a config dataclass.

## 2. Architecture Overview

- **Configuration (`PasswordConfig`):** A simple class (or `@dataclass`) holding:
  - `length`: int (default 16)
  - `use_uppercase`, `use_lowercase`, `use_digits`, `use_symbols`: bool (all True initially)
  - `exclude_ambiguous`: bool (default False)
  - `word_count`: int (default 4)
  - `delimiter`: str (e.g., `"-"`)
- **Character Set Builder:** Function that returns the current set of allowed characters based on config, filtering out ambiguous characters if `exclude_ambiguous` is on.
- **Password Generator:** `generate_password(config) -> str` uses `secrets.choice()` over the allowed character set.
- **Passphrase Generator:** `generate_passphrase(config, wordlist) -> str` picks `word_count` words from a hard‑coded wordlist (e.g., EFF short list, ~1296 words) using `secrets.choice`, joined by `delimiter`.
- **Strength Rater:** `rate_password(...)` and `rate_passphrase(...)` calculate entropy in bits and map it to a label (`weak`, `medium`, `strong`, `very strong`).
- **REPL Loop:** Parses commands, modifies config, calls generators, prints results. Supported commands:
  - `length <num>`
  - `uppercase on|off|toggle` (same for `lowercase`, `digits`, `symbols`)
  - `ambiguous on|off|toggle`
  - `generate [N]` – generate N passwords (default 1)
  - `passphrase [N] [words]` – generate N passphrases (default 1, word count from config)
  - `config`
  - `help`
  - `quit` / `exit`

Interaction: REPL → Config → Generator → Rater → Print.

## 3. Implementation Order

1. **Define constants** – character sets (uppercase, lowercase, digits, symbols), ambiguous mapping, wordlist (embed a list of 1296 common Diceware words as a global).
2. **Create `PasswordConfig` dataclass** with defaults.
3. **Implement `get_allowed_chars(config)`** – builds the allowed string based on config flags, optionally removing ambiguous characters.
4. **Implement `generate_password(config)`** – uses `secrets.choice`.
5. **Implement `generate_passphrase(config, wordlist)`** – uses `secrets.choice` for words.
6. **Implement strength rating** – compute entropy = `len(password) * math.log2(len(char_set))` for passwords, and `word_count * math.log2(len(wordlist))` for passphrases. Map to labels (e.g., <50 weak, ≥50 medium, ≥70 strong, ≥100 very strong).
7. **Implement REPL** – `while True:` loop, command parsing with `shlex.split()` or simple `split()`, calling appropriate functions, handling errors.
8. **Add safety checks** – avoid generating when allowed char set is empty, display meaningful errors.
9. **Add `generate N` and `passphrase N words`** logic with loops.
10. **Add `config` and `help` commands**.
11. **Test basic flows manually** (length change, char toggles, multiple generation, ambiguous exclusion, all-off error).

## 4. Libraries Required

- **Standard library only:**
  - `secrets` – cryptographically secure random choice
  - `string` – for predefined character sets (`ascii_lowercase`, etc.)
  - `math` – for `log2`
  - `dataclasses` (or plain class) – for configuration
  - `sys` / `shlex` (optional) – for input parsing

## 5. Feature Implementation Details

| Requirement | How It Will Be Implemented |
|-------------|----------------------------|
| REPL loop | `while True: cmd = input("> ")` – parses with `split()`, dispatches. |
| Default length 16 | Set in `PasswordConfig.length = 16`. |
| `length` command | Updates `config.length` after validating integer. |
| Toggle character sets | Commands `uppercase on/off/toggle` update booleans. Real-time effect: `generate` uses current flags. |
| Password generation | `generate_password` builds allowed characters via `get_allowed_chars(config)`, then uses `''.join(secrets.choice(allowed) for _ in range(length))`. |
| Strength rating for passwords | Entropy = `length * math.log2(len(allowed_chars))`. Label thresholds: ≤49 weak, 50–69 medium, 70–99 strong, ≥100 very strong. Printed after each generation. |
| `generate N` | Loop N times, call `generate_password`, print each with index and rating. |
| Refuse if all char sets off | Before generation, check `get_allowed_chars` returns empty string. Print error: “Cannot generate password: no character sets enabled.” |
| Exclude ambiguous characters | `ambiguous on/off/toggle` sets flag. In `get_allowed_chars`, if flag is true, remove characters `0 O 1 l I` from the final string using a filter. |
| Passphrase generation | Use `passphrase [N] [words]` command. Default word count from config (initially 4). `generate_passphrase` picks random words from a hard‑coded `WORDS` list, joins with `config.delimiter`. Strength rating uses entropy = `word_count * math.log2(len(WORDS))`. |
| `config` command | Prints current length, status of each character set, ambiguous flag, word count, delimiter. |
| `quit` / `exit` | Break out of the REPL loop, print goodbye. |

**Wordlist:** A hard‑coded Python list of the 1296 Diceware words (short list) will be included as a global constant. No external file is needed; this satisfies the standard‑library‑only requirement and gives a reasonable passphrase entropy of ~10.3 bits per word.

**Error handling:** Invalid commands and values produce a brief error message and return to prompt. The program never crashes.