# AGENTS.md — OpenRouter Top-Bar Tracker

> Lightweight Ubuntu/GNOME panel indicator for real-time OpenRouter credit & model-usage tracking.

## Architecture

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| Entry point | `run.py` | Instantiates indicator, installs Ctrl-C handler, starts GTK main loop |
| Indicator UI | `openrouter_tracker/indicator.py` | AppIndicator3 tray icon, menu, hover/fetch display, raw-data window |
| API Client | `openrouter_tracker/api.py` | `GET /api/v1/key` key/credit fetch, `GET /api/v1/credits` account credits, `GET /api/v1/activity` per-model daily usage, env-based key management |
| Config | `openrouter_tracker/config.py` | Env-driven defaults (`OPENROUTER_API_KEY`, `DEFAULT_MODEL`, `REFRESH_INTERVAL`, `USAGE_GRAPH_DAYS`) |

### Data Flow
```
run.py
 └── OpenRouterIndicator (GTK/AppIndicator3)
      ├── Background thread (urllib)
      │    └── GET https://openrouter.ai/api/v1/auth/key
      └── GLib.idle_add → update label & menu items
```

## Tech Decisions

- **Python + GTK3 + AppIndicator3** because it integrates natively with Ubuntu/GNOME top bar; avoids Electron bloat.
- **Background threading** so the UI stays responsive on slow network; `GLib.idle_add` marshals results to the GTK thread.
- **urllib** instead of `requests` to minimize external dependencies (only need `PyGObject` plus system `libgtk-3-dev`).
- **Env-based config** so nothing sensitive is hard-coded; `.env.example` shows the contract.

## Setup

1. Install GTK3/gi headers (Ubuntu):
   ```bash
   sudo apt install libgtk-3-dev libgirepository1.0-dev libcairo2-dev gir1.2-appindicator3-0.1
   ```
2. Install Python dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Export your API key (or copy `.env.example` to `.env` and source it).
4. Start the tracker:
   ```bash
   python3 run.py
   ```

## Roadmap

- [x] Model-specific usage query — inline 7-day per-model barchart in the dropdown (via `/api/v1/activity`; requires a Management key)
- [ ] Config file (`~/.config/openrouter-tracker/config.json`) so model/interval can be set via UI menu
- [ ] Click-to-copy current credit balance to clipboard
- [ ] Auto-start `.desktop` entry for GNOME startup
- [ ] Optional GTK4 + libayatana-appindicator3 port for newer distros

## API Reference

- **OpenRouter Key Auth endpoint**: `GET https://openrouter.ai/api/v1/auth/key`
  - Returns: `{ data: { total_credits, total_usage, limit, ... } }`
- **OpenRouter Activity endpoint**: `GET https://openrouter.ai/api/v1/activity`
  - Returns: `{ data: [ { date, model, usage, requests, prompt_tokens, ... } ] }` (last 30 completed UTC days; Management key required)
- **Docs**: https://openrouter.ai/docs

---
*If future models become top priority, extend `indicator.py` to fetch generations and filter by `model`.*
