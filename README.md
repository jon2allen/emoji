# Portable Global Git Hook: Emoji Detector & Cleaner

A portable, cross-platform global Git pre-commit hook that automatically catches and cleans emoji (and emoji-like pictographs, symbols, flags, and their invisible joiners/selectors) in staged files upon `git commit`. Detected emoji are removed by default, or replaced with curated ASCII equivalents such as `[ok]` and `<3` with `--mode replace`.

Compatible across **macOS**, **Linux** (bash/sh), and **FreeBSD** (sh/csh/tcsh).

---

## What It Does
When installed, running `git commit` in **any** Git repository on your machine will:
1. Identify all currently staged files (excluding deletions).
2. Scan their staged content in a single batched pass with `detect_emoji.py`.
3. If any emoji are staged, automatically remove them, dropping any space the removal strands in front of punctuation. Orphaned invisible components (variation selectors, zero-width joiners) are always deleted.
4. Re-stage the cleaned files before completing the commit.

The commit is **rejected** rather than auto-fixed when fixing could disturb your work: the file has unstaged edits, you ran `git commit <path>`, or the file cannot be written. Files with no staged emoji are never touched.

The hook also runs the repository's own `.git/hooks/pre-commit` first, then any sibling hook sharing the global hooks directory (for example the em-dash cleaner preserved as `pre-commit-emdash`). Hooks in other locations and other hook types are not chained, and commit messages are not scanned.

### Multi-codepoint emoji are handled as one unit
Zero-width-joiner sequences (family groups, profession emoji), flags (regional indicator pairs), skin tone modifiers, and keycap sequences are processed as a single cluster, so no half-emoji or orphaned joiners are left behind. A keycap like `1` plus the keycap component reduces to the digit itself.

### Paths that must keep emoji
Auto-fix changes string literals as well as prose. Exempt paths or entire projects in a repository's `.gitattributes`:

```gitattributes
# Exempt an entire project:
* -emoji

# Exempt specific directories or files:
tests/fixtures/** -emoji
locale/** -emoji
README.md -emoji
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

The hook hands the NUL-delimited list of staged paths to `detect_emoji.py --scan-staged`, which filters exempt paths (`git check-attr`) and reads every staged blob (`git cat-file --batch`) in one batched pass: a 50-file commit pays one Python startup instead of fifty. The staged path list is NUL-delimited end to end, so filenames containing newlines are detected; only the rare fixing loop falls back to newline splitting, and a path it cannot round-trip is rejected rather than silently committed. Requires Git 2.20+ for the batched object protocol.

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

---

## Bypassing or Exempting Emoji
If a project, file, or commit legitimately needs emoji, there are three ways to bypass the filter:

### 1. Project or Path Exemption via `.gitattributes` (Recommended)
Add `-emoji` to `.gitattributes` in the repository root. This is committed with the repo so all collaborators automatically share the exemption:

```gitattributes
# Exempt the entire project:
* -emoji

# Exempt specific directories or files:
docs/** -emoji
fixtures/** -emoji
cat_story.txt -emoji
```

### 2. One-Off Commit Bypass
To bypass pre-commit hooks for a single commit:

```bash
git commit --no-verify -m "commit message"
# or short form:
git commit -n -m "commit message"
```

### 3. Disable Global Hooks for One Repository Only
To disable the global hook for a specific repository while keeping it active everywhere else on your machine:

```bash
# Inside the repository where you want to disable global hooks:
git config core.hooksPath .git/hooks
```

This sets repository-local config to point back to `.git/hooks`, overriding the global `core.hooksPath` for that repo only.
