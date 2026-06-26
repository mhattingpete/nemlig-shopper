# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nemlig Shopper is a CLI tool that parses recipes from URLs or text, matches ingredients to products on Nemlig.com (Danish online grocery store), and adds them directly to your cart. Built with Click for CLI, uses the unofficial Nemlig.com API.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run nemlig --help

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_recipe_parser.py

# Run a specific test
uv run pytest tests/test_recipe_parser.py::TestParseQuantity::test_simple_integer

# Lint and format (runs automatically via hooks - no need to run manually)
uv run ruff check .
uv run ruff format .

# Type checking (runs automatically via hooks - no need to run manually)
uv run ty check
```

## Architecture

### Data Flow

```
Recipe URL/Text → recipe_parser → Recipe (ingredients)
Search query → api.search_products → product dicts → api.add_to_cart → Cart
```

### Core Modules

The package is exactly these modules:

- **cli.py**: Click-based CLI entry point. Commands: `login`, `logout`, `parse`, `search`, `add`, `cart`. Uses a singleton `NemligAPI` via `get_api()` (the seam tests patch).

- **api.py**: HTTP client for Nemlig.com's unofficial API. Handles authentication (JWT tokens), product search via search gateway, and cart operations. Key endpoints:
  - `/webapi/login` - Authentication
  - `/searchgateway/api/search` - Product search (external gateway, requires specific headers)
  - `/webapi/basket/*` - Cart operations

- **recipe_parser.py**: Parses recipes from URLs (using `recipe-scrapers` library) or manual text input. Extracts quantities, units, and ingredient names. Handles fractions (Unicode and text), ranges, and mixed numbers.

- **config.py**: Manages credentials (env vars `NEMLIG_USERNAME`/`NEMLIG_PASSWORD`, or `~/.nemlig-shopper/credentials.json`).

- **mcp_server.py**: FastMCP server (`nemlig-mcp` entry point) exposing the same core as tools for Claude clients: `search_products` (with cheapest/recommended/organic tags), `parse_recipe`, `add_to_cart`, `view_cart`, `clear_cart`. Cart-only — there is intentionally no checkout tool. Reuses `cli.get_api()`.

### Key Design Patterns

- **Product attributes**: `api._parse_products()` derives flags (`is_organic`, `is_frozen`, `is_dairy`, `is_on_discount`, etc.) inline from each product's category and labels.

- **Lazy API initialization**: Session data (JWT token, timestamps, timeslot) is fetched on-demand and cached for subsequent requests.

- **HTTP robustness**: the `httpx.Client` uses `HTTPTransport(retries=3)` (connection-error retries) and `event_hooks` for debug logging; `nemlig -v/--debug` (or `NEMLIG_DEBUG`) turns logging on.

## Testing

Tests use pytest with `respx` for HTTP mocking (120 tests). Files:
- `test_recipe_parser.py`: Quantity/unit parsing, fractions, ingredient extraction
- `test_api.py`: Auth, search, cart operations (respx-mocked HTTP)
- `test_cli.py`: CLI commands (patch `nemlig_shopper.cli.get_api`)
- `test_config.py`: Credential storage (env + JSON file)

## API Discovery

The Chrome DevTools MCP is configured for this project. Use it to reverse-engineer the Nemlig.com API:

1. Navigate to nemlig.com in Chrome
2. Use `mcp__chrome-devtools__list_network_requests` to capture API calls
3. Use `mcp__chrome-devtools__get_network_request` to inspect request/response details

This is essential when the API changes or new endpoints need to be discovered, since there's no official API documentation.

## Code Quality Hooks

**Post-edit hooks** (run automatically after every file edit):
1. `ruff format` - Code formatting
2. `ruff check --fix` - Linting with auto-fix
3. `ty check` - Type checking

**Pre-commit hooks** (run on git commit):
1. `ruff-format` - Code formatting
2. `ruff --fix` - Linting with auto-fix
3. `ty check` - Type checking

Since these run automatically, there's no need to manually run linting or type checking.

## Script Execution Rules

- **Never run inline Python scripts** - Always create script files first, then execute them
- **Debug scripts**: Prefix with `debug_` (e.g., `debug_search.py`) - these are temporary and can be deleted
- **Production scripts**: Use descriptive names in `/tmp/claude/` for one-off tasks

## Quick Reference

### Adding a new CLI command
Reference: `cli.py` - follow the pattern of `add_to_cart()` or `search()`

### Testing a recipe URL
```bash
uv run nemlig parse "https://recipe-url.com"
```

### API changes
Use Chrome DevTools MCP to capture new endpoints, then update `api.py`
