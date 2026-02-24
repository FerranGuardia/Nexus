"""Nexus Control Panel — floating HUD for monitoring and controlling Nexus.

Launch: python -m nexus.panel

Shows live pipeline status (which step is executing), elapsed time,
recent action log, and lets you pause/resume or send hints to Claude.
Communicates with the MCP server through ~/.nexus/state.json.
"""

import time
import objc
from AppKit import (
    NSApplication, NSApp, NSWindow, NSPanel,
    NSBackingStoreBuffered, NSMakeRect,
    NSFloatingWindowLevel, NSTitledWindowMask, NSClosableWindowMask,
    NSUtilityWindowMask, NSNonactivatingPanelMask,
    NSTextField, NSButton, NSFont, NSColor,
    NSBezelStyleRounded,
    NSTextAlignmentLeft, NSTextAlignmentRight, NSLineBreakByTruncatingTail,
    NSLineBreakByWordWrapping,
    NSScreen, NSTimer, NSRunLoop, NSDefaultRunLoopMode,
    NSApplicationActivationPolicyAccessory,
    NSScrollView, NSTextView,
    NSBorderlessWindowMask,
)
from nexus.state import read_state, write_state

# Window size
W, H = 340, 380
POLL_INTERVAL = 0.3  # seconds


def _color(hex_str):
    """Convert hex color to NSColor."""
    r = int(hex_str[1:3], 16) / 255
    g = int(hex_str[3:5], 16) / 255
    b = int(hex_str[5:7], 16) / 255
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)


BG = _color("#1a1a1a")
FG = _color("#cccccc")
FG_DIM = _color("#666666")
GREEN = _color("#4ec9b0")
RED = _color("#f44747")
YELLOW = _color("#dcdcaa")
BLUE = _color("#569cd6")
ORANGE = _color("#ce9178")
INPUT_BG = _color("#2d2d2d")
LOG_BG = _color("#222222")


def _make_label(frame, text, x, y, w, h, color=None, size=12, bold=False, align=None, wrap=False):
    """Create a non-editable text label."""
    label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setTextColor_(color or FG)
    font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    label.setFont_(font)
    if wrap:
        label.setLineBreakMode_(NSLineBreakByWordWrapping)
        label.setMaximumNumberOfLines_(2)
    else:
        label.setLineBreakMode_(NSLineBreakByTruncatingTail)
    if align == "right":
        label.setAlignment_(NSTextAlignmentRight)
    frame.addSubview_(label)
    return label


def _make_input(frame, placeholder, x, y, w, h):
    """Create an editable text input field."""
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    field.setPlaceholderString_(placeholder)
    field.setFont_(NSFont.systemFontOfSize_(11))
    field.setTextColor_(FG)
    field.setBackgroundColor_(INPUT_BG)
    field.setBezeled_(True)
    field.setEditable_(True)
    frame.addSubview_(field)
    return field


