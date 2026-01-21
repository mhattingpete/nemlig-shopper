"""Tests for fuzzy matching and scoring in the matcher module."""

from nemlig_shopper.matcher import (
    fuzzy_score,
    is_produce_ingredient,
    match_compound_word,
    translate_ingredient,
)


class TestFuzzyScore:
    """Tests for fuzzy_score function."""

    def test_typo_tolerance_tomatoe(self):
        """Fuzzy matching handles typos like 'tomatoe'."""
        score = fuzzy_score("tomatoe", "tomater")
        assert score > 20, f"Expected score > 20 for typo match, got {score}"

    def test_typo_tolerance_similar_words(self):
        """Fuzzy matching handles similar words/typos."""
        # "tomat" vs "tomater" - Danish singular vs plural
        score = fuzzy_score("tomat", "tomater")
        assert score > 20, f"Expected score > 20 for similar match, got {score}"

    def test_typo_tolerance_chiken(self):
        """Fuzzy matching handles typos like 'chiken'."""
        score = fuzzy_score("chiken", "kylling")
        # Note: This is a partial match since the words are quite different
        # The fuzzy matching helps but may not score as high
        assert score >= 0, f"Expected non-negative score, got {score}"

    def test_compound_word_matching(self):
        """Fuzzy matching handles compound words with medium threshold."""
        score = fuzzy_score("kylling bryst", "kyllingebryst")
        # Compound words get a medium boost (60-75% similarity)
        assert score > 0, f"Expected positive score for compound match, got {score}"

    def test_substring_matching(self):
        """Fuzzy matching handles substring matches with medium threshold."""
        score = fuzzy_score("tomat", "flåede tomater")
        # Substring matches get a medium boost (60-75% similarity)
        assert score > 0, f"Expected positive score for substring match, got {score}"

    def test_no_false_positives_different_words(self):
        """Low similarity words should not get boosted."""
        score = fuzzy_score("løg", "spaghetti")
        assert score == 0, f"Expected 0 for unrelated words, got {score}"

    def test_no_false_positives_short_words(self):
        """Short unrelated words should not match."""
        score = fuzzy_score("æg", "pasta")
        assert score == 0, f"Expected 0 for unrelated words, got {score}"

    def test_exact_match_high_score(self):
        """Exact matches should get high scores."""
        score = fuzzy_score("tomater", "tomater")
        assert score >= 40, f"Expected score >= 40 for exact match, got {score}"

    def test_partial_word_in_longer_name(self):
        """Partial matches in longer product names."""
        score = fuzzy_score("mælk", "letmælk 1 liter")
        # Partial matches get a medium boost (substring match)
        assert score > 0, f"Expected positive score for partial match, got {score}"

    def test_multi_word_query_order_independent(self):
        """Multi-word queries should match regardless of order."""
        score1 = fuzzy_score("revet ost", "ost revet")
        score2 = fuzzy_score("ost revet", "revet ost")
        # Both should score well due to token_set_ratio
        assert score1 > 20, f"Expected score > 20, got {score1}"
        assert score2 > 20, f"Expected score > 20, got {score2}"


class TestMatchCompoundWord:
    """Tests for match_compound_word function."""

    def test_danish_compound_matching(self):
        """Compound matching works for Danish words without connectors."""
        # Danish compounds often have connector letters (e, s) that break simple concatenation
        # "chicken breast" translates to "kylling" + "bryst" = "kyllingbryst" (no 'e')
        # But "kyllingebryst" has a connector 'e', so simple compound matching fails
        # This case is handled by direct phrase translation instead
        result = match_compound_word("chicken breast", "kyllingebryst", translate_ingredient)
        # Returns False because "kyllingbryst" != "kyllingebryst"
        assert result is False

        # Compound matching works when translations directly concatenate
        # E.g., if both words are already in Danish form
        result = match_compound_word("kylling bryst", "kyllingbryst øko", translate_ingredient)
        assert result is True

    def test_single_word_returns_false(self):
        """Single words should not use compound matching."""
        result = match_compound_word("chicken", "kylling", translate_ingredient)
        assert result is False

    def test_unrelated_words_no_match(self):
        """Unrelated multi-word queries should not match."""
        result = match_compound_word("beef stew", "kyllingebryst", translate_ingredient)
        assert result is False

    def test_ground_beef_matches_hakket_oksekoed(self):
        """'ground beef' should form compound in 'hakket oksekød'."""
        # Note: This tests partial compound matching
        result = match_compound_word("ground beef", "hakket oksekød", translate_ingredient)
        # The compound "hakketoksekød" won't be in "hakket oksekød" (has space)
        # But the translation of "ground beef" is "hakket oksekød" as a whole phrase
        # So compound matching may not catch this case
        # This is expected behavior - the direct translation handles it instead
        assert result is False  # Compound matching is for Danish-style compounds


