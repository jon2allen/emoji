#!/bin/csh -f
# setup.csh - Native FreeBSD / csh / tcsh setup script
# Supports interactive prompt or --noprompt / -y to install both automatically.

set SCRIPT_DIR = `dirname "$0"`
set SCRIPT_DIR = `cd "$SCRIPT_DIR" && pwd`
if ( ! -f "$SCRIPT_DIR/detect_emoji.py" || ! -f "$SCRIPT_DIR/pre-commit" ) then
    echo "Error: could not find detect_emoji.py and pre-commit next to setup.csh."
    exit 1
endif
set HOOKS_DIR = "$HOME/.git_hooks"
set BIN_DIR = "$HOME/.local/bin"

set INSTALL_HOOK = 0
set INSTALL_BIN = 0
set PROMPT_USER = 1

# Parse arguments
foreach arg ( $argv:q )
    switch ( "$arg" )
        case "--noprompt":
        case "-y":
        case "--all":
            set INSTALL_HOOK = 1
            set INSTALL_BIN = 1
            set PROMPT_USER = 0
            breaksw
        case "--hook-only":
            set INSTALL_HOOK = 1
            set INSTALL_BIN = 0
            set PROMPT_USER = 0
            breaksw
        case "--bin-only":
            set INSTALL_HOOK = 0
            set INSTALL_BIN = 1
            set PROMPT_USER = 0
            breaksw
        case "--help":
        case "-h":
            echo "Usage: ./setup.csh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --noprompt, -y, --all   Install both global Git hook and CLI tool without prompting"
            echo "  --hook-only             Install only global Git hook (~/.git_hooks)"
            echo "  --bin-only              Install only CLI tool (~/.local/bin)"
            echo "  -h, --help              Show this help message"
            exit 0
        default:
            echo "Unknown option: $arg"
            echo "Run ./setup.csh --help for available options."
            exit 1
    endsw
end

# Check non-interactive TTY
if ( $PROMPT_USER == 1 ) then
    # In csh, if stdin is not a terminal, do not proceed blindly
    if ( ! -t 0 ) then
        echo "Error: Non-interactive shell detected and no flag passed."
        echo "Please rerun with --noprompt, --hook-only, or --bin-only."
        exit 1
    endif

    echo "========================================================"
    echo "             Emoji Cleaner Setup (csh)"
    echo "========================================================"
    echo ""
    echo "What would you like to install?"
    echo "  1) Both: Global Git Hook (~/.git_hooks) AND CLI Tool (~/.local/bin) [Recommended]"
    echo "  2) Global Git Hook only (~/.git_hooks)"
    echo "  3) CLI Tool only (~/.local/bin)"
    echo "  4) Exit without installing"
    echo ""
    echo -n "Enter choice [1-4] (default: 1): "
    set choice = "$<"

    switch ( "$choice" )
        case "1":
        case "":
        case "both":
            set INSTALL_HOOK = 1
            set INSTALL_BIN = 1
            breaksw
        case "2":
        case "hook":
            set INSTALL_HOOK = 1
            set INSTALL_BIN = 0
            breaksw
        case "3":
        case "bin":
            set INSTALL_HOOK = 0
            set INSTALL_BIN = 1
            breaksw
        case "4":
        case "q":
        case "quit":
        case "exit":
            echo "Setup cancelled. No changes made."
            exit 0
        default:
            echo "Invalid selection: $choice. Aborting."
            exit 1
    endsw
endif

echo ""
echo "--------------------------------------------------------"

# 1. Install CLI Tool to ~/.local/bin
if ( $INSTALL_BIN == 1 ) then
    echo "[1/2] Installing CLI Tool to $BIN_DIR..."
    if ( ! -d "$BIN_DIR" ) then
        mkdir -p "$BIN_DIR"
    endif
    cp "$SCRIPT_DIR/detect_emoji.py" "$BIN_DIR/detect_emoji.py"
    chmod +x "$BIN_DIR/detect_emoji.py"
    echo "      -> Installed: $BIN_DIR/detect_emoji.py"
endif

