# `webscraper` — Architecture & Strategy

> **Version**: 0.1.0 | **Python**: ≥ 3.11 | **Concurrency**: asyncio

---

## 1. Goal

A production-grade Python scraping library that can:

- Log into web portals (HTML form-based login)
- Perform multi-step declarative DOM form interactions and file download submissions (`FormInteractor`)
- Navigate through multi-page content (links, pagination)
- Extract structured data (CSS, XPath)
- Download files attached to pages or triggered via form submits
- Persist extracted rows to a SQL Server database
- Handle JavaScript-rendered pages via a real browser
- Run concurrently without saturating the target server
- Map all reachable pages in **debug mode**

The library is designed as a **package** that can be installed (`pip install -e .` or distributed via a private PyPI mirror) and imported into any Python project.

---

## 2. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Open/Closed** | Every extension point (auth, backend, extractor…) is an ABC — extend without modifying core |
| **Single Responsibility** | Each class has one job (fetch, authenticate, extract, store) |
| **Dependency Inversion** | High-level engine depends on abstractions, not concrete classes |
| **Strategy Pattern** | Backends, auth handlers, navigators, extractors are all swappable strategies |
| **Builder Pattern** | `ScraperBuilder` assembles sessions fluently — no god object constructors |
| **Observer Pattern** | `EventDispatcher` lets code react to lifecycle events without coupling |
| **Plugin / Registry** | Any ABC subclass can be dropped in — no registration required |

---

## 3. Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User Code / Examples                  │
└─────────────────────────┬────────────────────────────────────┘
                          │  ScraperBuilder (fluent API)
                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           ScraperEngine (core)                           │
│   asyncio.Queue worker pool        │      EventDispatcher (observer)     │
└──┬──────────┬────────────────┬─────────┴──────┬────────────────┬─────────┘
   │          │                │                │                │
   ▼          ▼                ▼                ▼                ▼
Backend    Auth            Interactors     Navigators      Extractors      Storage
(Strategy) (Plugin)        (Plugin list)   (Plugin list)   (Plugin list)   (Plugin)
   │
   ├── RequestsBackend  (httpx async)
   └── PlaywrightBackend (real browser, JS)
```

---

## 4. Project Structure (Client Portals & Scraper Library)

The codebase is organized into two distinct layers:

```
portals/                         ← CLIENT APPLICATION / MULTI-PORTAL SCRAPER PROJECTS
├── config/
│   ├── __init__.py              ← Automatically loads portals/.env
│   ├── models.py                ← PortalConfig dataclass + get_builder() helper
│   ├── registry.py              ← PortalRegistry loader (YAML metadata + YAML secrets)
│   ├── portals.yml              ← Public portal metadata (URLs, CSS selectors)
│   └── portals_credentials.yml  ← Gitignored portal secrets (username, password, api_key)
├── messer/
│   └── flow.py                  ← Messer (Global Datacenter) XLS export scraper
├── carburos_metalicos/
│   └── flow.py                  ← Carburos Metálicos CSV telemetry scraper
├── run.py                       ← CLI runner (python portals/run.py [portal_key | --all])
└── .env                         ← Active infrastructure config (SQL Server, headless, concurrent)

