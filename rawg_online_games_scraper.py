import argparse
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Set

import requests

RAWG_LIST_URL = "https://rawg.io/api/games"
RAWG_DETAIL_URL = "https://rawg.io/api/games/{slug}"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_PLATFORM_IDS = [18, 7, 4, 1, 5, 6, 187, 186, 21]

FIELD_BLOCKS = {
    "basic": ["id", "slug", "name", "name_original", "tba"],
    "dates": ["released", "updated"],
    "platforms": ["parent_platforms", "platforms"],
    "genres": ["genres"],
    "tags": ["tags"],
    "ratings": ["rating", "rating_top", "ratings", "ratings_count", "reviews_text_count"],
    "classification": ["esrb_rating", "metacritic", "metacritic_platforms"],
    "popularity": ["added", "added_by_status", "suggestions_count", "playtime"],
    "media": ["background_image", "background_image_additional", "short_screenshots", "clip", "movies"],
    "stores": ["stores"],
    "people": ["developers", "publishers"],
    "description": ["description_raw"],
    "website": ["website", "reddit_url"],
    "alt_names": ["alternative_names"],
    "metacritic_url": ["metacritic_url"],
}

DEFAULT_INCLUDE_BLOCKS = [
    "basic",
    "dates",
    "platforms",
    "genres",
    "tags",
    "ratings",
    "classification",
    "popularity",
    "media",
    "stores",
    "people",
    "description",
    "website",
    "alt_names",
    "metacritic_url",
]


def parse_csv_list(raw: str) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for part in (raw or "").split(","):
        token = part.strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def parse_platform_ids(raw: str) -> List[int]:
    out: List[int] = []
    seen: Set[int] = set()
    for part in (raw or "").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not os.path.exists(path):
        return values

    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value

    return values


def resolve_api_key(cli_api_key: Optional[str], env_file: str) -> str:
    if cli_api_key and cli_api_key.strip():
        return cli_api_key.strip()

    for name in ["RAWG_API_KEY", "key", "KEY"]:
        value = os.getenv(name, "")
        if value and value.strip():
            return value.strip()

    env_values = parse_env_file(env_file)
    for name in ["RAWG_API_KEY", "key", "KEY"]:
        value = env_values.get(name, "")
        if value and value.strip():
            return value.strip()

    return ""


def safe_get_json(
    session: requests.Session,
    url: str,
    params: Dict,
    timeout: int,
    max_retries: int,
    debug: bool,
    context: str,
) -> Optional[Dict]:
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as error:
            if debug:
                print(f"[debug][retry] {context}: network {attempt}/{max_retries} -> {error}")
            if attempt >= max_retries:
                return None
            time.sleep(min(20.0, attempt * 0.8))
            continue

        if response.status_code in {401, 403}:
            raise RuntimeError(f"RAWG API refused ({response.status_code})")

        if response.status_code in RETRY_STATUS_CODES:
            if debug:
                print(f"[debug][retry] {context}: status {response.status_code} {attempt}/{max_retries}")
            if attempt >= max_retries:
                return None
            time.sleep(min(20.0, attempt * 0.8))
            continue

        if response.status_code >= 400:
            if response.status_code in {400, 404}:
                try:
                    payload = response.json()
                    detail = payload.get("detail") if isinstance(payload, dict) else None
                    if isinstance(detail, str) and "invalid page" in detail.lower():
                        return {"_invalid_page": True}
                except ValueError:
                    pass
            if debug:
                print(f"[debug][error] {context}: status {response.status_code}")
            return None

        try:
            payload = response.json()
        except ValueError:
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    return None


def compute_selected_fields(include_blocks: List[str], exclude_blocks: List[str]) -> Set[str]:
    selected_blocks = [block for block in include_blocks if block in FIELD_BLOCKS]
    for block in exclude_blocks:
        selected_blocks = [value for value in selected_blocks if value != block]

    selected_fields: Set[str] = set()
    for block in selected_blocks:
        selected_fields.update(FIELD_BLOCKS[block])

    return selected_fields


def sanitize_alternative_names(values: object) -> List[str]:
    if not isinstance(values, list):
        return []

    out: List[str] = []
    seen: Set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        alias = value.strip()
        if not alias:
            continue
        key = alias.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(alias)
    return out


