STATUS: COMPLETE

## Features Implemented

1. **REPL loop accepting commands** - Full interactive REPL with `>` prompt, handles EOF/KeyboardInterrupt gracefully. Also supports piped input for scripting.

2. **Random password generation with configurable length** - Default length 16, configurable via `length <N>` command (range 1-256).

3. **Toggle character sets on/off** - `uppercase`, `lowercase`, `digits`, `symbols` commands each toggle when used alone or accept `on`/`off` argument.

4. **Generates passwords using only enabled character sets** - Character set is built dynamically from enabled sets only.

5. **Strength rating** - Each generated password is rated: weak (< 40 bits entropy), medium (40-60), strong (60-80), very strong (> 80). Also adjusted for character class diversity.

6. **Generate multiple passwords** - `generate N` command generates N passwords (1-100).

7. **Config display** - `config` command shows all settings, active charset size, and estimated entropy.

8. **All-disabled error** - Generates clear error message when all character sets are off.

9. **Ambiguous character exclusion** - `ambiguous on/off` toggles exclusion of `0`, `O`, `1`, `l`, `I`.

10. **Quit/exit** - Both `quit` and `exit` stop the program cleanly.

11. **Passphrase generation** - `passphrase [N] [-sep X] [-capitalize] [-number]` generates memorable passphrases from a built-in word list, with configurable word count, separator, capitalization, and numeric suffix. Strength is also rated.

12. **Help system** - `help` or `?` shows all available commands.

## Testing Summary

- All commands tested via piped input
- Edge cases: negative length, zero length, excessive length, zero count, excessive count, unknown commands
- Ambiguous character exclusion verified (no 0/O/1/l/I in generated passwords when enabled)
- All-disabled error message confirmed
- Passphrase generation with various options verified
- Both `quit` and `exit` work correctly