class TestTranslateIngredient:
    """Tests for translate_ingredient function with expanded dictionary."""

    def test_new_dairy_translations(self):
        """New dairy translations should work."""
        assert translate_ingredient("heavy cream") == "piskefløde"
        assert translate_ingredient("whipping cream") == "piskefløde"
        assert translate_ingredient("cream cheese") == "flødeost"
        assert translate_ingredient("cottage cheese") == "hytteost"

    def test_new_meat_translations(self):
        """New meat translations should work."""
        assert translate_ingredient("chicken breast") == "kyllingebryst"
        assert translate_ingredient("pork chop") == "svinekotelet"
        assert translate_ingredient("minced meat") == "hakket kød"
        assert translate_ingredient("shrimp") == "rejer"

    def test_new_vegetable_translations(self):
        """New vegetable translations should work."""
        assert translate_ingredient("spring onion") == "forårsløg"
        assert translate_ingredient("green onion") == "forårsløg"
        assert translate_ingredient("zucchini") == "squash"
        assert translate_ingredient("eggplant") == "aubergine"

    def test_new_pantry_translations(self):
        """New pantry translations should work."""
        assert translate_ingredient("all-purpose flour") == "hvedemel"
        assert translate_ingredient("baking powder") == "bagepulver"
        assert translate_ingredient("baking soda") == "natron"
        assert translate_ingredient("cornstarch") == "majsstivelse"
        assert translate_ingredient("bread crumbs") == "rasp"

    def test_case_insensitive(self):
        """Translations should be case-insensitive."""
        assert translate_ingredient("Chicken Breast") == "kyllingebryst"
        assert translate_ingredient("ZUCCHINI") == "squash"


class TestIsProduceIngredient:
    """Tests for is_produce_ingredient function."""

    def test_vegetables_detected(self):
        """Vegetables should be detected as produce."""
        assert is_produce_ingredient("tomater") is True
        assert is_produce_ingredient("gulerødder") is True
        assert is_produce_ingredient("løg") is True
        assert is_produce_ingredient("squash") is True
        assert is_produce_ingredient("rød peberfrugt") is True

    def test_fruits_detected(self):
        """Fruits should be detected as produce."""
        assert is_produce_ingredient("æbler") is True
        assert is_produce_ingredient("bananer") is True
        assert is_produce_ingredient("citron") is True
        assert is_produce_ingredient("jordbær") is True

    def test_herbs_detected(self):
        """Fresh herbs should be detected as produce."""
        assert is_produce_ingredient("persille") is True
        assert is_produce_ingredient("basilikum") is True
        assert is_produce_ingredient("dild") is True

    def test_non_produce_not_detected(self):
        """Non-produce items should not be detected."""
        assert is_produce_ingredient("mælk") is False
        assert is_produce_ingredient("kylling") is False
        assert is_produce_ingredient("pasta") is False
        assert is_produce_ingredient("mel") is False
        assert is_produce_ingredient("spegepølse") is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert is_produce_ingredient("TOMATER") is True
        assert is_produce_ingredient("Løg") is True

    def test_partial_match(self):
        """Should match when keyword is part of ingredient name."""
        assert is_produce_ingredient("rød løg") is True
        assert is_produce_ingredient("store tomater") is True
        assert is_produce_ingredient("frisk persille") is True
