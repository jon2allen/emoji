#!/usr/bin/env bash
# test_commit_hook.sh - Self-contained test: installs a temporary local hook in .git/hooks,
# runs a test commit to verify local + global hook execution, and resets everything.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || echo ".git")"
HOOKS_DIR="$GIT_DIR/hooks"
LOCAL_HOOK="$HOOKS_DIR/pre-commit"
BACKUP_HOOK="$HOOKS_DIR/pre-commit.test_backup.$$"
TEST_FILE="test_emoji_sample.txt"
COMMIT_CREATED=0

# 1. Back up any existing local hook
HAD_PREV_HOOK=0
if [ -f "$LOCAL_HOOK" ]; then
    HAD_PREV_HOOK=1
    mv "$LOCAL_HOOK" "$BACKUP_HOOK"
fi

# Cleanup handler: restores local hook and removes test file on exit or interrupt
cleanup() {
    # If a commit was left un-reset, rewind it safely without wiping other uncommitted files
    if [ "$COMMIT_CREATED" -eq 1 ]; then
        git reset HEAD~1 >/dev/null 2>&1 || true
    fi

    # Remove temporary test file if present
    rm -f "$TEST_FILE"

    # Restore or remove the local hook
    if [ "$HAD_PREV_HOOK" -eq 1 ]; then
        if [ -f "$BACKUP_HOOK" ]; then
            mv "$BACKUP_HOOK" "$LOCAL_HOOK"
        fi
    else
        rm -f "$LOCAL_HOOK"
    fi
}
trap cleanup EXIT INT TERM ERR

echo "========================================================================"
echo " 1. Setting up temporary local hook in $LOCAL_HOOK"
echo "========================================================================"
mkdir -p "$HOOKS_DIR"
cat << 'EOF' > "$LOCAL_HOOK"
#!/bin/sh
echo "========================================================"
echo "[Local Repo Hook] Executing .git/hooks/pre-commit"
echo "========================================================"
git diff --cached --name-only --diff-filter=d | while IFS= read -r file; do
    if [ -f "$file" ]; then
        bytes=$(wc -c < "$file" | tr -d ' ')
        echo "  [staged file] $file (${bytes} bytes)"
    fi
done
echo "========================================================"
exit 0
EOF
chmod +x "$LOCAL_HOOK"
echo "Installed temporary local hook at $LOCAL_HOOK"

echo ""
echo "========================================================================"
echo " 2. Creating test file with emojis"
echo "========================================================================"
cat << 'EOF' > "$TEST_FILE"
First line with cat emoji: 🐱
Second line with rocket emoji: 🚀
Third line with checkmark and fire: ✅ 🔥
EOF

echo "File created: $TEST_FILE"
echo "Original content:"
cat "$TEST_FILE"

echo ""
echo "========================================================================"
echo " 3. Staging file with 'git add'"
echo "========================================================================"
git add "$TEST_FILE"
git status --short "$TEST_FILE"

echo ""
echo "========================================================================"
echo " 4. Running 'git commit' (triggers local hook + global emoji cleaner)"
echo "========================================================================"
git commit -m "test: verify local hook and global emoji cleaner execution"
COMMIT_CREATED=1

echo ""
echo "========================================================================"
echo " 5. Verifying commit result"
echo "========================================================================"
echo "Commit log (most recent commit):"
git log -1 --oneline

echo ""
echo "Content of committed file (emojis cleaned by global hook):"
cat "$TEST_FILE"

echo ""
echo "========================================================================"
echo " 6. Performing 'git reset HEAD~1' (resets commit and cleans test file)"
echo "========================================================================"
git reset HEAD~1
rm -f "$TEST_FILE"
COMMIT_CREATED=0

echo ""
echo "========================================================================"
echo " 7. Restoring original local hook state"
echo "========================================================================"
if [ "$HAD_PREV_HOOK" -eq 1 ]; then
    mv "$BACKUP_HOOK" "$LOCAL_HOOK"
    echo "Restored previous local hook at $LOCAL_HOOK"
else
    rm -f "$LOCAL_HOOK"
    echo "Removed temporary local hook ($LOCAL_HOOK was not present prior to test)."
fi
# Disable trap so it doesn't run again on clean exit
trap - EXIT INT TERM ERR

echo ""
echo "Current git status:"
git status --short

echo ""
echo "Test completed successfully! Working tree and hooks are fully restored."
