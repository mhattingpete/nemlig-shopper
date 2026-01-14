# Nemlig Shopper 🛒

A CLI tool that parses recipes from URLs or text, matches ingredients to products on [Nemlig.com](https://nemlig.com) (Danish online grocery store), and adds them directly to your cart.

## Features

- **Recipe Parsing**: Extract ingredients from recipe URLs (supports 100+ recipe sites) or manual text input
- **Product Matching**: Automatically match ingredients to Nemlig.com products
- **Recipe Scaling**: Double, halve, or scale recipes to any serving size
- **Favorites**: Save recipes locally for quick re-ordering
- **Cart Integration**: Add matched products directly to your Nemlig.com cart

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nemlig-shopper.git
cd nemlig-shopper

# Install with uv (recommended)
uv sync

# Or install as a package
uv pip install -e .
```

## Quick Start

```bash
# 1. Log in to Nemlig.com
nemlig login

# 2. Parse a recipe and add to cart
nemlig add https://www.example.com/recipe/chocolate-cake

# 3. Or parse first, then decide
nemlig parse https://www.example.com/recipe/chocolate-cake
```

## Usage

### Authentication

```bash
# Log in (credentials saved locally)
nemlig login

# Log in without saving credentials
nemlig login --no-save

# Clear saved credentials
nemlig logout
```

### Parsing Recipes

```bash
# Parse from URL
nemlig parse https://www.allrecipes.com/recipe/12345

# Parse with scaling (double the recipe)
nemlig parse https://example.com/recipe --scale 2

# Parse and scale to 8 servings
nemlig parse https://example.com/recipe --servings 8

# Parse from text input
nemlig parse-text --title "My Recipe"
# Then enter ingredients one per line, empty line to finish
```

### Adding to Cart

```bash
# Parse and add to cart
nemlig add https://example.com/recipe

# Add with scaling
nemlig add https://example.com/recipe --scale 2

# Skip confirmation
nemlig add https://example.com/recipe --yes

# Add and save as favorite
nemlig add https://example.com/recipe --save-as "weekly-pasta"
```

### Searching Products

```bash
# Search for a product
nemlig search "mælk"

# Limit results
nemlig search "ost" --limit 10
```

### Managing Favorites

```bash
# List all favorites
nemlig favorites list

# Save a recipe as favorite
nemlig favorites save "sunday-roast" https://example.com/roast-recipe

# Show favorite details
nemlig favorites show "sunday-roast"

# Quick re-order a favorite
nemlig favorites order "sunday-roast"

# Order with scaling
nemlig favorites order "sunday-roast" --scale 2
nemlig favorites order "sunday-roast" --servings 6

# Re-match products (if prices/availability changed)
nemlig favorites update "sunday-roast"

# Delete a favorite
nemlig favorites delete "sunday-roast"
```

## Configuration

Credentials can be provided via:

1. **Environment variables** (`.env` file):
   ```
   NEMLIG_USERNAME=your-email@example.com
   NEMLIG_PASSWORD=your-password
   ```

2. **Saved credentials**: Run `nemlig login` to save credentials locally

Configuration files are stored in `~/.nemlig-shopper/`:
- `credentials.json` - Saved login credentials (chmod 600)
- `favorites.json` - Saved favorite recipes

## Scaling Examples

```bash
# Double a recipe
nemlig add https://example.com/recipe --scale 2

# Halve a recipe
nemlig add https://example.com/recipe --scale 0.5

# Scale to specific servings (if recipe has serving info)
nemlig add https://example.com/recipe --servings 8

# Scale a favorite
nemlig favorites order "pasta" --scale 3
```

## Supported Recipe Sites

This tool uses [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) which supports 100+ recipe websites including:

- AllRecipes
- BBC Good Food
- Bon Appétit
- Epicurious
- Food Network
- Serious Eats
- And many more...

## Project Structure

```
nemlig_shopper/
├── __init__.py      # Package exports
├── api.py           # Nemlig.com API client
├── cli.py           # CLI commands
├── config.py        # Configuration management
├── favorites.py     # Favorites storage
├── matcher.py       # Ingredient-to-product matching
├── recipe_parser.py # Recipe parsing
└── scaler.py        # Recipe scaling logic
```

## Development

```bash
# Sync dependencies with uv
uv sync

# Run the CLI
uv run nemlig --help

# Or run directly
uv run python -m nemlig_shopper.cli --help
```

## Notes

- This tool uses an unofficial Nemlig.com API discovered through network inspection
- Product matching is based on search results and may not always be perfect
- Prices shown are estimates and may differ from actual cart totals
- Danish and English ingredient names are supported

## License

MIT License - See LICENSE file for details
