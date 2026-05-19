STATUS: COMPLETE

## Features Implemented

### 1. REPL Loop
- Runs in an interactive loop accepting commands with a `passgen>` prompt.
- Handles Ctrl+D (EOF) and Ctrl+C (KeyboardInterrupt) gracefully.
- Also supports non-interactive mode via CLI arguments: `python password_generator.py generate [N]` or `python password_generator.py config`.

### 2. Random Password Generation
- Uses `secrets.choice()` for cryptographically secure random passwords.
- Default length is 16 characters.
- All character sets (uppercase, lowercase, digits, symbols) enabled by default.

### 3. Configurable Length
- `length <N>` command sets password length.
- Validates input: must be a positive integer, max 256.
- Error messages for invalid values (non-numeric, out of range).

### 4. Character Set Toggles
- `uppercase` - toggle A-Z on/off
- `lowercase` - toggle a-z on/off
- `digits` - toggle 0-9 on/off
- `symbols` - toggle special characters on/off
- Each toggle reports its new state (ON/OFF).

### 5. Character-Set-Aware Generation
- Passwords are generated using only currently enabled character sets.
- If all sets are disabled, generates a clear error message.

### 6. Strength Rating
- Each generated password is rated: weak, medium, strong, very strong.
- Rating algorithm considers both password length and character type diversity.
- Displayed inline for single passwords; shown in brackets for batch generation.

### 7. Multiple Password Generation
- `generate N` generates N passwords at once (max 100).
- `generate` (no argument) generates a single password.
- Batch output shows numbered list with individual strength ratings.

### 8. Configuration Display
- `config` command displays all current settings in a formatted table.
- Shows length, state of each character set, and ambiguous exclusion toggle.

### 9. All-Sets-Disabled Protection
- If user disables all four character sets, attempting to generate produces:
  `Error: All character sets are disabled. Enable at least one.`

### 10. Ambiguous Character Exclusion
- `ambiguous` command toggles exclusion of (0, O, 1, l, I).
- When enabled, these characters are removed from the character pool.
- Verified via unit-style test that these 5 chars are excluded/included correctly.

### 11. Quit/Exit
- `quit` and `exit` both terminate the program with a goodbye message.

## Testing Summary
- All commands tested via piped input and direct execution.
- Edge cases tested: invalid numbers, out-of-range values, all sets disabled.
- Strength rating verified across all four levels.
- Ambiguous exclusion verified by inspecting the character pool.
- Non-interactive CLI mode tested and working.
