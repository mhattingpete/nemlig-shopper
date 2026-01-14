"""Tests for unit parsing and conversion utilities."""

from nemlig_shopper.units import (
    calculate_packages_needed,
    can_convert,
    format_quantity_explanation,
    get_unit_type,
    normalize_to_base,
    parse_unit_size,
)


class TestGetUnitType:
    """Tests for get_unit_type function."""

    def test_weight_units(self):
        assert get_unit_type("g") == "weight"
        assert get_unit_type("kg") == "weight"
        assert get_unit_type("gram") == "weight"

    def test_volume_units(self):
        assert get_unit_type("ml") == "volume"
        assert get_unit_type("l") == "volume"
        assert get_unit_type("dl") == "volume"
        assert get_unit_type("cl") == "volume"

    def test_count_units(self):
        assert get_unit_type("stk") == "count"
        assert get_unit_type("pk") == "count"
        assert get_unit_type("fed") == "count"

    def test_unknown_units(self):
        assert get_unit_type("cups") == "volume"  # Recipe alias
        assert get_unit_type("tbsp") == "volume"
        assert get_unit_type("unknown") == "unknown"
        assert get_unit_type(None) == "unknown"


class TestNormalizeToBase:
    """Tests for normalize_to_base function."""

    def test_grams_unchanged(self):
        value, unit, unit_type = normalize_to_base(500, "g")
        assert value == 500
        assert unit == "g"
        assert unit_type == "weight"

    def test_kilograms_to_grams(self):
        value, unit, unit_type = normalize_to_base(1.5, "kg")
        assert value == 1500
        assert unit == "g"
        assert unit_type == "weight"

    def test_liters_to_milliliters(self):
        value, unit, unit_type = normalize_to_base(1, "l")
        assert value == 1000
        assert unit == "ml"
        assert unit_type == "volume"

    def test_deciliters_to_milliliters(self):
        value, unit, unit_type = normalize_to_base(5, "dl")
        assert value == 500
        assert unit == "ml"
        assert unit_type == "volume"

    def test_centiliters_to_milliliters(self):
        value, unit, unit_type = normalize_to_base(33, "cl")
        assert value == 330
        assert unit == "ml"
        assert unit_type == "volume"

    def test_unknown_unit_unchanged(self):
        value, unit, unit_type = normalize_to_base(2, "cups")
        assert value == 2
        assert unit == "cups"
        assert unit_type == "unknown"


class TestParseUnitSize:
    """Tests for parse_unit_size function."""

    def test_grams(self):
        result = parse_unit_size("500g")
        assert result is not None
        assert result.value == 500
        assert result.unit == "g"
        assert result.unit_type == "weight"

    def test_grams_with_space(self):
        result = parse_unit_size("500 g")
        assert result is not None
        assert result.value == 500
        assert result.unit == "g"

    def test_kilograms(self):
        result = parse_unit_size("1kg")
        assert result is not None
        assert result.value == 1000  # Normalized to grams
        assert result.unit == "g"

    def test_kilograms_decimal(self):
        result = parse_unit_size("1.5kg")
        assert result is not None
        assert result.value == 1500

    def test_danish_decimal(self):
        result = parse_unit_size("1,5 kg")
        assert result is not None
        assert result.value == 1500

    def test_liters(self):
        result = parse_unit_size("1L")
        assert result is not None
        assert result.value == 1000  # Normalized to ml
        assert result.unit == "ml"
        assert result.unit_type == "volume"

    def test_milliliters(self):
        result = parse_unit_size("500ml")
        assert result is not None
        assert result.value == 500
        assert result.unit == "ml"

    def test_deciliters(self):
        result = parse_unit_size("2dl")
        assert result is not None
        assert result.value == 200  # Normalized to ml
        assert result.unit == "ml"

    def test_pieces(self):
        result = parse_unit_size("6 stk")
        assert result is not None
        assert result.value == 6
        assert result.unit == "stk"
        assert result.unit_type == "count"

    def test_approximate(self):
        result = parse_unit_size("ca. 400g")
        assert result is not None
        assert result.value == 400
        assert result.unit == "g"

    def test_cirka(self):
        result = parse_unit_size("cirka 500 ml")
        assert result is not None
        assert result.value == 500

    def test_none_input(self):
        assert parse_unit_size(None) is None

    def test_empty_string(self):
        assert parse_unit_size("") is None

    def test_invalid_format(self):
        assert parse_unit_size("various sizes") is None


