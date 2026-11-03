#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import stat
import sys

# Emoji codepoint ranges, grouped for reporting.
# (category, first codepoint, last codepoint), inclusive.
EMOJI_RANGES = [
    ('ARROWS', 0x2194, 0x2199),
    ('ARROWS', 0x21A9, 0x21AA),
    ('MISC_TECH', 0x231A, 0x231B),
    ('MISC_TECH', 0x2328, 0x2328),
    ('MISC_TECH', 0x23CF, 0x23CF),
    ('MISC_TECH', 0x23E9, 0x23FA),
    ('GEOMETRIC', 0x25AA, 0x25AB),
    ('GEOMETRIC', 0x25B6, 0x25B6),
    ('GEOMETRIC', 0x25C0, 0x25C0),
    ('GEOMETRIC', 0x25FB, 0x25FE),
    ('MISC_SYMBOLS', 0x2600, 0x26FF),
    ('DINGBATS', 0x2700, 0x27BF),
    ('MISC_SYMBOLS_ARROWS', 0x2B00, 0x2BFF),
    ('ARROWS', 0x2934, 0x2935),
    ('CJK_SYMBOLS', 0x3030, 0x3030),
    ('CJK_SYMBOLS', 0x303D, 0x303D),
    ('CJK_SYMBOLS', 0x3297, 0x3297),
    ('CJK_SYMBOLS', 0x3299, 0x3299),
    ('MAHJONG_CARDS', 0x1F000, 0x1F0FF),
    ('ENCLOSED_ALPHANUM', 0x1F100, 0x1F1E5),
    ('REGIONAL_INDICATOR', 0x1F1E6, 0x1F1FF),
    ('EMOJI_PICTOGRAPHS', 0x1F200, 0x1F3FA),
    ('SKIN_TONE', 0x1F3FB, 0x1F3FF),
    ('EMOJI_PICTOGRAPHS', 0x1F400, 0x1F5FF),
    ('EMOTICONS', 0x1F600, 0x1F64F),
    ('TRANSPORT_MAP', 0x1F650, 0x1F6FF),
    ('SUPPLEMENTAL', 0x1F900, 0x1F9FF),
    ('EXTENDED_A', 0x1FA70, 0x1FAFF),
]

EMOJI_CHARS = set()
for _name, _lo, _hi in EMOJI_RANGES:
    EMOJI_CHARS.update(range(_lo, _hi + 1))

REGIONAL_INDICATORS = set(range(0x1F1E6, 0x1F200))

# Combining characters that only exist as part of an emoji cluster
ZWJ = '\u200d'           # zero width joiner
VS16 = '\ufe0f'         # emoji variation selector
VS15 = '\ufe0e'         # text variation selector
KEYCAP = '\u20e3'       # combining enclosing keycap
SKIN_TONES = {chr(c) for c in range(0x1F3FB, 0x1F400)}
TAG_CHARS = {chr(c) for c in range(0xE0020, 0xE0080)}  # subdivision-flag tags
CLUSTER_COMPONENTS = {ZWJ, VS16, VS15, KEYCAP} | SKIN_TONES | TAG_CHARS
KEYCAP_BASES = '0123456789#*'

