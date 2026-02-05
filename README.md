# Nemlig Shopper 🛒

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

## Notes

- Uses an unofficial Nemlig.com API
- Danish ingredient/product names work best
- Product IDs are shown in search results

## License

MIT License - See LICENSE file for details
