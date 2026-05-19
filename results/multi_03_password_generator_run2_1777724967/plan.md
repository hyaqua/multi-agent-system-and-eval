```markdown
# Implementation Plan for Password Generator (CLI)

## Architecture
- **Single Python file**: `password_generator.py`
- **No external dependencies** – uses only `string`, `random`, `sys` from the standard library.
- **Global configuration dict** holds all current settings (length, sets, ambiguous exclusion).
- **REPL loop** in `main()` reads, parses, and dispatches commands.
- **Generator functions** create passwords/passphrases using the current pool of characters/words.
- **Strength rating** computed from entropy (bits) based on length and effective pool size, mapped to four tiers.

## Files and Purposes
- `password_generator.py` – all code: REPL, configuration management, generation, rating, and passphrase feature (optional bonus).

## Configuration State (global dict)
```python
config = {
    "length": 16,
    "uppercase": True,
    "lowercase": True,
    "digits": True,
    "symbols": True,
    "exclude_ambiguous": False
}
```
Character pools (pre‑processed when `exclude_ambiguous` changes):
- `uppercase_chars = string.ascii_uppercase`
- `lowercase_chars = string.ascii_lowercase`
- `digit_chars = string.digits`
- `symbol_chars = string.punctuation`
- Ambiguous removal set: `{'0','O','1','l','I'}`

Whenever config changes (toggle or length), rebuild the current pool:  
`pool = (uppercase_chars if config['uppercase'] else '') + (lowercase_chars if config['lowercase'] else '') + ...`  
Then apply `exclude_ambiguous` filtering.

## Command Syntax and Handling
| Command              | Action |
|----------------------|--------|
| `config`             | Print all current settings. |
| `length <int>`       | Set password length (must be ≥ 1). |
| `uppercase [on/off]` | Toggle (if no arg) or set explicitly. Same for `lowercase`, `digits`, `symbols`. |
| `ambiguous [on/off]` | Toggle ambiguous character exclusion. |
| `generate [N]`       | Generate N passwords (default 1). Show each password and its strength rating. |
| `passphrase [words] [sep]` | (Optional) Generate passphrase with `words` words (default 4) separated by `sep` (default `-`). Uses embedded word list. |
| `quit` / `exit`      | Exit the program. |

All unrecognised commands or invalid arguments print a help/error message.

## Feature‑by‑Feature Implementation Details

### 1. REPL Loop with Command Dispatch
- `main()` runs an infinite `while True:` loop.
- Read input with `input("> ")`, strip, split into parts (`cmd = parts[0]`, `args = parts[1:]`).
- Dispatch using if‑elif chain calling dedicated handler functions.
- Catch `EOFError`/`KeyboardInterrupt` to exit gracefully.

### 2. `config` Command
- Print all keys from `config` in a readable format.
- Show current pool size and effective entropy if no sets are enabled (or indicate all sets disabled).

### 3. `length <N>` Command
- Validate N is a positive integer.
- Update `config["length"]`. If N < 1, show error and keep previous.

### 4. Toggle Character Sets (`uppercase`, `lowercase`, `digits`, `symbols`)
- If no argument: flip the boolean value.
- If argument is `on`/`off`/`true`/`false` (case‑insensitive): set accordingly.
- Print new state and “all sets disabled” warning if appropriate.
- After each toggle, update the pool function (see character pool building).

### 5. `ambiguous [on/off]` Command
- Toggle `config["exclude_ambiguous"]`. Print new state.
- Rebuild pool after toggling.

### 6. `generate [N]` Command
- Default N = 1.
- Check that at least one character set is enabled; if not, print error and return.
- Build pool from currently enabled sets, filtering ambiguous chars if `exclude_ambiguous` is `True`.
- For each password:
  - Use `secrets.choice(pool)` or `random.SystemRandom().choice` for cryptographically strong randomness (prefer `secrets` module if Python 3.6+, else `random.SystemRandom`).
  - Build string of length `config["length"]` by repeatedly choosing from the pool.
  - Calculate entropy: `entropy = length * log2(len(pool))`.
  - Map entropy to rating:  
    - 0‑39 bits → “Weak”  
    - 40‑59 bits → “Medium”  
    - 60‑79 bits → “Strong”  
    - 80+ bits → “Very Strong”
  - Print password and rating.

### 7. Strength Rating Implementation
- Reusable function `rating(entropy: float) -> str`.
- Use thresholds as above.
- Display rating in clear text, e.g. `"Password: kj3A1…  | Strength: Strong (72 bits)"`.

### 8. Passphrase Generation (Optional Enhancement)
- Embed a list of ~100–200 common English words (e.g., from EFF diceware list, stored as a constant tuple).
- Command `passphrase [num_words] [separator]`:
  - Default `num_words = 4`, `separator = "-"`.
  - Validate `num_words` ≥ 1.
  - Use cryptographically strong random choice to select `num_words` words.
  - Join with separator.
  - Calculate entropy as `num_words * log2(len(wordlist))`.
  - Display passphrase and strength rating (same function).
  - Respect ambiguous exclusion? Not applicable for words; unconditional.

### 9. Graceful Exit
- Commands `quit`, `exit`, or `q` break the REPL loop and print a goodbye message.

### 10. Error Handling & Edge Cases
- Invalid `length` value (non‑integer, ≤0) → error message.
- Generate with all sets disabled → error `Error: All character sets are disabled. Enable at least one.`
- Unknown commands → print brief help.

## Implementation Order (Build Sequence)
1. **Main REPL skeleton** – loop, quit, basic dispatch.
2. **Configuration dict and `config` command** – display current state.
3. **Length command** – parse and store.
4. **Character set toggles** – each command, with `on/off/toggle` logic.
5. **Pool building** – function to assemble characters based on active sets and ambiguous flag.
6. **Ambiguous toggle** – filter logic.
7. **`generate` command** – password creation, entropy, strength printing.
8. **Multiple passwords** – loop over N.
9. **Refuse generation if no sets enabled** – add guard.
10. **Passphrase command (optional)** – embed word list and generate (if time permits).
11. **Final testing** – all commands, edge cases, help messages.

## Notes for Implementation
- Use `secrets` if available (Python 3.6+). Fallback to `random.SystemRandom` for older versions.
- Print entropy without decimals for clarity, e.g., `"62 bits"`.
- Keep user messages short and consistent.
- No external libraries or files needed – the word list for passphrases is embedded as a Python tuple.

```