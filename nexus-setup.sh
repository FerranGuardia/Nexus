#!/usr/bin/env bash
# nexus-setup.sh — One-time permission setup for Nexus
#
# Grants all the macOS permissions Nexus needs in a single session.
# Run once, approve the prompts, and permissions persist forever.
#
# Usage:
#   chmod +x nexus-setup.sh && ./nexus-setup.sh

set -uo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

NEXUS_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$NEXUS_DIR/.venv/bin/python"

# Track results
declare -a CHECK_NAMES=()
declare -a CHECK_RESULTS=()

record() {
    CHECK_NAMES+=("$1")
    CHECK_RESULTS+=("$2")
}

header() {
    echo ""
    echo -e "${BOLD}${BLUE}[$1]${NC} $2"
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }

# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}Nexus Permission Setup${NC}"
echo "This script grants the macOS permissions Nexus needs."
echo "You'll approve some system prompts. Each one only appears once."
echo ""

# ---------------------------------------------------------------------------
# 1. Check Python venv
# ---------------------------------------------------------------------------
header "1/7" "Checking Python environment"

if [ -f "$VENV" ]; then
    ok "Found venv at $VENV"
else
    fail "No venv at $VENV — run: python3 -m venv .venv && pip install -e ."
    record "Python venv" "FAIL"
    echo ""
    echo -e "${RED}Cannot continue without Python venv. Exiting.${NC}"
    exit 1
fi
record "Python venv" "OK"

# ---------------------------------------------------------------------------
# 2. Accessibility permission
# ---------------------------------------------------------------------------
header "2/7" "Checking Accessibility permission"