# Curated ASCII equivalents for --mode map, keyed by the cluster's first
# character. Emoji not listed here are stripped in map mode.
REPLACEMENT_MAP = {
    '\u2705': '[ok]',        # WHITE HEAVY CHECK MARK (✅)
    '\u2714': '[ok]',        # HEAVY CHECK MARK (✔)
    '\u2611': '[x]',         # BALLOT BOX WITH CHECK (☑)
    '\u2610': '[ ]',         # BALLOT BOX (☐)
    '\u274c': '[no]',        # CROSS MARK (❌)
    '\u2716': 'x',           # HEAVY MULTIPLICATION X (✖)
    '\u2718': 'x',           # HEAVY BALLOT X (✘)
    '\u26a0': '[warning]',   # WARNING SIGN (⚠)
    '\u2764': '<3',          # HEAVY BLACK HEART (❤)
    '\u2665': '<3',          # BLACK HEART SUIT (♥)
    '\u2661': '<3',          # WHITE HEART SUIT (♡)
    '\u2605': '*',           # BLACK STAR (★)
    '\u2606': '*',           # WHITE STAR (☆)
    '\u2b50': '*',           # WHITE MEDIUM STAR (⭐)
    '\u2734': '*',           # HEAVY EIGHT POINTED BLACK STAR (✴)
    '\u2733': '*',           # EIGHT SPOKED ASTERISK (✳)
    '\u1f44d': '+1',        # THUMBS UP SIGN (👍)
    '\u1f44e': '-1',        # THUMBS DOWN SIGN (👎)
    '\u1f642': ':)',        # SLIGHTLY SMILING FACE (🙂)
    '\u1f600': ':)',        # GRINNING FACE (😀)
    '\u1f603': ':)',        # SMILING FACE WITH OPEN MOUTH (😃)
    '\u1f604': ':)',        # SMILING FACE WITH OPEN MOUTH AND SMILING EYES (😄)
    '\u1f60a': ':)',        # SMILING FACE WITH SMILING EYES (😊)
    '\u1f609': ';)',        # WINKING FACE (😉)
    '\u1f61e': ':(',        # DISAPPOINTED FACE (😞)
    '\u1f622': ':(',        # CRYING FACE (😢)
    '\u1f641': ':(',        # SLIGHTLY FROWNING FACE (🙁)
    '\u263a': ':)',         # WHITE SMILING FACE (☺)
    '\u2639': ':(',         # WHITE FROWNING FACE (☹)
    '\u27a1': '->',         # BLACK RIGHTWARDS ARROW (➡)
    '\u2b05': '<-',         # LEFTWARDS BLACK ARROW (⬅)
    '\u2b06': '^',          # UPWARDS BLACK ARROW (⬆)
    '\u2b07': 'v',          # DOWNWARDS BLACK ARROW (⬇)
}

MODES = ('strip', 'space', 'map')

# Punctuation that binds to the preceding word; --format drops a space a
# removal strands in front of one of these
LEFT_BINDING_PUNCTUATION = ',.;:!?)]}%'

# File argument meaning stdin (a file really named '-' can be passed as ./-)
STDIN_TARGET = '-'

DEFAULT_IGNORE_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.idea', '.vscode'}


def is_self_script(filepath: str) -> bool:
    """Check if the given filepath is actually this exact script running on disk."""
    try:
        this_file = os.path.realpath(__file__)
        target_file = os.path.realpath(filepath)
        return os.path.samefile(this_file, target_file)
    except (OSError, ValueError):
        return False


def _category_of(cp: int) -> str:
    for name, lo, hi in EMOJI_RANGES:
        if lo <= cp <= hi:
            return name
    return 'EMOJI'


def _codepoints(cluster: str) -> str:
    return '+'.join('U+%04X' % ord(c) for c in cluster)


def _is_keycap_at(text: str, i: int) -> bool:
    """True if a keycap sequence (digit/#/* plus U+20E3) starts at index i."""
    j = i + 1
    if j >= len(text):
        return False
    if text[j] == VS16:
        j += 1
    return j < len(text) and text[j] == KEYCAP


def find_emoji(text: str):
    """Yield (start, end, category, cluster) for each emoji cluster in text.

    A cluster is one perceived emoji: a base character plus any variation
    selectors, ZWJ-joined bases, skin tone modifiers, and flag/tag/keycap
    components. This keeps multi-codepoint emoji (ZWJ sequences, flags with
    skin tones, family groups) intact as a single unit. Orphaned components
    (a stray joiner or selector with no base) are yielded as single clusters.
    """
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        cp = ord(ch)
        if ch in KEYCAP_BASES and _is_keycap_at(text, i):
            j = i + 1
            if text[j] == VS16:
                j += 1
            j += 1  # the KEYCAP char
            yield (i, j, 'KEYCAP', text[i:j])
            i = j
        elif cp in EMOJI_CHARS:
            j = i + 1
            if cp in REGIONAL_INDICATORS and j < n and ord(text[j]) in REGIONAL_INDICATORS:
                j += 1  # a flag is exactly two regional indicators
            while j < n:
                c = text[j]
                if c in CLUSTER_COMPONENTS:
                    j += 1
                elif c == ZWJ:
                    j += 1
                    if j < n and ord(text[j]) in EMOJI_CHARS:
                        j += 1
                else:
                    break
            yield (i, j, _category_of(cp), text[i:j])
            i = j
        elif ch in CLUSTER_COMPONENTS:
            yield (i, i + 1, 'ORPHAN_COMPONENT', ch)
            i += 1
        else:
            i += 1


