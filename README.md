# Nemlig Shopper 🛒

[![PyPI](https://img.shields.io/pypi/v/nemlig-shopper)](https://pypi.org/project/nemlig-shopper/)
[![Downloads](https://img.shields.io/pypi/dm/nemlig-shopper)](https://pypi.org/project/nemlig-shopper/)
[![Python](https://img.shields.io/pypi/pyversions/nemlig-shopper)](https://pypi.org/project/nemlig-shopper/)
[![License](https://img.shields.io/github/license/mhattingpete/nemlig-shopper)](LICENSE)

A CLI tool for shopping on [Nemlig.com](https://nemlig.com) (Danish online grocery store). Parse recipes, search products, and add items to your cart.

## Installation

```bash
# Install from PyPI
uv tool install nemlig-shopper

# Or run directly with uvx
uvx nemlig-shopper --help
```

## Quick Start

```bash
# Log in to Nemlig.com
nemlig-shopper login

# Parse a recipe to see ingredients
nemlig-shopper parse "https://www.valdemarsro.dk/pasta-carbonara/"

# Search for products
nemlig-shopper search "mælk"

# Add a product to cart (by product ID from search results)
nemlig-shopper add 701015

# View your cart
nemlig-shopper cart
```

## Commands

| Command | Description |
|---------|-------------|
| `login` | Authenticate with Nemlig.com |
| `logout` | Clear saved credentials |
| `parse <url>` | Parse recipe and display ingredient list |
| `search <query>` | Search Nemlig products |
| `add <product_id>` | Add product to cart |
| `cart` | View current cart contents |

## Usage Examples

### Parse a Recipe

```bash
# From URL (supports 100+ recipe sites)
nemlig-shopper parse "https://www.valdemarsro.dk/lasagne/"

# From text input
nemlig-shopper parse --text "500g hakket oksekød
1 løg
2 fed hvidløg
400g hakkede tomater"
```

### Search Products

```bash
# Basic search
nemlig-shopper search "økologisk mælk"

# Limit results
nemlig-shopper search "ost" --limit 5
```

### Add to Cart

```bash
# Add single item
nemlig-shopper add 701015

# Add with quantity
nemlig-shopper add 701015 --quantity 2
```

## Configuration

Credentials can be provided via:

1. **Environment variables** (`.env` file):
   ```
   NEMLIG_USERNAME=your-email@example.com
   NEMLIG_PASSWORD=your-password
   ```

2. **Saved credentials**: Run `nemlig-shopper login` to save credentials locally

Credentials are stored in `~/.nemlig-shopper/credentials.json` (chmod 600).

## Supported Recipe Sites

Uses [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) supporting 100+ sites including:

- Valdemarsro (Danish)
- Mummum (Danish)
- AllRecipes
- BBC Good Food
- Serious Eats
- And many more...

## Development

```bash
# Clone and install
git clone https://github.com/mhattingpete/nemlig-shopper.git
cd nemlig-shopper
uv sync

# Run tests
uv run pytest

# Run CLI locally
uv run nemlig --help
```

## Using with Claude Code or LLM Agents

This CLI is designed to be agent-friendly. An LLM agent (Claude Code, custom agents, etc.) can drive the full shopping workflow by chaining CLI commands.

### Prerequisites

1. Install the CLI (see [Installation](#installation))
2. Set up credentials via environment variables or `nemlig-shopper login`
3. Point your agent at [`SKILL.md`](SKILL.md) for the full command reference

### Agent Workflow

A shopping list can contain a mix of **recipe URLs** and **plain ingredients**. The agent workflow is:

```
Shopping List (URLs + plain items)
  ├─ Recipe URLs → nemlig-shopper parse <url> → extract ingredients
  ├─ Plain items → use directly
  ↓
For each ingredient:
  → nemlig-shopper search "<danish ingredient name>" → get product IDs
  → nemlig-shopper add <product_id> --quantity <n> → add to cart
  ↓
nemlig-shopper cart → verify final cart
```

### Example: Agent Shopping Session

```bash
# 1. Parse a recipe URL to get ingredients
nemlig-shopper parse "https://www.valdemarsro.dk/pasta-carbonara/"
# Output: list of ingredients with quantities and units

# 2. Search for each ingredient (Danish names work best)
nemlig-shopper search "spaghetti"
nemlig-shopper search "pancetta"
nemlig-shopper search "æg"
nemlig-shopper search "parmesan"

# 3. Add selected products by ID
nemlig-shopper add 701015 --quantity 1
nemlig-shopper add 503220 --quantity 1
nemlig-shopper add 100042 --quantity 1
nemlig-shopper add 504100 --quantity 1

# 4. Verify the cart
nemlig-shopper cart
```

### Tips for Agent Integration

- **Translation**: Nemlig.com is Danish. Translate English ingredient names to Danish before searching (e.g., "milk" → "mælk", "onion" → "løg", "chicken" → "kylling").
- **Product selection**: Search results include product ID, name, price, size, and stock status. Pick products that are in stock and match the needed quantity/size.
- **Quantities**: The `parse` command outputs quantities and units per ingredient. Use these to determine how many units of a product to add.
- **Multiple recipes**: Process each recipe URL separately with `parse`, then search and add all ingredients.
- **Plain items**: Items like "mælk" or "rugbrød" that aren't from a recipe can be searched directly without parsing.
- **Skill file**: See [`SKILL.md`](SKILL.md) for the complete agent-readable command reference.

## Notes

- Uses an unofficial Nemlig.com API
- Danish ingredient/product names work best
- Product IDs are shown in search results

## License

MIT License - See LICENSE file for details