class PanelDelegate(objc.lookUpClass("NSObject")):
    """Handles button clicks and timer polling."""

    panel = objc.ivar()
    # Status area
    dot_label = objc.ivar()
    action_label = objc.ivar()
    elapsed_label = objc.ivar()
    step_label = objc.ivar()
    # Log area
    log_view = objc.ivar()
    # Error
    error_label = objc.ivar()
    # Controls
    pause_btn = objc.ivar()
    hint_field = objc.ivar()
    # State
    paused = objc.ivar()
    last_log_len = objc.ivar()

    def init(self):
        self = objc.super(PanelDelegate, self).init()
        if self:
            self.paused = False
            self.last_log_len = 0
        return self

    @objc.typedSelector(b"v@:@")
    def togglePause_(self, sender):
        self.paused = not self.paused
        write_state(paused=self.paused)
        if self.paused:
            self.pause_btn.setTitle_("\u25b6  Resume")
        else:
            self.pause_btn.setTitle_("\u23f8  Pause")

    @objc.typedSelector(b"v@:@")
    def sendHint_(self, sender):
        hint = str(self.hint_field.stringValue()).strip()
        if hint:
            write_state(hint=hint, hint_ts=time.time())
            self.hint_field.setStringValue_("")

    @objc.typedSelector(b"v@:@")
    def poll_(self, timer):
        """Read state.json and update the display."""
        try:
            state = read_state()
            status = state.get("status", "idle")
            action = state.get("action", "")
            step = state.get("step", "")
            error = state.get("error", "")
            start_ts = state.get("start_ts", 0)
            paused = state.get("paused", False)
            log = state.get("log", [])

            # --- Status dot ---
            if status == "running":
                self.dot_label.setTextColor_(YELLOW)
            elif status == "done":
                self.dot_label.setTextColor_(GREEN)
            elif status == "failed":
                self.dot_label.setTextColor_(RED)
            else:
                self.dot_label.setTextColor_(FG_DIM)

            # --- Action text ---
            tool = state.get("tool", "")
            if action:
                prefix = f"[{tool}] " if tool else ""
                display = prefix + action
                if len(display) > 45:
                    display = display[:42] + "..."
                self.action_label.setStringValue_(display)
            else:
                self.action_label.setStringValue_("Idle")

            # --- Elapsed time ---
            if status == "running" and start_ts:
                elapsed = time.time() - start_ts
                if elapsed < 60:
                    elapsed_str = f"{elapsed:.1f}s"
                else:
                    elapsed_str = f"{elapsed/60:.0f}m{elapsed%60:.0f}s"
                self.elapsed_label.setStringValue_(elapsed_str)
                # Color warning for slow actions
                if elapsed > 5:
                    self.elapsed_label.setTextColor_(RED)
                elif elapsed > 2:
                    self.elapsed_label.setTextColor_(ORANGE)
                else:
                    self.elapsed_label.setTextColor_(FG_DIM)
            elif status in ("done", "failed") and log:
                last = log[-1]
                e = last.get("elapsed", 0)
                self.elapsed_label.setStringValue_(f"{e}s")
                self.elapsed_label.setTextColor_(FG_DIM)
            else:
                self.elapsed_label.setStringValue_("")

            # --- Current step ---
            if step and status == "running":
                self.step_label.setStringValue_(f"\u2192 {step}")
                self.step_label.setTextColor_(BLUE)
            elif status == "done" and action:
                self.step_label.setStringValue_("\u2713 Done")
                self.step_label.setTextColor_(GREEN)
            elif status == "failed":
                self.step_label.setStringValue_("\u2717 Failed")
                self.step_label.setTextColor_(RED)
            else:
                self.step_label.setStringValue_("")

            # --- Error ---
            if error and status == "failed":
                display_err = error[:100] + ("..." if len(error) > 100 else "")
                self.error_label.setStringValue_(display_err)
            else:
                self.error_label.setStringValue_("")

            # --- Log (only update if changed) ---
            if len(log) != self.last_log_len:
                self.last_log_len = len(log)
                self._update_log(log)

            # --- Sync pause ---
            if paused != self.paused:
                self.paused = paused
                if self.paused:
                    self.pause_btn.setTitle_("\u25b6  Resume")
                else:
                    self.pause_btn.setTitle_("\u23f8  Pause")

        except Exception:
            pass

    def _update_log(self, log):
        """Rebuild the log text view."""
        if not self.log_view:
            return
        lines = []
        # Show last 10 entries
        recent = log[-10:]
        for entry in recent:
            icon = "\u2713" if entry.get("status") == "done" else "\u2717"
            action = entry.get("action", "?")
            elapsed = entry.get("elapsed", 0)
            tool = entry.get("tool", "")
            prefix = f"[{tool}] " if tool else ""
            if len(action) > 30:
                action = action[:27] + "..."
            line = f" {icon} {prefix}{action}  {elapsed}s"
            err = entry.get("error", "")
            if err:
                err_short = err[:40] + ("..." if len(err) > 40 else "")
                line += f"\n    {err_short}"
            lines.append(line)
        text = "\n".join(lines) if lines else " (no actions yet)"
        self.log_view.textStorage().mutableString().setString_(text)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Position: bottom-right of screen
    screen = NSScreen.mainScreen().frame()
    sx = screen.size.width - W - 20
    sy = 60  # above dock

    # Create floating panel
    mask = NSTitledWindowMask | NSClosableWindowMask | NSUtilityWindowMask | NSNonactivatingPanelMask
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(sx, sy, W, H), mask, NSBackingStoreBuffered, False,
    )
    panel.setTitle_("Nexus")
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setAlphaValue_(0.93)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    panel.setBackgroundColor_(BG)

    content = panel.contentView()
    pad = 12
    y = H - 35  # top-down layout (flipped Y)

    # ===== Status row: dot + action + elapsed =====
    dot = _make_label(content, "\u25cf", pad, y, 18, 20, color=FG_DIM, size=14)
    action_lbl = _make_label(content, "Idle", pad + 20, y, W - 90, 20, size=12, bold=True)
    elapsed_lbl = _make_label(content, "", W - 60, y, 48, 20, color=FG_DIM, size=11, align="right")
    y -= 22

    # ===== Step line =====
    step_lbl = _make_label(content, "", pad + 4, y, W - 2 * pad, 32, color=BLUE, size=11, wrap=True)
    y -= 34

    # ===== Error line =====
    error_lbl = _make_label(content, "", pad, y, W - 2 * pad, 16, color=RED, size=10)
    y -= 20

    # ===== Separator =====
    sep = _make_label(content, "\u2500" * 40, pad, y, W - 2 * pad, 12, color=FG_DIM, size=9)
    y -= 14

    # ===== Log header =====
    _make_label(content, "Recent", pad, y, 60, 14, color=FG_DIM, size=10, bold=True)
    y -= 6

    # ===== Log scroll area =====
    log_height = 150
    y -= log_height
    scroll_view = NSScrollView.alloc().initWithFrame_(
        NSMakeRect(pad, y, W - 2 * pad, log_height)
    )
    scroll_view.setHasVerticalScroller_(True)
    scroll_view.setHasHorizontalScroller_(False)
    scroll_view.setAutohidesScrollers_(True)
    scroll_view.setBackgroundColor_(LOG_BG)
    scroll_view.setBorderType_(0)

    text_view = NSTextView.alloc().initWithFrame_(
        NSMakeRect(0, 0, W - 2 * pad - 15, log_height)
    )
    text_view.setEditable_(False)
    text_view.setSelectable_(True)
    text_view.setBackgroundColor_(LOG_BG)
    text_view.setTextColor_(FG_DIM)
    text_view.setFont_(NSFont.monospacedSystemFontOfSize_weight_(10, 0.0))
    text_view.textStorage().mutableString().setString_(" (no actions yet)")

    scroll_view.setDocumentView_(text_view)
    content.addSubview_(scroll_view)
    y -= 10

    # ===== Pause button =====
    pause_btn = NSButton.alloc().initWithFrame_(NSMakeRect(pad, y - 26, W - 2 * pad, 26))
    pause_btn.setTitle_("\u23f8  Pause")
    pause_btn.setBezelStyle_(NSBezelStyleRounded)
    pause_btn.setFont_(NSFont.systemFontOfSize_(11))
    content.addSubview_(pause_btn)
    y -= 34

    # ===== Hint input + send =====
    hint_field = _make_input(content, "Send hint to Claude...", pad, y - 24, W - 70, 24)
    send_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 55, y - 24, 43, 24))
    send_btn.setTitle_("Send")
    send_btn.setBezelStyle_(NSBezelStyleRounded)
    send_btn.setFont_(NSFont.systemFontOfSize_(11))
    content.addSubview_(send_btn)

    # ===== Wire up delegate =====
    delegate = PanelDelegate.alloc().init()
    delegate.panel = panel
    delegate.dot_label = dot
    delegate.action_label = action_lbl
    delegate.elapsed_label = elapsed_lbl
    delegate.step_label = step_lbl
    delegate.error_label = error_lbl
    delegate.log_view = text_view
    delegate.pause_btn = pause_btn
    delegate.hint_field = hint_field

    pause_btn.setTarget_(delegate)
    pause_btn.setAction_(objc.selector(delegate.togglePause_, signature=b"v@:@"))

    send_btn.setTarget_(delegate)
    send_btn.setAction_(objc.selector(delegate.sendHint_, signature=b"v@:@"))

    # Also send hint on Enter key
    hint_field.setTarget_(delegate)
    hint_field.setAction_(objc.selector(delegate.sendHint_, signature=b"v@:@"))

    # Start polling timer
    timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        POLL_INTERVAL, delegate, objc.selector(delegate.poll_, signature=b"v@:@"), None, True,
    )
    NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSDefaultRunLoopMode)

    panel.makeKeyAndOrderFront_(None)
    app.run()


if __name__ == "__main__":
    main()