def categorize_emoji(text: str) -> dict:
    """Categorize and count emoji clusters found in text.
    Returns a dict of category -> {count, char, unicode_format, unicode_escape}.
    Does NOT modify the input text.
    """
    found = {}
    for _start, _end, category, cluster in find_emoji(text):
        if category not in found:
            found[category] = {
                'count': 0,
                'char': cluster,
                'unicode_format': _codepoints(cluster),
                'unicode_escape': ''.join('\\u%04x' % ord(c) for c in cluster),
            }
        found[category]['count'] += 1
    return found


def cluster_replacement(cluster: str, category: str, mode: str) -> str:
    """Return the ASCII replacement for a cluster, or '' to delete it."""
    if category == 'KEYCAP':
        # A keycap sequence reduces to its own base: '1' + keycap -> '1'
        return cluster[0]
    if category == 'ORPHAN_COMPONENT':
        # Joiners and selectors are invisible; deleting needs no substitute
        return ''
    if mode == 'map':
        return REPLACEMENT_MAP.get(cluster[0], '')
    if mode == 'space':
        return ' '
    return ''  # strip


def replace_emoji_in_text(text: str, mode: str, format_cleanup: bool = False) -> tuple:
    """Remove or replace emoji clusters in text.
    Returns (new_text, cluster_count).
    """
    out = []
    pos = 0
    total = 0
    prev = ''  # last emitted character ('' before any output)
    for start, end, category, cluster in find_emoji(text):
        segment = text[pos:start]
        if segment:
            out.append(segment)
            prev = segment[-1]
        replacement = cluster_replacement(cluster, category, mode)
        if replacement == ' ' and (prev == ' ' or (end < len(text) and text[end] == ' ')):
            replacement = ''  # a blank next to an existing space is redundant
        if replacement:
            out.append(replacement)
            prev = replacement[-1]
        else:
            next_ch = text[end] if end < len(text) else ''
            if format_cleanup and prev == ' ' and next_ch and next_ch in LEFT_BINDING_PUNCTUATION:
                # A removal stranded a space in front of punctuation; drop it
                out[-1] = out[-1][:-1]
                prev = out[-1][-1] if out[-1] else ''
            elif next_ch == ' ' and prev in ('', '\n', ' '):
                # Swallow a space a deletion would orphan: one of a pair around
                # the cluster, or one at the very start of a line
                end += 1
        total += 1
        pos = end
    out.append(text[pos:])
    return ''.join(out), total


def process_file(filepath: str, verbose: bool = True, fix: bool = False, dry_run: bool = False, backup: bool = False, mode: str = 'strip', format_cleanup: bool = False) -> tuple:
    """Scan and optionally clean emoji in a file.
    Returns (emoji_found, file_summary, replacements_made, is_excluded, file_error).
    """
    emoji_found = False
    file_summary = {}
    replacements_made = 0
    file_error = False

    # 1. Skip symlinks to avoid replacing links with target regular files
    if os.path.islink(filepath):
        if verbose:
            print(f"Skipping symlink: {filepath}", file=sys.stderr)
        return False, {}, 0, False, False

    is_excluded = is_self_script(filepath)

    try:
        # Open with newline='' to preserve original CRLF / LF line endings
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            content = f.read()

        # Binary check: null bytes usually indicate non-text files
        if '\x00' in content:
            if verbose:
                print(f"Skipping binary file: {filepath}", file=sys.stderr)
            return False, {}, 0, False, False

        # Split preserving newlines to keep exact line numbering aligned
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            categories = categorize_emoji(line)
            if categories:
                if verbose:
                    prefix = "[SELF-DEFINITION] " if is_excluded else ""
                    display_line = line.rstrip('\r')
                    print(f"{prefix}{filepath}:{line_num}: {display_line}")
                emoji_found = True

                for category, data in categories.items():
                    if category not in file_summary:
                        file_summary[category] = {
                            'count': 0,
                            'char': data['char'],
                            'unicode_format': data['unicode_format'],
                            'unicode_escape': data['unicode_escape'],
                        }
                    file_summary[category]['count'] += data['count']

        if fix and emoji_found:
            if is_excluded:
                if verbose:
                    print(f"[SKIPPED FIX] Excluded self script from replacement: {filepath}")
            else:
                new_content, count_to_replace = replace_emoji_in_text(content, mode, format_cleanup)
                if count_to_replace > 0:
                    if dry_run:
                        replacements_made = count_to_replace
                        if verbose:
                            print(f"[DRY-RUN] Would clean {count_to_replace} emoji cluster(s) in: {filepath}")
                    else:
                        if backup:
                            shutil.copy2(filepath, f"{filepath}.bak")

                        tmp_filepath = f"{filepath}.tmp_emoji_fix"
                        try:
                            # Preserve line endings
                            with open(tmp_filepath, 'w', encoding='utf-8', newline='') as f_out:
                                f_out.write(new_content)

                            # Preserve exact POSIX permissions / execute bit
                            shutil.copymode(filepath, tmp_filepath)

                            # Atomic rename
                            os.replace(tmp_filepath, filepath)
                            replacements_made = count_to_replace

                            if verbose:
                                print(f"[FIXED] Cleaned {replacements_made} emoji cluster(s) in: {filepath}")
                        except Exception as write_err:
                            if os.path.exists(tmp_filepath):
                                try:
                                    os.remove(tmp_filepath)
                                except OSError:
                                    pass
                            raise write_err

    except UnicodeDecodeError:
        if verbose:
            print(f"Skipping non-UTF-8 / binary file: {filepath}", file=sys.stderr)
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        file_error = True

    return emoji_found, file_summary, replacements_made, is_excluded, file_error


