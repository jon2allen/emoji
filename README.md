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
- **`detect_emoji.py`**: Standalone Python 3 scanner and cleaner (supports `-r`, `--fix`, `--mode strip|space|map`, `--format`, `--dry-run`, `--backup`, `--json`, `--exit-code`, `--density`, `--group-by`, `--top`, and `-q`; requires Python 3.7+).
- **`pre-commit`**: POSIX `/bin/sh` hook script placed in `~/.git_hooks/`.
- **`setup.sh`**: Setup installer for macOS and Linux (`sh`/`bash`/`zsh`).
- **`setup.csh`**: Setup installer for FreeBSD and `csh`/`tcsh` shells.
- **`test_emoji.py`**, **`test_hook.py`**: Test suite (`python3 -m pytest`).
- **`generate_testbed.py`**: Injects emoji into a source text at a target density for testing the metric.
- **`emoji_analysis.sh`**: Runner script that executes unit tests and generates the density analysis table across the testbed.
- **`testbed/`**: Synthetic emoji-laden texts at controlled densities (generated from `cat_story.txt` with emoji stripped).

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

## Emoji Density
`detect_emoji.py --density` reports, for each file, how many emoji appear per 1,000 words:

```
density = (emoji count / word count) x 1000
```

The counting unit is the **cluster**: a ZWJ family sequence, a flag, or a keycap each count as one, matching the detector's perception of a single emoji. A word is any token, split on whitespace with emoji clusters removed, that contains a letter or digit. Every file is measured the same way, and nothing is modified (`--density` cannot be combined with `--fix`).

### Breakdown levels: `--group-by`

| Level | What it shows | Flag |
|-------|--------------|------|
| `all` | Per-file aggregate: total emoji per 1,000 words | `--group-by all` (default) |
| `category` | Per emoji category (EMOTICONS, DINGBATS, TRANSPORT_MAP, etc.) | `--group-by category` |
| `emoji` | Per individual emoji cluster, capped by `--top N` | `--group-by emoji --top 15` |

Levels can be combined: `--group-by all,category,emoji` prints all three tables. The `--top` option (default 20, `0` for all) limits the per-emoji table to the most frequent clusters.

```bash
detect_emoji.py --density docs/
detect_emoji.py --density --group-by category -r docs/
detect_emoji.py --density --group-by emoji --top 15 docs/
cat draft.md | detect_emoji.py --density --json
```

### Synthetic Testbed

No public domain novels contain emoji (they predate Unicode emoji by decades), and the only natural emoji-bearing corpora are tweets and social media (short-form). To test the metric on longer prose with known ground truth, `generate_testbed.py` injects emoji into a source text at a target density. Inject N emoji into W words, and `--density` should report N/W x 1000.

The testbed is built from `cat_story.txt` (a short story already in the repo) with emoji stripped, then re-injected at controlled densities:

```bash
./detect_emoji.py --fix - < cat_story.txt > testbed/baseline.txt
./generate_testbed.py testbed/baseline.txt --density 5  > testbed/low_density.txt
./generate_testbed.py testbed/baseline.txt --density 20 > testbed/medium_density.txt
./generate_testbed.py testbed/baseline.txt --density 50 > testbed/high_density.txt
./generate_testbed.py testbed/baseline.txt --density 30 --category emoticons > testbed/emoticons_only.txt
```

Running `./detect_emoji.py --density --group-by all,category testbed/*.txt cat_story.txt` produces:

```
File                            Words    Emoji  Emoji/1k
--------------------------------------------------------
cat_story.txt                     262       57    217.56
testbed/baseline.txt              262        0      0.00
testbed/emoticons_only.txt        262        8     30.53
testbed/high_density.txt          262       13     49.62
testbed/low_density.txt           262        1      3.82
testbed/medium_density.txt        262        5     19.08
--------------------------------------------------------
TOTAL                            1572       84     53.44

Category                    Count   Per 1k
------------------------------------------
EMOJI_PICTOGRAPHS              47    29.90
EMOTICONS                     10     6.36
SUPPLEMENTAL                   8     5.09
TRANSPORT_MAP                  6     3.82
DINGBATS                       4     2.54
MISC_SYMBOLS                   3     1.91
EXTENDED_A                     2     1.27
KEYCAP                         2     1.27
MISC_SYMBOLS_ARROWS            2     1.27
------------------------------------------
TOTAL                         84    53.44
Density = (emoji count / word count) x 1000
```

The injected densities track the targets (low 3.82 vs 5, medium 19.08 vs 20, high 49.62 vs 50), with small rounding error from the word count denominator. The `emoticons_only` sample confirms `--group-by category` isolates a single category. `cat_story.txt` (the original, hand-written story) shows what naturalistic high-density emoji prose looks like at 217.56 per 1,000 words.

