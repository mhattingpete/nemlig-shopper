# Contributing to Nemlig Shopper

Thank you for your interest in contributing to Nemlig Shopper! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- A Nemlig.com account (for testing cart operations)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/mhattingpete/nemlig-shopper.git
cd nemlig-shopper

# Install dependencies (including dev dependencies)
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Verify installation
uv run nemlig --help
```

### Environment Variables

Copy `.env.example` to `.env` and add your credentials for testing:

```bash
cp .env.example .env
```

## Development Workflow

### Running the CLI

```bash
# Run any CLI command
uv run nemlig --help
uv run nemlig search "mælk"
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_recipe_parser.py

# Run a specific test
uv run pytest tests/test_recipe_parser.py::TestParseQuantity::test_simple_integer

# Run with verbose output
uv run pytest -v
```

### Code Quality

Pre-commit hooks automatically run on every commit:

- **ruff format** - Code formatting
- **ruff check --fix** - Linting with auto-fix
- **ty check** - Type checking

You can run these manually:

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-dietary-filters`
- `fix/recipe-parsing-fractions`
- `docs/update-readme`

### Commit Messages

Follow conventional commits:

- `feat: add lactose-free product filter`
- `fix: handle unicode fractions in quantities`
- `docs: update installation instructions`
- `test: add tests for scaler edge cases`
- `refactor: simplify product matching logic`

### Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch from `main`
3. **Make** your changes with appropriate tests
4. **Ensure** all tests pass: `uv run pytest`
5. **Ensure** code quality checks pass (pre-commit hooks)
6. **Submit** a pull request with a clear description

## Code Architecture

### Core Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Click-based CLI entry point |
| `api.py` | Nemlig.com API client |
| `recipe_parser.py` | Recipe parsing from URLs/text |
| `scaler.py` | Recipe quantity scaling |
| `matcher.py` | Ingredient-to-product matching |
| `pantry.py` | Pantry item management |
| `preference_engine.py` | Dietary/allergy filtering |
| `config.py` | Configuration management |

### Data Flow

```
Recipe URL/Text → recipe_parser → Recipe → scaler → ScaledIngredient[] → matcher → ProductMatch[] → api → Cart
```

### Key Design Decisions

- **Product matching scoring**: Products are scored based on category relevance, name matching, and penalized for non-food items
- **Lazy API initialization**: Session data is fetched on-demand and cached
- **Context-aware matching**: Meal context improves ingredient-to-product matching (e.g., "ost" in Mexican context → "revet mozzarella")

## Testing Guidelines

- Write tests for new functionality
- Focus on parsing logic and scoring algorithms
- Use pytest fixtures for common test data
- Integration tests that require network access should be marked: `@pytest.mark.integration`

## API Discovery

The Chrome DevTools MCP can be used to reverse-engineer Nemlig.com API changes:

1. Navigate to nemlig.com in Chrome
2. Use `mcp__chrome-devtools__list_network_requests` to capture API calls
3. Inspect request/response details to understand endpoint changes

## Questions?

Open an issue for:

- Bug reports
- Feature requests
- Questions about the codebase

Thank you for contributing!
