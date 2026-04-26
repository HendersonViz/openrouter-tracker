#!/usr/bin/env python3
"""AppIndicator for displaying OpenRouter credit status."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser
import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # type: ignore[attr-defined]
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3  # type: ignore[attr-defined]
from gi.repository import Gtk, GLib  # type: ignore[attr-defined]

from openrouter_tracker.api import fetch_usage
from openrouter_tracker.config import (
    DEFAULT_MODEL,
    OPENROUTER_BASE_URL,
    PROJECT_ROOT,
    REFRESH_INTERVAL,
)


class OpenRouterIndicator:
    """Simple top-bar credit indicator."""

    def __init__(self) -> None:
        self.indicator = AppIndicator3.Indicator.new(
            "openrouter-tracker",
            "",  # no fallback icon
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_icon_theme_path(str(PROJECT_ROOT / "icons"))
        self.indicator.set_icon_full("robot", "OpenRouter Tracker")
        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)

        self.title_item = Gtk.MenuItem(label="OpenRouter Tracker")
        self.title_item.set_sensitive(False)
        self.menu.append(self.title_item)

        self.sep1 = Gtk.SeparatorMenuItem()
        self.menu.append(self.sep1)

        self.balance_item = Gtk.MenuItem(label="Balance: --")
        self.balance_item.set_sensitive(False)
        self.menu.append(self.balance_item)

        self.account_balance_item = Gtk.MenuItem(label="Account balance: --")
        self.account_balance_item.set_sensitive(False)
        self.menu.append(self.account_balance_item)

        self.key_balance_item = Gtk.MenuItem(label="API key remaining: --")
        self.key_balance_item.set_sensitive(False)
        self.menu.append(self.key_balance_item)

        self.spent_item = Gtk.MenuItem(label="API key usage: --")
        self.spent_item.set_sensitive(False)
        self.menu.append(self.spent_item)

        self.model_item = Gtk.MenuItem(label=f"Model: {DEFAULT_MODEL}")
        self.model_item.set_sensitive(False)
        self.menu.append(self.model_item)

        self.updated_item = Gtk.MenuItem(label="Updated: --")
        self.updated_item.set_sensitive(False)
        self.menu.append(self.updated_item)

        self.refresh_item = Gtk.MenuItem(label="Refresh now")
        self.refresh_item.connect("activate", self._request_refresh)
        self.menu.append(self.refresh_item)

        self.sep2 = Gtk.SeparatorMenuItem()
        self.menu.append(self.sep2)

        self.dashboard_item = Gtk.MenuItem(label="Open dashboard")
        self.dashboard_item.connect("activate", self._open_dashboard)
        self.menu.append(self.dashboard_item)

        self.autostart_item = Gtk.MenuItem(label="Install startup launcher")
        self.autostart_item.connect("activate", self._install_autostart)
        self.menu.append(self.autostart_item)

        self.disable_autostart_item = Gtk.MenuItem(label="Disable startup launcher")
        self.disable_autostart_item.connect("activate", self._disable_autostart)
        self.menu.append(self.disable_autostart_item)

        self.raw_item = Gtk.MenuItem(label="View raw response (logs)")
        self.raw_item.connect("activate", self._show_raw)
        self.menu.append(self.raw_item)

        self.quit_item = Gtk.MenuItem(label="Quit")
        self.quit_item.connect("activate", self._quit)
        self.menu.append(self.quit_item)

        self.menu.show_all()

        self._latest_raw: dict | None = None
        self._latest_updated_at: float | None = None
        self._stop = threading.Event()
        self._refresh_requested = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        GLib.timeout_add_seconds(1, self._tick_updated_age)

    @staticmethod
    def _as_amount(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:.2f}"

    @staticmethod
    def _format_optional_currency(value: float | None) -> str:
        if value is None:
            return "unavailable"
        return f"${value:.2f}"

    def _resolve_key_remaining(self, key_data: dict) -> float | None:
        remaining = key_data.get("limit_remaining")
        if remaining is not None:
            return max(self._as_amount(remaining), 0.0)

        limit = key_data.get("limit")
        if limit is None:
            return None

        return max(self._as_amount(limit) - self._as_amount(key_data.get("usage")), 0.0)

    def _resolve_effective_balance(
        self,
        account_balance: float | None,
        key_balance: float | None,
    ) -> float | None:
        balances = [value for value in (account_balance, key_balance) if value is not None]
        if not balances:
            return None
        return min(balances)

    def _poll(self) -> None:
        while not self._stop.is_set():
            GLib.idle_add(self._set_refresh_state, True)
            data = fetch_usage()
            self._latest_raw = data
            self._latest_updated_at = time.time() if data is not None else None
            GLib.idle_add(self._update_ui, data)
            GLib.idle_add(self._set_refresh_state, False)

            while not self._stop.is_set():
                if self._refresh_requested.wait(timeout=REFRESH_INTERVAL):
                    self._refresh_requested.clear()
                    break
                break

    def _set_refresh_state(self, is_refreshing: bool) -> bool:
        self.refresh_item.set_sensitive(not is_refreshing)
        self.refresh_item.set_label("Refreshing..." if is_refreshing else "Refresh now")
        return False

    def _tick_updated_age(self) -> bool:
        if self._stop.is_set():
            return False
        if self._latest_updated_at is None:
            return True
        age_seconds = max(int(time.time() - self._latest_updated_at), 0)
        self.updated_item.set_label(f"Updated: {age_seconds}s ago")
        return True

    def _update_ui(self, data: dict | None) -> bool:
        if data is None:
            self.balance_item.set_label("Balance: error")
            self.account_balance_item.set_label("Account balance: error")
            self.key_balance_item.set_label("API key remaining: error")
            self.spent_item.set_label("API key usage: error")
            self.updated_item.set_label("Updated: fetch failed")
            return False

        key_payload = data.get("key") or {}
        key_data = key_payload.get("data", key_payload)
        credits_payload = data.get("credits") or {}
        credits_data = credits_payload.get("data") if "data" in credits_payload else None

        key_usage = self._as_amount(key_data.get("usage"))
        key_balance = self._resolve_key_remaining(key_data) if key_data else None

        account_balance = None
        if credits_data is not None:
            total_credits = self._as_amount(credits_data.get("total_credits"))
            total_usage = self._as_amount(credits_data.get("total_usage"))
            account_balance = max(total_credits - total_usage, 0.0)

        effective_balance = self._resolve_effective_balance(account_balance, key_balance)
        indicator_label = (
            self._format_currency(effective_balance) if effective_balance is not None else "--"
        )

        self.indicator.set_label(indicator_label, "OpenRouter Balance")
        self.balance_item.set_label(
            f"Balance: {self._format_optional_currency(effective_balance)}"
        )
        self.account_balance_item.set_label(
            f"Account balance: {self._format_optional_currency(account_balance)}"
        )
        self.key_balance_item.set_label(
            f"API key remaining: {self._format_optional_currency(key_balance)}"
        )
        self.spent_item.set_label(f"API key usage: {self._format_currency(key_usage)}")
        self._tick_updated_age()
        return False

    def _request_refresh(self, _item=None) -> None:
        if self._stop.is_set():
            return
        self.updated_item.set_label("Updated: refreshing...")
        self._refresh_requested.set()

    def _show_raw(self, _item) -> None:
        win = Gtk.Window(title="OpenRouter Raw Usage (last fetch)")
        win.set_default_size(500, 300)
        scrolled = Gtk.ScrolledWindow()
        win.add(scrolled)
        buf = Gtk.TextBuffer()
        buf.set_text(
            json.dumps(self._latest_raw, indent=2, sort_keys=True)
            if self._latest_raw
            else "No data yet"
        )
        view = Gtk.TextView(buffer=buf, editable=False, monospace=True)
        scrolled.add(view)
        win.show_all()
        self._raw_window = win  # keep reference alive

    def _quit(self, _item) -> None:
        Gtk.main_quit()

    def _open_dashboard(self, _item) -> None:
        webbrowser.open(f"{OPENROUTER_BASE_URL}/settings/credits")

    def _install_autostart(self, _item) -> None:
        try:
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "install_autostart.py")],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            self.updated_item.set_label("Updated: startup install failed")
            self._latest_raw = {"autostart_error": exc.stderr.strip() or exc.stdout.strip()}
            return

        self.updated_item.set_label("Updated: startup enabled")

    def _disable_autostart(self, _item) -> None:
        autostart_path = Path.home() / ".config" / "autostart" / "openrouter-tracker.desktop"
        try:
            autostart_path.unlink(missing_ok=True)
        except OSError as exc:
            self.updated_item.set_label("Updated: startup disable failed")
            self._latest_raw = {"autostart_error": str(exc)}
            return

        self.updated_item.set_label("Updated: startup disabled")

    def run(self) -> None:
        self._thread.start()
        Gtk.main()
        self._stop.set()
        self._thread.join(timeout=5)
