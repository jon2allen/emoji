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
