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
Recipe URL/Text → recipe_parser → Recipe → scaler → ScaledIngredient[] → matcher → ProductMatch[] → api → Cart
```

### Core Modules

- **cli.py**: Click-based CLI entry point. Defines all commands (`login`, `parse`, `add`, `search`, `favorites`). Uses a singleton `NemligAPI` instance.

- **api.py**: HTTP client for Nemlig.com's unofficial API. Handles authentication (JWT tokens), product search via search gateway, and cart operations. Key endpoints:
  - `/webapi/login` - Authentication
  - `/searchgateway/api/search` - Product search (external gateway, requires specific headers)
  - `/webapi/basket/*` - Cart operations

- **recipe_parser.py**: Parses recipes from URLs (using `recipe-scrapers` library) or manual text input. Extracts quantities, units, and ingredient names. Handles fractions (Unicode and text), ranges, and mixed numbers.

- **scaler.py**: Scales recipe quantities by multiplier or target servings. Rounds to practical cooking measurements (e.g., ceiling for countable items, quarters for small quantities).

- **matcher.py**: Matches ingredients to Nemlig products. Uses English→Danish translation dictionary, smart scoring to prioritize food categories over non-food, and filters out derivative products (e.g., "onion chips" when searching for "onion").

- **favorites.py**: Persists recipes and product matches to `~/.nemlig-shopper/favorites.json`. Enables quick re-ordering without re-matching.

- **config.py**: Manages credentials (env vars or `~/.nemlig-shopper/credentials.json`) and app configuration.

### Key Design Patterns

- **ProductMatch scoring**: The matcher scores products based on category relevance, name matching, and penalizes non-food items and derivative products (chips, sauces, cleaning products).

- **Lazy API initialization**: Session data (JWT token, timestamps, timeslot) is fetched on-demand and cached for subsequent requests.

- **Recipe serialization**: Recipes use `to_dict()`/`from_dict()` for JSON persistence in favorites.

## Testing

Tests use pytest. Focus areas:
- `test_recipe_parser.py`: Quantity/unit parsing, fractions, ingredient extraction
- `test_scaler.py`: Scaling math, practical rounding

No mocking of external APIs in current tests - they test parsing logic only.

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
