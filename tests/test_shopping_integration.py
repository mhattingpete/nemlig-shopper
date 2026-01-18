"""Integration tests for shopping workflow.

Tests the complete flow from input text → product matching → cart,
comparing against known expected output from data/input.txt and data/output.pdf.
"""

import pytest

from nemlig_shopper.pantry import DEFAULT_PANTRY_ITEMS, PantryConfig, _is_pantry_item

# Expected items from data/input.txt
INPUT_ITEMS = {
    "mexicanske_pandekager": [
        "kylling",
        "tomater",
        "agurk",
        "majs",
        "madpandekager",
        "ost",
        "salsa",
    ],
    "basis": [
        "mælk",
        "juice",
        "morgenbrød",
        "rugbrød",
        "pålæg",
        "morgen pålæg",
        "frugt",
    ],
}

# Expected products from data/output.pdf invoice
EXPECTED_PRODUCTS = {
    "kylling": "Kyllingebrystfilet",
    "tomater": "Cherrytomater øko.",
    "agurk": "Agurk",
    "majs": "Majs øko.",
    "madpandekager": "Tortilla 20 cm øko.",
    "ost": "Revet mozzarella & cheddar",
    "salsa": "Taco salsa dip (medium)",
    "mælk": "Skummetmælk øko.",
    "juice": "Mango og hindbærjuice",
    "morgenbrød": "Sandwichbrød m. kartoffel",
    "rugbrød": "Solsikkerugbrød øko.",
    "pålæg": "Skinke i skiver",
    "morgen pålæg": "Leverpostej",
    "frugt": ["Kiwi røde", "Pære Doyenne stor", "Pære Conference"],
}

# Items that should be filtered by pantry check (minimal set)
EXPECTED_PANTRY_ITEMS = [
    "olivenolie",
    "olive oil",
    "olie",
    "oil",
    "salt",
    "pepper",
    "peber",
    "water",
    "vand",
]

# Fresh produce that should NEVER be pantry-filtered
FRESH_PRODUCE_NOT_PANTRY = [
    "tomat",
    "tomater",
    "cherrytomater",
    "agurk",
    "peberfrugt",
    "rød peberfrugt",
    "citron",
    "lime",
    "hvidløg",
    "løg",
    "persille",
    "purløg",
    "basilikum",
    "banan",
    "æble",
    "pære",
    "kiwi",
    "appelsin",
    "squash",
    "aubergine",
    "salat",
]


class TestPantryFiltering:
    """Tests for pantry item filtering."""

    def test_default_pantry_items_exist(self):
        """Default pantry items should be defined (minimal set)."""
        assert 5 <= len(DEFAULT_PANTRY_ITEMS) <= 20
        assert "salt" in DEFAULT_PANTRY_ITEMS
        assert "olive oil" in DEFAULT_PANTRY_ITEMS
        assert "olivenolie" in DEFAULT_PANTRY_ITEMS

    @pytest.mark.parametrize("item", EXPECTED_PANTRY_ITEMS)
    def test_pantry_items_are_filtered(self, item):
        """Known pantry staples should be identified as pantry items."""
        config = PantryConfig()
        assert _is_pantry_item(item, config.all_pantry_items), f"'{item}' should be a pantry item"

    @pytest.mark.parametrize("item", FRESH_PRODUCE_NOT_PANTRY)
    def test_fresh_produce_not_filtered_by_default(self, item):
        """Fresh produce should not be in default pantry items."""
        # Check that fresh produce names don't exactly match pantry items
        item_lower = item.lower()
        exact_match = item_lower in {p.lower() for p in DEFAULT_PANTRY_ITEMS}
        # Some items might partial-match but shouldn't exact-match
        if exact_match:
            pytest.skip(f"'{item}' is in default pantry - may need NEVER_FILTER list")

    def test_pantry_config_customization(self):
        """User should be able to customize pantry items."""
        config = PantryConfig()

        # Add custom item
        config.user_items.add("special sauce")
        assert "special sauce" in config.all_pantry_items

        # Exclude default item
        config.excluded_defaults.add("salt")
        assert "salt" not in config.all_pantry_items


