---
name: nemlig-shopper-cli
description: Shop groceries on Nemlig.com using the nemlig-shopper CLI. Use when user wants to order groceries from a shopping list, buy items from recipe URLs, add products to Nemlig cart, or mentions nemlig shopping with a list of items or recipes.
---

# Nemlig Shopper CLI

Shop groceries on Nemlig.com by parsing recipes, searching products, and adding to cart via CLI.

## Quick Reference

```bash
# Parse a recipe URL to extract ingredients
nemlig-shopper parse "https://recipe-url.com"

# Parse ingredients from text
nemlig-shopper parse --text "500g mel, 2 æg, 1L mælk"

# Search for a product (Danish terms work best)
nemlig-shopper search "mælk" --limit 5

# Add product to cart by ID
nemlig-shopper add PRODUCT_ID --quantity N

# View cart contents
nemlig-shopper cart
```

## Prerequisites

1. Install: `uv tool install nemlig-shopper` or run via `uvx nemlig-shopper`
2. Authenticate: Set `NEMLIG_USERNAME` and `NEMLIG_PASSWORD` environment variables, or run `nemlig-shopper login`

Credentials persist in `~/.nemlig-shopper/credentials.json` after login.

## Workflow

```
Shopping list (recipe URLs + plain items)
  │
  ├─ Recipe URLs ──→ parse ──→ extract ingredients with quantities
  ├─ Plain items ──→ use directly
  │
  ├─ Deduplicate: combine quantities for repeated ingredients
  ├─ Translate: English → Danish if needed
  │
  ├─ For each ingredient:
  │    search ──→ select best in-stock product ──→ add to cart
  │
  └─ cart ──→ verify all items present
```

### Step 1: Categorize Input

Split the shopping list into:
- **Recipe URLs**: Items starting with `http://` or `https://`
- **Plain items**: Ingredient names or product names

### Step 2: Parse Recipe URLs

For each recipe URL, extract ingredients:

```bash
nemlig-shopper parse "https://www.valdemarsro.dk/pasta-carbonara/"
```

Output:
```
Recipe: Pasta Carbonara
Servings: 4

Ingredients:
  400.0 g spaghetti
  150.0 g pancetta
  4.0     æg
  100.0 g parmesan
        peber
```

Each line: `quantity unit ingredient_name`. Collect all ingredients with their quantities.

For text-based ingredient lists:

```bash
nemlig-shopper parse --text "500g hakket oksekød
1 løg
2 fed hvidløg" --title "Kødsauce" --servings 4
```

### Step 3: Deduplicate Across Recipes

When multiple recipes share ingredients, combine quantities before searching:
- Recipe 1: 200g smør + Recipe 2: 100g smør → need 300g total
- Recipe 1: 2 løg + Recipe 2: 1 løg → need 3 total

### Step 4: Translate to Danish

Nemlig.com is Danish. Translate English ingredient names before searching.

| English | Danish | English | Danish |
|---------|--------|---------|--------|
| milk | mælk | cream | fløde |
| egg | æg | butter | smør |
| flour | mel | sugar | sukker |
| salt | salt | pepper | peber |
| onion | løg | garlic | hvidløg |
| chicken | kylling | beef | oksekød |
| pork | svinekød | ground beef | hakket oksekød |
| cheese | ost | bread | brød |
| potato | kartoffel | carrot | gulerod |
| tomato | tomat | rice | ris |
| pasta | pasta | olive oil | olivenolie |
| lemon | citron | apple | æble |
| banana | banan | salmon | laks |
| shrimp | rejer | mushroom | champignon |
| bell pepper | peberfrugt | spinach | spinat |
| cucumber | agurk | lettuce | salat |
| ginger | ingefær | coconut milk | kokosmælk |
| canned tomatoes | hakkede tomater | parsley | persille |
| basil | basilikum | thyme | timian |
| cinnamon | kanel | vanilla | vanilje |

### Step 5: Search and Add Products

For each ingredient:

```bash
nemlig-shopper search "DANISH_NAME" --limit 5
```

Output:
```
ID       Name                           Price    Size          Stock
701015   Spaghetti                      12.95    500 g         ✓ In Stock
         Brand: Barilla  Category: Pasta  [Tørvare]
```

**Product selection criteria:**
- Must be `✓ In Stock` (skip `✗ Sold Out`)
- Size should cover the needed quantity (e.g., 500g product for 400g needed)
- Name should closely match the ingredient
- Labels: `[Øko]` organic, `[Laktosefri]` lactose-free, `[Glutenfri]` gluten-free, `[Vegan]` vegan, `[Tilbud]` on sale

**Calculate quantity** — divide needed amount by product size, round up:
- Need 750g flour, product is 1kg → quantity 1
- Need 6 eggs, product is 10-pack → quantity 1
- Need 2L milk, product is 1L → quantity 2

Add the selected product:

```bash
nemlig-shopper add PRODUCT_ID --quantity N
```

### Step 6: Verify Cart

```bash
nemlig-shopper cart
```

Confirm all items are present with correct quantities. Show the summary to the user.

## CLI Command Reference

| Command | Arguments | Options | Description |
|---------|-----------|---------|-------------|
| `login` | — | `--username`, `--password`, `--save/--no-save` | Authenticate with Nemlig.com |
| `logout` | — | — | Clear saved credentials |
| `parse` | `[URL]` | `--text`, `--title`, `--servings` | Extract ingredients from recipe |
| `search` | `QUERY` | `--limit N` (default 10) | Search Nemlig product catalog |
| `add` | `PRODUCT_ID` | `--quantity N` (default 1) | Add product to cart |
| `cart` | — | — | View cart contents and totals |

## Error Handling

| Error | Resolution |
|-------|------------|
| Not logged in | Run `nemlig-shopper login` or set env vars |
| No search results | Simplify query (e.g., "hakket oksekød" → "oksekød") |
| Product sold out | Search again, pick alternative product |
| Add fails | Verify product ID is correct and in stock |
| Recipe URL fails | Try `--text` input with manually copied ingredients |

## Example Session

Shopping list:
```
https://www.valdemarsro.dk/pasta-carbonara/
mælk
rugbrød
```

Execution:
```bash
# 1. Parse recipe
nemlig-shopper parse "https://www.valdemarsro.dk/pasta-carbonara/"

# 2. Search + add each recipe ingredient
nemlig-shopper search "spaghetti" --limit 5
nemlig-shopper add 701015 --quantity 1

nemlig-shopper search "pancetta" --limit 5
nemlig-shopper add 503220 --quantity 1

nemlig-shopper search "æg" --limit 5
nemlig-shopper add 100042 --quantity 1

nemlig-shopper search "parmesan" --limit 5
nemlig-shopper add 504100 --quantity 1

# 3. Search + add plain items
nemlig-shopper search "mælk" --limit 5
nemlig-shopper add 300015 --quantity 1

nemlig-shopper search "rugbrød" --limit 5
nemlig-shopper add 400022 --quantity 1

# 4. Verify
nemlig-shopper cart
```

## Tips

- **Always confirm with the user** before running `add` commands — show matched products first
- **Danish terms produce better results** than English
- **Combine `parse` output** from multiple recipes before searching to avoid duplicate purchases
- **Use `--limit 5`** on searches to keep output concise for product selection
- **Common staples** (salt, pepper, oil) can be skipped if user confirms they have them