scraper/                         ← REUSABLE SCRAPING FRAMEWORK PACKAGE
├── __init__.py                  ← Public API surface
├── core/
│   ├── engine.py                ← Async worker pool + pipeline orchestrator
│   ├── session.py               ← Immutable job descriptor
│   ├── builder.py               ← Fluent ScraperBuilder
│   └── context.py               ← Frozen config (env vars → dataclass)
├── backends/
│   ├── base.py                  ← AbstractBackend + PageResponse
│   ├── requests_backend.py      ← httpx async (no JS)
│   └── playwright_backend.py    ← Chromium/Firefox/WebKit (full JS)
├── auth/
│   ├── base.py                  ← AbstractAuthHandler
│   └── form_auth.py             ← HTML form login (HTTP + Playwright)
├── interaction/
│   ├── base.py                  ← AbstractPageInteractor + AbstractFormAction
│   └── form_actions.py          ← FormInteractor + form actions (Select, Checkbox, DownloadSubmit...)
├── navigation/
│   ├── base.py                  ← AbstractNavigator
│   ├── link_navigator.py        ← Follow <a href> links
│   └── pagination_navigator.py  ← Next-page link / ?page=N increment
├── extractors/
│   ├── base.py                  ← AbstractExtractor
│   ├── css_extractor.py         ← CSS selector extraction
│   ├── xpath_extractor.py       ← XPath extraction (lxml)
│   ├── csv_extractor.py         ← CSV stream processing and extraction
│   ├── excel_extractor.py       ← Excel (XLS/XLSX) table extraction
│   └── file_downloader.py       ← Concurrent file download
├── storage/
│   ├── base.py                  ← AbstractStorage
│   ├── repository.py            ← Repository pattern for SQL telemetry tables
│   └── sqlserver_storage.py     ← SQL Server (SQLAlchemy + pyodbc + MERGE/upsert)
├── debug/
│   └── crawler.py               ← BFS DebugCrawler → CrawlNode tree
├── events/
│   └── dispatcher.py            ← Async EventDispatcher (observer)
├── middleware/
│   └── rate_limiter.py          ← Per-host async rate limiter
└── utils/
    ├── url.py                   ← URL normalisation / link extraction
    └── logging.py               ← Rich console + RotatingFileHandler logs (scraper.log & error.log)
```

---

## 5. Execution Flow

```
ScraperBuilder.build()
        │
        ▼
ScraperEngine.run()
  │
  ├─ 1. AuthHandler.authenticate(backend, context)
  │       └─ FormAuthHandler: GET login page → harvest CSRF → POST credentials
  │
  ├─ 2. Seed queue with start_urls
  │
  └─ 3. Worker pool (max_concurrent coroutines consuming the queue)
          │
          ├─ backend.get(url)          → PageResponse
          ├─ [interactor.interact(page)]  × N interactors  (DOM manipulation / form submits / downloads)
          ├─ [extractor.extract(page)  → dict]  × N extractors  (merged)
          ├─ storage.save(merged_data)
          └─ [navigator.discover(page) → urls]  × N navigators  (enqueued)
```

---

## 6. Concurrency Model

The engine uses **asyncio + asyncio.Queue**:

- `max_concurrent` worker coroutines (default: 5, env: `SCRAPER_MAX_CONCURRENT`)
- Workers drain a shared `asyncio.Queue[str]`
- `asyncio.Queue.join()` blocks until all work is complete
- `PerHostRateLimiter` enforces a minimum delay per host (default: 1s)
- `FileDownloader` uses its own `asyncio.Semaphore(3)` for download concurrency

```
Queue ──► Worker 0 ──► fetch → extract → store → discover → enqueue
      ──► Worker 1 ──► fetch → extract → store → discover → enqueue
      ──► Worker 2 ──► ...
      ──► Worker N ──► ...
```

---

## 7. Configuration via Environment Variables (`portals/.env`)

All engine and infrastructure settings can be overridden via a `.env` file located in `portals/.env` (loaded automatically when importing `portals.config`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_DB_CONNECTION_STRING` | — | SQLAlchemy SQL Server connection string |
| `SCRAPER_DB_TABLE` | `scraped_data` | Target table for extracted rows |
| `SCRAPER_DB_UPSERT_KEY` | — | Column to use as MERGE key (optional) |
| `SCRAPER_DB_SCHEMA` | `dbo` | SQL Server schema |
| `SCRAPER_MAX_CONCURRENT` | `5` | Concurrent page workers |
| `SCRAPER_RATE_LIMIT_DELAY` | `1.0` | Seconds between requests per host |
| `SCRAPER_MAX_RETRIES` | `3` | Retry attempts on transient failures |
| `SCRAPER_DOWNLOAD_DIR` | `./downloads` | Local path for downloaded files |
| `SCRAPER_DEBUG` | `false` | Enable debug logging + verbose output |
| `SCRAPER_HEADLESS` | `true` | Playwright headless mode |

> **Note**: `portals/.env` is exclusively for infrastructure and engine defaults. It must **never** contain portal-specific credentials.

---

## 8. Extending the Library

### Adding a new Auth Handler

```python
from scraper.auth.base import AbstractAuthHandler

class OAuthHandler(AbstractAuthHandler):
    async def authenticate(self, backend, context):
        token = await get_oauth_token(...)
        backend.set_cookies({"access_token": token})
```

### Adding a new Form Action or Interactor