def build_output_item(detail_payload: Dict, selected_fields: Set[str]) -> Optional[Dict]:
    slug = detail_payload.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        return None

    item: Dict = {}
    for field in selected_fields:
        if field in detail_payload:
            item[field] = detail_payload.get(field)

    if "alternative_names" in item:
        item["alternative_names"] = sanitize_alternative_names(item.get("alternative_names"))

    return item if item else None


def merge_item(existing: Optional[Dict], incoming: Dict) -> Dict:
    if not existing:
        return incoming

    merged = dict(existing)

    for key, value in incoming.items():
        if key not in merged or merged.get(key) in [None, "", [], {}]:
            merged[key] = value
            continue

        if isinstance(merged.get(key), list) and isinstance(value, list):
            seen = set()
            out = []
            for entry in merged.get(key, []) + value:
                serialized = json.dumps(entry, sort_keys=True, ensure_ascii=False)
                if serialized in seen:
                    continue
                seen.add(serialized)
                out.append(entry)
            merged[key] = out
            continue

        if isinstance(merged.get(key), (int, float)) and isinstance(value, (int, float)):
            merged[key] = max(merged[key], value)

    return merged


def default_state(platform_ids: List[int]) -> Dict:
    return {
        "version": 1,
        "next_page_by_platform": {str(platform_id): 1 for platform_id in platform_ids},
        "completed_platforms": [],
        "stats": {
            "seen": 0,
            "details_ok": 0,
            "errors": 0,
        },
        "updated_at": None,
    }


