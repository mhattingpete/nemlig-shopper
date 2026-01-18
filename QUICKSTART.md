# Quickstart Guide

## Setup (One-time)

```bash
# Install
git clone https://github.com/mhattingpete/nemlig-shopper.git
cd nemlig-shopper
uv sync

# Login to Nemlig.com
uv run nemlig login
```

---

## Common Workflows

### 1. Add a recipe to cart

```bash
uv run nemlig add https://www.valdemarsro.dk/pasta-carbonara/
```

This will:
- Parse the recipe
- Show pantry items you likely have (salt, oil, etc.) - deselect what you need
- Match ingredients to Nemlig products
- Show matches for review
- Add to cart (with confirmation)

**Options:**
```bash
--scale 2           # Double the recipe
--servings 6        # Scale to 6 servings
--skip-pantry-check # Don't prompt for pantry items
--yes               # Skip confirmation
--dry-run           # Don't add to cart (preview only)
```

### 2. Multiple recipes (ingredients consolidated)

```bash
uv run nemlig add \
  https://www.valdemarsro.dk/pasta-carbonara/ \
  https://www.valdemarsro.dk/lasagne/
```

If both need onions, you get the combined amount in one cart item.

### 3. Manual items or mixed input

```bash
# Just manual items
uv run nemlig add --text "mælk, brød, æg x6"

# Mix of URLs and items
uv run nemlig add --text "https://www.valdemarsro.dk/one-pot-pasta/
mælk
æg x6
ost 200g"

# From a file
uv run nemlig add --file shopping-list.txt
```

### 4. Dietary filters

```bash
uv run nemlig add URL --lactose-free
uv run nemlig add URL --gluten-free
uv run nemlig add URL --vegan
```

---

## Pantry Management

Your pantry = items you always have at home (salt, oil, flour, etc.).

```bash
# See your pantry
uv run nemlig pantry list

# Add items
uv run nemlig pantry add "fish sauce" "sesame oil"

# Remove items (will be included in shopping)
uv run nemlig pantry remove "eggs"

# See all default pantry items
uv run nemlig pantry defaults
```

---

## Other Commands

```bash
# Search for products
uv run nemlig search "mælk"

# Parse recipe without adding to cart
uv run nemlig parse URL

# Manage favorites (saved recipes)
uv run nemlig favorites list
uv run nemlig favorites order "saved-name"
```

---

## Tips

1. **Danish recipes work best** - The tool translates English→Danish but native Danish ingredients match better

2. **Review matches** - The TUI lets you swap products before adding to cart

3. **Dry run first** - Use `--dry-run` to preview without modifying your cart

4. **Scale smartly** - `--servings 8` scales based on original serving count; `--scale 2` just doubles everything
