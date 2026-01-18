# Nemlig Shopper 🛒

A CLI tool that parses recipes from URLs or text, matches ingredients to products on [Nemlig.com](https://nemlig.com) (Danish online grocery store), and adds them directly to your cart.

## Features

- **Recipe Parsing**: Extract ingredients from recipe URLs (supports 100+ recipe sites) or manual text input
- **Product Matching**: Automatically match ingredients to Nemlig.com products with smart scoring
- **Recipe Scaling**: Double, halve, or scale recipes to any serving size
- **Meal Planning**: Combine multiple recipes with ingredient consolidation
- **Pantry Check**: Identifies common household items (salt, oil, etc.) so you don't buy what you have
- **Dietary Filters**: Filter for lactose-free, gluten-free, or vegan products
- **Interactive Review**: TUI for reviewing and swapping product matches before checkout
- **Price Tracking**: SQLite-backed price history
- **Favorites**: Save recipes locally for quick re-ordering
- **Export**: Shopping lists to JSON, Markdown, or PDF

## Installation

```bash
# Clone the repository
git clone https://github.com/mhattingpete/nemlig-shopper.git
cd nemlig-shopper

# Install with uv (recommended)
uv sync
```

## Quick Start

```bash
# 1. Log in to Nemlig.com
uv run nemlig login

# 2. Add a recipe to cart
uv run nemlig add https://www.valdemarsro.dk/pasta-carbonara/

# 3. Or meal plan multiple recipes
uv run nemlig plan URL1 URL2 URL3
```

See [QUICKSTART.md](QUICKSTART.md) for more examples.

## Commands

| Command | Description |
|---------|-------------|
| `nemlig login` | Authenticate with Nemlig.com |
| `nemlig add URL` | Parse recipe and add to cart |
| `nemlig plan URL...` | Multi-recipe meal planning with consolidation |
| `nemlig shop` | Interactive mode for mixed URLs and manual items |
| `nemlig parse URL` | Parse recipe without adding to cart |
| `nemlig search QUERY` | Search Nemlig products |
| `nemlig favorites` | Manage saved recipes |
| `nemlig pantry` | Manage household pantry items |

## Usage Examples

### Adding Recipes

```bash
# Basic usage
uv run nemlig add https://example.com/recipe

# Scale to double
uv run nemlig add https://example.com/recipe --scale 2

# Scale to 8 servings
uv run nemlig add https://example.com/recipe --servings 8

# With dietary filter
uv run nemlig add https://example.com/recipe --lactose-free

# Preview without adding to cart
uv run nemlig add https://example.com/recipe --dry-run

# Skip pantry check
uv run nemlig add https://example.com/recipe --skip-pantry-check
```

### Meal Planning

```bash
# Combine multiple recipes (consolidates ingredients)
uv run nemlig plan \
  https://www.valdemarsro.dk/pasta-carbonara/ \
  https://www.valdemarsro.dk/lasagne/ \
  https://www.valdemarsro.dk/tiramisu/
```

### Quick Shopping

```bash
# Interactive mode - paste URLs and manual items
uv run nemlig shop
# Then enter:
#   https://recipe-site.com/recipe
#   mælk
#   æg x6
#   ost 200g
# Press Ctrl+D when done
```

### Pantry Management

```bash
# List your pantry items
uv run nemlig pantry list

# Add items you always have
uv run nemlig pantry add "fish sauce" "sesame oil"

# Remove items (so they're included in shopping)
uv run nemlig pantry remove "eggs"

# Show default pantry items
uv run nemlig pantry defaults

# Reset to defaults
uv run nemlig pantry clear
```

### Favorites

```bash
# List saved favorites
uv run nemlig favorites list

# Save a recipe
uv run nemlig add URL --save-as "sunday-dinner"

# Quick re-order
uv run nemlig favorites order "sunday-dinner"

# Re-order with scaling
uv run nemlig favorites order "sunday-dinner" --scale 2
```

## Configuration

Credentials can be provided via:

1. **Environment variables** (`.env` file):
   ```
   NEMLIG_USERNAME=your-email@example.com
   NEMLIG_PASSWORD=your-password
   ```

2. **Saved credentials**: Run `uv run nemlig login` to save credentials locally

Configuration files are stored in `~/.nemlig-shopper/`:
- `credentials.json` - Login credentials (chmod 600)
- `favorites.json` - Saved recipes
- `pantry.json` - Custom pantry items
- `prices.db` - Price history (SQLite)

## Supported Recipe Sites

Uses [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) supporting 100+ sites:

- Valdemarsro (Danish)
- AllRecipes
- BBC Good Food
- Bon Appétit
- Serious Eats
- And many more...

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run a specific test
uv run pytest tests/test_recipe_parser.py -v
```

## Notes

- Uses an unofficial Nemlig.com API (discovered via network inspection)
- Product matching uses smart scoring but may occasionally need manual adjustment
- Danish ingredient names match better than English
- Prices are estimates; actual cart totals may differ slightly

## License

MIT License - See LICENSE file for details