# 2. Install Global Git Hook to ~/.git_hooks
if ( $INSTALL_HOOK == 1 ) then
    echo "[2/2] Installing Global Git Hook to $HOOKS_DIR..."

    # Check if a previous custom core.hooksPath was configured
    set PREV_HOOKS = "`git config --global core.hooksPath`"
    if ( "$PREV_HOOKS" != "" && "$PREV_HOOKS" != "$HOOKS_DIR" ) then
        echo "      WARNING: Previous global core.hooksPath was set to: $PREV_HOOKS"
        echo "      Backing up previous setting in git config as 'core.hooksPathBackup'"
        git config --global core.hooksPathBackup "$PREV_HOOKS"
    endif

    if ( ! -d "$HOOKS_DIR" ) then
        mkdir -p "$HOOKS_DIR"
    endif

    set BOTH_INSTALLED = 0
    if ( -f "$HOOKS_DIR/detect_emdash.py" ) then
        set BOTH_INSTALLED = 1
    endif

    if ( -f "$HOOKS_DIR/detect_emoji.py" ) then
        cmp -s "$SCRIPT_DIR/detect_emoji.py" "$HOOKS_DIR/detect_emoji.py"
        if ( $status == 0 ) then
            echo "      NOTE: detect_emoji.py in $HOOKS_DIR is already up to date (identical file)."
        else
            set OLD_SIZE = `wc -c < "$HOOKS_DIR/detect_emoji.py" | tr -d ' '`
            set NEW_SIZE = `wc -c < "$SCRIPT_DIR/detect_emoji.py" | tr -d ' '`
            echo "      NOTE: Updating existing detect_emoji.py in $HOOKS_DIR ($OLD_SIZE bytes -> $NEW_SIZE bytes)."
        endif
    endif

    if ( -f "$HOOKS_DIR/pre-commit-emoji" ) then
        rm -f "$HOOKS_DIR/pre-commit-emoji"
        echo "      NOTE: Removed redundant pre-commit-emoji sibling to prevent hook loops."
    endif

    # Preserve a different hook already occupying the pre-commit slot (for
    # example the em-dash cleaner). The new hook chains to pre-commit-emdash /
    # pre-commit-legacy siblings, so preserved hooks keep running.
    if ( -f "$HOOKS_DIR/pre-commit" ) then
        cmp -s "$HOOKS_DIR/pre-commit" "$SCRIPT_DIR/pre-commit"
        if ( $status != 0 ) then
            grep -q "detect_emoji" "$HOOKS_DIR/pre-commit"
            if ( $status == 0 ) then
                echo "      NOTE: Updating existing emoji pre-commit hook in place."
            else
                grep -q "detect_emdash" "$HOOKS_DIR/pre-commit"
                if ( $status == 0 ) then
                    set BOTH_INSTALLED = 1
                    set PRESERVE_AS = "$HOOKS_DIR/pre-commit-emdash"
                    mv "$HOOKS_DIR/pre-commit" "$PRESERVE_AS"
                    echo "      NOTE: Existing emdash pre-commit hook preserved as pre-commit-emdash (chained automatically)."
                else
                    set PRESERVE_AS = "$HOOKS_DIR/pre-commit-legacy"
                    # Never overwrite a previously preserved unknown hook: bump the numeric suffix
                    if ( -f "$PRESERVE_AS" ) then
                        @ N = 1
                        while ( -f "$PRESERVE_AS.$N" )
                            @ N = $N + 1
                        end
                        set PRESERVE_AS = "$PRESERVE_AS.$N"
                    endif
                    mv "$HOOKS_DIR/pre-commit" "$PRESERVE_AS"
                    echo "      NOTE: Existing pre-commit hook preserved as `basename $PRESERVE_AS` (chained automatically)."
                endif
            endif
        endif
    endif

    cp "$SCRIPT_DIR/detect_emoji.py" "$HOOKS_DIR/detect_emoji.py"
    cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
    chmod +x "$HOOKS_DIR/detect_emoji.py"
    chmod +x "$HOOKS_DIR/pre-commit"

    git config --global core.hooksPath "$HOOKS_DIR"
    set CURRENT_PATH = `git config --global core.hooksPath`
    echo "      -> Installed: $HOOKS_DIR/pre-commit"
    echo "      -> Configured git core.hooksPath = $CURRENT_PATH"

    if ( $BOTH_INSTALLED == 1 ) then
        echo ""
        echo "      WARNING: Both detect_emoji.py and detect_emdash.py are installed in $HOOKS_DIR."
        echo "               They are chained to run together. If you ever encounter hook issues,"
        echo "               delete $HOOKS_DIR and re-run setup.csh to start fresh:"
        echo "                   rm -rf $HOOKS_DIR && ./setup.csh"
    endif
endif

echo "--------------------------------------------------------"
echo "Setup completed successfully!"
if ( $INSTALL_HOOK == 1 ) then
    echo "* 'git commit' in any repo will check and clean emoji safely."
    echo "* Note: Repo-local .git/hooks/pre-commit and the em-dash sibling hook still run."
endif
if ( $INSTALL_BIN == 1 ) then
    echo "* Run 'detect_emoji.py --help' to use the CLI tool manually anytime."
endif
echo "========================================================"