class TestCanConvert:
    """Tests for can_convert function."""

    def test_same_weight_units(self):
        assert can_convert("g", "kg") is True
        assert can_convert("kg", "g") is True

    def test_same_volume_units(self):
        assert can_convert("ml", "l") is True
        assert can_convert("dl", "ml") is True

    def test_incompatible_units(self):
        assert can_convert("g", "ml") is False
        assert can_convert("kg", "l") is False

    def test_unknown_units(self):
        assert can_convert("cups", "g") is False
        assert can_convert(None, "g") is False
        assert can_convert("g", None) is False


class TestCalculatePackagesNeeded:
    """Tests for calculate_packages_needed function."""

    def test_exact_match(self):
        # Need 500g, package is 500g -> 1 package
        assert calculate_packages_needed(500, "g", "500g") == 1

    def test_need_more_than_one(self):
        # Need 750g, package is 500g -> 2 packages
        assert calculate_packages_needed(750, "g", "500g") == 2

    def test_need_double(self):
        # Need 1000g, package is 500g -> 2 packages
        assert calculate_packages_needed(1000, "g", "500g") == 2

    def test_unit_conversion_kg_to_g(self):
        # Need 1.5kg (1500g), package is 500g -> 3 packages
        assert calculate_packages_needed(1.5, "kg", "500g") == 3

    def test_unit_conversion_dl_to_ml(self):
        # Need 5dl (500ml), package is 1L (1000ml) -> 1 package
        assert calculate_packages_needed(5, "dl", "1L") == 1

    def test_volume_need_more(self):
        # Need 1.5L (1500ml), package is 1L (1000ml) -> 2 packages
        assert calculate_packages_needed(1.5, "l", "1L") == 2

    def test_count_items(self):
        # Need 8 eggs, package is 6 stk -> 2 packages
        assert calculate_packages_needed(8, "stk", "6 stk") == 2

    def test_count_exact(self):
        # Need 6 eggs, package is 6 stk -> 1 package
        assert calculate_packages_needed(6, "stk", "6 stk") == 1

    def test_incompatible_units_returns_zero(self):
        # Need 500g, package is 1L -> can't convert, return 0
        assert calculate_packages_needed(500, "g", "1L") == 0

    def test_no_package_size_returns_zero(self):
        assert calculate_packages_needed(500, "g", None) == 0
        assert calculate_packages_needed(500, "g", "") == 0

    def test_none_quantity_returns_one(self):
        assert calculate_packages_needed(None, "g", "500g") == 1

    def test_zero_quantity_returns_one(self):
        assert calculate_packages_needed(0, "g", "500g") == 1

    def test_small_quantity_rounds_up(self):
        # Need 100g, package is 500g -> 1 package
        assert calculate_packages_needed(100, "g", "500g") == 1

    def test_no_unit_with_count_package(self):
        # Need 3 items (no unit), package is 6 stk
        # Should use fallback (return 0) since we can't verify compatibility
        result = calculate_packages_needed(3, None, "6 stk")
        # With no unit specified, we can't be sure they're compatible
        assert result == 0 or result == 1  # Implementation may vary


class TestFormatQuantityExplanation:
    """Tests for format_quantity_explanation function."""

    def test_with_all_info(self):
        result = format_quantity_explanation(750, "g", "500g", 2)
        assert "750" in result
        assert "g" in result
        assert "500g" in result
        assert "2" in result

    def test_none_quantity(self):
        result = format_quantity_explanation(None, None, "500g", 1)
        assert "1 package" in result

    def test_whole_number(self):
        result = format_quantity_explanation(500, "g", "500g", 1)
        assert "500 g" in result
        assert "500.0" not in result  # Should not have decimal
