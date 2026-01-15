# Nemlig Shopper Feature Roadmap

## Overview

Implement 11 features across 4 phases, building foundational capabilities first.

---

## Phase 1: Core Improvements (Foundation)

### 1.1 Smart Package Quantities
**Problem:** "400g pasta" buys 400 units instead of 1 package (500g)

**Solution:** Create `units.py` module to parse product `unit_size` and calculate packages needed.

**Files:**
- Create `nemlig_shopper/units.py`
- Modify `nemlig_shopper/scaler.py:212-230` - update `calculate_product_quantity()`
- Modify `nemlig_shopper/matcher.py:448` - pass unit info to calculation
- Create `tests/test_units.py`

**Key functions:**
```python
# units.py
def parse_unit_size(unit_size: str) -> ParsedUnit | None
def calculate_packages_needed(needed_qty, needed_unit, package_size) -> int
```

### 1.2 Organic Preference (`--organic`)
**Files:**
- Modify `nemlig_shopper/matcher.py:246-359` - add organic boost in `score_product_match()`
- Modify `nemlig_shopper/cli.py` - add `--organic` flag to `add` command

**Logic:** +50 score for products with "øko" in name or "Økologisk" in labels

### 1.3 Budget Mode (`--budget`)
**Files:**
- Modify `nemlig_shopper/matcher.py` - add price-based scoring
- Modify `nemlig_shopper/cli.py` - add `--budget` flag

**Logic:** Use `unit_price_calc` field to prefer lower-priced alternatives

### 1.4 Out-of-Stock Handling
**Files:**
- Modify `nemlig_shopper/matcher.py` - check `available` field, auto-select alternative

**Logic:** If best match has `available=False`, use first available alternative

---

## Phase 2: Meal Planning & Export

### 2.1 Meal Planning (`nemlig plan`)
**Files:**
- Create `nemlig_shopper/planner.py`
- Modify `nemlig_shopper/cli.py` - add `plan` command
- Create `tests/test_planner.py`

**Features:**
- Parse multiple recipe URLs
- Consolidate duplicate ingredients (e.g., "2 onions" + "1 onion" = "3 onions")
- De-duplicate products in cart

**CLI:**
```bash
nemlig plan url1 url2 url3
nemlig plan --file recipes.txt --organic --budget
```

### 2.2 Shopping List Export
**Files:**
- Create `nemlig_shopper/export.py`
- Modify `nemlig_shopper/cli.py` - add `export` command

**Formats:**
- Markdown: `nemlig export shopping-list.md`
- PDF: `nemlig export shopping-list.pdf` (using `reportlab` or `weasyprint`)
- JSON: `nemlig export shopping-list.json`

---

## Phase 3: Interactive & Delivery

### 3.1 Interactive Review (TUI)
**Dependencies:** Add `textual` to dependencies

**Files:**
- Create `nemlig_shopper/tui.py`
- Modify `nemlig_shopper/cli.py` - add `--interactive` flag

**Features:**
- Table view of all matches
- Arrow keys to navigate
- Enter to swap with alternative
- Confirm/cancel buttons

### 3.2 Delivery Slot Selection
**Files:**
- Modify `nemlig_shopper/api.py` - add `get_delivery_slots()`, `select_slot()`
- Modify `nemlig_shopper/cli.py` - add `slots` and `checkout` commands

**API Discovery needed:** Use Chrome DevTools MCP to find slot endpoints

**CLI:**
```bash
nemlig slots                           # List available slots
nemlig checkout --slot "Tirsdag 18-21" # Select slot
```

---

## Phase 4: Advanced Features

### 4.1 Dietary Filters
**Files:**
- Modify `nemlig_shopper/matcher.py` - add label-based filtering
- Modify `nemlig_shopper/cli.py` - add filter flags

**Flags:**
- `--lactose-free` - filter for "Laktosefri" label
- `--gluten-free` - filter for "Glutenfri" label
- `--vegan` - filter for "Vegansk" label

### 4.2 Price Tracking
**Files:**
- Create `nemlig_shopper/price_tracker.py`
- Create price database (`~/.nemlig-shopper/prices.db` using SQLite)
- Modify `nemlig_shopper/cli.py` - add `prices` command group

**Features:**
- Store prices on each search
- `nemlig prices history <product>` - show price history
- `nemlig prices alerts` - show products on sale vs historical avg

