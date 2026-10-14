# LunaVita

> **Work in progress:** LunaVita is an early-stage prototype and may change significantly.

## Track, Analyze, and Manage your Nutrition, Calories, Macros, and Fitness Goals using AI

LunaVita is a small, private health tracker for calories measured in kcal, macronutrients, and general health measurements. The stack runs locally with Docker Compose:

- PostgreSQL 17 stores all health data.
- A Python FastAPI service provides REST endpoints for the UI and a Streamable HTTP MCP endpoint.
- Streamlit provides the browser UI.

## Start

1. Copy `.env.example` to `.env` and replace the development database password.
2. Run `docker compose up --build -d`.
3. Open <http://127.0.0.1:18502>.

The REST API is available at <http://127.0.0.1:18001/docs>. The MCP endpoint is `http://127.0.0.1:18001/mcp`.

Docker is not started automatically by repository setup or validation.

Nutrition inference is optional and server-side. Set OPENAI_API_KEY in the ignored .env file; the key is passed only to the MCP/API service. OPENAI_MODEL defaults to gpt-4o-mini. The UI requests an estimate only when the user clicks the inference button, and the returned structured values remain editable until explicitly recorded.

## MCP tools

- `record_food`: stores a food item after the active ChatGPT model supplies the required quantity, kcal, macros, sugars, and optional representative image.
- `get_food_log`: lists entries, optionally within an inclusive date range.
- `update_food`: replaces the editable fields of a food entry.
- `set_food_image`: sets, replaces, or clears the optional image URL for a food entry.
- `remove_food`: deletes a food entry by ID, optionally guarded by its expected date.
- `record_health_measurement`: stores a named measurement such as weight, steps, or sleep.
- `get_health_measurements`: lists measurements, optionally filtered by metric.
- `get_daily_nutrition_summary`: totals calories in kcal and macros for one date.

For conversational logging, the active ChatGPT model infers missing kcal, protein, carbohydrates, fat, natural sugar, added sugar, and a representative image before calling the MCP tool. Food name and quantity are always required; inferred values remain editable.

The Streamlit **Daily log** tab filters food entries to one date and persists cell edits and marked removals through the API. It also downloads a small draft PDF report for the selected date. This report is intentionally simple for the rough-draft phase and can be restyled later without changing the stored data.

## Data model

The database mirrors the Daily Calorie Tracker report fields. Food rows preserve the date/time plus an optional display time label, food or supplement name, image URL, quantity, calories in kcal, protein, carbohydrates, fat, natural sugar, added sugar, meal category, and notes.

Each date can also store calorie and macro targets, fat and added-sugar ranges, historical reported totals, activity notes, supplement notes, daily notes, and report caveats. Reported totals are separate because rounded historical line items may not reconcile exactly. Health measurements preserve metric, value, unit, timestamp, optional time label (such as morning or night), and notes.

`food_entries` records food name, meal category, calories in kcal, protein/carbohydrate/fat grams, consumption time, and optional notes. `health_measurements` is intentionally flexible: each row contains a metric name, numeric value, unit, time, and notes. Constraints prevent negative nutrition values and unsupported meal categories. Timestamps are stored with time zones.

The schema is created from `database/init.sql` only when PostgreSQL initializes a new data volume. Later schema changes should use migrations rather than editing an already-applied initialization file.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_DB` | `lunavita` | Database name |
| `POSTGRES_USER` | `lunavita` | Database user |
| `POSTGRES_PASSWORD` | `lunavita-dev` | Database password; override in `.env` |
| `MCP_PORT` | `18001` | Host port for REST and MCP |
| `UI_PORT` | `18502` | Host port for Streamlit |

Both published services bind to `127.0.0.1` so they are not exposed on the local network by default.

The default host ports intentionally differ from Luna Vault, allowing both stacks to run at the same time.
