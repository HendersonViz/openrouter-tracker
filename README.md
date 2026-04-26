# OpenRouter Top-Bar Tracker

A minimal Ubuntu/GNOME panel indicator that polls your [OpenRouter](https://openrouter.ai) credit balance and displays it in the top bar.

## Features

- **Live credit balance** in the top panel (`$12.34` style)
- **Hover / click** the tray icon to see total credits, usage, and your selected model
- **Manual refresh** from the tray menu when you want an immediate balance update
- **Auto-refresh** every 5 minutes by default (configurable via env)
- **Combined balance view** showing account credits, API-key remaining, and the lower effective amount in the tray
- **Raw JSON viewer** for quick debugging of the API response
- Zero Electron / no browser engine — just GTK3 + Python

## Quick Start

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install libgtk-3-dev libgirepository1.0-dev libcairo2-dev \
    gir1.2-ayatanaappindicator3-0.1
```

> If `gir1.2-ayatanaappindicator3-0.1` is not found, try `gir1.2-appindicator3-0.1`.

### 2. Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure your API key

```bash
cp .env.example .env
# edit .env and paste your OpenRouter API key
```

### 4. Run

```bash
python3 run.py
```

You should see a new icon appear in your Ubuntu top bar. Click it to expand usage details.

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `OPENROUTER_DEFAULT_MODEL` | `openai/gpt-4o` | Model shown in the menu |
| `OPENROUTER_REFRESH_INTERVAL` | `300` | Poll interval in seconds |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai` | API base URL |

`/api/v1/credits` is used for account-level credits when the current key is allowed to access it. If OpenRouter returns `403`, the tray will still show API-key remaining and mark account balance as unavailable.

## Auto-start on Login

Install the tracker into GNOME autostart:

```bash
python3 install_autostart.py
```

That creates:

- `~/.config/autostart/openrouter-tracker.desktop`
- `~/.config/openrouter-tracker/config.env`

The app will then start on login and appear in the top-right indicator area. If you update your API key later, edit `~/.config/openrouter-tracker/config.env`.

If you want it to poll more or less often after install, set `OPENROUTER_REFRESH_INTERVAL` in `~/.config/openrouter-tracker/config.env`.

You can also manage startup directly from the tray menu with `Install startup launcher` and `Disable startup launcher`.

## Project Layout

```
├── AGENTS.md                  # Coding agent instructions
├── README.md                  # Human docs (this file)
├── requirements.txt           # PyGObject
├── run.py                     # Entry point
├── .env.example               # API key template
└── openrouter_tracker/
    ├── __init__.py
    ├── indicator.py           # GTK / AppIndicator UI
    ├── api.py                 # OpenRouter HTTP client
    └── config.py              # Env defaults
```

## License

MIT
