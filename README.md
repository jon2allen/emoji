# Portable Global Git Hook: Emoji Detector & Cleaner

A portable, cross-platform global Git pre-commit hook that automatically catches and cleans emoji (and emoji-like pictographs, symbols, flags, and their invisible joiners/selectors) in staged files upon `git commit`. Detected emoji are removed by default, or replaced with curated ASCII equivalents such as `[ok]` and `<3` with `--mode replace`.

Compatible across **macOS**, **Linux** (bash/sh), and **FreeBSD** (sh/csh/tcsh).

---

## What It Does
When installed, running `git commit` in **any** Git repository on your machine will:
1. Identify all currently staged files (excluding deletions).
2. Scan them with `detect_emoji.py`.
3. If any emoji are staged, automatically remove them, dropping any space the removal strands in front of punctuation. Orphaned invisible components (variation selectors, zero-width joiners) are always deleted.
4. Re-stage the cleaned files before completing the commit.

The commit is **rejected** rather than auto-fixed when fixing could disturb your work: the file has unstaged edits, you ran `git commit <path>`, or the file cannot be written. Files with no staged emoji are never touched.

The hook also runs the repository's own `.git/hooks/pre-commit` first, then any sibling hook sharing the global hooks directory (for example the em-dash cleaner preserved as `pre-commit-emdash`). Hooks in other locations and other hook types are not chained, and commit messages are not scanned.

### Multi-codepoint emoji are handled as one unit
Zero-width-joiner sequences (family groups, profession emoji), flags (regional indicator pairs), skin tone modifiers, and keycap sequences are processed as a single cluster, so no half-emoji or orphaned joiners are left behind. A keycap like `1` plus the keycap component reduces to the digit itself.

### Paths that must keep emoji
Auto-fix changes string literals as well as prose. Exempt paths in a repository's `.gitattributes`:

```
tests/fixtures/** -emoji
locale/**
```

---

## Directory Contents
- **`detect_emoji.py`**: Standalone Python 3 scanner and cleaner (supports `-r`, `--fix`, `--mode strip|space|map`, `--format`, `--dry-run`, `--backup`, `--json`, `--exit-code`, and `-q`; requires Python 3.7+).
- **`pre-commit`**: POSIX `/bin/sh` hook script placed in `~/.git_hooks/`.
- **`setup.sh`**: Setup installer for macOS and Linux (`sh`/`bash`/`zsh`).
- **`setup.csh`**: Setup installer for FreeBSD and `csh`/`tcsh` shells.
- **`test_emoji.py`**, **`test_hook.py`**: Test suite (`python3 -m pytest`).

---

## Quick Installation

### On macOS / Linux (bash / zsh / sh):
```bash
cd emoji_detect
chmod +x setup.sh
./setup.sh
```

### On FreeBSD (csh / tcsh):
```csh
cd emoji_detect
chmod +x setup.csh
./setup.csh
```

Both installers prompt by default and accept `--noprompt` / `-y` / `--all`, `--hook-only`, or `--bin-only`. Without a terminal, one of these flags is required.

If a different global pre-commit hook already occupies `~/.git_hooks/pre-commit` (for example the em-dash cleaner), it is preserved as `pre-commit-emdash` (or `pre-commit-legacy`) and chained automatically, so both hooks keep running.

---

## Cleaning Modes
- **strip** (default): delete each emoji cluster outright. A deletion flanked by spaces collapses the doubled space it would leave behind.
- **space**: substitute a single blank for each cluster; an adjacent space is absorbed so no doubled spaces appear.
- **map**: substitute a curated ASCII equivalent where one exists, then strip the rest:

| Emoji cluster | ASCII |
|---------------|-------|
| heavy check mark, white heavy check mark | `[ok]` |
| cross mark | `[no]` |
| warning sign | `[warning]` |
| hearts | `<3` |
| stars | `*` |
| thumbs up / thumbs down | `+1` / `-1` |
| smiling / frowning faces | `:)` / `:(` |
| black rightwards arrow | `->` |

The map lives at the top of `detect_emoji.py` and is easy to extend.

### Exit Codes
`--exit-code` is for CI and scripting:

- `0`: no emoji found, or every detected cluster was successfully cleaned (`--fix`)
- `1`: emoji remain uncleaned (detected without `--fix`, or with `--dry-run`), or a file could not be read or written

Note the difference from the em-dash cleaner, which still reports exit code 1 after a successful fix.

### Format cleanup: `--format`
Removing an emoji can leave the text irregular: a space that used to sit between a word and an emoji ends up stranded in front of the following punctuation. `--format` fixes what the cleanup itself caused:

```
radiator [fire emoji],   --fix                ->  radiator ,
radiator [fire emoji],   --fix --format       ->  radiator,
```

It only touches deletions the cleaner just made, in every mode, and never rewrites punctuation that was already adjacent in the original. The global hook always cleans with `--format` so committed text stays tidy.

---

## Scanning Piped Input
With no file arguments, piped or redirected input is scanned automatically. Use `-` to request stdin explicitly, which is the safer choice in scripts:

```bash
git log | detect_emoji.py
git log | detect_emoji.py --exit-code -q
detect_emoji.py --fix - < notes.txt > clean.txt
```

With `--fix`, the cleaned text goes to stdout and reports go to stderr.

---

## How It Works Under the Hood
1. Copies `detect_emoji.py` and `pre-commit` into `~/.git_hooks/`.
2. Runs `git config --global core.hooksPath ~/.git_hooks`, saving any previous value as `core.hooksPathBackup`.
3. Applies universally to all current and future Git repositories on the system without needing per-repository configuration.

---

## How to Uninstall / Disable
If you ever want to remove or disable the global hook:

```bash
# Disable global hooks in Git:
git config --global --unset core.hooksPath

# If setup saved a previous value, restore it:
git config --global core.hooksPath "$(git config --global core.hooksPathBackup)"
git config --global --unset core.hooksPathBackup

# Optional: Remove the ~/.git_hooks folder:
rm -rf ~/.git_hooks
```

To temporarily bypass the hook on a single commit:
```bash
git commit --no-verify
```
