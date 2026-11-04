#!/usr/bin/env python3
"""Generate synthetic emoji-laden texts from a source for density testing.

No public domain novels contain emoji (they predate Unicode emoji by decades),
so this script injects emoji into prose at a target density. This gives known
ground truth: inject N emoji into W words, and detect_emoji.py --density
should report N/W x 1000.

The pool includes multi-codepoint clusters (ZWJ sequences, flags, keycaps,
skin tones) to exercise the cluster detector, not just single-codepoint emoji.

Usage:
    generate_testbed.py source.txt --density 20 > output.txt
    generate_testbed.py source.txt --density 50 --category emoticons > output.txt
    generate_testbed.py source.txt --density 10 --seed 99 > output.txt
"""
import argparse
import random
import re
import sys

# Emoji pool by category. Includes multi-codepoint clusters to exercise
# the cluster detector (ZWJ sequences, flags, keycaps, skin tones).
EMOJI_POOL = {
    'emoticons': [
        '\U0001F600', '\U0001F603', '\U0001F604', '\U0001F601', '\U0001F606',
        '\U0001F605', '\U0001F923', '\U0001F602', '\U0001F642', '\U0001F609',
        '\U0001F60A', '\U0001F60D', '\U0001F970', '\U0001F60E', '\U0001F914',
        '\U0001F634', '\U0001F971', '\U0001F62D', '\U0001F622', '\U0001F621',
    ],
    'animals': [
        '\U0001F431', '\U0001F436', '\U0001F98A', '\U0001F43B', '\U0001F43C',
        '\U0001F428', '\U0001F430', '\U0001F439', '\U0001F426', '\U0001F984',
        '\U0001F41D', '\U0001F98B', '\U0001F419', '\U0001F433', '\U0001F42C',
        '\U0001F41F', '\U0001F420', '\U0001F408', '\U0001F995', '\U0001F996',
    ],
    'food': [
        '\u2615', '\U0001F375', '\U0001F35E', '\U0001F950', '\U0001F9C0',
        '\U0001F356', '\U0001F357', '\U0001F354', '\U0001F35F', '\U0001F355',
        '\U0001F32D', '\U0001F32E', '\U0001F32F', '\U0001F957', '\U0001F35D',
        '\U0001F35C', '\U0001F363', '\U0001F370', '\U0001F382', '\U0001F366',
    ],
    'nature': [
        '\u2600\ufe0f', '\u2601\ufe0f', '\u26c5', '\U0001F327\ufe0f', '\u26c8\ufe0f',
        '\U0001F328\ufe0f', '\U0001F308', '\U0001F525', '\U0001F4A7', '\U0001F30A',
        '\U0001F33F', '\U0001F338', '\U0001F33A', '\U0001F33B', '\U0001F33C',
        '\U0001F337', '\U0001F339', '\U0001F940', '\U0001F340', '\U0001F343',
    ],
    'objects': [
        '\U0001F4A1', '\U0001F511', '\U0001F4E6', '\U0001F4EC', '\U0001F4DD',
        '\U0001F4D6', '\U0001F4DA', '\u270f\ufe0f', '\U0001F4CC', '\U0001F4CE',
        '\U0001F527', '\U0001F528', '\u2699\ufe0f', '\U0001F48E', '\U0001F514',
        '\U0001F3B5', '\U0001F3B6', '\U0001F3A4', '\U0001F3A7', '\U0001F4FB',
    ],
    'symbols': [
        '\u2764\ufe0f', '\u2728', '\u2b50', '\U0001F31F', '\U0001F4AB',
        '\u26a1', '\u274c', '\u2705', '\u2757', '\u2753',
        '\u27a1\ufe0f', '\u2b05\ufe0f', '\u2b06\ufe0f', '\u2b07\ufe0f',
        '\U0001F4AF', '\U0001F531', '\u267b\ufe0f', '\U0001F4A2', '\U0001F4A5', '\U0001F4AB',
    ],
    'transport': [
        '\U0001F680', '\U0001F697', '\U0001F695', '\U0001F699', '\U0001F68C',
        '\U0001F3CE\ufe0f', '\U0001F693', '\U0001F691', '\U0001F692', '\U0001F690',
        '\U0001F69A', '\U0001F69B', '\u2708\ufe0f', '\U0001F682', '\U0001F686',
        '\U0001F68A', '\U0001F689', '\U0001F6A2', '\u26f5', '\U0001F6A4',
    ],
    'multi': [
        '\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466',
        '\U0001F468\u200D\U0001F469\u200D\U0001F467',
        '\U0001F469\u200D\U0001F466',
        '\U0001F468\u200D\U0001F466',
        '\U0001F1FA\U0001F1F8', '\U0001F1EC\U0001F1E7', '\U0001F1EF\U0001F1F5',
        '\U0001F1EB\U0001F1F7', '\U0001F1E9\U0001F1EA', '\U0001F1E8\U0001F1E6',
        '1\ufe0f\u20e3', '2\ufe0f\u20e3', '3\ufe0f\u20e3',
        '\U0001F44D\U0001F3FD', '\U0001F44E\U0001F3FE', '\U0001F44F\U0001F3FF',
        '\U0001F64C\U0001F3FB', '\U0001F91D', '\U0001F64F', '\U0001FAF6',
    ],
}

ALL_CATEGORIES = list(EMOJI_POOL.keys())


def count_words(text):
    return sum(1 for token in text.split() if any(c.isalnum() for c in token))


def generate(source_text, target_density, categories, seed=42):
    """Inject emoji into source_text at target_density (emoji per 1000 words)."""
    rng = random.Random(seed)
    words = count_words(source_text)
    n_emoji = max(1, round(target_density * words / 1000))

    pool = []
    for cat in categories:
        pool.extend(EMOJI_POOL.get(cat, []))
    if not pool:
        for cat in ALL_CATEGORIES:
            pool.extend(EMOJI_POOL[cat])

    # Split into tokens preserving whitespace via capture group
    parts = re.split(r'(\s+)', source_text)
    # parts: [text, ws, text, ws, ...] (text tokens are at even indices)
    text_indices = [i for i in range(0, len(parts), 2) if parts[i].strip()]
    if not text_indices:
        return source_text

    inject_at = set(rng.sample(text_indices, min(n_emoji, len(text_indices))))

    result = []
    for i, part in enumerate(parts):
        result.append(part)
        if i in inject_at:
            emoji = rng.choice(pool)
            # Attach emoji to the end of the text token, before the whitespace
            result[-1] = result[-1] + ' ' + emoji

    return ''.join(result)


def main():
    parser = argparse.ArgumentParser(
        description='Generate synthetic emoji-laden texts for density testing')
    parser.add_argument('source', help='Source text file (no emoji)')
    parser.add_argument('--density', type=float, default=20.0,
                        help='Target emoji per 1,000 words (default: 20)')
    parser.add_argument('--category',
                        choices=ALL_CATEGORIES + ['mixed'], default='mixed',
                        help='Emoji category to inject (default: mixed)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    args = parser.parse_args()

    with open(args.source, 'r', encoding='utf-8') as f:
        source_text = f.read()

    categories = ALL_CATEGORIES if args.category == 'mixed' else [args.category]
    result = generate(source_text, args.density, categories, args.seed)
    sys.stdout.write(result)


if __name__ == '__main__':
    main()
