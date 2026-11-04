import os
import subprocess
import sys
import tempfile

import pytest

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "detect_emoji.py"))
EMOJI = "\U0001F600"  # grinning face


def run_emoji(*args):
    return subprocess.run([sys.executable, SCRIPT_PATH, *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_permissions_preserved():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sh", encoding="utf-8") as f:
        f.write(f"#!/bin/sh\necho '{EMOJI} hi'\n")
        path = f.name
    try:
        os.chmod(path, 0o755)
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o755, f"Expected 0755, got {oct(mode)}"
        with open(path, encoding="utf-8") as f:
            assert "echo ' hi'" in f.read()
    finally:
        os.remove(path)


def test_crlf_preserved():
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write(("Line 1: hi " + EMOJI + " there\r\nLine 2: normal\r\n").encode("utf-8"))
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, "rb") as f:
            content = f.read()
        assert b"\r\n" in content
        assert b"Line 1: hi there\r\n" in content
        assert EMOJI.encode("utf-8") not in content
    finally:
        os.remove(path)


def test_symlink_skipped():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"target with {EMOJI} emoji\n")
        real_file = f.name
    link_path = real_file + ".symlink"
    os.symlink(real_file, link_path)
    try:
        res = run_emoji("--fix", link_path)
        assert res.returncode == 0
        assert os.path.islink(link_path)
        with open(real_file, encoding="utf-8") as f:
            assert EMOJI in f.read()
    finally:
        os.remove(link_path)
        os.remove(real_file)


def test_quiet_mode_silence():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("Clean file without emoji\n")
        path = f.name
    try:
        res = run_emoji("-q", path)
        assert res.returncode == 0
        assert res.stdout == ""
    finally:
        os.remove(path)


def test_dry_run_implies_fix():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"File with {EMOJI} emoji\n")
        path = f.name
    try:
        res = run_emoji("--dry-run", path)
        assert res.returncode == 0
        assert "Would clean 1 emoji" in res.stdout
        with open(path, encoding="utf-8") as f:
            assert EMOJI in f.read()
    finally:
        os.remove(path)


def test_strip_is_default_mode():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"hello {EMOJI} world\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "hello world\n"
    finally:
        os.remove(path)


def test_space_mode_substitutes_single_blank():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"a{EMOJI}b\nhello {EMOJI} world\nx {EMOJI}y\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "space", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "a b\nhello world\nx y\n"
    finally:
        os.remove(path)


