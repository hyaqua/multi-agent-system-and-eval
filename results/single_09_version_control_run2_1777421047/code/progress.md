STATUS: COMPLETE

## Feature Verification

| # | Feature | Status |
|---|---------|--------|
| 1 | `init` – initializes repository with `.vcs/` directory structure | ✅ Working |
| 2 | `status` – shows new, modified, deleted files vs last commit | ✅ Working |
| 3 | `add` – stages specific files for next commit | ✅ Working |
| 4 | `commit` – creates snapshot of staged files with required `-m` message | ✅ Working |
| 5 | Each commit stores file contents, timestamp, message, unique SHA-1 hash | ✅ Working |
| 6 | `log` – displays commit history (hash, message, timestamp, author) | ✅ Working |
| 7 | `diff` – line-by-line unified diff between working directory and last commit | ✅ Working |
| 8 | `checkout <hash>` – restores all files to state of specific commit (partial hashes supported) | ✅ Working |
| 9 | `branch <name>` – creates named branch from current commit; no-arg lists branches | ✅ Working |
| 10 | `switch <name>` – switches between branches, restoring/removing files | ✅ Working |
| 11 | Commits on different branches tracked independently | ✅ Working |
| 12 | Content-addressable hashing – identical files share blob storage | ✅ Working |
| 13 | Binary file detection – diff displays "Binary file … differs" instead of line diff | ✅ Working |
| 14 | Helpful error message when commands run outside initialized repository | ✅ Working |

## Implementation Notes

- **Architecture**: Two files – `vcs.py` (CLI with argparse) and `repo.py` (core Repository class)
- **Storage**: `.vcs/objects/` for content-addressed blobs (SHA-1, two-level directory), `.vcs/commits/` for JSON commit objects, `.vcs/refs/heads/` for branch pointers, `.vcs/HEAD` for current branch reference, `.vcs/index` for staging area
- **Commit model**: Each commit stores a full tree (path→blob_hash map), built by merging the parent's tree with the staging index. This ensures files from previous commits persist unless explicitly removed.
- **Branch switching**: Deletes tracked files not present in the target branch and restores files from the target commit.
- **Detached HEAD**: Checkout sets HEAD directly to a commit hash; subsequent commits would not update any branch.
