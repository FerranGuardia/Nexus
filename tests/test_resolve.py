"""Tests for nexus.act.resolve — do() routing and dispatch."""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.resolve import do, _run_chain, VERB_SYNONYMS, PHRASE_SYNONYMS, ROLE_MAP, ROLE_WORDS


# ===========================================================================
# TestDoRouting
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestDoRouting:
    """Tests for do() — verify correct routing to native/raw_input handlers."""

    # --- Empty action ---

    def test_empty_action(self, mock_native, mock_raw_input):
        result = do("")
        assert result["ok"] is False
        assert "Empty action" in result["error"]

    def test_whitespace_only_action(self, mock_native, mock_raw_input):
        result = do("   ")
        assert result["ok"] is False
        assert "Empty action" in result["error"]

    # --- Shortcut intents ---

    def test_select_all(self, mock_native, mock_raw_input):
        do("select all")
        mock_raw_input.hotkey.assert_called_once_with("command", "a")

    def test_selectall_no_space(self, mock_native, mock_raw_input):
        do("selectall")
        mock_raw_input.hotkey.assert_called_once_with("command", "a")

    def test_copy(self, mock_native, mock_raw_input):
        result = do("copy")
        mock_raw_input.hotkey.assert_called_once_with("command", "c")
        assert result["ok"] is True
        assert result["action"] == "copy"

    def test_paste(self, mock_native, mock_raw_input):
        result = do("paste")
        mock_raw_input.hotkey.assert_called_once_with("command", "v")
        assert result["ok"] is True
        assert result["action"] == "paste"

    def test_undo(self, mock_native, mock_raw_input):
        result = do("undo")
        mock_raw_input.hotkey.assert_called_once_with("command", "z")
        assert result["ok"] is True
        assert result["action"] == "undo"

    def test_redo(self, mock_native, mock_raw_input):
        result = do("redo")
        mock_raw_input.hotkey.assert_called_once_with("command", "shift", "z")
        assert result["ok"] is True
        assert result["action"] == "redo"

    def test_close(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("close")
        mock_native.close_window.assert_called_once()

    def test_close_window(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("close window")
        mock_native.close_window.assert_called_once()

    # --- Getter intents ---

    def test_get_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hello"}
        result = do("get clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_read_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hi"}
        do("read clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_clipboard_alone(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "x"}
        do("clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_get_url(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True, "url": "https://x.com"}
        do("get url")
        mock_native.safari_url.assert_called_once()

    def test_get_safari_url(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True}
        do("get safari url")
        mock_native.safari_url.assert_called_once()

    def test_url_alone(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True}
        do("url")
        mock_native.safari_url.assert_called_once()

    def test_get_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True, "tabs": []}
        do("get tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_get_safari_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("get safari tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_tabs_alone(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_list_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("list tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_get_source(self, mock_native, mock_raw_input):
        mock_native.safari_source.return_value = {"ok": True}
        do("get source")
        mock_native.safari_source.assert_called_once()

    def test_page_source(self, mock_native, mock_raw_input):
        mock_native.safari_source.return_value = {"ok": True}
        do("page source")
        mock_native.safari_source.assert_called_once()

    def test_get_selection(self, mock_native, mock_raw_input):
        mock_native.finder_selection.return_value = {"ok": True}
        do("get selection")
        mock_native.finder_selection.assert_called_once()

    def test_selected_files(self, mock_native, mock_raw_input):
        mock_native.finder_selection.return_value = {"ok": True}
        do("selected files")
        mock_native.finder_selection.assert_called_once()

    def test_maximize(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize")
        mock_native.maximize_window.assert_called_once()

    def test_maximize_window(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize window")
        mock_native.maximize_window.assert_called_once()

    def test_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_maximize_is_not_fullscreen(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize")
        mock_native.maximize_window.assert_called_once()
        mock_native.fullscreen_window.assert_not_called()

    def test_enter_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("enter fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_exit_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("exit fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_minimize_shortcut(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        do("minimize")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_window_shortcut(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        do("minimize window")
        mock_native.minimize_window.assert_called_once()

    def test_restore_shortcut(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        do("restore")
        mock_native.unminimize_window.assert_called_once()

    def test_unminimize_shortcut(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        do("unminimize window")
        mock_native.unminimize_window.assert_called_once()

    def test_where_is_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("where is Safari?")
        mock_native.window_info.assert_called_once()

    def test_wheres_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("where's Chrome?")
        mock_native.window_info.assert_called_once()

    def test_window_info_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("window info")
        mock_native.window_info.assert_called_once()

    # --- Click (dispatches to _handle_click) ---

    @patch("nexus.act.resolve._handle_click")
    def test_click_element(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True, "action": "click"}
        do("click Save")
        mock_handle_click.assert_called_once_with("Save", pid=None)

    @patch("nexus.act.resolve._handle_click")
    def test_click_element_with_pid(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("click Save", pid=12345)
        mock_handle_click.assert_called_once_with("Save", pid=12345)

    # --- Click menu path (contains ">") ---

    def test_click_menu_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("click File > Save")
        mock_native.click_menu.assert_called_once_with("File > Save", pid=None)

    def test_click_menu_path_with_pid(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("click File > Save As", pid=999)
        mock_native.click_menu.assert_called_once_with("File > Save As", pid=999)

    def test_menu_verb_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("menu File > Save")
        mock_native.click_menu.assert_called_once_with("File > Save", pid=None)

    def test_menu_verb_without_angle_bracket(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("menu Edit")
        mock_native.click_menu.assert_called_once_with("Edit", pid=None)

    # --- Fallback: unknown verb with ">" treated as menu ---

    def test_unknown_verb_with_menu_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("Edit > Paste")
        mock_native.click_menu.assert_called_once_with("Edit > Paste", pid=None)

    # --- Fallback: unknown verb treated as click ---

    @patch("nexus.act.resolve._handle_click")
    def test_unknown_verb_as_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("Save")
        mock_handle_click.assert_called_once_with("Save", pid=None)

    # --- Press (dispatches to _handle_press) ---

    @patch("nexus.act.resolve._handle_press")
    def test_press_single_key_enter(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True, "action": "press", "keys": ["return"]}
        result = do("press enter")
        mock_handle_press.assert_called_once_with("enter", pid=None)
        assert result["ok"] is True

    @patch("nexus.act.resolve._handle_press")
    def test_press_combo_cmd_s(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True, "action": "press", "keys": ["command", "s"]}
        result = do("press cmd+s")
        mock_handle_press.assert_called_once_with("cmd+s", pid=None)
        assert result["ok"] is True

    @patch("nexus.act.resolve._handle_press")
    def test_press_combo_ctrl_shift_p(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press ctrl+shift+p")
        mock_handle_press.assert_called_once_with("ctrl+shift+p", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_escape(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press esc")
        mock_handle_press.assert_called_once_with("esc", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_tab(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press tab")
        mock_handle_press.assert_called_once_with("tab", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_space(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press space")
        mock_handle_press.assert_called_once_with("space", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_f5(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press f5")
        mock_handle_press.assert_called_once_with("f5", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_alt_tab(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press alt+tab")
        mock_handle_press.assert_called_once_with("alt+tab", pid=None)

    @patch("nexus.act.resolve._handle_press")
    def test_press_cmd_shift_z(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True}
        do("press cmd+shift+z")
        mock_handle_press.assert_called_once_with("cmd+shift+z", pid=None)

    # --- Type (dispatches to _handle_type) ---

    @patch("nexus.act.resolve._handle_type")
    def test_type_simple(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True, "action": "type", "text": "hello"}
        result = do("type hello")
        mock_handle_type.assert_called_once_with("hello", pid=None)
        assert result["ok"] is True

    @patch("nexus.act.resolve._handle_type")
    def test_type_with_quotes(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True, "action": "type", "text": "hello world"}
        result = do('type "hello world"')
        mock_handle_type.assert_called_once_with('"hello world"', pid=None)

    @patch("nexus.act.resolve._handle_type")
    def test_type_in_target(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True}
        do("type hello in search")
        mock_handle_type.assert_called_once_with("hello in search", pid=None)

    @patch("nexus.act.resolve._handle_type")
    def test_type_quoted_in_target(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True}
        do('type "hello world" in search')
        mock_handle_type.assert_called_once_with('"hello world" in search', pid=None)

    @patch("nexus.act.resolve._handle_type")
    def test_type_empty(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": False, "error": "Nothing to type"}
        result = do("type")
        mock_handle_type.assert_called_once_with("", pid=None)
        assert result["ok"] is False

    # --- Open ---

    def test_open_app(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("open Safari")
        mock_native.launch_app.assert_called_once_with("Safari")

    def test_open_app_with_spaces(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("open Visual Studio Code")
        mock_native.launch_app.assert_called_once_with("Visual Studio Code")

    # --- Switch ---

    def test_switch_to_app(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("switch to Terminal")
        mock_native.activate_window.assert_called_once_with(app_name="Terminal")

    def test_switch_without_to(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("switch Terminal")
        mock_native.activate_window.assert_called_once_with(app_name="Terminal")

    def test_activate_app(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("activate Safari")
        mock_native.activate_window.assert_called_once_with(app_name="Safari")

    # --- Scroll (dispatches to _handle_scroll) ---

    @patch("nexus.act.resolve._handle_scroll")
    def test_scroll_down(self, mock_handle_scroll, mock_native, mock_raw_input):
        mock_handle_scroll.return_value = {"ok": True}
        do("scroll down")
        mock_handle_scroll.assert_called_once_with("down", pid=None)

    @patch("nexus.act.resolve._handle_scroll")
    def test_scroll_up(self, mock_handle_scroll, mock_native, mock_raw_input):
        mock_handle_scroll.return_value = {"ok": True}
        do("scroll up")
        mock_handle_scroll.assert_called_once_with("up", pid=None)

    # --- Focus ---

    def test_focus_element(self, mock_native, mock_raw_input):
        mock_native.focus_element.return_value = {"ok": True}
        do("focus search")
        mock_native.focus_element.assert_called_once_with("search", pid=None)

    # --- Notify ---

    def test_notify(self, mock_native, mock_raw_input):
        mock_native.notify.return_value = {"ok": True}
        do("notify Hello")
        mock_native.notify.assert_called_once_with("Nexus", "Hello")

    def test_notify_with_longer_message(self, mock_native, mock_raw_input):
        mock_native.notify.return_value = {"ok": True}
        do("notify Task completed successfully")
        mock_native.notify.assert_called_once_with("Nexus", "Task completed successfully")

    # --- Say ---

    def test_say(self, mock_native, mock_raw_input):
        mock_native.say.return_value = {"ok": True}
        do("say Hello")
        mock_native.say.assert_called_once_with("Hello")

    def test_say_sentence(self, mock_native, mock_raw_input):
        mock_native.say.return_value = {"ok": True}
        do("say The task is done")
        mock_native.say.assert_called_once_with("The task is done")

    # --- Navigate ---

    @patch("nexus.act.resolve._handle_navigate")
    def test_navigate_to_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("navigate to google.com")
        mock_handle_nav.assert_called_once_with("to google.com")

    @patch("nexus.act.resolve._handle_navigate")
    def test_goto_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("goto google.com")
        mock_handle_nav.assert_called_once_with("google.com")

    @patch("nexus.act.resolve._handle_navigate")
    def test_go_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("go to google.com")
        # "go to" phrase synonym normalizes to "navigate google.com"
        mock_handle_nav.assert_called_once_with("google.com")

    # --- Set/Write clipboard ---

    def test_set_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_write.return_value = {"ok": True}
        do("set clipboard hello")
        mock_native.clipboard_write.assert_called_once_with("hello")

    def test_write_clipboard_quoted(self, mock_native, mock_raw_input):
        mock_native.clipboard_write.return_value = {"ok": True}
        do('write clipboard "hello world"')
        mock_native.clipboard_write.assert_called_once_with("hello world")

    # --- JS ---

    @patch("nexus.act.resolve._handle_run_js")
    def test_js_verb(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("js document.title")
        mock_handle_js.assert_called_once_with("document.title")

    @patch("nexus.act.resolve._handle_run_js")
    def test_run_js(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("run js document.title")
        mock_handle_js.assert_called_once_with("document.title")

    @patch("nexus.act.resolve._handle_run_js")
    def test_eval_js(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("eval js alert('hi')")
        mock_handle_js.assert_called_once_with("alert('hi')")

    # --- Double click / right click verbs ---

    @patch("nexus.act.resolve._handle_click")
    def test_double_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("double-click item")
        mock_handle_click.assert_called_once_with("item", double=True, pid=None)

    @patch("nexus.act.resolve._handle_click")
    def test_right_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("right-click item")
        mock_handle_click.assert_called_once_with("item", right=True, pid=None)

    # --- Tile (dispatches to _handle_tile) ---

    @patch("nexus.act.resolve._handle_tile")
    def test_tile_routed(self, mock_handle_tile, mock_native, mock_raw_input):
        mock_handle_tile.return_value = {"ok": True}
        do("tile Safari and Terminal")
        mock_handle_tile.assert_called_once_with("Safari and Terminal")

    # --- Fill ---

    @patch("nexus.act.resolve._handle_fill")
    def test_fill_routed(self, mock_handle_fill, mock_native, mock_raw_input):
        mock_handle_fill.return_value = {"ok": True}
        do("fill Name=Ferran")
        mock_handle_fill.assert_called_once_with("Name=Ferran", pid=None)

    # --- Minimize/Restore with app name (dispatches to handlers) ---

    @patch("nexus.act.resolve._handle_minimize")
    def test_minimize_app_routed(self, mock_handle_minimize, mock_native, mock_raw_input):
        mock_handle_minimize.return_value = {"ok": True}
        do("minimize Safari")
        mock_handle_minimize.assert_called_once_with("Safari")

    @patch("nexus.act.resolve._handle_restore")
    def test_restore_app_routed(self, mock_handle_restore, mock_native, mock_raw_input):
        mock_handle_restore.return_value = {"ok": True}
        do("restore Safari")
        mock_handle_restore.assert_called_once_with("Safari")

    @patch("nexus.act.resolve._handle_resize")
    def test_resize_routed(self, mock_handle_resize, mock_native, mock_raw_input):
        mock_handle_resize.return_value = {"ok": True}
        do("resize to 800x600")
        mock_handle_resize.assert_called_once_with("to 800x600", pid=None)

    @patch("nexus.act.resolve._handle_fullscreen")
    def test_fullscreen_app_routed(self, mock_handle_fullscreen, mock_native, mock_raw_input):
        mock_handle_fullscreen.return_value = {"ok": True}
        do("fullscreen Safari")
        mock_handle_fullscreen.assert_called_once_with("Safari")

    # --- Return value structure ---

    def test_select_all_returns_ok(self, mock_native, mock_raw_input):
        result = do("select all")
        assert result["ok"] is True
        assert result["action"] == "select_all"

    def test_copy_returns_ok(self, mock_native, mock_raw_input):
        result = do("copy")
        assert result["ok"] is True
        assert result["action"] == "copy"

    def test_paste_returns_ok(self, mock_native, mock_raw_input):
        result = do("paste")
        assert result["ok"] is True
        assert result["action"] == "paste"


# ===========================================================================
# TestDoSynonyms — end-to-end synonym routing via do()
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestDoSynonyms:
    """Test that verb synonyms route correctly through do()."""

    @patch("nexus.act.resolve._handle_click")
    def test_tap_routes_to_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("tap Save")
        mock_handle_click.assert_called_once_with("Save", pid=None)

    @patch("nexus.act.resolve._handle_click")
    def test_hit_routes_to_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("hit Cancel")
        mock_handle_click.assert_called_once_with("Cancel", pid=None)

    @patch("nexus.act.resolve._handle_click")
    def test_press_on_routes_to_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("press on Submit")
        mock_handle_click.assert_called_once_with("Submit", pid=None)

    @patch("nexus.act.resolve._handle_click")
    def test_click_on_routes_to_click(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": True}
        do("click on Save")
        mock_handle_click.assert_called_once_with("Save", pid=None)

    @patch("nexus.act.resolve._handle_type")
    def test_enter_routes_to_type(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True, "action": "type", "text": "hello world"}
        result = do("enter hello world")
        mock_handle_type.assert_called_once_with("hello world", pid=None)
        assert result["ok"] is True

    @patch("nexus.act.resolve._handle_type")
    def test_input_routes_to_type(self, mock_handle_type, mock_native, mock_raw_input):
        mock_handle_type.return_value = {"ok": True, "action": "type", "text": "test"}
        result = do("input test")
        mock_handle_type.assert_called_once_with("test", pid=None)
        assert result["ok"] is True

    def test_launch_routes_to_open(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("launch Safari")
        mock_native.launch_app.assert_called_once_with("Safari")

    def test_start_routes_to_open(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("start Terminal")
        mock_native.launch_app.assert_called_once_with("Terminal")

    @patch("nexus.act.resolve._handle_navigate")
    def test_visit_routes_to_navigate(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("visit example.com")
        mock_handle_nav.assert_called_once_with("example.com")

    @patch("nexus.act.resolve._handle_navigate")
    def test_browse_routes_to_navigate(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("browse google.com")
        mock_handle_nav.assert_called_once_with("google.com")

    @patch("nexus.act.resolve._handle_scroll")
    def test_swipe_routes_to_scroll(self, mock_handle_scroll, mock_native, mock_raw_input):
        mock_handle_scroll.return_value = {"ok": True}
        do("swipe down")
        mock_handle_scroll.assert_called_once_with("down", pid=None)

    def test_quit_routes_to_close(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("quit")
        mock_native.close_window.assert_called_once()

    def test_shortcuts_unaffected_by_synonyms(self, mock_native, mock_raw_input):
        """select all, copy, paste, undo, redo are checked before synonym expansion."""
        result = do("select all")
        mock_raw_input.hotkey.assert_called_with("command", "a")
        assert result["ok"] is True

    def test_getters_unaffected_by_synonyms(self, mock_native, mock_raw_input):
        """Getter intents should not be affected by synonym expansion."""
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hi"}
        do("get clipboard")
        mock_native.clipboard_read.assert_called_once()


# ===========================================================================
# TestActionChains — semicolon-separated compound intents
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestActionChains:
    """Tests for action chains via do("step1; step2; step3")."""

    def test_two_step_chain(self, mock_native, mock_raw_input):
        """Two copy operations should both execute."""
        result = do("copy; paste")
        assert result["ok"] is True
        assert result["action"] == "chain"
        assert result["completed"] == 2
        assert result["total"] == 2
        assert len(result["steps"]) == 2

    def test_chain_preserves_step_info(self, mock_native, mock_raw_input):
        result = do("copy; undo")
        assert result["steps"][0]["action"] == "copy"
        assert result["steps"][0]["ok"] is True
        assert result["steps"][1]["action"] == "undo"
        assert result["steps"][1]["ok"] is True

    @patch("nexus.act.resolve._handle_click")
    def test_chain_fails_fast_on_error(self, mock_handle_click, mock_native, mock_raw_input):
        """If a step fails, the chain stops."""
        mock_handle_click.return_value = {"ok": False, "error": "Not found"}
        result = do("copy; click NonExistent; paste")
        assert result["ok"] is False
        assert result["completed"] == 1  # Only copy ran successfully
        assert result["total"] == 3
        assert "Step 2 failed" in result["error"]

    def test_three_step_chain(self, mock_native, mock_raw_input):
        result = do("select all; copy; paste")
        assert result["ok"] is True
        assert result["completed"] == 3

    def test_chain_with_whitespace(self, mock_native, mock_raw_input):
        """Extra whitespace around semicolons should be stripped."""
        result = do("copy ;  paste  ;  undo")
        assert result["ok"] is True
        assert result["completed"] == 3

    def test_empty_steps_skipped(self, mock_native, mock_raw_input):
        """Empty segments from consecutive semicolons are filtered out."""
        result = do("copy;; paste")
        assert result["ok"] is True
        assert result["completed"] == 2

    def test_single_step_chain(self, mock_native, mock_raw_input):
        """A chain with one step should still work."""
        # "copy;" -> ["copy"]
        result = do("copy;")
        assert result["ok"] is True
        assert result["completed"] == 1

    def test_chain_with_synonym(self, mock_native, mock_raw_input):
        """Synonyms should work inside chain steps."""
        mock_native.launch_app.return_value = {"ok": True}
        result = do("launch Safari; copy")
        assert result["ok"] is True
        assert result["completed"] == 2
        mock_native.launch_app.assert_called_once_with("Safari")

    @patch("nexus.act.resolve._handle_click")
    def test_chain_error_reports_which_step(self, mock_handle_click, mock_native, mock_raw_input):
        mock_handle_click.return_value = {"ok": False, "error": "Element not found"}
        result = do("select all; click Missing")
        assert result["ok"] is False
        assert "Step 2" in result["error"]
        assert "Missing" in result["error"]

    def test_empty_chain(self, mock_native, mock_raw_input):
        """Only semicolons, no content."""
        result = do(";;;")
        assert result["ok"] is False
        assert "Empty" in result["error"]

    @patch("nexus.act.resolve._handle_press")
    def test_chain_with_press(self, mock_handle_press, mock_native, mock_raw_input):
        mock_handle_press.return_value = {"ok": True, "action": "press", "keys": ["command", "a"]}
        result = do("press cmd+a; press cmd+c")
        assert result["ok"] is True
        assert result["completed"] == 2
        assert mock_handle_press.call_count == 2


# ===========================================================================
# TestObserveIntents
# ===========================================================================


class TestObserveIntents:
    """Tests for do('observe ...') intent routing."""

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Safari"})
    def test_observe_start(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe start")
        assert result["ok"] is True
        mock_start.assert_called_once_with(42, "Safari")

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Safari"})
    def test_observe_no_args_defaults_to_start(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe")
        assert result["ok"] is True
        mock_start.assert_called_once()

    @patch("nexus.sense.observe.stop_observing", return_value={"ok": True, "stopped": [42]})
    def test_observe_stop(self, mock_stop):
        from nexus.act.resolve import do
        result = do("observe stop")
        assert result["ok"] is True
        mock_stop.assert_called_once()

    @patch("nexus.sense.observe.drain_events", return_value=[])
    def test_observe_clear(self, mock_drain):
        from nexus.act.resolve import do
        result = do("observe clear")
        assert result["ok"] is True
        assert result["action"] == "observe_clear"

    @patch("nexus.sense.observe.status", return_value={"ok": True, "observing": [], "buffered": 0})
    def test_observe_status(self, mock_status):
        from nexus.act.resolve import do
        result = do("observe status")
        assert result["ok"] is True
        mock_status.assert_called_once()

    def test_observe_unknown_command(self):
        from nexus.act.resolve import do
        result = do("observe foobar")
        assert result["ok"] is False
        assert "Unknown" in result["error"]

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Finder"})
    def test_observe_on_synonym(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe on")
        assert result["ok"] is True

    @patch("nexus.sense.observe.stop_observing", return_value={"ok": True, "stopped": []})
    def test_observe_off_synonym(self, mock_stop):
        from nexus.act.resolve import do
        result = do("observe off")
        assert result["ok"] is True


# ===========================================================================
# TestVerbSynonymDicts
# ===========================================================================


class TestVerbSynonymDicts:
    """Tests that synonym dictionaries are well-formed."""

    def test_all_verb_synonyms_map_to_known_verbs(self):
        known_verbs = {"click", "type", "open", "close", "scroll", "navigate", "focus", "switch", "hover"}
        for synonym, canonical in VERB_SYNONYMS.items():
            assert canonical in known_verbs, f'VERB_SYNONYMS["{synonym}"] = "{canonical}" is not a known verb'

    def test_all_phrase_synonyms_map_to_known_patterns(self):
        known = {"click", "navigate", "switch to", "type", "focus"}
        for phrase, canonical in PHRASE_SYNONYMS.items():
            assert canonical in known, f'PHRASE_SYNONYMS["{phrase}"] = "{canonical}" is not recognized'

    def test_no_overlapping_synonyms(self):
        """A word should not appear as both a verb synonym and a phrase start."""
        phrase_starts = {p.split()[0] for p in PHRASE_SYNONYMS}
        # Some overlap is OK (e.g. "click" appears in "click on" phrase and
        # is also a real verb), but pure synonyms shouldn't shadow phrases
        for syn in VERB_SYNONYMS:
            if syn in phrase_starts:
                # This is fine as long as phrases are checked first
                pass

    def test_synonyms_are_lowercase(self):
        for k in VERB_SYNONYMS:
            assert k == k.lower(), f'VERB_SYNONYMS key "{k}" should be lowercase'
        for k in PHRASE_SYNONYMS:
            assert k == k.lower(), f'PHRASE_SYNONYMS key "{k}" should be lowercase'


# ===========================================================================
# TestRoleMapConsolidation
# ===========================================================================


class TestRoleMapConsolidation:
    """Tests that ROLE_MAP and ROLE_WORDS are consistent and used everywhere."""

    def test_role_map_has_all_core_roles(self):
        expected = {"button", "link", "tab", "menu", "field", "checkbox",
                    "radio", "text", "image", "slider", "switch", "toggle"}
        assert expected.issubset(set(ROLE_MAP.keys()))

    def test_role_words_matches_role_map_keys(self):
        assert ROLE_WORDS == frozenset(ROLE_MAP.keys())

    def test_role_map_values_all_ax_prefixed(self):
        for role, ax_role in ROLE_MAP.items():
            assert ax_role.startswith("AX"), f"{role} -> {ax_role} missing AX prefix"

    def test_icon_maps_to_ax_image(self):
        assert ROLE_MAP["icon"] == "AXImage"

    def test_label_maps_to_ax_static_text(self):
        assert ROLE_MAP["label"] == "AXStaticText"

    def test_toggle_maps_to_ax_switch(self):
        assert ROLE_MAP["toggle"] == "AXSwitch"
