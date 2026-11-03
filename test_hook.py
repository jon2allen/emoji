import os
import shutil
import subprocess
import sys

import pytest

SRC = os.path.dirname(os.path.abspath(__file__))
EM = '\U0001F600'.encode('utf-8')
SHELLS = [s for s in ('sh', 'dash') if shutil.which(s)]


@pytest.fixture
def env(tmp_path):
    home = tmp_path / 'home'
    hooks = home / '.git_hooks'
    hooks.mkdir(parents=True)
    shutil.copy(os.path.join(SRC, 'detect_emoji.py'), hooks)
    shutil.copy(os.path.join(SRC, 'pre-commit'), hooks)
    e = dict(os.environ, HOME=str(home), GIT_CONFIG_NOSYSTEM='1',
             GIT_CONFIG_GLOBAL=str(home / '.gitconfig'))
    return e, str(hooks)


@pytest.fixture(params=SHELLS)
def repo(request, env, tmp_path):
    e, hooks = env
    # Run the hook through the shell under test via a wrapper
    wrapper = os.path.join(hooks, 'wrapped')
    os.makedirs(wrapper)
    with open(os.path.join(wrapper, 'pre-commit'), 'w') as f:
        f.write(f'#!/bin/sh\nexec {request.param} "{hooks}/pre-commit" "$@"\n')
    os.chmod(os.path.join(wrapper, 'pre-commit'), 0o755)
    r = tmp_path / 'repo'
    r.mkdir()
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=r, env=e, check=check,
                              capture_output=True, text=True)
    git('init', '-q')
    git('config', 'user.name', 't')
    git('config', 'user.email', 't@example.test')
    git('config', 'core.hooksPath', wrapper)
    return r, git


def head(git, name):
    return subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=git_cwd(git),
                          capture_output=True).stdout


def git_cwd(git):
    return git('rev-parse', '--show-toplevel').stdout.strip()


def test_fixes_and_commits(repo):
    r, git = repo
    (r / 'f').write_bytes(b'a' + EM + b'b\n')
    git('add', 'f')
    git('commit', '-qm', 'c')
    assert head(git, 'f') == b'ab\n'


def test_non_ascii_and_dash_filenames(repo):
    r, git = repo
    for name in ('caf\u00e9 x.txt', '-x.txt'):
        (r / name).write_bytes(b'a' + EM + b'b\n')
        git('add', '--', name)
    git('commit', '-qm', 'c')
    assert head(git, './-x.txt') == b'ab\n'
    assert head(git, 'caf\u00e9 x.txt') == b'ab\n'


def test_unstaged_edits_not_swept_in(repo):
    r, git = repo
    (r / 'f').write_text('a\nb\n')
    git('add', 'f')
    git('commit', '-qm', 'i')
    (r / 'f').write_text('A\nb\n')
    git('add', 'f')
    (r / 'f').write_text('A\nWIP\n')
    git('commit', '-qm', 'c')
    assert head(git, 'f') == b'A\nb\n'


def test_rejects_when_emoji_staged_with_unstaged_edits(repo):
    r, git = repo
    (r / 'f').write_bytes(b'a' + EM + b'b\n')
    git('add', 'f')
    (r / 'f').write_text('clean\n')
    assert git('commit', '-qm', 'c', check=False).returncode == 1


def test_binary_with_unstaged_edits_allowed(repo):
    r, git = repo
    (r / 'p').write_bytes(b'\x89PNG\xff\xfe')
    git('add', 'p')
    (r / 'p').write_bytes(b'\x89PNG\xff\xfc')
    git('commit', '-qm', 'c')


def test_partial_commit_rejected_and_index_untouched(repo):
    r, git = repo
    (r / 'a').write_text('x\n')
    git('add', 'a')
    git('commit', '-qm', 'i')
    (r / 'a').write_bytes(b'a' + EM + b'b\n')
    assert git('commit', '-qm', 'c', 'a', check=False).returncode == 1
    assert head(git, 'a') == b'x\n'


def test_gitattributes_exemption(repo):
    r, git = repo
    (r / '.gitattributes').write_text('keep.txt -emoji\n')
    (r / 'keep.txt').write_bytes(b'a' + EM + b'b\n')
    git('add', '.')
    git('commit', '-qm', 'c')
    assert EM in head(git, 'keep.txt')


def test_keycap_commits_to_ascii_digit(repo):
    r, git = repo
    (r / 'f').write_bytes(b'1\xef\xb8\x8f\xe2\x83\xa3 x\n')
    git('add', 'f')
    git('commit', '-qm', 'c')
    assert head(git, 'f') == b'1 x\n'


def test_hook_format_drops_stranded_space(repo):
    r, git = repo
    (r / 'f').write_bytes(b'radiator \xf0\x9f\x94\xa5,\n')
    git('add', 'f')
    git('commit', '-qm', 'c')
    assert head(git, 'f') == b'radiator,\n'


