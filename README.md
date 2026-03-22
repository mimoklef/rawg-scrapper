# RAWG Simple Scraper + Userscript

This publish package contains:
- one simple Python scraper for RAWG
- one browser userscript for manual game collection on rawg.io

No name formating is applied. Field names are kept as RAWG names.

## Included Files

- requirements.txt
- online_games_scraper.py
- rawg_online_games_scraper.py
- rawg_collect_games.user.js

## 1) Python Scraper (Simple, Raw Field Names)

Entrypoint:
- online_games_scraper.py

Implementation:
- rawg_online_games_scraper.py

### What it does

- Crawls RAWG game list pages
- Fetches game detail by slug
- Exports JSON with RAWG field names unchanged
- Includes alternative_names by default (which require an additionnal request by game)
- Supports resume/checkpoints in case of crash
- Lets you choose which data blocks to include/exclude

### Install

```bash
pip install -r requirements.txt
```

### API Key

The scraper checks, in order:
- --api-key
- environment variables RAWG_API_KEY / key / KEY
- .env file (RAWG_API_KEY or key)

Example .env:

```dotenv
key=YOUR_RAWG_API_KEY
```
(You can get one from the search URL in the website 🤭)


### Quick Start

```bash
python online_games_scraper.py --output rawg_games.json --resume --debug
```

### Useful Options

- --output: output JSON file
- --resume: resume from output + state
- --state-file: custom state file path
- --count: max number of games (0 = unlimited)
- --platform-ids: RAWG platform IDs CSV
- --page-size: RAWG page size (max 40)
- --max-pages-per-platform: 0 = unlimited
- --ordering: RAWG ordering (example: -added, -rating)
- --tags: RAWG tags filter for list endpoint (default: multiplayer)
- --checkpoint-every: save every N successful detail fetches
- --pause: delay between detail requests
- --timeout: HTTP timeout
- --max-retries: retry count

### Select Data Blocks

By default, all available blocks below are included:
- basic
- dates
- platforms
- genres
- tags
- ratings
- classification
- popularity
- media
- stores
- people
- description
- website
- alt_names
- metacritic_url

Use include/exclude controls:

```bash
python online_games_scraper.py \
  --include-blocks basic,platforms,genres,ratings,alt_names \
  --exclude-blocks description,website \
  --output rawg_games_light.json
```

Notes:
- RAWG field names are preserved (example: name, released, rating, alternative_names).

## 2) Userscript (RAWG Manual Collector)

File:
- rawg_collect_games.user.js

### What it does

- Adds + Add buttons on game cards
- Adds Add game to JSON on game page
- Fetches game detail by slug via RAWG API
- Exports selected games as JSON
- Includes alternative_names in userscript output
- Keeps RAWG field names unchanged (no field renaming)

### Usage

1. Install Tampermonkey (or Violentmonkey).
2. Create a new userscript and paste rawg_collect_games.user.js.
3. Open rawg.io and set API key in the script panel.
4. Add games and export JSON (Copy or Download).