def stdin_has_data() -> bool:
    """Return True if stdin is a pipe or redirected file, not a terminal or /dev/null."""
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
    except (OSError, ValueError):
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def process_stdin(output, verbose: bool = True, fix: bool = False, dry_run: bool = False, mode: str = 'strip', format_cleanup: bool = False) -> tuple:
    """Scan stdin; with fix (and not dry_run) write the cleaned text to output as a filter.
    Returns the same tuple as process_file.
    """
    # surrogateescape round-trips any non-UTF-8 bytes unchanged
    content = sys.stdin.buffer.read().decode('utf-8', 'surrogateescape')
    file_summary = {}
    for line_num, line in enumerate(content.split('\n'), 1):
        categories = categorize_emoji(line)
        if categories and verbose:
            display_line = line.rstrip('\r').encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
            print(f"<stdin>:{line_num}: {display_line}")
        for category, data in categories.items():
            if category in file_summary:
                file_summary[category]['count'] += data['count']
            else:
                file_summary[category] = dict(data)

    if not fix:
        replacements_made = 0
    else:
        new_content, replacements_made = replace_emoji_in_text(content, mode, format_cleanup)
        if not dry_run:
            output.write(new_content.encode('utf-8', 'surrogateescape'))
            output.flush()
    return bool(file_summary), file_summary, replacements_made, False, False


def scan_directory(path: str, recursive: bool = False):
    """Yield file paths from directory, optionally recursively, ignoring VCS/virtualenvs."""
    if recursive:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in DEFAULT_IGNORE_DIRS]
            for f in files:
                if not f.startswith('.'):
                    yield os.path.join(root, f)
    else:
        try:
            for f in os.listdir(path):
                if f.startswith('.'):
                    continue
                full = os.path.join(path, f)
                if os.path.isfile(full):
                    yield full
        except OSError as e:
            print(f"Error accessing directory {path}: {e}", file=sys.stderr)


