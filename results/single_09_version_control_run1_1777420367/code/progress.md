STATUS: COMPLETE

## VCS - Simplified Git-like Version Control System

All 14 required features are implemented and tested.

### Implemented Features

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | `init` command | ✅ Working | Creates `.vcs/` with `objects/`, `refs/heads/`, `HEAD`, and `index` |
| 2 | `status` command | ✅ Working | Shows new, modified, deleted files; staged vs unstaged; branch/detached HEAD info |
| 3 | `add` command | ✅ Working | Stages files by content hash; supports staging deletions for removed tracked files |
| 4 | `commit` command | ✅ Working | Creates snapshot from staged changes + parent tree; requires `-m` message |
| 5 | Commit metadata | ✅ Working | Each commit stores: file contents (via tree→blob), ISO timestamp, message, unique SHA-1 hash, author |
| 6 | `log` command | ✅ Working | Shows full hash, author, date, message for all commits; supports `-n` limit |
| 7 | `diff` command | ✅ Working | Unified diff format; compares working directory against HEAD commit |
| 8 | `checkout` command | ✅ Working | Restores all files to a specific commit by full or abbreviated hash; updates HEAD (detached) |
| 9 | `branch` command | ✅ Working | Creates named branch at current commit; lists branches with `*` for active; `-d` for delete |
| 10 | `switch` command | ✅ Working | Switches working directory to target branch; updates HEAD reference |
| 11 | Independent branches | ✅ Working | Commits on different branches are tracked independently; switching restores correct files |
| 12 | Content-addressable hashing | ✅ Working | SHA-1 based blob storage (Git-style: `hash("blob <size>\\0<content>")`); identical files share one blob |
| 13 | Binary file handling | ✅ Working | Detects binary via null bytes / invalid UTF-8; shows "Binary files differ" instead of line diff |
| 14 | Outside-repo error | ✅ Working | "error: not a VCS repository (or any parent directory)" with hint to run `vcs init` |

### Project Structure

```
vcs/
  __init__.py      # Package marker
  __main__.py      # Entry point for `python -m vcs`
  repo.py          # Core Repository class (all VCS logic)
  cli.py           # Argument parsing and command dispatch
vcs_entry.py       # Convenience entry script
```

### Storage Model

- **Objects**: Content-addressable in `.vcs/objects/XX/YYYY...` (SHA-1, 40-char hex)
- **Blob**: Raw file content, hashed as `"blob <len>\\0<content>"`
- **Tree**: JSON `{filepath: blob_hash}`, hashed as `"tree <len>\\0<json>"`
- **Commit**: JSON `{tree, parent, message, timestamp, author}`, hashed as `"commit <len>\\0<json>"`
- **Index**: `.vcs/index` — JSON `{filepath: blob_hash}` (null = staged deletion)
- **HEAD**: `.vcs/HEAD` — either `ref: refs/heads/<branch>` or a commit hash (detached)
- **Branches**: `.vcs/refs/heads/<name>` — contains commit hash

### Test Scenarios Verified

- Initialize repo, add files, commit, view log
- Modify files and view diffs (including empty files)
- Checkout by abbreviated hash (restores old file versions)
- Binary file detection and diff suppression
- Branch creation, switching, independent commit histories
- Branch deletion
- Detached HEAD commits
- Content-addressable deduplication (same content = same blob hash)
- Stage-then-modify shows file in both staged and unstaged sections
- Stage deletion of tracked files
- Error message when running commands outside a repository
- Author from VCS_AUTHOR environment variable