The per-emoji view (`--group-by emoji --top 15`) shows the most frequent individual clusters, including multi-codepoint sequences:

```
Emoji  Codepoints              Count   Per 1k
---------------------------------------------
🐾     U+1F43E                     3     5.73
🚪     U+1F6AA                     3     5.73
🌿     U+1F33F                     2     3.82
🐱     U+1F431                     2     3.82
🔥     U+1F525                     2     3.82
1️⃣     U+0031+U+FE0F+U+20E3        1     1.91
☀️     U+2600+U+FE0F               1     1.91
☕️     U+2615+U+FE0F               1     1.91
⚡️     U+26A1+U+FE0F               1     1.91
✅     U+2705                      1     1.91
---------------------------------------------
TOTAL                             70   133.59
```

Run `./emoji_analysis.sh` to regenerate the testbed and produce the full report.

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

---

## References

The density calculation — `(emoji count / word count) x 1000` — follows the per-1,000-words frequency metric introduced for em dashes in:

- Freeburg, E. M. (2026). *The Last Fingerprint: How Markdown Training Shapes LLM Prose*. [arXiv:2603.27006](https://arxiv.org/abs/2603.27006) — research code: [emfreeburg/the-last-fingerprint](https://github.com/emfreeburg/the-last-fingerprint). The em dash density tool that inspired this one lives in the [emdash](https://github.com/jon2allen/emdash) repository.

No published paper measures emoji density per 1,000 words across LLM-generated prose the way Freeburg measures em dash density. The following papers and analyses study emoji generation, LLM stylistic fingerprints, and AI-text detection, and collectively motivate extending the density metric to emoji:

1. Jain, N., Wu, Z., Munoz, C., Hilliard, A., Guan, X., Treleaven, P., Kazim, E., & Koshiyama, A. (2025). *From Text to Emoji: How PEFT-Driven Personality Manipulation Unleashes the Emoji Potential in LLMs*. Findings of NAACL 2025. [arXiv:2409.10245](https://arxiv.org/abs/2409.10245) — after personality fine-tuning, LLaMA-2 and Mistral spontaneously generated emoji despite no emoji in the training data; traced to specific neurons.

2. Michael, D. & Kenneth, H. *How Good Is GPT's "Emojinal Intelligence"? Investigating Emoji Patterns in LLM-Generated Social Media Text*. Proceedings of the International Conference on AI Research (ICAIR). [Paper](https://papers.academic-conferences.org/index.php/icair/article/view/3225) — compares GPT-3.5 emoji patterns against human tweets; finds LLMs use broader emoji variety with literal subject representation, while humans prefer faces, hearts, and repetition.

3. *Emoji as interpersonal resources in LLM chatbot conversations: a social semiotic analysis of tenor and affiliation in human–AI interaction* (2025). [Taylor & Francis](https://www.tandfonline.com/doi/full/10.1080/10350330.2025.2570317) — analyzes emoji use across one million chatbot–human interactions as resources for shaping interpersonal tone.

4. Peng, L. et al. (2023). *EmojiLM: Modeling the New Emoji Language*. [arXiv:2311.01751](https://arxiv.org/abs/2311.01751) — synthesizes a text-emoji parallel corpus from an LLM and treats emoji as an emerging linguistic system.

5. *Detecting Stylistic Fingerprints of Large Language Models* (2025). [arXiv:2503.01659](https://arxiv.org/html/2503.01659v1) — classifies texts by LLM family (Claude, Gemini, Llama, OpenAI) using stylistic fingerprints that persist across domains and writing styles.

6. Netcraft. *Excessive Emojis as an AI Indicator*. [netcraft.com/blog/excessive-emojis-as-an-ai-indicator](https://www.netcraft.com/blog/excessive-emojis-as-an-ai-indicator) — industry analysis identifying emoji in code comments and console outputs as a consistent machine-generated footprint.

7. Pangram. *9 Signs of AI Writing, Backed by Data*. [pangram.com/signs-of-ai-writing](https://www.pangram.com/signs-of-ai-writing) — detector vendor analysis noting that aggregate emoji use is barely elevated in AI text, but which specific emojis are used differs significantly from human text.

8. *Markers of AI-generated text: the measurable signs*. ScriptGrain. [scriptgrain.com/reference/markers-of-ai-writing](https://scriptgrain.com/reference/markers-of-ai-writing) — survey of measurable frequency shifts (em dashes, vocabulary, punctuation) that distinguish AI-generated text, with discussion of false-positive rates.