def test_unwritable_file_rejected(repo):
    if os.geteuid() == 0:
        pytest.skip('root ignores permissions')
    r, git = repo
    (r / 'a').write_bytes(b'a' + EM + b'b\n')
    git('add', 'a')
    os.chmod(r, 0o555)
    try:
        assert git('commit', '-qm', 'c', check=False).returncode == 1
    finally:
        os.chmod(r, 0o755)


def test_git_dir_invocation(repo):
    r, git = repo
    (r / 'f').write_bytes(b'a' + EM + b'b\n')
    git('add', 'f')
    git('--git-dir=.git', '--work-tree=.', 'commit', '-qm', 'c')
    assert head(git, 'f') == b'ab\n'


def test_local_hook_chained(env, tmp_path):
    e, hooks = env
    r = tmp_path / 'r'
    r.mkdir()
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=r, env=e, check=check,
                              capture_output=True, text=True)
    git('config', '--global', 'core.hooksPath', hooks)
    git('config', '--global', 'user.name', 't')
    git('config', '--global', 'user.email', 't@example.test')
    git('init', '-q')
    local = r / '.git' / 'hooks' / 'pre-commit'
    local.write_text('#!/bin/sh\nexit 3\n')
    local.chmod(0o755)
    (r / 'a').write_text('x\n')
    git('add', 'a')
    assert git('commit', '-qm', 'c', check=False).returncode == 1


def test_sibling_hook_failure_blocks_commit(env, tmp_path):
    e, hooks = env
    sib = os.path.join(hooks, 'pre-commit-emdash')
    with open(sib, 'w') as f:
        f.write('#!/bin/sh\nexit 3\n')
    os.chmod(sib, 0o755)
    r = tmp_path / 'r'
    r.mkdir()
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=r, env=e, check=check,
                              capture_output=True, text=True)
    git('config', '--global', 'core.hooksPath', hooks)
    git('config', '--global', 'user.name', 't')
    git('config', '--global', 'user.email', 't@example.test')
    git('init', '-q')
    (r / 'a').write_text('x\n')
    git('add', 'a')
    assert git('commit', '-qm', 'c', check=False).returncode == 1


def test_sibling_hook_runs_then_scan_still_fixes(env, tmp_path):
    e, hooks = env
    sib = os.path.join(hooks, 'pre-commit-emdash')
    with open(sib, 'w') as f:
        f.write('#!/bin/sh\ntouch sibling_ran\n')
    os.chmod(sib, 0o755)
    r = tmp_path / 'r'
    r.mkdir()
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=r, env=e, check=check,
                              capture_output=True, text=True)
    git('config', '--global', 'core.hooksPath', hooks)
    git('config', '--global', 'user.name', 't')
    git('config', '--global', 'user.email', 't@example.test')
    git('init', '-q')
    (r / 'f').write_bytes(b'a' + EM + b'b\n')
    git('add', 'f')
    git('commit', '-qm', 'c')
    assert (r / 'sibling_ran').exists()
    assert head(git, 'f') == b'ab\n'


def run_cli(tmp_path, *args):
    return subprocess.run([sys.executable, os.path.join(SRC, 'detect_emoji.py'), *args],
                          cwd=tmp_path, capture_output=True, text=True)


def test_binary_passes_exit_code(tmp_path):
    (tmp_path / 'p').write_bytes(b'\xff\xfe')
    assert run_cli(tmp_path, '-q', '--exit-code', 'p').returncode == 0


def test_soft_hyphen_deleted_wave_dash_kept(tmp_path):
    f = tmp_path / 't'
    f.write_text('ok\ufe0f there 5\u301c10\n', encoding='utf-8')
    run_cli(tmp_path, '-q', '--fix', 't')
    assert f.read_text(encoding='utf-8') == 'ok there 5\u301c10\n'


def run_stdin(tmp_path, data, *args):
    return subprocess.run([sys.executable, os.path.join(SRC, 'detect_emoji.py'), *args],
                          cwd=tmp_path, input=data, capture_output=True)


def test_piped_stdin_auto_detected(tmp_path):
    r = run_stdin(tmp_path, b'ok\na' + EM + b'b\n', '--exit-code')
    assert r.returncode == 1
    assert b'<stdin>:2:' in r.stdout


def test_stdin_fix_is_a_clean_filter(tmp_path):
    r = run_stdin(tmp_path, b'a' + EM + b'b\r\n\xff\n', '--fix', '-')
    assert r.stdout == b'ab\r\n\xff\n'
    assert b'SUMMARY' in r.stderr


def test_stdin_fix_format(tmp_path):
    r = run_stdin(tmp_path, b'word ' + EM + b', end\n', '--fix', '--format', '-')
    assert r.stdout == b'word, end\n'


def test_dev_null_stdin_still_scans_directory(tmp_path):
    (tmp_path / 'f').write_bytes(b'a' + EM + b'b\n')
    r = subprocess.run([sys.executable, os.path.join(SRC, 'detect_emoji.py'), '--exit-code', '-q'],
                       cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True)
    assert r.returncode == 1