def resolve_targets(paths: list, recursive: bool = False):
    """Resolve file or directory arguments into a stream of target file paths."""
    if not paths:
        yield from scan_directory('.', recursive=recursive)
        return

    for path in paths:
        if path == STDIN_TARGET:
            yield path
        elif os.path.islink(path):
            continue
        elif os.path.isdir(path):
            yield from scan_directory(path, recursive=recursive)
        elif os.path.isfile(path):
            yield path
        else:
            print(f"Target not found: {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Detect and remove or replace emoji in files')
    parser.add_argument('files', nargs='*', help="Files or directories to scan, or '-' for stdin (default: piped stdin, else current directory)")
    parser.add_argument('-r', '--recursive', action='store_true', help='Scan directories recursively')
    parser.add_argument('--fix', action='store_true', help="Clean detected emoji (strip, or substitute via --mode space|map)")
    parser.add_argument('--mode', choices=MODES, default='strip', help="Cleaning mode: 'strip' deletes emoji clusters, 'space' substitutes a single blank, 'map' substitutes ASCII equivalents where the curated map has one (default: strip)")
    parser.add_argument('--dry-run', action='store_true', help='Simulate cleaning with --fix without altering files')
    parser.add_argument('--format', action='store_true', help='With --fix, also fix format irregularities the cleanup causes (drops a space stranded before punctuation)')
    parser.add_argument('--backup', action='store_true', help='Create .bak backup files before modifying with --fix')
    parser.add_argument('--json', action='store_true', help='Output summary strictly as JSON to stdout')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress per-file progress output')
    parser.add_argument('--exit-code', action='store_true', help='Exit with code 1 if emoji found or read errors (for CI)')
    args = parser.parse_args()

    # If --dry-run is supplied without --fix, automatically imply fix inspection mode
    if args.dry_run and not args.fix:
        args.fix = True

    if not args.files and stdin_has_data():
        args.files = [STDIN_TARGET]

    # Filter mode: cleaned text owns stdout, so every report moves to stderr
    filter_output = sys.stdout.buffer
    if STDIN_TARGET in args.files and args.fix and not args.dry_run:
        sys.stdout = sys.stderr

    overall_summary = {}
    any_found = False
    any_errors = False
    total_replacements = 0
    excluded_files = []
    verbose = not args.json and not args.quiet

    if verbose and not args.files:
        print("Scanning current directory for emoji...")

    for filepath in resolve_targets(args.files, args.recursive):
        if verbose:
            print(f"\nProcessing: {filepath}")

        if filepath == STDIN_TARGET:
            result = process_stdin(filter_output, verbose=verbose and not args.fix, fix=args.fix, dry_run=args.dry_run, mode=args.mode, format_cleanup=args.format)
        else:
            result = process_file(
                filepath,
                verbose=verbose,
                fix=args.fix,
                dry_run=args.dry_run,
                backup=args.backup,
                mode=args.mode,
                format_cleanup=args.format,
            )
        found, file_summary, replaced, is_excluded, file_error = result

        if file_error:
            any_errors = True

        total_replacements += replaced

        if is_excluded and found:
            excluded_files.append(filepath)

        if found:
            if not is_excluded:
                any_found = True

            if verbose and not args.fix and not is_excluded:
                print(f"Emoji found in: {filepath}")
            if is_excluded:
                continue
            for category, data in file_summary.items():
                if category not in overall_summary:
                    overall_summary[category] = {
                        'count': 0,
                        'char': data['char'],
                        'unicode_format': data['unicode_format'],
                        'unicode_escape': data['unicode_escape'],
                    }
                overall_summary[category]['count'] += data['count']
        elif verbose:
            print(f"No emoji found in: {filepath}")

    if args.json:
        payload = {
            'emoji_found': any_found,
            'errors_encountered': any_errors,
            'total_detected': sum(d['count'] for d in overall_summary.values()),
            'fix_enabled': args.fix,
            'mode': args.mode,
            'format_cleanup': args.format,
            'dry_run': args.dry_run,
            'replacements_made': total_replacements,
            'excluded_from_fix': list(set(excluded_files)),
            'summary': overall_summary,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif overall_summary:
        print("\n" + "=" * 100)
        mode_header = "EMOJI DETECTION & CLEANING SUMMARY" if args.fix else "EMOJI DETECTION SUMMARY"
        print(mode_header)
        print("=" * 100)
        print(f"{'Category':<22} {'Count':<8} {'Codepoints':<32} {'Prints As'}")
        print("-" * 100)
        for category, data in sorted(overall_summary.items()):
            print(f"{category:<22} {data['count']:<8} {data['unicode_format']:<32} {repr(data['char'])}")
        print("=" * 100)
        total = sum(data['count'] for data in overall_summary.values())
        print(f"Total emoji clusters detected: {total}")
        if excluded_files:
            print(f"Note: Self-utility ({', '.join(set(excluded_files))}) was preserved and excluded from --fix.")
        if args.fix:
            status = "would be cleaned (dry-run)" if args.dry_run else "successfully cleaned"
            print(f"Total emoji clusters {status}: {total_replacements}")
    elif not args.quiet:
        print("\nNo emoji found in any files.")

    if args.exit_code:
        # Exit with error if un-excluded emoji remain or if file errors occurred
        sys.exit(1 if (any_found or any_errors) else 0)


if __name__ == "__main__":
    main()