```python
from scraper.interaction.base import AbstractFormAction

class HoverAction(AbstractFormAction):
    def __init__(self, selector: str):
        self.selector = selector

    async def execute(self, page, context):
        await page.hover(self.selector)
```

### Adding a new Extractor

```python
from scraper.extractors.base import AbstractExtractor

class JSONExtractor(AbstractExtractor):
    async def extract(self, page):
        import json
        return json.loads(page.content)
```

### Adding a new Storage Sink

```python
from scraper.storage.base import AbstractStorage

class CSVStorage(AbstractStorage):
    async def save(self, data):
        with open("output.csv", "a") as f:
            f.write(",".join(str(v) for v in data.values()) + "\n")
```

### Adding a new Navigator

```python
from scraper.navigation.base import AbstractNavigator

class SitemapNavigator(AbstractNavigator):
    async def discover(self, page, context):
        # Parse sitemap XML and return all URLs
        ...
```

---

## 9. SQL Server Storage Details

The `SQLServerStorage` sink:

1. **Auto-creates the table** on first insert using row keys as column names
2. **Serialises complex types** (lists, dicts) as JSON strings (`NVARCHAR(MAX)`)
3. **Supports MERGE (upsert)** when `upsert_key` / `SCRAPER_DB_UPSERT_KEY` is set
4. **Runs DB I/O in a thread-pool executor** so it never blocks the async event loop
5. **Connection string** follows SQLAlchemy format with `mssql+pyodbc://`

### Column name → SQL type mapping

| Python type | SQL Server type |
|-------------|----------------|
| `int` | `BIGINT` |
| `float` | `FLOAT` |
| `bool` | `BIT` |
| `str` | `NVARCHAR(MAX)` |
| `list` / `dict` | `NVARCHAR(MAX)` (JSON) |
| other | `NVARCHAR(MAX)` (str) |

---

## 10. Debug Crawler

`DebugCrawler` performs a **BFS traversal** of all same-origin pages:

```
seed (depth 0)
├─ /about (depth 1)
│   └─ /about/team (depth 2)
├─ /products (depth 1)
│   ├─ /products/item-1 (depth 2)
│   └─ /products/item-2 (depth 2)
└─ /contact (depth 1)
```

Output:
- **Pretty-printed tree** (terminal)
- **JSON export** (`crawl_map.json`)
- **Flat URL list** (`crawler.all_urls(root)`)

Usage:
```bash
python examples/debug_crawl.py https://portal.example.com 3
```

---

## 11. Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests (no network required)
pytest tests/unit/

# Run all tests (requires network + optional SQL Server)
pytest tests/
```

---

## 12. Installation

```bash
# Development (editable)
pip install -e .

# Install Playwright browsers (needed only for JS pages)
playwright install chromium

# SQL Server ODBC driver (Windows)
# Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

---

## 13. Portal Registry Pattern (`portals.config`)

To support multi-portal environments cleanly without code modification or committing sensitive credentials:

- **`portals/config/portals.yml` (Git-tracked)**: Contains public portal metadata, login URLs, target form field names, CSS selectors, and custom properties (e.g. `export_url`, `db_table`).
- **`portals/config/portals_credentials.yml` (Gitignored)**: Contains authentication credentials (`username` and `password`) and optional portal-specific sensitive extra parameters (`api_key`, `client_id`, etc.). See `portals_credentials.example.yml` for the template.
- **`PortalRegistry` & `PortalConfig`**: Loads `portals.yml`, merges with `portals_credentials.yml` at runtime, and exposes `.get_builder()` to generate a `ScraperBuilder` pre-configured with generic `.env` parameters and authentication (`form_auth()`).
- **`portals/run.py` (CLI Runner)**: Executes single (`python portals/run.py messer`) or multiple (`python portals/run.py --all`) portals cleanly.

---

## 14. Rotating Logging Architecture (`scraper.utils.logging`)

All scraper activity is logged via structured `rich` console handlers and automatic rotating file logs:

- **`scraper.log`**: Captures all logs from `INFO` / `DEBUG` upwards. Configurable via `SCRAPER_LOG_MAX_BYTES` (default 10 MB) and `SCRAPER_LOG_BACKUPS` (default 5).
- **`error.log`**: Dedicated log stream for `ERROR` and `CRITICAL` entries only, enabling rapid detection and auditing of navigation, authentication, or selector failures without scanning noisy info logs.