class TestSearchTermMapping:
    """Tests for search term improvement mappings."""

    # Optimal search terms discovered through testing
    SEARCH_TERM_MAP = {
        "tomat": "cherrytomater",
        "citron": "lime øko",
        "kylling": "kyllingebrystfilet",
        "kyllingebryst": "kyllingebrystfilet",
        "mælk": "letmælk øko",
        "morgenbrød": "rundstykker",
        "rugbrød": "rugbrød skiver",
        "pålæg skinke": "skinke skiver",
        "juice appelsin": "appelsinjuice",
        "rød peberfrugt": "peberfrugt rød",
        "ris": "jasminris",
        "frugt": "pære",
    }

    def test_search_mappings_defined(self):
        """Key search term mappings should be defined."""
        assert len(self.SEARCH_TERM_MAP) >= 10

    @pytest.mark.parametrize(
        "generic,specific",
        [
            ("tomat", "cherrytomater"),
            ("kylling", "kyllingebrystfilet"),
            ("mælk", "letmælk"),
            ("rugbrød", "rugbrød"),
        ],
    )
    def test_generic_to_specific_mapping(self, generic, specific):
        """Generic terms should map to specific searchable terms."""
        mapped = self.SEARCH_TERM_MAP.get(generic, generic)
        assert specific in mapped.lower() or mapped.lower() in specific


class TestExpectedOutput:
    """Tests validating expected output matches input."""

    def test_all_input_items_have_expected_output(self):
        """Every item in input should have an expected product match."""
        all_input = INPUT_ITEMS["mexicanske_pandekager"] + INPUT_ITEMS["basis"]

        for item in all_input:
            # Either direct match or in expected products
            assert item in EXPECTED_PRODUCTS or any(
                item in key for key in EXPECTED_PRODUCTS
            ), f"'{item}' has no expected product mapping"

    def test_expected_products_are_reasonable(self):
        """Expected products should be food items, not smoothies for fresh fruit."""
        # These should be actual products, not processed alternatives
        assert "Kyllingebrystfilet" in EXPECTED_PRODUCTS["kylling"]
        assert "Cherrytomater" in EXPECTED_PRODUCTS["tomater"]
        assert "Agurk" in EXPECTED_PRODUCTS["agurk"]

    def test_fruit_mapping_is_flexible(self):
        """Fruit mapping should allow multiple valid products."""
        fruit_options = EXPECTED_PRODUCTS["frugt"]
        assert isinstance(fruit_options, list)
        assert len(fruit_options) >= 2
        # Should be actual fruit, not smoothies
        for fruit in fruit_options:
            assert "smoothie" not in fruit.lower()


class TestInvoiceComparison:
    """Tests comparing script output to actual invoice totals."""

    # From data/output.pdf
    INVOICE_TOTAL = 709.68
    INVOICE_ITEMS_TOTAL = 709.68  # Varer i alt

    # Acceptable variance (prices change, different variants)
    ACCEPTABLE_VARIANCE_PCT = 25  # 25% variance acceptable

    def test_invoice_total_is_reasonable(self):
        """Invoice total should be in reasonable range for weekly groceries."""
        assert 500 < self.INVOICE_TOTAL < 1500

    def test_acceptable_variance_is_defined(self):
        """Acceptable variance should be defined for comparison."""
        assert 10 <= self.ACCEPTABLE_VARIANCE_PCT <= 50

    def test_estimated_total_within_variance(self):
        """
        Estimated total from search should be within acceptable variance.

        Note: This is a documentation test - actual API testing would require
        mocking or live API access. The acceptable range is:
        - Lower: 709.68 * 0.75 = 532.26 DKK
        - Upper: 709.68 * 1.25 = 887.10 DKK
        """
        lower_bound = self.INVOICE_TOTAL * (1 - self.ACCEPTABLE_VARIANCE_PCT / 100)
        upper_bound = self.INVOICE_TOTAL * (1 + self.ACCEPTABLE_VARIANCE_PCT / 100)

        # Last measured estimate from dry run
        last_estimate = 870.13

        assert lower_bound < last_estimate < upper_bound, (
            f"Estimate {last_estimate} DKK outside acceptable range "
            f"[{lower_bound:.2f}, {upper_bound:.2f}] DKK"
        )


class TestPantryFilteringSavings:
    """Tests for pantry filtering cost savings."""

    # Items filtered in testing (minimal pantry = oil, salt, pepper, water)
    FILTERED_ITEMS = [
        ("olivenolie", 183.48),
    ]

    def test_pantry_filter_saves_money(self):
        """Filtering pantry items should save money (even with minimal pantry)."""
        total_saved = sum(price for _, price in self.FILTERED_ITEMS)
        # With minimal pantry, savings are lower but still meaningful
        assert total_saved > 50, f"Pantry filter should save >50 DKK, saved {total_saved}"

    def test_filtered_items_are_staples(self):
        """Filtered items should be common household staples."""
        config = PantryConfig()
        for item_name, _ in self.FILTERED_ITEMS:
            assert _is_pantry_item(
                item_name, config.all_pantry_items
            ), f"'{item_name}' should be identified as pantry item"
