// ==UserScript==
// @name         RAWG Game Collector (Public JSON Export)
// @namespace    https://rawg.io/
// @version      2.0.0
// @description  Collect RAWG games and export configurable JSON for public use.
// @match        https://rawg.io/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  const STORAGE_KEY = "rawgCollectorPublic.items.v1";
  const API_KEY_STORAGE = "rawgCollectorPublic.apiKey.v1";
  const SETTINGS_STORAGE = "rawgCollectorPublic.settings.v1";

  const DEFAULT_SETTINGS = {
    includeDates: true,
    includeRatings: true,
    includePlatforms: true,
    includeGenres: true,
    includeTags: false,
    includeMedia: true,
    includeStoreData: false,
    includeCompanyData: false,
    includeText: false,
    includeWebsite: true,
    includeStats: true,
    includeAltNames: true,
    includeRawObject: false,
  };

  function safeJsonParse(raw, fallback) {
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return fallback;
    }
  }

  function getItemsMap() {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = safeJsonParse(raw || "{}", {});
    if (!parsed || typeof parsed !== "object") return {};
    return parsed;
  }

  function saveItemsMap(itemsMap) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(itemsMap));
  }

  function getApiKey() {
    return (localStorage.getItem(API_KEY_STORAGE) || "").trim();
  }

  function setApiKey(value) {
    localStorage.setItem(API_KEY_STORAGE, (value || "").trim());
  }

  function getSettings() {
    const raw = localStorage.getItem(SETTINGS_STORAGE);
    const parsed = safeJsonParse(raw || "{}", {});
    if (!parsed || typeof parsed !== "object") {
      return { ...DEFAULT_SETTINGS };
    }
    return { ...DEFAULT_SETTINGS, ...parsed };
  }

  function saveSettings(settings) {
    localStorage.setItem(SETTINGS_STORAGE, JSON.stringify({ ...DEFAULT_SETTINGS, ...settings }));
  }

  function slugFromUrl(url) {
    if (!url) return "";
    const match = url.match(/\/games\/([^/?#]+)/i);
    return match ? decodeURIComponent(match[1]).trim().toLowerCase() : "";
  }

  function fetchGameBySlug(slug, apiKey) {
    const url = `https://rawg.io/api/games/${encodeURIComponent(slug)}?key=${encodeURIComponent(apiKey)}`;
    return fetch(url, { credentials: "omit" }).then((response) => {
      if (!response.ok) {
        throw new Error(`RAWG API ${response.status}`);
      }
      return response.json();
    });
  }

  function normalizeNames(values) {
    const out = [];
    const seen = new Set();

    for (const value of values || []) {
      if (!value || typeof value.name !== "string") continue;
      const name = value.name.trim();
      if (!name) continue;
      const key = name.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(name);
    }

    return out;
  }

  function normalizeAlternativeNames(values) {
    const out = [];
    const seen = new Set();

    for (const value of values || []) {
      if (typeof value !== "string") continue;
      const alias = value.trim();
      if (!alias) continue;
      const key = alias.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(alias);
    }

    return out;
  }

  function simplifyPlatforms(game) {
    const out = [];
    const seen = new Set();

    for (const entry of game.platforms || []) {
      const platform = (entry || {}).platform || {};
      const slug = typeof platform.slug === "string" ? platform.slug.trim() : "";
      const name = typeof platform.name === "string" ? platform.name.trim() : "";
      const id = Number.isInteger(platform.id) ? platform.id : null;

      const key = slug || name.toLowerCase();
      if (!key || seen.has(key)) continue;
      seen.add(key);

      out.push({
        id,
        slug,
        name,
      });
    }

    return out;
  }

  function simplifyStores(game) {
    const out = [];
    const seen = new Set();

    for (const entry of game.stores || []) {
      const store = (entry || {}).store || {};
      const slug = typeof store.slug === "string" ? store.slug.trim() : "";
      const name = typeof store.name === "string" ? store.name.trim() : "";
      const domain = typeof store.domain === "string" ? store.domain.trim() : "";

      const key = slug || name.toLowerCase();
      if (!key || seen.has(key)) continue;
      seen.add(key);

      out.push({ slug, name, domain });
    }

    return out;
  }

  function buildPublicItem(game, settings) {
    const slug = (game.slug || "").trim();
    const name = (game.name || "").trim();
    if (!slug || !name) return null;

    const item = {};

    for (const field of ["id", "slug", "name", "name_original", "tba"]) {
      if (field in game) item[field] = game[field];
    }

    if (settings.includeDates) {
      for (const field of ["released", "updated"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeRatings) {
      for (const field of ["rating", "rating_top", "ratings", "ratings_count", "metacritic", "esrb_rating"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includePlatforms) {
      for (const field of ["parent_platforms", "platforms"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeGenres) {
      if ("genres" in game) item.genres = game.genres;
    }

    if (settings.includeTags) {
      if ("tags" in game) item.tags = game.tags;
    }

    if (settings.includeMedia) {
      for (const field of ["background_image", "background_image_additional", "short_screenshots", "clip", "movies"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeStoreData) {
      if ("stores" in game) item.stores = game.stores;
    }

    if (settings.includeCompanyData) {
      for (const field of ["developers", "publishers"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeWebsite) {
      for (const field of ["website", "reddit_url", "metacritic_url"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeStats) {
      for (const field of ["added", "added_by_status", "suggestions_count", "playtime", "reviews_count", "reviews_text_count", "achievements_count"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeText) {
      for (const field of ["description_raw", "description"]) {
        if (field in game) item[field] = game[field];
      }
    }

    if (settings.includeAltNames) {
      item.alternative_names = normalizeAlternativeNames(game.alternative_names);
    }

    if (settings.includeRawObject) {
      item.rawg = game;
    }

    return item;
  }

  function downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }

  function getItemsArray() {
    const map = getItemsMap();
    return Object.values(map).sort((a, b) => {
      const aa = Number(a.added || 0);
      const bb = Number(b.added || 0);
      return bb - aa;
    });
  }

  const panel = document.createElement("div");
  panel.id = "rawg-collector-panel";
  panel.style.cssText = [
    "position:fixed",
    "right:12px",
    "bottom:12px",
    "z-index:999999",
    "width:340px",
    "max-height:85vh",
    "overflow:auto",
    "background:#0f172a",
    "color:#e2e8f0",
    "border:1px solid #334155",
    "border-radius:10px",
    "font:12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    "box-shadow:0 8px 22px rgba(0,0,0,.35)",
    "padding:10px",
  ].join(";");

  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;">
      <strong style="font-size:13px;">RAWG Collector (Public)</strong>
      <span id="rawg-count" style="color:#93c5fd;">0 game</span>
    </div>

    <div style="margin-bottom:8px;">
      <label style="display:block;margin-bottom:4px;color:#94a3b8;">RAWG API key</label>
      <div style="display:flex;gap:6px;">
        <input id="rawg-api-key" type="password" placeholder="Enter key" style="flex:1;min-width:0;background:#020617;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px;" />
        <button id="rawg-save-key" style="background:#1d4ed8;color:white;border:0;border-radius:6px;padding:6px 8px;cursor:pointer;">Save</button>
      </div>
    </div>

    <details style="margin-bottom:8px;border:1px solid #334155;border-radius:8px;padding:6px;">
      <summary style="cursor:pointer;color:#cbd5e1;font-weight:700;">Export settings</summary>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;">
        <label><input type="checkbox" id="cfg-dates" /> Dates</label>
        <label><input type="checkbox" id="cfg-ratings" /> Ratings</label>
        <label><input type="checkbox" id="cfg-platforms" /> Platforms</label>
        <label><input type="checkbox" id="cfg-genres" /> Genres</label>
        <label><input type="checkbox" id="cfg-tags" /> Tags</label>
        <label><input type="checkbox" id="cfg-media" /> Media</label>
        <label><input type="checkbox" id="cfg-stores" /> Stores</label>
        <label><input type="checkbox" id="cfg-company" /> Dev/Publisher</label>
        <label><input type="checkbox" id="cfg-text" /> Description</label>
        <label><input type="checkbox" id="cfg-website" /> URLs</label>
        <label><input type="checkbox" id="cfg-stats" /> Stats</label>
        <label><input type="checkbox" id="cfg-alt-names" /> Alternative names</label>
        <label><input type="checkbox" id="cfg-raw" /> Full raw object</label>
      </div>
      <button id="rawg-save-settings" style="margin-top:8px;background:#0f766e;color:white;border:0;border-radius:6px;padding:6px 8px;cursor:pointer;">Save settings</button>
    </details>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
      <button id="rawg-export-copy" style="background:#334155;color:white;border:0;border-radius:6px;padding:7px;cursor:pointer;">Copy JSON</button>
      <button id="rawg-export-file" style="background:#334155;color:white;border:0;border-radius:6px;padding:7px;cursor:pointer;">Download</button>
      <button id="rawg-clear" style="grid-column:1 / span 2;background:#7f1d1d;color:white;border:0;border-radius:6px;padding:7px;cursor:pointer;">Clear list</button>
    </div>
    <div id="rawg-status" style="margin-top:8px;color:#93c5fd;min-height:16px;"></div>
  `;

  document.body.appendChild(panel);

  const countEl = panel.querySelector("#rawg-count");
  const statusEl = panel.querySelector("#rawg-status");
  const keyInput = panel.querySelector("#rawg-api-key");
  const saveKeyBtn = panel.querySelector("#rawg-save-key");
  const saveSettingsBtn = panel.querySelector("#rawg-save-settings");
  const exportCopyBtn = panel.querySelector("#rawg-export-copy");
  const exportFileBtn = panel.querySelector("#rawg-export-file");
  const clearBtn = panel.querySelector("#rawg-clear");

  const settingInputs = {
    includeDates: panel.querySelector("#cfg-dates"),
    includeRatings: panel.querySelector("#cfg-ratings"),
    includePlatforms: panel.querySelector("#cfg-platforms"),
    includeGenres: panel.querySelector("#cfg-genres"),
    includeTags: panel.querySelector("#cfg-tags"),
    includeMedia: panel.querySelector("#cfg-media"),
    includeStoreData: panel.querySelector("#cfg-stores"),
    includeCompanyData: panel.querySelector("#cfg-company"),
    includeText: panel.querySelector("#cfg-text"),
    includeWebsite: panel.querySelector("#cfg-website"),
    includeStats: panel.querySelector("#cfg-stats"),
    includeAltNames: panel.querySelector("#cfg-alt-names"),
    includeRawObject: panel.querySelector("#cfg-raw"),
  };

  function setStatus(message, isError) {
    statusEl.textContent = message || "";
    statusEl.style.color = isError ? "#fda4af" : "#93c5fd";
  }

  function refreshCount() {
    const count = getItemsArray().length;
    countEl.textContent = `${count} game${count > 1 ? "s" : ""}`;
  }

  function loadSettingsToUi() {
    const settings = getSettings();
    for (const key of Object.keys(settingInputs)) {
      settingInputs[key].checked = Boolean(settings[key]);
    }
  }

  function readSettingsFromUi() {
    const out = { ...DEFAULT_SETTINGS };
    for (const key of Object.keys(settingInputs)) {
      out[key] = Boolean(settingInputs[key].checked);
    }
    return out;
  }

  keyInput.value = getApiKey();
  loadSettingsToUi();
  refreshCount();

  saveKeyBtn.addEventListener("click", () => {
    setApiKey(keyInput.value);
    setStatus("API key saved", false);
  });

  saveSettingsBtn.addEventListener("click", () => {
    const settings = readSettingsFromUi();
    saveSettings(settings);
    setStatus("Export settings saved", false);
  });

  exportCopyBtn.addEventListener("click", async () => {
    const rows = getItemsArray();
    const text = JSON.stringify(rows, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      setStatus(`Copied ${rows.length} games to clipboard`, false);
    } catch (_error) {
      setStatus("Clipboard blocked. Use Download.", true);
    }
  });

  exportFileBtn.addEventListener("click", () => {
    const rows = getItemsArray();
    downloadJson("rawg_games_public.json", rows);
    setStatus(`Downloaded ${rows.length} games`, false);
  });

  clearBtn.addEventListener("click", () => {
    if (!window.confirm("Clear collected game list?")) return;
    saveItemsMap({});
    refreshCount();
    setStatus("List cleared", false);
  });

  async function collectSlug(slug) {
    const apiKey = getApiKey();
    if (!apiKey) {
      setStatus("Set API key first", true);
      return;
    }

    try {
      const settings = getSettings();
      setStatus(`Fetching ${slug}...`, false);
      const detail = await fetchGameBySlug(slug, apiKey);
      const item = buildPublicItem(detail, settings);
      if (!item) {
        setStatus(`Skipped ${slug} (missing slug/name)`, true);
        return;
      }

      const map = getItemsMap();
      map[item.slug] = item;
      saveItemsMap(map);
      refreshCount();
      setStatus(`Added ${item.name}`, false);
    } catch (error) {
      setStatus(`Failed ${slug}: ${String(error.message || error)}`, true);
    }
  }

  function createAddButton(slug) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "+ Add";
    button.className = "rawg-collector-add-btn";
    button.style.cssText = [
      "position:absolute",
      "right:8px",
      "top:8px",
      "z-index:3",
      "background:#0ea5e9",
      "color:#082f49",
      "border:0",
      "border-radius:999px",
      "padding:5px 8px",
      "font-size:11px",
      "font-weight:700",
      "cursor:pointer",
      "box-shadow:0 2px 8px rgba(0,0,0,.35)",
    ].join(";");

    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      collectSlug(slug);
    });

    return button;
  }

  function injectButtonsOnCards() {
    const links = document.querySelectorAll('a[href*="/games/"]');
    for (const link of links) {
      const href = link.getAttribute("href") || "";
      const slug = slugFromUrl(href);
      if (!slug) continue;

      const card = link.closest("article, div") || link.parentElement;
      if (!card || !(card instanceof HTMLElement)) continue;
      if (card.querySelector(".rawg-collector-add-btn")) continue;

      const style = window.getComputedStyle(card);
      if (style.position === "static") {
        card.style.position = "relative";
      }

      card.appendChild(createAddButton(slug));
    }
  }

  function injectDetailPageButton() {
    const slug = slugFromUrl(window.location.pathname);
    if (!slug || !window.location.pathname.startsWith("/games/")) return;
    if (document.querySelector("#rawg-collector-detail-btn")) return;

    const button = document.createElement("button");
    button.id = "rawg-collector-detail-btn";
    button.type = "button";
    button.textContent = "Add game to JSON";
    button.style.cssText = [
      "position:fixed",
      "left:12px",
      "bottom:12px",
      "z-index:999999",
      "background:#22c55e",
      "color:#052e16",
      "border:0",
      "border-radius:8px",
      "padding:10px 12px",
      "font:700 12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
      "cursor:pointer",
      "box-shadow:0 8px 22px rgba(0,0,0,.35)",
    ].join(";");

    button.addEventListener("click", () => collectSlug(slug));
    document.body.appendChild(button);
  }

  let lastHref = window.location.href;
  setInterval(() => {
    if (window.location.href !== lastHref) {
      lastHref = window.location.href;
      setTimeout(() => {
        injectButtonsOnCards();
        injectDetailPageButton();
      }, 500);
    }
  }, 500);

  const observer = new MutationObserver(() => {
    injectButtonsOnCards();
    injectDetailPageButton();
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });

  injectButtonsOnCards();
  injectDetailPageButton();
})();
