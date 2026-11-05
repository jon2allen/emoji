#!/bin/sh
# setup.sh - Portable POSIX setup script for macOS, Linux, and FreeBSD (sh/bash)
# Supports interactive prompt or --noprompt / -y to install both automatically.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$HOME/.git_hooks"
BIN_DIR="$HOME/.local/bin"

INSTALL_HOOK=0
INSTALL_BIN=0
HAS_FLAG=0

# Parse command line options
for arg in "$@"; do
    case "$arg" in
        --noprompt|-y|--all)
            INSTALL_HOOK=1
            INSTALL_BIN=1
            HAS_FLAG=1
            ;;
        --hook-only)
            INSTALL_HOOK=1
            INSTALL_BIN=0
            HAS_FLAG=1
            ;;
        --bin-only)
            INSTALL_HOOK=0
            INSTALL_BIN=1
            HAS_FLAG=1
            ;;
        --help|-h)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --noprompt, -y, --all   Install both global Git hook and CLI tool without prompting"
            echo "  --hook-only             Install only global Git hook (~/.git_hooks)"
            echo "  --bin-only              Install only CLI tool (~/.local/bin)"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Run ./setup.sh --help for available options." >&2
            exit 1
            ;;
    esac
done

# If no flags passed, check if running in an interactive terminal
if [ "$HAS_FLAG" -eq 0 ]; then
    if [ ! -t 0 ]; then
        echo "Error: Non-interactive shell detected and no installation flag passed." >&2
        echo "Please rerun with --noprompt, --hook-only, or --bin-only." >&2
        exit 1
    fi

    echo "========================================================"
    echo "             Emoji Cleaner Setup"
    echo "========================================================"
    echo ""
    echo "What would you like to install?"
    echo "  1) Both: Global Git Hook (~/.git_hooks) AND CLI Tool (~/.local/bin) [Recommended]"
    echo "  2) Global Git Hook only (~/.git_hooks)"
    echo "  3) CLI Tool only (~/.local/bin)"
    echo "  4) Exit without installing"
    echo ""
    printf "Enter choice [1-4] (default: 1): "
    read -r choice || choice=""

    case "$choice" in
        1|""|"both"|"b")
            INSTALL_HOOK=1
            INSTALL_BIN=1
            ;;
        2|"hook"|"h")
            INSTALL_HOOK=1
            INSTALL_BIN=0
            ;;
        3|"bin")
            INSTALL_HOOK=0
            INSTALL_BIN=1
            ;;
        4|"q"|"quit"|"exit")
            echo "Setup cancelled. No changes made."
            exit 0
            ;;
        *)
            echo "Invalid selection: $choice. Aborting." >&2
            exit 1
            ;;
    esac
fi

echo ""
echo "--------------------------------------------------------"

# 1. Install CLI Tool to ~/.local/bin
if [ "$INSTALL_BIN" -eq 1 ]; then
    echo "[1/2] Installing CLI Tool to $BIN_DIR..."
    mkdir -p "$BIN_DIR"
    cp "$SCRIPT_DIR/detect_emoji.py" "$BIN_DIR/detect_emoji.py"
    chmod +x "$BIN_DIR/detect_emoji.py"
    echo "      -> Installed: $BIN_DIR/detect_emoji.py"

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            echo "      NOTE: $BIN_DIR is not currently in your PATH."
            echo "            Add it with: export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac
fi

