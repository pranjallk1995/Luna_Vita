# Luna Vita

![Docker required](https://img.shields.io/badge/Docker-required-2496ED?logo=docker&logoColor=white)
![Docker Compose v2](https://img.shields.io/badge/Docker_Compose-v2-2496ED?logo=docker&logoColor=white)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Streamlit included](https://img.shields.io/badge/Streamlit-included-FF4B4B?logo=streamlit&logoColor=white)
![FastMCP included](https://img.shields.io/badge/FastMCP-included-5C4EE5?logo=python&logoColor=white)
![PostgreSQL included](https://img.shields.io/badge/PostgreSQL-included-4169E1?logo=postgresql&logoColor=white)

> **Work in progress:** Luna Vita is a local-first and desktop first nutrition and body-measurement tracker under active development.

## Track, Analyze, and Manage your Nutrition, Calories, Macros, and Fitness Goals using AI

Luna Vita combines a responsive Streamlit interface, one FastMCP service for conversational tools and UI-facing HTTP routes, and PostgreSQL persistence. It is designed to run beside Luna Vault on the same private Docker network while keeping its service names, host ports, database, and volumes separate.

<p align="center">
  <img src="docs/assets/luna-vita-dashboard.png" alt="Luna Vita daily nutrition dashboard" width="1200">
</p>

## Current features

### Daily nutrition

- Date-based daily log with running totals for calories in kcal, protein, carbohydrates, fat, and sugar.
- Recommendation-aware status cards with neutral, warning, exceeded, and protein-target states.
- Editable food table backed by PostgreSQL.
- Time, image, and food-name columns remain pinned during horizontal scrolling.
- Food name and quantity are required.
- Optional consumed time; historical or free-form time labels remain supported.
- Optional image upload from the device. Images are resized before being stored with the entry.
- Row deletion through the final **Delete** column.
- Save and daily PDF actions on one row.
- Daily, Weekly, and Monthly navigation; Daily is implemented and the other two are placeholders.
- Persistent navigation selection, including repeated clicks on the active segment.

### Macro distribution

The donut chart displays:

- Protein
- Carbohydrates
- Fat
- Natural sugar
- Added sugar

Each percentage is calculated from the raw displayed macro values:

```text
macro percentage = macro value × 100 / sum of all displayed macro values
```

Hovering a segment shows its name, percentage, and value in grams. The donut center shows the day's total energy in kcal.

### Body measurements

Morning and night weigh-ins support:

- Weight in kg
- BMR in kcal/day
- Health score out of 100
- Body age in years
- BMI
- Water ratio in percent

Weight and Morning/Night are required. Measured time is optional and controlled by a toggle. The daily viewer shows the latest morning and night values side by side. Separate controls delete all morning or all night measurements for the selected date.

### Responsive interface

- Luna Vault-inspired dark, monochrome styling and Luna Vita branding.
- The mobile logo and title remain on one line.
- Daily/Weekly/Monthly navigation becomes icon-only on mobile.
- Morning and Night deletion controls use compact one-line mobile buttons.
- Dialogs are centered and inputs are arranged responsively.

### Daily PDF

The generated PDF contains:

1. Daily nutrition totals and the food log.
2. Activity, supplement, daily-note, and report-caveat content when present.
3. A second page containing Morning and Night body measurements.

All user-facing energy values are labeled in kcal.

## Architecture

| Component | Technology | Purpose |
| --- | --- | --- |
| UI | Streamlit | Daily tracker, entry dialogs, editable food log, charts, and PDF download |
| HTTP and MCP | FastMCP custom routes + tools | UI endpoints and conversational tools on one server |
| Database | PostgreSQL 17 | Food, health measurements, recommendations, and daily context |
| Network | `luna_vault_lunavault_network` | Shared private network with Luna Vault |

The services use unique network aliases:

- `luna-vita-db`
- `luna-vita-mcp`
- `luna-vita-ui`

This avoids collisions with Luna Vault services such as `postgres` or `mcp`.

## Start

Luna Vault's Docker network must exist first because Luna Vita joins it as an external network:

```powershell
docker network inspect luna_vault_lunavault_network
```

If Luna Vault normally creates this network, start Luna Vault first. Then, from the Luna Vita repository, run:

```powershell
docker compose up --build --watch
```

Open:

- UI: <http://127.0.0.1:18502>
- Service health: <http://127.0.0.1:18001/health>
- MCP endpoint: <http://127.0.0.1:18001/mcp>

The built-in development credentials work without creating a `.env` file:

| Setting | Default |
| --- | --- |
| Database | `lunavita` |
| Username | `lunavita` |
| Password | `lunavita-dev` |
| Database host inside Docker | `luna-vita-db` |

Environment overrides remain available when needed, but they are not required for local development.

Docker is not started automatically by repository setup or validation.

## Codex MCP configuration

Add the following to the Codex `config.toml`:

```toml
[mcp_servers.lunavita]
url = "http://127.0.0.1:18001/mcp"
enabled = true
required = false
startup_timeout_sec = 20
tool_timeout_sec = 60
```

A task that was already open before a new tool was added may need to be reloaded or reopened for tool discovery.

## Conversational food logging

The active ChatGPT/Codex model performs nutrition estimation before calling Luna Vita. For example:

> I had 4 parathas of 40 g each right now.

The model should infer the complete-quantity values for kcal, protein, carbohydrates, fat, natural sugar, and added sugar, then call `log_consumed_food`. Food name and quantity are always mandatory. A verified representative image URL or data URI can be supplied when available; otherwise the image must be left empty rather than invented.

Inference happens in the active AI conversation. Luna Vita stores the supplied structured values and does not require a separate API key for this workflow.

## MCP tools

### Food

- `record_food` — store a completed food entry.
- `log_consumed_food` — store food described conversationally after the active model infers missing nutrition.
- `get_food_log` — list food entries, optionally over an inclusive date range.
- `update_food` — replace an existing food entry.
- `set_food_image` — set, replace, or clear an optional food image.
- `remove_food` — delete a food entry, optionally guarded by its expected date.

### Measurements and summaries

- `record_health_measurement` — store weight, BMI, BMR, water ratio, or another measurement.
- `get_health_measurements` — list recent measurements, optionally filtered by metric.
- `get_daily_nutrition_summary` — return daily totals in kcal and grams.

### Daily context and recommendations

- `get_day_context` — read goals, reported totals, activity, supplements, and notes.
- `save_day_context` — store the day's context.
- `update_daily_recommendations` — replace calorie, protein, carbohydrate, fat, and sugar recommendations together with the body profile.
- `get_daily_recommendations` — return the current recommendations and profile.
- `update_body_profile` — update height, date of birth, sex, or weight while preserving other profile fields.

Age is calculated dynamically from the stored date of birth, so it changes automatically on the birthday.

## Data model

### `food_entries`

Stores the consumed date and timestamp, optional display-time label, food/supplement name, quantity, calories in kcal, protein, carbohydrates, fat, natural sugar, added sugar, optional image, and notes.

### `health_measurements`

Stores one metric per row with its value, unit, timestamp, Morning/Night label, and optional notes. Grouped body-measurement submissions therefore remain independently queryable.

### `daily_recommendations`

Stores the current kcal and macro recommendations plus height, sex, date of birth, weight, goal, and notes.

### `daily_logs`

Stores date-specific goals, reported totals, activity notes, supplement notes, daily notes, and report caveats.

Nutrition fields reject negative values, food names and quantities cannot be blank, and timestamps are stored with time-zone support.

The idempotent schema in `mcp/app/database.py` is applied whenever the Luna Vita service starts. It creates a new database structure when needed and applies safe additive upgrades to existing databases.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_DB` | `lunavita` | Database name |
| `POSTGRES_USER` | `lunavita` | Database user used by the health check |
| `POSTGRES_PASSWORD` | `lunavita-dev` | Database password |
| `LUNAVITA_API_URL` | `http://luna-vita-mcp:8000` | API address used by the UI container |

Published host ports are intentionally fixed and separate from Luna Vault:

- `127.0.0.1:18001` → API and MCP
- `127.0.0.1:18502` → Streamlit UI

Both bind to loopback only, so they are not exposed directly to the local network.

## Development workflow

Compose Watch synchronizes source changes while the foreground watcher is running:

- Changes under `mcp/app` sync and restart the API/MCP container.
- Changes under `ui` sync into the Streamlit container.
- Dependency or Dockerfile changes rebuild the affected service.

Use:

```powershell
docker compose up --build --watch
```

or, if the services are already running:

```powershell
docker compose watch --no-up
```

Stopping the foreground watcher also stops automatic source synchronization.