def test_space_mode_keycap_and_orphans_untouched_by_blank():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("1\ufe0f\u20e3 x\nok\ufe0f there\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "space", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "1 x\nok there\n"
    finally:
        os.remove(path)


def test_map_mode_substitutes_ascii():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("\u2705 shipped\n\u26a0 careful\n\u2764 it\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "map", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "[ok] shipped\n[warning] careful\n<3 it\n"
    finally:
        os.remove(path)


def test_map_mode_unmapped_falls_back_to_strip():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("\U0001F680 launch\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "map", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "launch\n"
    finally:
        os.remove(path)


def test_detection_reports_each_line_once():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"a {EMOJI} b \U0001F620\nclean\nlast {EMOJI}\n")
        path = f.name
    try:
        res = run_emoji(path)
        assert res.returncode == 0
        assert res.stdout.count(":1:") == 1
        assert ":3:" in res.stdout
        assert ":2:" not in res.stdout
    finally:
        os.remove(path)


def test_format_drops_space_stranded_before_punctuation():
    source = "radiator \U0001F525, kingdom \U0001F451. hi \U0001F4A1! really \U0001F602?\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "radiator , kingdom . hi ! really ?\n"

        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        res = run_emoji("--fix", "--format", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "radiator, kingdom. hi! really?\n"
    finally:
        os.remove(path)


def test_format_leaves_original_punctuation_untouched():
    source = "already , irregular . text\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        res = run_emoji("--fix", "--format", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == source
    finally:
        os.remove(path)


def test_format_applies_to_map_mode():
    source = "went out \u26a0\ufe0f, then \u274c it\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "map", "--format", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "went out [warning], then [no] it\n"
    finally:
        os.remove(path)


def test_format_applies_to_space_mode():
    source = "cat \U0001F431, dog \U0001F436.\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "space", "--format", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "cat, dog.\n"
    finally:
        os.remove(path)


def test_zwj_cluster_removed_as_one_unit():
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"a{family}b\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert content == "ab\n"
        assert "\u200d" not in content
        assert "\U0001F468" not in content
    finally:
        os.remove(path)


def test_flag_cluster_removed_completely():
    flag = "\U0001F1FA\U0001F1F8"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"flag {flag} ok\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "flag ok\n"
    finally:
        os.remove(path)


def test_skin_tone_consumed_with_base():
    cluster = "\U0001F44D\U0001F3FD"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"a {cluster} b\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "a b\n"
    finally:
        os.remove(path)


def test_keycap_reduced_to_ascii_base():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("1\ufe0f\u20e3 item\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "1 item\n"
    finally:
        os.remove(path)


def test_orphan_components_removed():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("ok\ufe0f there\na\u200db\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "ok there\nab\n"
    finally:
        os.remove(path)


def test_adjacent_clusters_and_space_collapse():
    two = EMOJI + "\U0001F601"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"a {two} b\n")
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "a b\n"
    finally:
        os.remove(path)


def test_common_non_emoji_not_flagged():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("copyright \u00a9, trademark \u2122, arrow \u2192, dashes \u2013\u2014, accents caf\u00e9\n")
        path = f.name
    try:
        res = run_emoji("--exit-code", path)
        assert res.returncode == 0
    finally:
        os.remove(path)


def test_self_script_excluded_from_fix():
    with open(SCRIPT_PATH, "rb") as f:
        before = f.read()
    try:
        res = run_emoji("--fix", SCRIPT_PATH)
        assert res.returncode == 0
        assert "SKIPPED FIX" in res.stdout
        with open(SCRIPT_PATH, "rb") as f:
            assert f.read() == before
    finally:
        with open(SCRIPT_PATH, "wb") as f:
            f.write(before)


def test_map_mode_supplementary_plane_emoji():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("\U0001f44d good \U0001f44e bad \U0001f600 smile \U0001f622 cry\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--mode", "map", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "+1 good -1 bad :) smile :( cry\n"
    finally:
        os.remove(path)


def test_zwj_cluster_treated_as_single_cluster():
    import detect_emoji
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
    clusters = list(detect_emoji.find_emoji(family))
    assert len(clusters) == 1
    assert clusters[0][3] == family

    cleaned, count = detect_emoji.replace_emoji_in_text(f"hi {family} bye", mode="strip")
    assert count == 1
    assert cleaned == "hi bye"


def test_zwj_followed_by_bare_digit_keeps_digit():
    import detect_emoji
    # Malformed sequence: ZWJ then a digit with no keycap; the digit is text
    cleaned, _ = detect_emoji.replace_emoji_in_text("a\U0001F468\u200d123 b", mode="strip")
    assert cleaned == "a123 b"
    cleaned, _ = detect_emoji.replace_emoji_in_text("ok\U0001F468\u200d#z", mode="strip")
    assert cleaned == "ok#z"


def test_fix_with_exit_code_zero_when_cleaned():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(f"file with {EMOJI} emoji\n")
        path = f.name
    try:
        res = run_emoji("--fix", "--exit-code", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "file with emoji\n"
    finally:
        os.remove(path)


def test_unicode_escape_formatting_smp():
    import detect_emoji
    cats = detect_emoji.categorize_emoji(EMOJI)
    assert cats["EMOTICONS"]["unicode_escape"] == "\\U0001f600"


def test_geometric_extended_shapes_detected_and_cleaned():
    # Colored circles and squares: U+1F7E0 - U+1F7EB
    text = "Status: \U0001F7E1 in progress \U0001F7E2 done \U0001F7E5 blocker\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        res = run_emoji("--fix", path)
        assert res.returncode == 0
        with open(path, encoding="utf-8") as f:
            assert f.read() == "Status: in progress done blocker\n"
    finally:
        os.remove(path)


# --density: emoji per 1,000 words
import json

from detect_emoji import count_words, emoji_density

GRIN = "\U0001F600"      # EMOTICONS
ROCKET = "\U0001F680"    # TRANSPORT_MAP
HEART = "\u2764"         # MISC_SYMBOLS


def test_count_words_removes_emoji():
    assert count_words(f"one two{GRIN}three") == 3
    assert count_words(f"pages 10{ROCKET}20") == 3
    # ZWJ family cluster is one unit, removed as one
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
    assert count_words(f"a{family}b") == 2
    assert count_words("") == 0
    assert count_words("clean text only") == 3


def test_emoji_density_formula():
    r = emoji_density(f"one two three{GRIN}four five six seven{ROCKET}eight")
    assert r["words"] == 8
    assert r["total_emoji"] == 2
    assert r["categories"] == {"EMOTICONS": 1, "TRANSPORT_MAP": 1}
    assert r["emoji"] == {GRIN: 1, ROCKET: 1}


def test_emoji_density_no_words():
    r = emoji_density(GRIN)
    assert r["words"] == 0
    assert r["total_emoji"] == 1


def test_density_cli_all(tmp_path):
    (tmp_path / "a.txt").write_text(f"one{GRIN}two three four", encoding="utf-8")
    (tmp_path / "b.txt").write_text("five six seven eight", encoding="utf-8")
    res = run_emoji("--density", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "Emoji/1k" in res.stdout
    assert "TOTAL" in res.stdout
    # a.txt: 4 words, 1 emoji -> 250.0
    assert "250.00" in res.stdout


def test_density_cli_json(tmp_path):
    (tmp_path / "a.txt").write_text(f"one{GRIN}two three four", encoding="utf-8")
    (tmp_path / "b.txt").write_text("five six seven eight", encoding="utf-8")
    res = run_emoji("--density", "--json", str(tmp_path))
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert len(data["files"]) == 2
    assert data["total"]["words"] == 8
    assert data["total"]["total_emoji"] == 1
    assert data["total"]["total_density"] == 125.0
    assert data["group_by"] == ["all"]


def test_density_group_by_category(tmp_path):
    (tmp_path / "a.txt").write_text(
        f"{GRIN} {GRIN} {ROCKET} {HEART} word word word word word word", encoding="utf-8")
    res = run_emoji("--density", "--group-by", "category", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "Category" in res.stdout
    assert "EMOTICONS" in res.stdout
    assert "TRANSPORT_MAP" in res.stdout
    assert "DINGBATS" in res.stdout
    assert "TOTAL" in res.stdout


def test_density_group_by_emoji(tmp_path):
    (tmp_path / "a.txt").write_text(
        f"{GRIN} {GRIN} {ROCKET} word word word word word word word", encoding="utf-8")
    res = run_emoji("--density", "--group-by", "emoji", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "Codepoints" in res.stdout
    assert GRIN in res.stdout
    assert "U+1F600" in res.stdout
    assert "TOTAL" in res.stdout
    header = [l for l in res.stdout.splitlines() if "Codepoints" in l][0]
    assert header.startswith("Emoji  Codepoints")
    assert header.index("Codepoints") < header.index("Count") < header.index("Per 1k")


def test_density_top_n(tmp_path):
    text = " ".join([GRIN] * 5 + [ROCKET] * 3 + [HEART] * 1 + ["word"] * 20)
    (tmp_path / "a.txt").write_text(text, encoding="utf-8")
    res = run_emoji("--density", "--group-by", "emoji", "--top", "2", str(tmp_path))
    assert res.returncode == 0, res.stderr
    # Top 2 by count: GRIN (5) and ROCKET (3); HEART should be excluded
    assert GRIN in res.stdout
    assert ROCKET in res.stdout
    # HEART appears only in the TOTAL line count, not as its own row
    lines = [l for l in res.stdout.splitlines() if HEART in l]
    assert len(lines) == 0


def test_density_top_zero_shows_all(tmp_path):
    text = " ".join([GRIN] * 2 + [ROCKET] * 1 + [HEART] * 1 + ["word"] * 10)
    (tmp_path / "a.txt").write_text(text, encoding="utf-8")
    res = run_emoji("--density", "--group-by", "emoji", "--top", "0", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert GRIN in res.stdout
    assert ROCKET in res.stdout
    assert HEART in res.stdout


def test_density_group_by_combined(tmp_path):
    (tmp_path / "a.txt").write_text(f"{GRIN} {ROCKET} word word word", encoding="utf-8")
    res = run_emoji("--density", "--group-by", "all,category,emoji", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert "Emoji/1k" in res.stdout
    assert "Category" in res.stdout
    assert "Codepoints" in res.stdout


def test_density_does_not_modify_files(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text(f"x{GRIN}y", encoding="utf-8")
    res = run_emoji("--density", str(p))
    assert res.returncode == 0
    assert p.read_text(encoding="utf-8") == f"x{GRIN}y"


def test_density_rejects_fix():
    res = run_emoji("--density", "--fix", "x.txt")
    assert res.returncode == 2


def test_density_rejects_invalid_group_by():
    res = run_emoji("--density", "--group-by", "bogus", "x.txt")
    assert res.returncode == 2


def test_density_stdin():
    res = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--density"],
        input=f"one two{GRIN}three four five",
        capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    assert "<stdin>" in res.stdout
    # 5 words, 1 emoji -> 200.0
    assert "200.00" in res.stdout


