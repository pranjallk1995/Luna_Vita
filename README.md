# Luna Vita

![Docker required](https://img.shields.io/badge/Docker-required-2496ED?logo=docker&logoColor=white)
![Docker Compose v2](https://img.shields.io/badge/Docker_Compose-v2-2496ED?logo=docker&logoColor=white)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Luna Sentia required](https://img.shields.io/badge/Luna_Sentia-required-6C5CE7?logo=docker&logoColor=white)
![PostgreSQL in Luna Sentia](https://img.shields.io/badge/PostgreSQL-in_Luna_Sentia-4169E1?logo=postgresql&logoColor=white)
![Status: v1.4](https://img.shields.io/badge/Status-v1.4-2EA043)

<p align="center">
  <a href="docs/assets/luna-vita-showcase.mp4"><img src="docs/assets/luna-vita-showcase.webp" alt="From Google sign-in through Luna Unia to daily and monthly tracking in Luna Vita, then asking a chat assistant about the day and logging a meal through its MCP tools" width="900"></a>
</p>

<p align="center"><em>From Google sign-in through Luna Unia to daily and monthly tracking in Luna Vita, then asking a chat assistant about the day and logging a meal through its MCP tools. Select it for the sharper video.</em></p>

> Luna Vita is a local-first and desktop-first nutrition and body-measurement tracker.

## Track, Analyze, and Manage your Nutrition, Calories, Macros, and Fitness Goals using LLMs

Luna Vita combines a responsive React interface, one FastMCP service for conversational tools and UI-facing HTTP routes, and persistence in Luna Sentia's shared PostgreSQL. It is designed to run beside [Luna Visia](https://github.com/pranjallk1995/Luna_Visia) on the shared private Docker network created by [Luna Sentia](https://github.com/pranjallk1995/Luna_Sentia) while keeping its service names, host ports, and database separate.

> **Requires Luna Sentia, running and healthy:** Luna Vita keeps its data in Luna Sentia's PostgreSQL (`luna-sentia-db`) and joins Sentia's `luna_sentia_network`; it has no database of its own. Start [Luna Sentia](https://github.com/pranjallk1995/Luna_Sentia) first and wait until its `postgres` and `ollama` services report healthy, as described under [Start](#start). Food-image matching also needs Luna Visia running on the same network.

<p align="center">
  <img src="docs/assets/luna-vita-dashboard.png" alt="Luna Vita daily nutrition dashboard" width="1200">
</p>

[Luna Visia](https://github.com/pranjallk1995/Luna_Visia) provides the private image-vault workflow, while Luna Vita records food, nutrition, consumed time, and the matching food images. Their separate services share the private `luna_sentia_network`, allowing both applications to remain independently managed while participating in the same conversational workflow.

<p align="center">
  <img src="docs/assets/luna-vita-monthly.png" alt="Luna Vita monthly tracking page with daily averages, a per-day chart, and a workout calendar" width="1200">
</p>

The active ChatGPT/Codex model (or the LLM of your choice) performs nutrition estimation before calling Luna Vita. For example:

> I had 4 parathas of 40 g each right now.

The model should infer the complete-quantity values for kcal, protein, carbohydrates, fat, natural sugar, and added sugar, then call `log_consumed_food`. Food name and quantity are always mandatory. The model searches Luna Visia for a representative image and passes its public image-ID URL (`.../api/public/images/<image-id>`). Luna Vita checks the URL against Visia's catalog before saving and stores the canonical URL Visia publishes, so filename URLs, data URIs, unknown or hidden images, and invented URLs are rejected. When the model finds no suitable image and omits the URL, the entry shows the Luna Vita food placeholder, an image stored in Visia itself (set with `LUNAVITA_PLACEHOLDER_IMAGE_ID`). If Luna Visia is unreachable the entry is refused rather than saved without an image. Photos uploaded through the Luna Vita UI remain optional and are not affected.

### Generated food images

A food can have its own image, shown on every entry of that food, past and future, under any of its spellings and aliases. Ask for one in chat:

> Generate and update the image for schezuan rice.

A model that can generate images (for example ChatGPT) creates a photo of the dish and passes it to `update_food_image` in one call. Luna Vita sends the image to Luna Visia, which stores, captions, and tags it (`food`, `luna vita`, the food's name), then links Visia's stable public URL to the food and updates its existing entries. If Visia cannot store the image, nothing in Vita changes. Visia returns the image it already has when it gets the same bytes again, so a retried call never makes a duplicate. A model that cannot generate images passes a Visia `public_url` instead. Every Visia image Vita uses, the placeholder included, is tagged `luna vita` and `food` in Visia, and Luna Vibia's cover art (tagged `luna vibia` or `cover art`, with a song title written on it) is refused. Entries logged with the placeholder include an `image_hint` that asks the model to generate one. Renames and aliases carry the image to the new name. Storing images needs `LUNAVISIA_COMPANION_TOKEN`, set to the same value here and in Luna Visia; without it, only existing Visia images can be linked.

A food with no image in Luna Visia gets one when it is logged, as Luna Vibia does for covers. Vita's MCP server tells connecting clients to log the food first, since generating an image can end the model's turn. When the result carries an `image_hint`, the model tells you the food is logged, then generates an appetizing, realistic photo of the dish: plated, no text, landscape with a 3:2 aspect ratio (4.5 x 3, e.g. 1536x1024). It passes the photo to `update_food_image`, which stores it in Visia and shows it on every entry of that food. If the turn ends first, the model finishes it on your next message without logging the food again. `log_consumed_foods` logs a whole meal or day in one call and lists the foods that need an image once each, so the model makes one image per food. `update_food_images` can store several generated images at once.

Inference happens in the active AI conversation. Luna Vita stores the supplied structured values and does not require a separate API key for this workflow.

## Current features

### Daily nutrition

- Date-based daily log with running totals for calories in kcal, protein, carbohydrates, fat, and sugar.
- Recommendation-aware status cards with neutral, warning, exceeded, and protein-target states.
- Editable food table backed by PostgreSQL.
- Time and image columns remain pinned during horizontal scrolling.
- Food name and quantity are required.
- Optional consumed time; historical or free-form time labels remain supported.
- Optional image upload from the device. Images are resized before being stored with the entry.
- Click a food photo to zoom it.
- Row deletion through the final **Delete** column.
- Save and daily PDF actions on one row.
- Daily, Weekly, and Monthly navigation; Daily and Monthly are implemented and Weekly is a placeholder.
- Persistent navigation selection, including repeated clicks on the active segment.

### Monthly tracking

The Monthly tab analyses the calendar month containing the selected date, however many days have been logged so far. The assistant can instead save a custom date range with `set_monthly_range`; the tab then shows that range (marked "range set through the assistant") until `reset_monthly_range` is called.

- **Overview** - entries, distinct foods, days logged, and daily-average nutrient cards against your targets. Averages use logged days only, so unlogged or future days don't dilute them. Below each card, a per-day column chart in the card's color shows that nutrient for every day of the range against its target line; hover or tap a column for the exact value, and unlogged days stay empty.
- **What you had** - a photo collage of every food in the month, with the foods you had most often shown biggest. Each tile shows how many times you had it and a thumbs up or down for its verdict. Tap a tile to see the photo large, with how many days you had it and its totals for the month. Spelling variants such as "Paratha" and "parathas" are grouped.
- **Top contributors** - the three foods that supplied the most calories, protein, carbs, fat, and added sugar, as a share of the month's total.
- **Food choices** - foods to prefer and to avoid, rated on macros unless you set a rating through the assistant (shown as "Your rating"). Shares are of each food's logged calories (4 kcal/g protein and carbs, 9 kcal/g fat); foods under 50 kcal per serving, such as supplements, are not rated.
  - *Prefer*: at least 20% of calories from protein, at most 40% from carbs, and under 5% from added sugar. Ranked by macro score.
  - *Avoid*: 10% or more of calories from added sugar (the WHO free-sugar guideline), or under 10% from protein. Ranked by calories consumed, so the biggest wins come first.

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

### Bulk corrections

Assistants can correct many records at once across a range of dates: food entries by food and meal, body measurements by metric, workout days by done or skipped, and logged exercises by name and type.

- Only the values given change, and only records inside the range.
- Values that describe one thing, such as calories, a weight, or an exercise's reps, need a food, metric, or exercise name.
- Overwritten values can't be recovered, so each tool has a `dry_run` preview, and assistants are told to confirm with you first.

### Responsive interface

- Luna Visia-inspired dark, monochrome styling and Luna Vita branding.
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

## Users and separate storage

Each person signs in with Google and has their own space in Luna Vita: the schema `u_<id>` in the `lunavita` database. It is created the first time they use the app. The owner adds, disables, and deletes people at Luna Sentia's `/admin`, and can hide this app from everyone else there; see [Users and separate storage](https://github.com/pranjallk1995/Luna_Sentia#users-and-separate-storage).

### Connecting an MCP client

Add `https://<your vita MCP host>/mcp` to your client, such as Claude or ChatGPT, as a custom connector using OAuth. The client signs you in with Google and shows an approval page; check the return address, then allow it. Its tools then act only on your data. A request without a valid token gets 401.

Food photos are stored in the person's own Luna Visia gallery. The food placeholder image is one shared image in the owner's gallery.

In the code, `mcp/app/core/tenancy.py` holds who the current request or job acts for, `mcp/app/data/tenants.py` creates and removes each person's schema, and `mcp/app/transport/luna_mcp.py` checks connector tokens and the private token on `/api/` routes. Code that does not say who it acts for raises `NoUserError` rather than reading anyone's data.

## Architecture

### Luna ecosystem

![Luna ecosystem architecture](docs/assets/luna-ecosystem.svg)

<!-- luna-models:start -->
**Which app uses which model.** All of them run on Luna Sentia, which keeps Socia's chat model on the GPU and lets the others visit; see its [Models](https://github.com/pranjallk1995/Luna_Sentia#models) and [Changing a model](https://github.com/pranjallk1995/Luna_Sentia#changing-a-model).

| Model | Served by | Used by | Before changing it |
| --- | --- | --- | --- |
| `qwen3-vl:8b-instruct` | Ollama | Lexia (`DOCUMENT_MODEL`), Visia (`VISION_MODEL`), Vibia (`CAPTION_MODEL`), Fiora (`OLLAMA_MODEL`), Socia's photo descriptions (`LUNASOCIA_VISION_MODEL`) | `model_checks/check_model.py`, then Lexia's, Visia's and Vibia's `model_evaluations/` |
| `qwen3:14b` | Ollama, resident at `SENTIA_RESIDENT_CONTEXT` | Socia's chat (`LUNASOCIA_CHAT_MODEL`) | `model_checks/check_model.py --context 8192`, then Socia's `model_evaluations/` |
| `qwen3-embedding:0.6b` | Ollama | Lexia's semantic search (`EMBEDDING_MODEL`) | Re-embed with Lexia's `reindex_semantic_search` |
| Qwen-Image 2.1 Turbo | ComfyUI | Socia's pictures of Luna | A few pictures by hand |
| SigLIP 2 (`google/siglip2-base-patch16-224`) | Visia itself, GPU only | Visia's meaning search | Pinned in Visia's image; `backfill_metadata` re-embeds |
| CLAP (`laion/clap-htsat-unfused`) | Vibia itself, GPU or CPU | Vibia's listening and search | Pinned in Vibia's image; every track is heard again |
| Docling (layout, tables, OCR) | Lexia itself, GPU or CPU | Lexia's page reading | Pinned in Lexia's image |
| Whisper `large-v3-turbo`, Kokoro 82M | Socia itself, CPU | Socia's voice messages and Luna's voice (`LUNASOCIA_STT_MODEL`, `LUNASOCIA_TTS_VOICE`) | Listen to a few replies; downloaded on first use |
<!-- luna-models:end -->

Every Luna app but Luna Socia is a React UI plus a FastMCP service on Luna Sentia's
`luna_sentia_network`; Socia, the owner's chat with Luna, is one service with no MCP
server. Each app's data lives in Sentia's PostgreSQL, people sign in through Sentia's
`auth`, and model calls go through Sentia's model monitor, which times each one, samples
the GPU and keeps Socia's chat model resident, to its Ollama. Socia's pictures come from
Sentia's ComfyUI, which takes turns with Ollama on the GPU. Visia's SigLIP 2, Vibia's CLAP
and Lexia's Docling run inside those apps instead, each in a process that exits when idle.
Orange lines are Visia image URLs that other apps use: food images for Vita, room images
for Lumia, and cover art for Vibia. Grey dashed lines are planned: links into Fiora (tax
details from Lexia, transaction image and icon URLs from Visia). Luna Unia is the one home
for the other apps, on port 42069: it checks which Luna stacks are running and opens each
one with the shared sign-in. The purple line is the mood and beats of the track Vibia
plays, which Lumia's lights follow.

| Component | Technology | Purpose |
| --- | --- | --- |
| UI | React + TypeScript (Vite), served by a Starlette gateway | Daily tracker, entry dialogs, editable food log, charts, and PDF download |
| HTTP and MCP | FastMCP custom routes + tools | UI endpoints and conversational tools on one server |
| Database | PostgreSQL 17 in Luna Sentia (`luna-sentia-db`) | Food, health measurements, recommendations, and daily context |
| Network | `luna_sentia_network` (external) | Shared private network created by Luna Sentia and joined by every Luna app |

The services use unique network aliases:

- `luna-vita-mcp`
- `luna-vita-ui`

This avoids collisions with other Luna apps' services such as `postgres` or `mcp` on the shared network.

## Start

Start [Luna Sentia](https://github.com/pranjallk1995/Luna_Sentia) first and wait until it is healthy. Sentia runs
the PostgreSQL server that holds Vita's `lunavita` database, serves the models,
and creates the shared `luna_sentia_network` every Luna app joins. Vita has no
database of its own: started before Sentia is healthy, it cannot reach its
data and keeps restarting until it can.

```sh
cd ../Luna_Sentia
docker compose up -d --wait postgres ollama adminer
docker compose run --rm postgres-init   # creates the lunavita role and database
docker compose ps                       # postgres and ollama must show (healthy)
```

See [Is Sentia healthy?](https://github.com/pranjallk1995/Luna_Sentia#is-sentia-healthy) if they do not.

To start Sentia and every Luna app together, with or without Compose Watch, use
`../luna.sh start [--watch]`; see the
[Sentia README](https://github.com/pranjallk1995/Luna_Sentia#start-everything).

A fresh clone needs no `.env`: `luna.sh start` runs Vita with localhost defaults, where only Luna Sentia's owner may use it and the UI-to-backend token is `lunavita-dev-token-for-localhost-only`. Set your own values before giving it a public (https) address; `luna.sh start` refuses a public app that still uses the default token.

To change them, create a private `.env`:

```dotenv
# Must equal LUNAVITA_DB_PASSWORD in Luna_Sentia/.env
POSTGRES_PASSWORD=replace-with-a-private-database-password
LUNAVISIA_API_URL=http://luna-visia-mcp:8000
LUNAVITA_PLACEHOLDER_IMAGE_ID=858eafb0-73ad-4717-8095-8cef43c62d3c
LUNAVITA_ALLOWED_EMAILS=*
LUNAVITA_API_TOKEN=replace-with-a-random-value-of-at-least-32-characters
```

`LUNAVITA_API_TOKEN` is a shared secret between the UI and the MCP server. Generate your own with `openssl rand -hex 32`.

`*` allows everyone with a Luna account; otherwise separate accounts with commas. Keep `LUNAVISIA_API_URL` on the shared
Docker network. `MCP_PUBLIC_URL` is optional and defaults to `http://localhost:18001`; set it to your public HTTPS origin when the server is exposed (plain HTTP is accepted only for localhost).Replace the placeholder image ID only when Vita should use a
different existing Visia image as its fallback.

### Sign-in

Vita signs people in through Luna Sentia's single sign-on: one Google sign-in at
Sentia opens every Luna app, and **Sign out** in any app signs out of all of them.
Vita needs no Google client of its own. Set in `.env`:

- `LUNA_SSO_URL`: Sentia's public sign-on address (`SENTIA_AUTH_PUBLIC_URL` in
  Sentia's `.env`), for example `https://auth.lunaapps.fyi`.
- `LUNA_SSO_INTERNAL_URL`: `http://luna-sentia-auth:8000`, where Vita checks
  sessions over `luna_sentia_network`.
- `LUNAVITA_ALLOWED_EMAILS`: who may use Vita among the people with a Luna account: blank
  (the default) for Sentia's owner only, `*` for everyone, or a comma-separated list. The owner always may. Checked after Sentia confirms who is signed in.

Sentia's auth service must be healthy before Vita can sign anyone in; see
[Single sign-on](https://github.com/pranjallk1995/Luna_Sentia#single-sign-on) for its setup.

Then start Luna Vita:

```powershell
docker compose up --build
```

Open:

- UI: <http://127.0.0.1:18502>
- Service health: <http://127.0.0.1:18001/health>
- MCP endpoint: <http://127.0.0.1:18001/mcp> (clients sign in; see Connecting an MCP client)
- Favicon and icons: <http://127.0.0.1:18001/favicon.ico> and `/icons/icon-{48,96,192,512}.png`; the 48 and 96 px icons are also embedded in the MCP `initialize` server info so connector clients such as Claude can show them.

The example keeps these development defaults:

| Setting | Default |
| --- | --- |
| Database | `lunavita` |
| Username | `lunavita` |
| Password | `lunavita-dev` |
| Database host inside Docker | `luna-sentia-db` |

The API token and Google-account allowlist have no defaults and must be set in `.env` before
Compose starts the UI.

Docker is not started automatically by repository setup or validation.

## Codex MCP configuration (optional)

Add the following to the Codex `config.toml` in `.codex` directory in root:

```toml
[mcp_servers.lunavita]
url = "https://vita-mcp.example.com/mcp"
enabled = true
required = false
startup_timeout_sec = 20
tool_timeout_sec = 60
```

A task that was already open before a new tool was added may need to be reloaded or reopened for tool discovery.

## Database UI

Use [Adminer in Luna Sentia](https://github.com/pranjallk1995/Luna_Sentia#database-ui) at
<http://127.0.0.1:19080>. It reaches every Luna database over the shared private
`luna_sentia_network`; the database port itself remains unavailable from the host. Use:

- System: `PostgreSQL`
- Server: `luna-sentia-db`
- Username: `lunavita`
- Password: your `POSTGRES_PASSWORD`, or `lunavita-dev` when unset
- Database: `lunavita`

## MCP tools

### Web UI

- `get_ui_link` - the link to open this app's web UI, to give the user; they sign in with their Luna account.

### Food

- `record_food` — store a completed food entry with a Visia-verified image URL, or the placeholder image when none is given.
- `log_consumed_food` — store food described conversationally after the active model infers missing nutrition and finds its image in Luna Visia, falling back to the placeholder image.
- `log_consumed_foods` — log up to 50 foods from one message, each saved on its own under `saved` or `failed`, with the foods that still need an image listed once under `foods_needing_images`.
- `get_food_log` — list food entries, optionally over an inclusive date range.
- `update_food` — replace an existing food entry.
- `update_food_entries` — set the same values on every matching food entry in a date range, by food and meal, with a `dry_run` preview. Quantity and nutrition need a food name.
- `set_food_image` — set or replace one entry's image with a Luna Visia image, or the food placeholder when none fits.
- `update_food_image` — store a generated or attached image in Luna Visia and show it on every entry of that food, now and later.
- `update_food_images` — give up to 50 foods their image at once, as Visia `public_url`s or generated images (data URLs or HTTPS links), each entry reported under `updated` or `failed`.
- `search_food_images` — find foods by name or alias, by whether they have their own image, or by the Visia image they use.
- `remove_food` — delete a food entry, optionally guarded by its expected date.

### Measurements and summaries

- `record_health_measurement` — store weight, BMI, BMR, water ratio, or another measurement.
- `get_health_measurements` — list recent measurements, optionally filtered by metric.
- `update_health_measurement` — replace an entire measurement entry by its database ID.
- `update_health_measurements` — set the same values on every measurement in a date range, optionally of one metric, with a `dry_run` preview. Value and unit need a metric.
- `remove_health_measurement` — delete an entire measurement entry by its database ID.
- `get_daily_nutrition_summary` — return daily totals in kcal and grams.
- `get_current_log_pdf` — generate and return today's complete log as a PDF.

### Workouts

- `update_workouts` — set the same values on every workout day already recorded in a date range, with a `dry_run` preview. Marking days skipped clears their types.
- `update_workout_exercises` — set the same values on every logged exercise in a date range, by name and type, with a `dry_run` preview. Sets, reps, weight, and duration need an exercise name.

### Monthly analysis

- `get_food_analysis` - return the Monthly Tracking data: counts, macro totals, verdicts, top contributors, and prefer/avoid lists. Without dates it returns exactly what the tab shows; with dates it analyses that range or month without changing the tab.
- `set_monthly_range` - choose the date range the Monthly tab shows (up to 366 days).
- `reset_monthly_range` - return the Monthly tab to the calendar month of the selected date.
- `get_monthly_range` - report the range the Monthly tab shows and whether it is saved.
- `rename_food` - rename or merge a food across its entries (matching ignores case, punctuation, and a trailing plural "s"), optionally within dates. Counts, totals, and computed verdicts follow automatically.
- `set_food_verdict` - rate a food prefer, avoid, or neutral with a reason, replacing its macro-based rating in every period.
- `clear_food_verdict` - remove a rating so the food is judged on its macros again.
- `list_food_verdicts` - list every rating set this way.

### Daily context and recommendations

- `get_day_context` — read goals, reported totals, activity, supplements, and notes.
- `save_day_context` — store the day's context.
- `update_daily_recommendations` — replace calorie, protein, carbohydrate, fat, and sugar recommendations together with the body profile.
- `get_daily_recommendations` — return the current recommendations and profile.
- `update_body_profile` — update height, date of birth, sex, or weight while preserving other profile fields.

Age is calculated dynamically from the stored date of birth, so it changes automatically on the birthday.

## Data model

### `food_entries`

Stores the consumed date and timestamp, optional display-time label, food/supplement name, quantity, calories in kcal, protein, carbohydrates, fat, natural sugar, added sugar, optional image, and notes. Luna Visia images are referenced through their immutable image-ID URLs, so renaming a file in Visia does not break its Vita entry.

### `health_measurements`

Stores one metric per row with its value, unit, timestamp, Morning/Night label, and optional notes. Grouped body-measurement submissions therefore remain independently queryable.

### `daily_recommendations`

Stores the current kcal and macro recommendations plus height, sex, date of birth, weight, goal, and notes.

### `food_verdicts`

Stores explicit prefer/avoid/neutral ratings and their reasons, keyed by the normalized food name so every spelling of a food shares one rating.

### `analysis_range`

A single optional row holding the custom date range the Monthly tab shows. When it is absent, the tab shows the selected date's calendar month.

### `daily_logs`

Stores date-specific goals, reported totals, activity notes, supplement notes, daily notes, and report caveats.

Nutrition fields reject negative values, food names and quantities cannot be blank, and timestamps are stored with time-zone support.

The idempotent schema in `mcp/app/data/database.py` is applied whenever the Luna Vita service starts. It creates a new database structure when needed and applies safe additive upgrades to existing databases.

## Project structure

The backend follows the same layered package layout across all three Luna apps:

- `mcp/app/core/` - configuration, validation models, and domain primitives.
- `mcp/app/data/` - database setup, repositories, and storage adapters.
- `mcp/app/services/` - transport-independent use cases and orchestration.
- `mcp/app/integrations/` - external services, devices, and peer-app clients.
- `mcp/app/transport/` - FastMCP tools, HTTP routes, authentication, and branding.
- `mcp/app/main.py` - the small composition root that wires the layers together.

Luna Vita, Luna Lumia, and Luna Visia share this layout:

```text
.
├── docker-compose.yaml     # services, shared-network membership, and Compose Watch rules
├── README.md
├── UI_STYLE_GUIDE.md       # shared Luna visual reference
├── docs/assets/            # README screenshots
├── mcp/                    # FastMCP server: MCP tools plus UI-facing HTTP routes
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/                # main.py composition root, config, database, models,
│   │                       # repositories, services, mcp_tools, http_routes,
│   │                       # and the app's own domain modules
│   ├── scripts/            # one-off maintenance scripts, when needed
│   └── tests/              # python -m unittest discover -s tests
└── ui/                     # React interface and its gateway
    ├── Dockerfile          # builds the React app, then the gateway image
    ├── requirements.txt
    ├── assets/             # source logo
    ├── config.py           # environment-backed settings
    ├── gateway.py          # serves the app; checks sign-in; fronts the backend
    ├── photos.py           # fits food photos stored in Luna Visia
    ├── sso.py              # single sign-on through Luna Sentia
    ├── tests/              # gateway tests: python -m unittest discover -s tests
    └── web/                # the React app (TypeScript, Vite); npm test runs its logic tests
```

The browser app talks only to the gateway, which checks the shared session and allowlist
on every data request and forwards only the backend routes the UI uses.

## Development workflow

Compose Watch synchronizes source changes while the foreground watcher is running:

- Changes under `mcp/app` sync and restart the API/MCP container.
- Changes to the gateway under `ui` sync and restart it; changes under `ui/web/src` rebuild the UI image (for hot reload, run `npm run dev` in `ui/web`).
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

### UI modules

Pure logic lives in `domain/` and is unit tested directly, backend access and caching live in `services/`, and the `views/` package only renders.

- `ui/gateway.py` - serves the built app, reports the session and settings at `/auth/session`, fits food photos, and forwards an allowlist of backend routes.
- `ui/config.py` and `ui/sso.py` - validated gateway settings, and single sign-on through Luna Sentia.
- `ui/web/src/nutrition.ts` - nutrient card definitions, target status rules, and macro percentages.
- `ui/web/src/food.ts` - consumed-time display, ordering, and parsing, food-entry payloads, and client-side mirrors of the backend's text and number rules.
- `ui/web/src/body.ts` - tracked body metrics, Morning/Night tables, measurement payloads, and weight and body fat series.
- `ui/web/src/workouts.ts` - workout types, the calendar, and exercise rows.
- `ui/web/src/clock.ts` - Asia/Kolkata dates and timestamps.
- `ui/web/src/api.ts` - the backend routes and hooks, and fitting a chosen food photo in the browser.
- `ui/web/src/components/` - the summary, food log, workout, measurements, and Monthly sections.
- `ui/web/src/domain.test.ts` - unit tests for ordering, validation, macro math, measurement tables, and payloads.
- `ui/requirements.txt` - Python dependencies used by the gateway.
- `ui/Dockerfile` - builds the UI container image.

### MCP modules

Dependencies point one way: transports (`mcp_tools.py`, `http_routes.py`) call services, services call repositories, and only `main.py` knows the concrete wiring.

- `mcp/app/main.py` - `LunaVitaApplication` composition root: builds the database, repositories, and services, then registers the MCP tools and HTTP routes on one FastMCP server.
- `mcp/app/core/config.py` - validated backend settings loaded from the environment.
- `mcp/app/transport/branding.py` - `ServerBranding`, the bundled icon set in `mcp/app/assets/` (favicon plus PNG sizes) exposed as MCP server-info icons and HTTP icon routes.
- `mcp/app/transport/mcp_tools.py` - conversational MCP tools, grouped by food, measurements, day context, and profile.
- `mcp/app/transport/http_routes.py` - UI-facing REST routes with uniform JSON error translation.
- `mcp/app/services/application.py` - transport-independent use cases: `FoodService`, `MeasurementService`, `DayContextService`, `ProfileService`, `ReportService`, and `AnalysisService`, grouped by the `LunaVitaService` facade.
- `mcp/app/data/repositories.py` - PostgreSQL persistence, one repository per table on a shared `Repository` base.
- `mcp/app/core/models.py` - validated food, measurement, recommendation, body-profile, and daily-context request models.
- `mcp/app/data/database.py` - connection-pool management and idempotent schema creation and upgrades.
- `mcp/app/services/analysis.py` - pure period analysis: food-name grouping, macro-quality rules, verdict overrides, and the JSON shared by the UI route and MCP tool.
- `mcp/app/integrations/visia.py` - `VisiaImageCatalog`, which verifies assistant-supplied food images against Luna Visia's catalog.
- `mcp/app/services/body_composition.py` - weight and body fat % series, estimating body fat when it was not recorded.
- `mcp/app/services/reports.py` - pure ReportLab rendering of a collected `DailyReport` into the daily PDF.
- `mcp/app/transport/report_tools.py` - MCP embedded-resource wrapper for the current daily PDF.
- `mcp/app/core/clock.py` - Asia/Kolkata dates and timestamp localization.
- `mcp/app/core/errors.py` - domain errors that the HTTP routes map to status codes.
- `mcp/tests/` - unit tests for schemas, models, services, HTTP error mapping, report formatting, and MCP report delivery.
- `mcp/requirements.txt` - Python dependencies used by the MCP/API container.
- `mcp/Dockerfile` - builds the MCP/API container image.
