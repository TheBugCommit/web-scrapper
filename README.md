# webscraper

> Extensible, async-capable Python web scraping engine with SQL Server storage and Playwright JS support.

[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://python.org)
[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

---

## Features

- 🔐 **HTML form authentication** — logs into portals automatically, harvests CSRF tokens
- ⚡ **Async concurrency** — configurable worker pool via `asyncio.Queue`
- 🌐 **JS-rendered pages** — Playwright backend (Chromium/Firefox/WebKit)
- 📄 **CSS & XPath extraction** — flexible rule-based data extraction
- 🖱️ **Declarative form interactions** — execute multi-step form workflows (dropdowns, checkboxes, clicks, file downloads) via `FormInteractor`
- 🗂️ **Dynamic Portal Registry** — multi-portal YAML configuration (`portals/config/portals.yml`) separated from gitignored credentials (`portals/config/portals_credentials.yml`)
- 📜 **Rotating file logs** — automatic rotating file logs (`logs/scraper.log` & `logs/error.log`) alongside rich colorised console output
- 📥 **File downloads** — concurrent file download with extension/pattern filtering
- 🗄️ **SQL Server storage** — auto-creates tables, supports MERGE (upsert) via Repository pattern
- 🕷️ **Debug crawler** — BFS recursive page map with JSON export
- 🔔 **Event hooks** — observer system for monitoring and custom side-effects
- 🐌 **Rate limiting** — per-host async token bucket
- 🔄 **Retry** — exponential backoff on transient failures (via `tenacity`)

---

## Installation

```bash
# Clone the repo
cd web-scrapper

# Install in editable mode
pip install -e .

# Install Playwright browsers (only needed for JS pages)
playwright install chromium
```

### SQL Server ODBC Driver

On Windows, download and install the ODBC Driver for SQL Server:
- [ODBC Driver 17 or 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

---

## Configuration

The project is clearly separated into two layers:
- **`portals/`**: Client application and multi-portal scraper flows.
- **`scraper/`**: Reusable async web scraping framework package.

### Infrastructure Configuration (`portals/.env`)

Copy `portals/.env.example` to `portals/.env` (which is gitignored) and configure your database and scraper engine options:

```bash
cp portals/.env.example portals/.env
```

Key variables in `portals/.env`:

```dotenv
# SQL Server connection string
SCRAPER_DB_CONNECTION_STRING=mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server

# Browser & Engine Execution Options
SCRAPER_HEADLESS=true
SCRAPER_MAX_CONCURRENT=5
SCRAPER_RATE_LIMIT_DELAY=1.0
SCRAPER_MAX_RETRIES=3
SCRAPER_TIMEOUT_MS=90000
SCRAPER_DEBUG=false
```

> **Note**: `portals/.env` is strictly reserved for infrastructure and generic scraper engine parameters. It should **never** contain portal-specific credentials.

### Multi-Portal Configuration (`portals.yml` & `portals_credentials.yml`)

The client application separates public portal metadata from sensitive login credentials:

1. **`portals/config/portals.yml`** (Safe to commit to Git): Defines portal metadata, URLs, login URLs, CSS selectors, and custom properties (e.g. `export_url`, `db_table`).
2. **`portals/config/portals_credentials.yml`** (Gitignored): Stores portal credentials (`username` and `password`) and any portal-specific sensitive parameters (e.g. `api_key`, `client_id`). See `portals_credentials.example.yml` for a template.

```yaml
# portals/config/portals_credentials.yml
messer:
  username: "myuser"
  password: "mypassword"

carburos_metalicos:
  username: "anotheruser"
  password: "anotherpassword"
```

```python
from portals.config import PortalRegistry

registry = PortalRegistry.load()
portal = registry.get("messer")

# Generates a pre-configured ScraperBuilder with environment defaults and authentication
builder = portal.get_builder()
```

### Rotating Log Files

When `SCRAPER_LOG_ENABLED=true`, the engine automatically generates UTF-8 rotating file logs inside `SCRAPER_LOG_DIR` (`./logs` by default):

- **`scraper.log`**: Records all execution outputs and events at the configured log level (`INFO` or `DEBUG`).
- **`error.log`**: Records only `ERROR` and `CRITICAL` messages for immediate troubleshooting.

---

## Quick Start

### Simple scrape (no login, no JS)

```python
import asyncio
from scraper import ScraperBuilder
from scraper.backends import RequestsBackend
from scraper.core.engine import ScraperEngine
from scraper.extractors import CSSExtractor

async def main():
    session = (
        ScraperBuilder()
        .with_url("https://books.toscrape.com")
        .with_backend(RequestsBackend())
        .with_extractor(CSSExtractor(rules={
            "title": "h1",
            "price": ".price_color",
        }))
        .build()
    )
    result = await ScraperEngine(session).run()
    for page in result.pages:
        print(page.data)

asyncio.run(main())
```

### Login + pagination + SQL Server

```python
import asyncio
import os
from scraper import ScraperBuilder
from scraper.auth import FormAuthHandler
from scraper.backends import RequestsBackend
from scraper.core.engine import ScraperEngine
from scraper.extractors import CSSExtractor
from scraper.navigation import PaginationNavigator
from scraper.storage import SQLServerStorage

async def main():
    session = (
        ScraperBuilder()
        .with_url("https://portal.example.com")
        .with_backend(RequestsBackend())
        .with_auth(FormAuthHandler(
            login_url="https://portal.example.com/login",
            username="myuser",
            password="mypass",
            success_selector=".dashboard",
        ))
        .with_navigator(PaginationNavigator(next_selector="a[rel=next]"))
        .with_extractor(CSSExtractor(rules={"title": "h1", "id": ".record-id"}))
        .with_storage(SQLServerStorage(
            connection_string=os.environ["SCRAPER_DB_CONNECTION_STRING"],
            table="scraped_data",
        ))
        .build()
    )
    result = await ScraperEngine(session).run()
    print(f"Scraped {len(result.pages)} pages")

asyncio.run(main())
```

### JS pages (Playwright)

```python
from scraper.backends import PlaywrightBackend

# Replace RequestsBackend() with:
PlaywrightBackend(browser="chromium", headless=True, wait_until="networkidle")
```

### Declarative Form Interactions & File Download

```python
from scraper.interaction import (
    CheckboxAction,
    DownloadSubmitAction,
    FormInteractor,
    SelectAction,
    UncheckAllAction,
)

session = (
    ScraperBuilder()
    .with_url("https://portal.example.com/export")
    .with_backend(PlaywrightBackend(headless=False))
    .with_interaction(
        FormInteractor(
            actions=[
                SelectAction("select[name='modul_id']", value="244425", auto_submit=True),
                SelectAction("select[name='dateTrunc']", "hour"),
                UncheckAllAction("input[type='checkbox'][name='channelList']"),
                CheckboxAction("input[name='channelList'][value='EAN000']", checked=True),
                DownloadSubmitAction(
                    selector="input[type='submit'][name='createLink']",
                    download_dir="downloads",
                ),
            ]
        )
    )
    .build()
)
```

### Debug crawler

```bash
python examples/debug_crawl.py https://portal.example.com 3
```

```
🕷  Starting debug crawl  seed=https://portal.example.com  max_depth=3

📄 Crawl map:

[200] https://portal.example.com — Home
  ├─ [200] https://portal.example.com/about — About Us
  ├─ [200] https://portal.example.com/products — Products
  │   ├─ [200] https://portal.example.com/products/1 — Product One
  │   └─ [200] https://portal.example.com/products/2 — Product Two
  └─ [200] https://portal.example.com/contact — Contact

📊 Total reachable pages: 6
💾 Saved to crawl_map.json
```

---

## Event Hooks

```python
from scraper.events import EventDispatcher

dispatcher = EventDispatcher()

@dispatcher.on("page.loaded")
async def on_page(payload):
    print(f"Loaded: {payload['url']}  status={payload['status']}")

@dispatcher.on("data.extracted")
def on_data(payload):
    print(f"Data: {payload['data']}")

@dispatcher.on("file.downloaded")
def on_download(payload):
    print(f"Downloaded: {payload['path']} ({payload['size_bytes']} bytes)")

@dispatcher.on("storage.saved")
def on_saved(payload):
    print(
        f"Upserted {payload['rows']} rows to SQL Server "
        f"[{payload['schema']}].[{payload['table']}]!"
    )

engine = ScraperEngine(session, dispatcher=dispatcher)
```

---

## Architecture & How It Works (Detailed Explanation)

This library is designed following **SOLID** principles and **Design Patterns** (Strategy, Builder, and Observer) to provide a modular, production-grade asynchronous (`asyncio`) web scraping engine that is easy to extend.

### 1. Layered Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             User / Examples                              │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │  ScraperBuilder (Fluent API)
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           ScraperEngine (Core)                           │
│      asyncio.Queue (Work Queue)        │      EventDispatcher (Hook)     │
└──┬──────────┬────────────────┬─────────┴──────┬────────────────┬─────────┘
   │          │                │                │                │
   ▼          ▼                ▼                ▼                ▼
Backend    Auth            Interactors     Navigators      Extractors      Storage
(Strategy) (Plugin)        (Plugin list)   (Plugin list)   (Plugin list)   (Plugin)
```

- **Core (`scraper/core/`)**:
  - `ScraperBuilder`: Constructs immutable instances of `ScraperSession` cleanly without huge constructors.
  - `ScraperEngine`: Orchestrates the async pipeline using a pool of concurrent workers (`max_concurrent`) and a work queue (`asyncio.Queue`) to prevent server saturation.
  - `ScraperContext`: Centralizes global configuration (rate limits, delays, and `.env` variables).
- **Backends (`scraper/backends/`)**:
  - `RequestsBackend`: Fast HTTP engine based on `httpx` for classic HTML pages and APIs without JavaScript.
  - `PlaywrightBackend`: Controls real browsers (Chromium, Firefox, WebKit) for dynamic JavaScript-rendered sites or SPAs.
- **Modular Strategies**:
  - **Authentication (`scraper/auth/`)**: `FormAuthHandler` automates login (handling CSRF tokens and checking success selectors).
  - **Interaction (`scraper/interaction/`)**: `FormInteractor` and declarative form actions (`SelectAction`, `CheckboxAction`, `DownloadSubmitAction`, etc.) execute DOM manipulations, form fills, dropdown auto-submits, and file downloads cleanly before data extraction.
  - **Navigation (`scraper/navigation/`)**: `LinkNavigator` and `PaginationNavigator` discover new URLs to traverse the target portal autonomously.
  - **Extraction (`scraper/extractors/`)**: `CSSExtractor`, `XPathExtractor`, or `FileDownloader` process DOM content to extract structured data.
  - **Storage (`scraper/storage/`)**: `SQLServerStorage` asynchronously saves scraped rows to SQL Server using SQLAlchemy and a `pyodbc` thread pool (with MERGE/upsert support).
  - **Debug Tools (`scraper/debug/`)**: `DebugCrawler` maps entire websites using a BFS traversal to inspect reachable URLs.

### 2. Execution Flow (`ScraperEngine.run()`)

1. **Authentication**: If an `AuthHandler` is defined, the backend logs in and retains authentication cookies/headers for the entire session.
2. **Initial Queue**: Seed URLs are pushed into the `asyncio.Queue`.
3. **Async Workers**: A pool of worker coroutines processes URLs in parallel:
   - Enforces per-host rate limits (`PerHostRateLimiter`).
   - Fetches the page via `backend.get(url) -> PageResponse`.
   - Runs **Interactors** (`FormInteractor`) to perform declarative DOM actions (selecting dropdowns, toggling checkboxes, submitting forms, or capturing downloaded files).
   - Runs **Extractors** to parse dictionary data and sends it to **Storage** (`storage.save(data)`).
   - Runs **Navigators** to inspect the page, discover new URLs (e.g., next page), and push them back into the queue.
4. **Completion**: Once all URLs in the queue are processed, the backend is closed, and an aggregate `ScrapeResult` is returned.

### 3. How It Is Designed to Be Used

The design prioritizes a **Fluent API** for assembling required components using `ScraperBuilder`:

```python
session = (
    ScraperBuilder()
    .with_url("https://portal.example.com")
    .with_backend(RequestsBackend(timeout=30.0))
    .with_auth(FormAuthHandler(...))
    .with_interaction(FormInteractor(...))
    .with_navigator(PaginationNavigator(next_selector="a[rel=next]"))
    .with_extractor(CSSExtractor(rules={"title": "h1"}))
    .with_storage(SQLServerStorage(
        connection_string=os.environ["SCRAPER_DB_CONNECTION_STRING"],
        table="scraped_data",
    ))
    .build()
)

result = await ScraperEngine(session).run()
```

### 4. How It Is Designed to Be Extended

The library follows the **Open/Closed** principle: no extension requires modifying core code (`core/`). Simply subclass the corresponding Abstract Base Class (ABC) in its category directory:

- **New Auth Handler**: Subclass `AbstractAuthHandler` (`scraper/auth/base.py`) and implement `async def authenticate(self, backend, context)`.
- **New Form Action or Interactor**: Subclass `AbstractFormAction` or `AbstractPageInteractor` (`scraper/interaction/base.py`) to encapsulate custom browser interaction patterns.
- **New Extractor** (e.g., JSON or PDF): Subclass `AbstractExtractor` (`scraper/extractors/base.py`) and implement `async def extract(self, page)`.
- **New Storage Sink** (e.g., CSV or PostgreSQL): Subclass `AbstractStorage` (`scraper/storage/base.py`) and implement `async def save(self, data)`.
- **New Navigator**: Subclass `AbstractNavigator` (`scraper/navigation/base.py`) and implement `async def discover(self, page, context)`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed extension guides and examples.

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/unit/
```

---

## Running Client Portals (CLI)

The project includes a unified CLI runner to execute scraping sessions for any configured portal:

```bash
# Execute a single portal by key (defined in portals/config/portals.yml)
python portals/run.py messer
python portals/run.py carburos_metalicos

# Execute all configured portals sequentially
python portals/run.py --all
```

---

## Project Structure

```
portals/                        ← CLIENT APPLICATION / PROJECTS
  ├── config/                   ← Multi-portal configuration and secrets
  │   ├── portals.yml           ← Public portal metadata and selectors
  │   ├── portals_credentials.yml          ← Ignored YAML credentials
  │   ├── portals_credentials.example.yml  <-- Example credentials template
  │   ├── models.py             ← PortalConfig & get_builder() helper
  │   └── registry.py           ← PortalRegistry loader
  ├── messer/                   ← Messer (Global Datacenter) XLS flow
  ├── carburos_metalicos/       ← Carburos Metálicos CSV telemetry flow
  ├── run.py                    ← CLI runner for portal executions
  ├── .env                      ← Active infrastructure config (ignored)
  ├── .env.example              ← Infrastructure template
  ├── .env.test                 ← Test environment config
  └── .env.production           ← Production environment config
scraper/                        ← REUSABLE SCRAPING FRAMEWORK PACKAGE
  ├── auth/                     ← Authentication strategies (HTML Form Auth)
  ├── backends/                 ← HTTP & Playwright browser backends
  ├── core/                     ← Engine, builder, session, context
  ├── extractors/               ← CSS, XPath, CSV, Excel & file downloaders
  ├── interaction/              ← FormInteractor & declarative DOM actions
  ├── navigation/               ← LinkNavigator & pagination
  └── storage/                  ← Repository & Storage sinks (SQL Server)
data/                           ← Scraped downloads and generated files
examples/                       ← Runnable usage examples
tests/
  ├── unit/                     ← Fast unit tests (pytest tests/unit/)
  └── integration/              ← Integration tests requiring DB/network
ARCHITECTURE.md                 ← Full design and architecture documentation
pyproject.toml                  ← Packaging config
```
