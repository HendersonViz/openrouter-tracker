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

from openrouter_tracker.api import fetch_activity, fetch_usage
from openrouter_tracker.config import (
    DEFAULT_MODEL,
    OPENROUTER_BASE_URL,
    PROJECT_ROOT,
    REFRESH_INTERVAL,
    USAGE_GRAPH_DAYS,
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

        self.sep_graph = Gtk.SeparatorMenuItem()
        self.menu.append(self.sep_graph)

        self.graph_header_item = Gtk.MenuItem(label="Usage (last 7 days)")
        self.graph_header_item.set_sensitive(False)
        self.menu.append(self.graph_header_item)

        self._graph_items: list[Gtk.MenuItem] = []
        self._graph_placeholder = Gtk.MenuItem(label="Usage graph: loading...")
        self._graph_placeholder.set_sensitive(False)
        self.menu.append(self._graph_placeholder)

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
            activity = fetch_activity()
            self._latest_raw = data
            self._latest_updated_at = time.time() if data is not None else None
            GLib.idle_add(self._update_ui, data, activity)
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

    def _update_ui(self, data: dict | None, activity: list[dict] | None = None) -> bool:
        if data is None:
            self._force_label("No key")
            self.balance_item.set_label("Balance: no API key")
            self.account_balance_item.set_label("Account balance: no API key")
            self.key_balance_item.set_label("API key remaining: no API key")
            self.spent_item.set_label("API key usage: no API key")
            self._render_usage_graph(activity)
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

        self._force_label(indicator_label)
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
        self._render_usage_graph(activity)
        self._tick_updated_age()
        return False

    def _force_label(self, label: str) -> None:
        """Re-apply the indicator label/status, defeating the panel's
        'label unchanged -> skip' cache that lets the top-bar dollar label
        disappear and never come back."""
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_label("", "")
        GLib.idle_add(lambda: (self.indicator.set_label(label, "OpenRouter Balance"), False)[1])

    _BLOCKS = " ▁▂▃▄▅▆▇█"  # index 0 (zero) -> space, 1..8 -> rising bars
    _MODEL_COL = 22

    def _graph_insert_pos(self) -> int:
        """Position in the menu where new graph rows should be inserted
        (immediately after the graph header)."""
        children = self.menu.get_children()
        try:
            return children.index(self.graph_header_item) + 1
        except ValueError:
            return len(children)

    def _render_usage_graph(self, activity: list[dict] | None) -> None:
        """Rebuild the inline barchart menu items (last N days, per model)."""
        for item in self._graph_items:
            self.menu.remove(item)
        self._graph_items = []

        def add_item(label: str) -> None:
            item = Gtk.MenuItem(label=label)
            item.set_sensitive(False)
            self.menu.insert(item, self._graph_insert_pos())
            item.show()
            self._graph_items.append(item)

        self.graph_header_item.set_label(f"Usage (last {USAGE_GRAPH_DAYS} days)")

        if not activity:
            self._graph_placeholder.set_label(
                "Usage graph: unavailable (needs management key)"
            )
            if self._graph_placeholder.get_parent() is None:
                self.menu.insert(self._graph_placeholder, self._graph_insert_pos())
                self._graph_placeholder.show()
            return

        if self._graph_placeholder.get_parent() is not None:
            self.menu.remove(self._graph_placeholder)

        import datetime as _dt

        per_model: dict[str, dict[str, float]] = {}
        all_dates: set[str] = set()
        for row in activity:
            date = row.get("date")
            model = row.get("model") or "unknown"
            usage = self._as_amount(row.get("usage"))
            if not date:
                continue
            all_dates.add(date)
            per_model.setdefault(model, {})
            per_model[model][date] = per_model[model].get(date, 0.0) + usage

        dates = sorted(all_dates)[-USAGE_GRAPH_DAYS:]
        if not dates:
            add_item("Usage graph: no data in range")
            return

        max_val = max(
            (per_model[m].get(d, 0.0) for m in per_model for d in dates),
            default=0.0,
        )

        def bar_for(day_values: dict[str, float]) -> str:
            chars = []
            for d in dates:
                v = day_values.get(d, 0.0)
                if v <= 0 or max_val <= 0:
                    chars.append(self._BLOCKS[0])
                    continue
                level = int(round((v / max_val) * (len(self._BLOCKS) - 2))) + 1
                level = max(1, min(level, len(self._BLOCKS) - 1))
                chars.append(self._BLOCKS[level])
            return "".join(chars)

        model_totals = sorted(
            ((m, sum(dv.values())) for m, dv in per_model.items()),
            key=lambda kv: kv[1],
            reverse=True,
        )

        for model, total in model_totals:
            name = (
                model
                if len(model) <= self._MODEL_COL
                else model[: self._MODEL_COL - 1] + "…"
            )
            add_item(f"{name:<{self._MODEL_COL}} {bar_for(per_model[model])} ${total:.2f}")

        weekday_initials = "".join(
            _dt.datetime.strptime(d, "%Y-%m-%d").strftime("%a")[0] for d in dates
        )
        grand_total = sum(t for _, t in model_totals)
        add_item(f"{'':<{self._MODEL_COL}} {weekday_initials} Total: ${grand_total:.2f}")

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