### 4.3 Recipe Suggestions
**Files:**
- Create `nemlig_shopper/suggestions.py`
- Modify `nemlig_shopper/cli.py` - add `suggest` command

**Features:**
- `nemlig suggest --on-sale` - recipes using currently discounted items
- `nemlig suggest --from-preferences` - recipes using previously bought items

---

## Implementation Order

```
Phase 1 (Week 1-2):
├── 1.1 Smart Package Quantities  ← Foundation for everything
├── 1.2 Organic Preference        ← Simple scoring addition
├── 1.3 Budget Mode               ← Simple scoring addition
└── 1.4 Out-of-Stock Handling     ← Critical for reliability

Phase 2 (Week 2-3):
├── 2.1 Meal Planning             ← Depends on Phase 1 matcher updates
└── 2.2 Shopping List Export      ← Independent

Phase 3 (Week 3-4):
├── 3.1 Interactive TUI           ← Nice-to-have UX improvement
└── 3.2 Delivery Slots            ← Requires API discovery

Phase 4 (Week 4+):
├── 4.1 Dietary Filters           ← Extends scoring system
├── 4.2 Price Tracking            ← New subsystem
└── 4.3 Recipe Suggestions        ← Depends on price tracking
```

---

## File Summary

### New Files
| File | Purpose |
|------|---------|
| `nemlig_shopper/units.py` | Unit parsing and conversion |
| `nemlig_shopper/planner.py` | Meal planning and consolidation |
| `nemlig_shopper/export.py` | Shopping list export |
| `nemlig_shopper/tui.py` | Interactive terminal UI |
| `nemlig_shopper/price_tracker.py` | Price history and alerts |
| `nemlig_shopper/suggestions.py` | Recipe suggestions |
| `tests/test_units.py` | Unit conversion tests |
| `tests/test_planner.py` | Meal planning tests |

### Modified Files
| File | Changes |
|------|---------|
| `nemlig_shopper/scaler.py` | Update `calculate_product_quantity()` |
| `nemlig_shopper/matcher.py` | Add scoring options, out-of-stock handling |
| `nemlig_shopper/api.py` | Add delivery slot methods |
| `nemlig_shopper/cli.py` | Add all new commands and flags |
| `pyproject.toml` | Add `textual`, `reportlab` dependencies |

---

## CLI Interface After All Features

```bash
# Enhanced add command
nemlig add <url> [--organic] [--budget] [--interactive]
nemlig add <url> --lactose-free --gluten-free
nemlig add <url> -o -b -s 2  # organic, budget, scale 2x

# Meal planning
nemlig plan <url1> <url2> ...
nemlig plan --file recipes.txt [--organic] [--budget]

# Export
nemlig export <filename> [--format md|pdf|json]

# Delivery
nemlig slots
nemlig checkout --slot "Tirsdag 18-21"

# Price tracking
nemlig prices history <product>
nemlig prices alerts
nemlig prices track  # Record current prices

# Suggestions
nemlig suggest --on-sale
nemlig suggest --from-preferences
```

---

## Verification Plan

### Phase 1 Tests
```bash
# Unit conversion
uv run pytest tests/test_units.py -v

# E2E with organic
uv run nemlig add "https://www.valdemarsro.dk/one-pot-vegetar-pasta-med-tomatfloedesauce/" --organic --yes

# E2E with budget
uv run nemlig add "https://www.valdemarsro.dk/one-pot-vegetar-pasta-med-tomatfloedesauce/" --budget --yes

# Verify package quantities
uv run nemlig parse <url>  # Check quantities make sense
```

### Phase 2 Tests
```bash
# Meal planning
uv run pytest tests/test_planner.py -v
uv run nemlig plan --file test_recipes.txt --yes

# Export
uv run nemlig export test.md
uv run nemlig export test.pdf
```

### Phase 3-4 Tests
```bash
# Interactive (manual)
uv run nemlig add <url> --interactive

# Delivery slots
uv run nemlig slots
uv run nemlig checkout --slot "..."

# Price tracking
uv run nemlig prices track
uv run nemlig prices history "mælk"
```

---

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "textual>=0.50.0",      # TUI
    "reportlab>=4.0.0",     # PDF export
]
```

---

## Start with Phase 1

Ready to implement:
1. Create `units.py` with unit parsing
2. Update `scaler.py` and `matcher.py` for smart quantities
3. Add `--organic` and `--budget` flags
4. Add out-of-stock fallback logic