AX_TRUSTED=$("$VENV" -c "
try:
    from ApplicationServices import AXIsProcessTrusted
    print('true' if AXIsProcessTrusted() else 'false')
except:
    print('false')
" 2>/dev/null)

if [ "$AX_TRUSTED" = "true" ]; then
    ok "Accessibility permission granted"
    record "Accessibility" "OK"
else
    fail "Accessibility permission NOT granted"
    info "Opening System Settings > Privacy & Security > Accessibility..."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || \
        open "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Accessibility" 2>/dev/null || \
        warn "Could not open System Settings — please navigate manually"
    echo ""
    warn "Add your terminal app (Terminal, VS Code, iTerm2, etc.) to the list."
    warn "Then re-run this script to verify."
    record "Accessibility" "MANUAL"
fi

# ---------------------------------------------------------------------------
# 3. Apple Events consent
# ---------------------------------------------------------------------------
header "3/7" "Triggering Apple Events permissions"
info "Each app will trigger a consent dialog. Click 'OK' / 'Allow' for each."
echo ""

APPS=("System Events" "Finder" "Safari" "Mail" "Calendar" "Reminders" "Notes" "Music" "Messages" "Terminal")
AE_PASS=0
AE_FAIL=0

for app in "${APPS[@]}"; do
    # Use perl alarm as macOS has no `timeout` command
    if perl -e 'alarm 8; exec @ARGV' osascript -e "tell application \"$app\" to return \"\"" >/dev/null 2>&1; then
        ok "$app — allowed"
        ((AE_PASS++)) || true
    else
        fail "$app — denied or timed out"
        ((AE_FAIL++)) || true
    fi
done

if [ "$AE_FAIL" -eq 0 ]; then
    record "Apple Events" "OK ($AE_PASS apps)"
else
    record "Apple Events" "PARTIAL ($AE_PASS ok, $AE_FAIL denied)"
    echo ""
    warn "Some apps were denied. To fix:"
    warn "  1. Run: tccutil reset AppleEvents"
    warn "  2. Re-run this script"
    warn "Or go to System Settings > Privacy & Security > Automation"
fi

# ---------------------------------------------------------------------------
# 4. Remove quarantine
# ---------------------------------------------------------------------------
header "4/7" "Removing quarantine attributes"

if xattr -lr "$NEXUS_DIR" 2>/dev/null | grep -q "com.apple.quarantine"; then
    xattr -dr com.apple.quarantine "$NEXUS_DIR" 2>/dev/null
    ok "Quarantine attributes removed from $NEXUS_DIR"
    record "Quarantine" "OK (cleared)"
else
    ok "No quarantine attributes found"
    record "Quarantine" "OK (clean)"
fi

# ---------------------------------------------------------------------------
# 5. Sudoers NOPASSWD
# ---------------------------------------------------------------------------
header "5/7" "Setting up sudoers for Nexus commands"

SUDOERS_FILE="/etc/sudoers.d/nexus"
CURRENT_USER=$(whoami)

SUDOERS_CONTENT="# Nexus automation — specific commands without password prompt
# Created by nexus-setup.sh — safe to remove with: sudo rm $SUDOERS_FILE
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/defaults
$CURRENT_USER ALL=(root) NOPASSWD: /usr/sbin/networksetup
$CURRENT_USER ALL=(root) NOPASSWD: /usr/sbin/periodic"

if [ -f "$SUDOERS_FILE" ]; then
    ok "Sudoers file already exists at $SUDOERS_FILE"
    record "Sudoers" "OK (exists)"
else
    echo "  This will create $SUDOERS_FILE with:"
    echo ""
    echo "$SUDOERS_CONTENT" | sed 's/^/    /'
    echo ""
    read -rp "  Create sudoers file? [y/N] " REPLY
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null
        sudo chmod 440 "$SUDOERS_FILE"
        if sudo visudo -c -f "$SUDOERS_FILE" >/dev/null 2>&1; then
            ok "Sudoers file created and validated"
            record "Sudoers" "OK"
        else
            fail "Sudoers file has syntax errors — removing"
            sudo rm -f "$SUDOERS_FILE"
            record "Sudoers" "FAIL"
        fi
    else
        warn "Skipped — some recipes may prompt for password"
        record "Sudoers" "SKIPPED"
    fi
fi

# ---------------------------------------------------------------------------
# 6. Screen Recording + Full Disk Access checks
# ---------------------------------------------------------------------------
header "6/7" "Checking Screen Recording & Full Disk Access"

SCREEN_REC=$("$VENV" -c "
try:
    from Quartz import (CGWindowListCreateImage, CGRectMake,
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault,
        CGImageGetWidth)
    img = CGWindowListCreateImage(
        CGRectMake(0, 0, 1, 1),
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault)
    print('true' if img and CGImageGetWidth(img) > 0 else 'false')
except:
    print('false')
" 2>/dev/null)

if [ "$SCREEN_REC" = "true" ]; then
    ok "Screen Recording permission granted"
    record "Screen Recording" "OK"
else
    fail "Screen Recording NOT granted (screenshots won't work)"
    warn "Enable in System Settings > Privacy & Security > Screen Recording"
    record "Screen Recording" "MANUAL"
fi

TCC_DB="$HOME/Library/Application Support/com.apple.TCC/TCC.db"
if [ -r "$TCC_DB" ]; then
    ok "Full Disk Access granted"
    record "Full Disk Access" "OK"
else
    warn "Full Disk Access not granted (optional, needed for some advanced features)"
    record "Full Disk Access" "off"
fi

# ---------------------------------------------------------------------------
# 7. Auto-dismiss preference
# ---------------------------------------------------------------------------
header "7/7" "Auto-dismiss safe dialogs"

CURRENT_PREF=$("$VENV" -c "
try:
    from nexus.mind.store import _get
    v = _get('auto_dismiss')
    print('true' if v in (True, 'true', 'True', '1') else 'false')
except:
    print('false')
" 2>/dev/null)

if [ "$CURRENT_PREF" = "true" ]; then
    ok "Auto-dismiss is already enabled"
    record "Auto-dismiss" "OK (on)"
else
    echo "  When enabled, Nexus automatically clicks 'Open' on Gatekeeper dialogs"
    echo "  and 'OK' on folder access prompts. Password and keychain dialogs"
    echo "  are NEVER auto-dismissed."
    echo ""
    read -rp "  Enable auto-dismiss for safe dialogs? [y/N] " REPLY
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        "$VENV" -c "from nexus.mind.store import memory; memory(op='set', key='auto_dismiss', value='true')" 2>/dev/null
        ok "Auto-dismiss enabled"
        record "Auto-dismiss" "OK (on)"
    else
        ok "Auto-dismiss stays off (agent will report dialogs for you to handle)"
        record "Auto-dismiss" "off"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Nexus Permission Summary${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

for i in "${!CHECK_NAMES[@]}"; do
    name="${CHECK_NAMES[$i]}"
    result="${CHECK_RESULTS[$i]}"
    if [[ "$result" == OK* ]]; then
        echo -e "  ${GREEN}✓${NC} $name: $result"
    elif [[ "$result" == MANUAL* || "$result" == PARTIAL* ]]; then
        echo -e "  ${YELLOW}!${NC} $name: $result"
    elif [[ "$result" == SKIP* || "$result" == off* ]]; then
        echo -e "  ${BLUE}–${NC} $name: $result"
    else
        echo -e "  ${RED}✗${NC} $name: $result"
    fi
done

echo ""

# Check if any manual steps remain
HAS_MANUAL=false
for result in "${CHECK_RESULTS[@]}"; do
    if [[ "$result" == MANUAL* || "$result" == FAIL* ]]; then
        HAS_MANUAL=true
        break
    fi
done

if [ "$HAS_MANUAL" = true ]; then
    echo -e "${YELLOW}Some permissions need manual steps (see above).${NC}"
    echo "Re-run this script after granting them to verify."
else
    echo -e "${GREEN}All permissions configured. Nexus is ready.${NC}"
fi
echo ""