def load_state(state_file: str, platform_ids: List[int], debug: bool) -> Dict:
    state = default_state(platform_ids)
    if not os.path.exists(state_file):
        return state

    try:
        with open(state_file, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as error:
        if debug:
            print(f"[debug][resume] failed reading state {state_file}: {error}")
        return state

    if not isinstance(payload, dict):
        return state

    next_pages = payload.get("next_page_by_platform")
    if isinstance(next_pages, dict):
        for platform_id in platform_ids:
            key = str(platform_id)
            value = next_pages.get(key)
            if isinstance(value, int) and value >= 1:
                state["next_page_by_platform"][key] = value

    completed = payload.get("completed_platforms")
    if isinstance(completed, list):
        valid = []
        allowed = set(platform_ids)
        for value in completed:
            if isinstance(value, int) and value in allowed and value not in valid:
                valid.append(value)
        state["completed_platforms"] = valid

    stats = payload.get("stats")
    if isinstance(stats, dict):
        for key in ["seen", "details_ok", "errors"]:
            value = stats.get(key)
            if isinstance(value, int) and value >= 0:
                state["stats"][key] = value

    return state


def save_state(
    state_file: str,
    next_page_by_platform: Dict[str, int],
    completed_platforms: List[int],
    seen: int,
    details_ok: int,
    errors: int,
) -> None:
    payload = {
        "version": 1,
        "next_page_by_platform": next_page_by_platform,
        "completed_platforms": completed_platforms,
        "stats": {
            "seen": max(0, seen),
            "details_ok": max(0, details_ok),
            "errors": max(0, errors),
        },
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_existing_output(output_file: str, debug: bool) -> Dict[str, Dict]:
    if not os.path.exists(output_file):
        return {}

    try:
        with open(output_file, "r", encoding="utf-8") as file:
            rows = json.load(file)
    except Exception as error:
        if debug:
            print(f"[debug][resume] failed reading output {output_file}: {error}")
        return {}

    if not isinstance(rows, list):
        return {}

    out: Dict[str, Dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = row.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            continue
        out[slug.strip().lower()] = row

    return out


def scrape_rawg(
    api_key: str,
    output_file: str,
    state_file: str,
    include_blocks: List[str],
    exclude_blocks: List[str],
    platform_ids: List[int],
    count: Optional[int],
    page_size: int,
    max_pages_per_platform: int,
    ordering: str,
    tags: str,
    pause: float,
    timeout: int,
    max_retries: int,
    checkpoint_every: int,
    resume: bool,
    debug: bool,
) -> List[Dict]:
    selected_fields = compute_selected_fields(include_blocks, exclude_blocks)
    if not selected_fields:
        raise ValueError("No fields selected. Check include/exclude blocks.")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
    )

    state = load_state(state_file, platform_ids=platform_ids, debug=debug) if resume else default_state(platform_ids)
    output_by_slug = load_existing_output(output_file, debug=debug) if resume else {}

    next_page_by_platform: Dict[str, int] = dict(state.get("next_page_by_platform") or {})
    completed_platforms: List[int] = list(state.get("completed_platforms") or [])

    seen = int((state.get("stats") or {}).get("seen") or 0)
    details_ok = int((state.get("stats") or {}).get("details_ok") or 0)
    errors = int((state.get("stats") or {}).get("errors") or 0)

    started = time.time()
    since_checkpoint = 0

    for platform_id in platform_ids:
        if platform_id in completed_platforms:
            if debug:
                print(f"[debug][resume] platform={platform_id} already done, skip")
            continue

        page = int(next_page_by_platform.get(str(platform_id), 1))
        platform_done = False

        while True:
            if max_pages_per_platform > 0 and page > max_pages_per_platform:
                break

            list_payload = safe_get_json(
                session=session,
                url=RAWG_LIST_URL,
                params={
                    "key": api_key,
                    "platforms": platform_id,
                    "tags": tags,
                    "ordering": ordering,
                    "page": page,
                    "page_size": max(1, min(40, page_size)),
                },
                timeout=timeout,
                max_retries=max_retries,
                debug=debug,
                context=f"list platform={platform_id} page={page}",
            )

            if list_payload is None:
                errors += 1
                break

            if list_payload.get("_invalid_page"):
                platform_done = True
                break

            results = list_payload.get("results")
            if not isinstance(results, list) or not results:
                platform_done = True
                break

            for game in results:
                seen += 1
                slug = (game.get("slug") or "").strip().lower() if isinstance(game, dict) else ""
                if not slug:
                    errors += 1
                    continue

                detail_payload = safe_get_json(
                    session=session,
                    url=RAWG_DETAIL_URL.format(slug=slug),
                    params={"key": api_key},
                    timeout=timeout,
                    max_retries=max_retries,
                    debug=debug,
                    context=f"detail slug={slug}",
                )

                if detail_payload is None:
                    errors += 1
                    continue

                if detail_payload.get("_invalid_page"):
                    errors += 1
                    continue

                item = build_output_item(detail_payload, selected_fields=selected_fields)
                if item is None:
                    errors += 1
                    continue

                details_ok += 1
                output_by_slug[slug] = merge_item(output_by_slug.get(slug), item)
                since_checkpoint += 1

                if isinstance(count, int) and len(output_by_slug) >= count:
                    break

                if checkpoint_every > 0 and since_checkpoint >= checkpoint_every:
                    rows = list(output_by_slug.values())
                    rows.sort(key=lambda row: str(row.get("slug") or ""))
                    with open(output_file, "w", encoding="utf-8") as file:
                        json.dump(rows, file, ensure_ascii=False, indent=2)
                    save_state(
                        state_file=state_file,
                        next_page_by_platform=next_page_by_platform,
                        completed_platforms=completed_platforms,
                        seen=seen,
                        details_ok=details_ok,
                        errors=errors,
                    )
                    since_checkpoint = 0
                    if debug:
                        elapsed = max(0.001, time.time() - started)
                        print(
                            f"[debug][checkpoint] items={len(output_by_slug)} seen={seen} "
                            f"ok={details_ok} errors={errors} speed={details_ok / elapsed:.2f}/s"
                        )

                if pause > 0:
                    time.sleep(pause)

            if isinstance(count, int) and len(output_by_slug) >= count:
                break

            if not list_payload.get("next"):
                platform_done = True
                break

            page += 1
            next_page_by_platform[str(platform_id)] = page

            save_state(
                state_file=state_file,
                next_page_by_platform=next_page_by_platform,
                completed_platforms=completed_platforms,
                seen=seen,
                details_ok=details_ok,
                errors=errors,
            )

        next_page_by_platform[str(platform_id)] = page
        if platform_done and platform_id not in completed_platforms:
            completed_platforms.append(platform_id)

        save_state(
            state_file=state_file,
            next_page_by_platform=next_page_by_platform,
            completed_platforms=completed_platforms,
            seen=seen,
            details_ok=details_ok,
            errors=errors,
        )

        if isinstance(count, int) and len(output_by_slug) >= count:
            break

    rows = list(output_by_slug.values())
    rows.sort(key=lambda row: str(row.get("slug") or ""))

    if isinstance(count, int):
        rows = rows[:count]

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)

    save_state(
        state_file=state_file,
        next_page_by_platform=next_page_by_platform,
        completed_platforms=completed_platforms,
        seen=seen,
        details_ok=details_ok,
        errors=errors,
    )

    print(f"Done: {len(rows)} games written to {output_file}")
    print(f"Stats: seen={seen}, details_ok={details_ok}, errors={errors}")

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple RAWG scraper with selectable field blocks.")

    parser.add_argument("--api-key", type=str, default=None, help="RAWG API key")
    parser.add_argument("--env-file", type=str, default=".env", help="Env file used to read key")

    parser.add_argument("--output", type=str, default="rawg_games.json", help="Output JSON file")
    parser.add_argument("--state-file", type=str, default=None, help="Resume state file (default: <output>.state.json)")
    parser.add_argument("--resume", action="store_true", help="Resume from existing output/state")

    parser.add_argument(
        "--include-blocks",
        type=str,
        default=",".join(DEFAULT_INCLUDE_BLOCKS),
        help="Comma-separated blocks to include",
    )
    parser.add_argument(
        "--exclude-blocks",
        type=str,
        default="",
        help="Comma-separated blocks to exclude",
    )

    parser.add_argument(
        "--platform-ids",
        type=str,
        default=",".join(str(value) for value in DEFAULT_PLATFORM_IDS),
        help="Comma-separated RAWG platform IDs",
    )
    parser.add_argument("--count", type=int, default=300, help="Max output size, 0 for unlimited")
    parser.add_argument("--page-size", type=int, default=40, help="RAWG list page size, max 40")
    parser.add_argument("--max-pages-per-platform", type=int, default=0, help="0 means no page limit")
    parser.add_argument("--ordering", type=str, default="-added", help="RAWG ordering (ex: -added, -rating)")
    parser.add_argument("--tags", type=str, default="multiplayer", help="RAWG tags filter for list endpoint")

    parser.add_argument("--pause", type=float, default=0.05, help="Pause between detail calls")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout (seconds)")
    parser.add_argument("--max-retries", type=int, default=6, help="Retry count for transient errors")
    parser.add_argument("--checkpoint-every", type=int, default=50, help="Save every N successful details")
    parser.add_argument("--debug", action="store_true", help="Verbose logs")

    args = parser.parse_args()

    api_key = resolve_api_key(args.api_key, env_file=args.env_file)
    if not api_key:
        raise ValueError("RAWG API key not found. Use --api-key or set RAWG_API_KEY/key in .env")

    include_blocks = parse_csv_list(args.include_blocks)
    exclude_blocks = parse_csv_list(args.exclude_blocks)

    invalid_blocks = [block for block in include_blocks + exclude_blocks if block not in FIELD_BLOCKS]
    if invalid_blocks:
        allowed = ", ".join(sorted(FIELD_BLOCKS.keys()))
        raise ValueError(f"Invalid blocks: {', '.join(sorted(set(invalid_blocks)))}. Allowed: {allowed}")

    platform_ids = parse_platform_ids(args.platform_ids)
    if not platform_ids:
        raise ValueError("No valid platform IDs")

    count: Optional[int] = None if args.count <= 0 else max(1, args.count)
    state_file = args.state_file or f"{args.output}.state.json"

    scrape_rawg(
        api_key=api_key,
        output_file=args.output,
        state_file=state_file,
        include_blocks=include_blocks,
        exclude_blocks=exclude_blocks,
        platform_ids=platform_ids,
        count=count,
        page_size=max(1, min(40, args.page_size)),
        max_pages_per_platform=max(0, args.max_pages_per_platform),
        ordering=args.ordering,
        tags=args.tags.strip(),
        pause=max(0.0, args.pause),
        timeout=max(5, args.timeout),
        max_retries=max(1, args.max_retries),
        checkpoint_every=max(0, args.checkpoint_every),
        resume=args.resume,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