# 2. Install Global Git Hook to ~/.git_hooks
if [ "$INSTALL_HOOK" -eq 1 ]; then
    echo "[2/2] Installing Global Git Hook to $HOOKS_DIR..."

    # Check if a previous custom core.hooksPath was configured
    PREV_HOOKS=$(git config --global core.hooksPath 2>/dev/null || echo "")
    if [ -n "$PREV_HOOKS" ] && [ "$PREV_HOOKS" != "$HOOKS_DIR" ]; then
        echo "      WARNING: Previous global core.hooksPath was set to: $PREV_HOOKS"
        echo "      Backing up previous setting in git config as 'core.hooksPathBackup'"
        git config --global core.hooksPathBackup "$PREV_HOOKS"
    fi

    mkdir -p "$HOOKS_DIR"

    # Check if both emoji and emdash are already present in ~/.git_hooks
    BOTH_INSTALLED=0
    if [ -f "$HOOKS_DIR/detect_emdash.py" ]; then
        BOTH_INSTALLED=1
    fi

    # Check if this exact version of detect_emoji.py is already installed
    if [ -f "$HOOKS_DIR/detect_emoji.py" ]; then
        if cmp -s "$SCRIPT_DIR/detect_emoji.py" "$HOOKS_DIR/detect_emoji.py"; then
            echo "      NOTE: detect_emoji.py in $HOOKS_DIR is already up to date (identical file)."
        else
            OLD_SIZE=$(wc -c < "$HOOKS_DIR/detect_emoji.py" | tr -d ' ')
            NEW_SIZE=$(wc -c < "$SCRIPT_DIR/detect_emoji.py" | tr -d ' ')
            echo "      NOTE: Updating existing detect_emoji.py in $HOOKS_DIR ($OLD_SIZE bytes -> $NEW_SIZE bytes)."
        fi
    fi

    # Remove any stale pre-commit-emoji sibling so emoji and emdash never chain in a loop
    if [ -f "$HOOKS_DIR/pre-commit-emoji" ]; then
        rm -f "$HOOKS_DIR/pre-commit-emoji"
        echo "      NOTE: Removed redundant pre-commit-emoji sibling to prevent hook loops."
    fi

    # Preserve a different hook already occupying the pre-commit slot (for
    # example the em-dash cleaner). The new hook chains to pre-commit-emdash /
    # pre-commit-legacy siblings, so preserved hooks keep running.
    if [ -f "$HOOKS_DIR/pre-commit" ] && ! cmp -s "$HOOKS_DIR/pre-commit" "$SCRIPT_DIR/pre-commit"; then
        if grep -q "detect_emoji" "$HOOKS_DIR/pre-commit" 2>/dev/null; then
            echo "      NOTE: Updating existing emoji pre-commit hook in place."
        elif grep -q "detect_emdash" "$HOOKS_DIR/pre-commit" 2>/dev/null; then
            BOTH_INSTALLED=1
            PRESERVE_AS="$HOOKS_DIR/pre-commit-emdash"
            mv "$HOOKS_DIR/pre-commit" "$PRESERVE_AS"
            echo "      NOTE: Existing emdash pre-commit hook preserved as pre-commit-emdash (chained automatically)."
        else
            PRESERVE_AS="$HOOKS_DIR/pre-commit-legacy"
            # Never overwrite a previously preserved unknown hook: bump the numeric suffix
            if [ -f "$PRESERVE_AS" ]; then
                N=1
                while [ -f "$PRESERVE_AS.$N" ]; do
                    N=$((N + 1))
                done
                PRESERVE_AS="$PRESERVE_AS.$N"
            fi
            mv "$HOOKS_DIR/pre-commit" "$PRESERVE_AS"
            echo "      NOTE: Existing pre-commit hook preserved as $(basename "$PRESERVE_AS") (chained automatically)."
        fi
    fi

    cp "$SCRIPT_DIR/detect_emoji.py" "$HOOKS_DIR/detect_emoji.py"
    cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
    chmod +x "$HOOKS_DIR/detect_emoji.py"
    chmod +x "$HOOKS_DIR/pre-commit"

    git config --global core.hooksPath "$HOOKS_DIR"
    echo "      -> Installed: $HOOKS_DIR/pre-commit"
    echo "      -> Configured git core.hooksPath = $(git config --global core.hooksPath)"

    if [ "$BOTH_INSTALLED" -eq 1 ]; then
        echo ""
        echo "      WARNING: Both detect_emoji.py and detect_emdash.py are installed in $HOOKS_DIR."
        echo "               They are chained to run together. If you ever encounter hook issues,"
        echo "               delete $HOOKS_DIR and re-run setup.sh to start fresh:"
        echo "                   rm -rf $HOOKS_DIR && ./setup.sh"
    fi
fi

echo "--------------------------------------------------------"
echo "Setup completed successfully!"
if [ "$INSTALL_HOOK" -eq 1 ]; then
    echo "* 'git commit' in any repo will check and clean emoji safely."
    echo "* Note: Repo-local .git/hooks/pre-commit and the em-dash sibling hook still run."
fi
if [ "$INSTALL_BIN" -eq 1 ]; then
    echo "* Run 'detect_emoji.py --help' to use the CLI tool manually anytime."
fi
echo "========================================================"
