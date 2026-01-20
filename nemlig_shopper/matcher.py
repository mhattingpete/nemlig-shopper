"""Ingredient to product matching logic."""

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from .api import NemligAPI, NemligAPIError
from .preference_engine import (
    check_allergy_safety,
    check_dietary_compatibility,
)
from .preferences import is_preferred_product
from .scaler import ScaledIngredient, calculate_product_quantity


def is_organic_product(product: dict[str, Any]) -> bool:
    """Check if a product is organic based on name and labels.

    Detects organic products by looking for:
    - "øko" prefix in product name (Danish organic indicator)
    - "Økologisk" in the product's labels array

    Args:
        product: Product dict from API

    Returns:
        True if product appears to be organic
    """
    product_name = (product.get("name") or "").lower()
    if "øko" in product_name:
        return True

    labels = product.get("labels", [])
    if isinstance(labels, list):
        for label in labels:
            label_text = label.lower() if isinstance(label, str) else label.get("name", "").lower()
            if "økologisk" in label_text:
                return True

    return False


def fuzzy_score(query: str, product_name: str) -> int:
    """Calculate fuzzy similarity score between query and product name.

    Uses token-based and partial matching to handle:
    - Word order differences ("chicken breast" → "bryst af kylling")
    - Substring matches ("tomat" → "flåede tomater")
    - Minor typos ("tomatoe" → "tomater")

    Args:
        query: The search query or ingredient name
        product_name: The product name to compare against

    Returns:
        Score boost (0-50) based on fuzzy similarity
    """
    query_lower = query.lower()
    name_lower = product_name.lower()

    # Token set ratio - handles multi-word matching regardless of order
    token_score = fuzz.token_set_ratio(query_lower, name_lower)

    # Partial ratio - handles substring matching
    partial_score = fuzz.partial_ratio(query_lower, name_lower)

    # Weighted combination (token matching slightly more important)
    combined = token_score * 0.6 + partial_score * 0.4

    # Threshold-based boosting to avoid false positives
    if combined >= 75:
        return int(combined * 0.5)  # Max +50 boost
    elif combined >= 60:
        return int(combined * 0.25)  # Max +25 boost
    return 0


def match_compound_word(query: str, product_name: str, translate_func) -> bool:
    """Check if query words form a compound in product name.

    Danish uses compound words heavily (e.g., "kyllingebryst" not "kylling bryst").
    This checks if translated words combine to match the product.

    Args:
        query: Multi-word query (e.g., "chicken breast")
        product_name: Product name to check against
        translate_func: Function to translate words to Danish

    Returns:
        True if compound word match found
    """
    words = query.lower().split()
    if len(words) < 2:
        return False

    name_lower = product_name.lower()

    # Translate each word and check if compound exists
    translated = [translate_func(w) or w for w in words]
    compound = "".join(translated)

    return compound in name_lower or name_lower.startswith(compound)


# English to Danish translations for common ingredients
INGREDIENT_TRANSLATIONS: dict[str, str] = {
    # Vegetables
    "onion": "løg",
    "onions": "løg",
    "garlic": "hvidløg",
    "tomato": "tomat",
    "tomatoes": "tomat",
    "potato": "kartoffel",
    "potatoes": "kartofler",
    "carrot": "gulerod",
    "carrots": "gulerødder",
    "celery": "selleri",
    "lettuce": "salat",
    "cucumber": "agurk",
    "pepper": "peber",
    "bell pepper": "peberfrugt",
    "mushroom": "champignon",
    "mushrooms": "champignon",
    "spinach": "spinat",
    "broccoli": "broccoli",
    "cabbage": "kål",
    "leek": "porre",
    "shallot": "skalotteløg",
    "shallots": "skalotteløg",
    "spring onion": "forårsløg",
    "spring onions": "forårsløg",
    "green onion": "forårsløg",
    "green onions": "forårsløg",
    "zucchini": "squash",
    "eggplant": "aubergine",
    "aubergine": "aubergine",
    "corn": "majs",
    "sweet corn": "majs",
    "peas": "ærter",
    "green beans": "grønne bønner",
    "asparagus": "asparges",
    # Dairy
    "milk": "mælk",
    "butter": "smør",
    "cheese": "ost",
    "cream": "fløde",
    "egg": "æg",
    "eggs": "æg",
    "yogurt": "yoghurt",
    "sour cream": "creme fraiche",
    "heavy cream": "piskefløde",
    "whipping cream": "piskefløde",
    "cream cheese": "flødeost",
    "cottage cheese": "hytteost",
    "parmesan": "parmesan",
    "mozzarella": "mozzarella",
    "feta": "feta",
    # Meat & Fish
    "chicken": "kylling",
    "beef": "oksekød",
    "pork": "svinekød",
    "fish": "fisk",
    "salmon": "laks",
    "bacon": "bacon",
    "ham": "skinke",
    "sausage": "pølse",
    "ground beef": "hakket oksekød",
    "ground pork": "hakket svinekød",
    "minced meat": "hakket kød",
    "minced beef": "hakket oksekød",
    "chicken breast": "kyllingebryst",
    "breast": "bryst",  # For compound word matching
    "chicken thigh": "kyllingelår",
    "thigh": "lår",  # For compound word matching
    "chicken thighs": "kyllingelår",
    "pork chop": "svinekotelet",
    "pork chops": "svinekoteletter",
    "lamb": "lam",
    "duck": "and",
    "turkey": "kalkun",
    "shrimp": "rejer",
    "prawns": "rejer",
    "cod": "torsk",
    "tuna": "tun",
    # Pantry
    "flour": "mel",
    "sugar": "sukker",
    "salt": "salt",
    "olive oil": "olivenolie",
    "vegetable oil": "rapsolie",
    "pasta": "pasta",
    "rice": "ris",
    "bread": "brød",
    "vinegar": "eddike",
    "soy sauce": "sojasauce",
    "all-purpose flour": "hvedemel",
    "plain flour": "hvedemel",
    "bread crumbs": "rasp",
    "breadcrumbs": "rasp",
    "panko": "panko",
    "baking powder": "bagepulver",
    "baking soda": "natron",
    "cornstarch": "majsstivelse",
    "corn starch": "majsstivelse",
    "yeast": "gær",
    "vanilla": "vanilje",
    "vanilla extract": "vaniljeekstrakt",
    "cocoa powder": "kakaopulver",
    "coconut milk": "kokosmælk",
    "coconut cream": "kokosfløde",
    "tomato paste": "tomatpuré",
    "tomato sauce": "tomatsauce",
    "canned tomatoes": "flåede tomater",
    "diced tomatoes": "hakkede tomater",
    # Fruits
    "lemon": "citron",
    "lemons": "citron",
    "lime": "lime",
    "apple": "æble",
    "apples": "æbler",
    "orange": "appelsin",
    "banana": "banan",
    # Herbs & Spices
    "parsley": "persille",
    "basil": "basilikum",
    "thyme": "timian",
    "oregano": "oregano",
    "rosemary": "rosmarin",
    "cilantro": "koriander",
    "dill": "dild",
    "chives": "purløg",
    "ginger": "ingefær",
    "cinnamon": "kanel",
    "paprika": "paprika",
    "cumin": "spidskommen",
    # Beverages
    "wine": "vin",
    "white wine": "hvidvin",
    "red wine": "rødvin",
    "dry white wine": "hvidvin",
    "beer": "øl",
    "water": "vand",
    # Other
    "stock": "bouillon",
    "broth": "bouillon",
    "chicken stock": "kyllingebouillon",
    "beef stock": "oksebouillon",
    "vegetable stock": "grøntsagsbouillon",
    "honey": "honning",
    "mustard": "sennep",
    "mayonnaise": "mayonnaise",
    "ketchup": "ketchup",
}

# Categories that are typically not food items
NON_FOOD_CATEGORIES: set[str] = {
    "Husholdning",
    "Pleje",
    "Rengøring",
    "Baby",
    "Dyremad",
    "Apotek",
}

# Categories that contain snacks/chips rather than fresh ingredients
SNACK_CATEGORIES: set[str] = {
    "Kiosk",
}

# Search term improvements for better matching
# Maps generic terms to more specific search queries
SEARCH_TERM_IMPROVEMENTS: dict[str, str] = {
    # Vegetables - prefer specific varieties
    "tomat": "cherrytomater",
    "tomater": "cherrytomater",
    # Tortillas/wraps
    "madpandekager": "tortilla wraps",
    "tortilla": "tortilla wraps",
    # Cheese - context dependent but default to shredded for cooking
    "revet ost": "revet mozzarella",
    # Salsa - default to taco salsa
    "salsa": "taco salsa",
    # Bread
    "morgenbrød": "toastbrød",
    "rugbrød": "rugbrød øko",
    # Dairy
    "mælk": "letmælk",
    # Meat
    "kylling": "kyllingebrystfilet",
    "kyllingebryst": "kyllingebrystfilet",
    # Rice
    "ris": "jasminris",
    # Stock/bouillon
    "hønsebouillonterning": "hønsebouillon",
    "hønsebouillon terning": "hønsebouillon",
    "kyllingebouillon": "hønsebouillon",
    "bouillonterning": "hønsebouillon",
}

# Context-specific search improvements
# Maps (ingredient, meal_context) to better search query
# Note: These search terms have been tested against the Nemlig API
CONTEXT_SEARCH_IMPROVEMENTS: dict[tuple[str, str], str] = {
    ("ost", "mexicansk"): "revet mozzarella",
    ("ost", "taco"): "revet mozzarella",
    ("ost", "pizza"): "pizzaost",
    ("ost", "pasta"): "parmesan",
    ("ost", "burger"): "cheddar revet",
    ("salsa", "mexicansk"): "taco salsa dip",
    ("salsa", "taco"): "taco salsa dip",
}

# Ambiguous terms that should prompt for user clarification
AMBIGUOUS_TERMS: set[str] = {
    "frugt",
    "grønt",
    "grøntsager",
    "pålæg",
    "morgen pålæg",
    "morgenpålæg",
    "kød",
    "fisk",
    "ost",  # Without context, ost is ambiguous
    "brød",
    "slik",
    "snacks",
    "drikkevarer",
    "juice",  # Many types of juice
}


@dataclass
class ProductMatch:
    """A matched product for an ingredient."""

    ingredient_name: str
    product: dict[str, Any] | None
    quantity: int
    matched: bool
    search_query: str
    alternatives: list[dict[str, Any]]
    # Dietary filtering info
    is_dietary_safe: bool = True
    dietary_warnings: list[str] | None = None
    excluded_count: int = 0  # Number of products filtered out due to dietary requirements

    @property
    def product_id(self) -> int | None:
        if self.product:
            return self.product.get("id")
        return None

    @property
    def product_name(self) -> str:
        if self.product:
            return self.product.get("name", "Unknown")
        return "No match found"

    @property
    def price(self) -> float | None:
        if self.product:
            return self.product.get("price")
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ingredient_name": self.ingredient_name,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "matched": self.matched,
            "search_query": self.search_query,
        }


def clean_ingredient_name(name: str) -> str:
    """
    Clean ingredient name for better search matching.

    Args:
        name: Raw ingredient name

    Returns:
        Cleaned name suitable for product search
    """
    # Remove common descriptors that don't help with search
    remove_words = {
        "fresh",
        "dried",
        "frozen",
        "organic",
        "large",
        "small",
        "medium",
        "chopped",
        "diced",
        "minced",
        "sliced",
        "grated",
        "crushed",
        "whole",
        "ground",
        "powdered",
        "raw",
        "cooked",
        "ripe",
        "frisk",
        "tørret",
        "frosset",
        "økologisk",
        "stor",
        "lille",
        "hakket",
        "skåret",
        "revet",
        "knust",
        "hel",
        "malet",
        "rå",
        "kogt",
    }

    words = name.lower().split()
    cleaned_words = [w for w in words if w not in remove_words]

    return " ".join(cleaned_words) if cleaned_words else name


def translate_ingredient(name: str) -> str | None:
    """
    Translate an English ingredient name to Danish.

    Args:
        name: Ingredient name (possibly in English)

    Returns:
        Danish translation if found, None otherwise
    """
    name_lower = name.lower().strip()

    # Try exact match first
    if name_lower in INGREDIENT_TRANSLATIONS:
        return INGREDIENT_TRANSLATIONS[name_lower]

    # Try matching multi-word phrases (e.g., "dry white wine")
    for eng, dan in INGREDIENT_TRANSLATIONS.items():
        if eng in name_lower:
            return dan

    # Try matching individual words
    words = name_lower.split()
    for word in words:
        if word in INGREDIENT_TRANSLATIONS:
            return INGREDIENT_TRANSLATIONS[word]

    return None


def score_product_match(
    product: dict[str, Any],
    ingredient_name: str,
    search_query: str,
    *,
    prefer_organic: bool = False,
    prefer_budget: bool = False,
) -> int:
    """
    Score a product match based on relevance to the ingredient.

    Higher scores indicate better matches. Products that the user has
    previously purchased receive a boost to prefer familiar items.
    Out-of-stock products are heavily penalized.

    Args:
        product: Product dict from API
        ingredient_name: Original ingredient name
        search_query: The query used to find this product
        prefer_organic: Boost organic products (+50 score)
        prefer_budget: Prefer cheaper products based on unit price

    Returns:
        Integer score (higher is better)
    """
    score = 0
    product_name = product.get("name", "").lower()
    category = product.get("category", "")
    ingredient_lower = ingredient_name.lower()
    query_lower = search_query.lower()

    # Heavily penalize out-of-stock products
    if not product.get("available", True):
        score -= 200

    # Boost products the user has purchased before
    product_id = product.get("id")
    if product_id and is_preferred_product(product_id):
        score += 75

    # Organic preference: boost products with organic indicators
    if prefer_organic and is_organic_product(product):
        score += 50

    # Budget preference: prefer lower unit prices
    if prefer_budget:
        unit_price = product.get("unit_price_calc") or product.get("unit_price")
        if unit_price:
            try:
                # Lower unit price = higher score
                # Scale: 10 DKK/unit = 0 bonus, 5 DKK/unit = +25 bonus, 1 DKK/unit = +45 bonus
                price_val = float(unit_price) if isinstance(unit_price, int | float | str) else 0
                if price_val > 0:
                    # Inverse relationship: lower price = higher bonus
                    # Cap at 50 bonus for very cheap items
                    budget_bonus = min(50, int(50 * (1 - min(price_val, 20) / 20)))
                    score += budget_bonus
            except (ValueError, TypeError):
                pass

    # Penalize non-food categories heavily
    if category in NON_FOOD_CATEGORIES:
        score -= 100

    # Penalize snack categories (chips, candy, etc.) when looking for fresh ingredients
    if category in SNACK_CATEGORIES:
        # Only penalize if we're not actually looking for snacks
        snack_terms = {"chips", "slik", "candy", "snack", "chokolade", "chocolate"}
        if not any(term in ingredient_lower for term in snack_terms):
            score -= 75

    # Boost food categories
    food_categories = {"Grønt", "Mejeri", "Kød", "Frost", "Brød", "VIN", "Drikke", "Kolonial"}
    if category in food_categories:
        score += 50

    # Boost if search query appears at the start of product name
    if product_name.startswith(query_lower):
        score += 100

    # Boost if search query appears anywhere in product name
    if query_lower in product_name:
        score += 50

    # Boost if all words of the search query appear in the product name
    # This helps context-specific searches like "revet mozzarella" match better
    query_words = set(query_lower.split())
    if query_words and all(word in product_name for word in query_words):
        score += 75

    # Boost for each word of the ingredient that appears in product name
    ingredient_words = set(ingredient_lower.split())
    for word in ingredient_words:
        if len(word) > 2 and word in product_name:
            score += 30

    # Fuzzy matching boost for near-matches (typos, partial matches)
    fuzzy_boost = fuzzy_score(search_query, product_name)
    score += fuzzy_boost

    # Compound word matching for multi-word queries
    if match_compound_word(search_query, product_name, translate_ingredient):
        score += 40

    # Penalize if product name contains words suggesting it's a derivative product
    # (like "onion chips" when we want actual onions)
    derivative_indicators = {
        "chips",
        "snack",
        "sauce",
        "dressing",
        "pulver",
        "powder",
        "mix",
        "krydderi",
        "spice",
        "klude",
        "refill",
        "rengøring",
        "spray",
        "sæbe",
        "vask",
        "ble",
        "bleer",
        "drynites",
        "shampoo",
    }
    for indicator in derivative_indicators:
        if indicator in product_name:
            # Don't penalize if the ingredient itself is the derivative
            if indicator not in ingredient_lower:
                score -= 40

    # Extra penalty when the ingredient appears only as a flavour
    # e.g. "sour cream & onion" chips when we want actual onions
    # But don't penalize when the & is part of a product name like "mozzarella & cheddar"
    flavor_indicators = [" m. ", " med ", " smag "]
    for flavor_indicator in flavor_indicators:
        if flavor_indicator in product_name:
            before, after = product_name.split(flavor_indicator, 1)
            if any(word in after for word in ingredient_words):
                score -= 60

    # Special handling for & - only penalize if ingredient word appears after &
    if "&" in product_name:
        before, after = product_name.split("&", 1)
        # Only penalize if the ingredient word appears ONLY after the &
        # (like "sour cream & onion" when searching for onion)
        if any(word in after for word in ingredient_words) and not any(
            word in before for word in ingredient_words
        ):
            score -= 60

    # Extra penalty for obvious cleaning / personal care products
    cleaning_terms = {
        "klud",
        "klude",
        "rengøring",
        "spray",
        "sæbe",
        "vask",
        "mopning",
        "ble",
        "bleer",
        "drynites",
        "shampoo",
    }
    if any(term in product_name for term in cleaning_terms) and not any(
        term in ingredient_lower for term in cleaning_terms
    ):
        score -= 100

    return score


def generate_search_queries(
    ingredient_name: str,
    meal_context: str | None = None,
) -> list[str]:
    """
    Generate multiple search queries for an ingredient.

    Prioritizes Danish translations for better results on Nemlig.com.
    Uses context-specific improvements when meal context is provided.

    Args:
        ingredient_name: The ingredient name
        meal_context: Optional meal context for better matching (e.g., "mexicansk", "pizza")

    Returns:
        List of search queries to try, in order of preference
    """
    queries = []
    name_lower = ingredient_name.lower().strip()

    # Check for context-specific improvements first
    # Use partial matching: context "mexicanske pandekager" matches key "mexicansk"
    if meal_context:
        context_lower = meal_context.lower()
        for (ing_key, ctx_key), search_query in CONTEXT_SEARCH_IMPROVEMENTS.items():
            if name_lower == ing_key and ctx_key in context_lower:
                queries.append(search_query)
                break  # Use first match

    # Check for general search term improvements
    if name_lower in SEARCH_TERM_IMPROVEMENTS:
        queries.append(SEARCH_TERM_IMPROVEMENTS[name_lower])

    # Try Danish translation
    danish = translate_ingredient(ingredient_name)
    if danish and danish not in queries:
        queries.append(danish)

    # Original name (cleaned)
    cleaned = clean_ingredient_name(ingredient_name)
    if cleaned and cleaned not in queries:
        queries.append(cleaned)

    # Original name as-is if different from cleaned
    if name_lower != cleaned and name_lower not in queries:
        queries.append(name_lower)

    # First word only (often the main ingredient)
    words = cleaned.split()
    if len(words) > 1:
        first_word = words[0]
        # Also try translating just the first word
        first_word_danish = translate_ingredient(first_word)
        if first_word_danish and first_word_danish not in queries:
            queries.append(first_word_danish)
        if first_word not in queries:
            queries.append(first_word)

    return queries


def is_ambiguous_term(ingredient_name: str) -> bool:
    """Check if an ingredient term is ambiguous and needs user clarification."""
    return ingredient_name.lower().strip() in AMBIGUOUS_TERMS


def filter_by_dietary_requirements(
    products: list[dict[str, Any]],
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Filter products by dietary requirements.

    Args:
        products: List of products to filter
        allergies: List of allergen types to avoid (e.g., ["lactose", "gluten"])
        dietary: List of dietary restrictions (e.g., ["vegan", "vegetarian"])

    Returns:
        Tuple of (safe_products, excluded_products)
    """
    if not allergies and not dietary:
        return products, []

    safe = []
    excluded = []

    for product in products:
        is_safe = True
        reasons = []

        # Check allergies
        if allergies:
            result = check_allergy_safety(product, allergies)
            if not result.is_safe:
                is_safe = False
                reasons.extend(result.allergens_found)

        # Check dietary restrictions
        if dietary and is_safe:
            result = check_dietary_compatibility(product, dietary)
            if not result.is_compatible:
                is_safe = False
                reasons.extend(result.conflicts)

        if is_safe:
            safe.append(product)
        else:
            # Annotate product with exclusion reason for potential display
            product = product.copy()
            product["_excluded_reasons"] = reasons
            excluded.append(product)

    return safe, excluded


def _get_dietary_alternative_query(
    ingredient_name: str,
    allergies: list[str] | None,
    dietary: list[str] | None,
) -> str | None:
    """Generate an alternative search query for dietary requirements."""
    from .preference_engine import get_safe_alternative_query

    return get_safe_alternative_query(ingredient_name, allergies, dietary)


def _apply_smart_organic_preference(
    products: list[dict[str, Any]],
    organic_price_threshold: float = 15.0,
) -> list[dict[str, Any]]:
    """
    Apply smart organic preference: prefer organic if price diff < threshold.

    This finds the cheapest conventional product and compares organic options.
    Organic products within the threshold of the cheapest are boosted.

    Args:
        products: List of products to process
        organic_price_threshold: Maximum extra cost for organic (default 15 DKK)

    Returns:
        Products with organic preference scores applied
    """
    if not products:
        return products

    # Find cheapest conventional product
    cheapest_conventional_price = float("inf")
    for product in products:
        if not is_organic_product(product):
            price = product.get("price") or float("inf")
            if price < cheapest_conventional_price:
                cheapest_conventional_price = price

    # If no conventional products, just return as-is
    if cheapest_conventional_price == float("inf"):
        return products

    # Add organic preference score
    for product in products:
        if is_organic_product(product):
            price = product.get("price") or float("inf")
            price_diff = price - cheapest_conventional_price
            if price_diff <= organic_price_threshold:
                # Boost organic products within threshold
                product["_organic_bonus"] = 100  # High bonus for smart organic
            else:
                # Organic but too expensive
                product["_organic_bonus"] = -10  # Small penalty
        else:
            product["_organic_bonus"] = 0

    return products


def match_ingredient(
    api: NemligAPI,
    ingredient_name: str,
    quantity: float | None = None,
    ingredient_unit: str | None = None,
    max_alternatives: int = 3,
    *,
    prefer_organic: bool = False,
    prefer_budget: bool = False,
    smart_organic: bool = False,
    organic_price_threshold: float = 15.0,
    meal_context: str | None = None,
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> ProductMatch:
    """
    Find matching products for a single ingredient.

    Uses smart scoring to find the best match, prioritizing:
    - Danish translations of English ingredients
    - Food categories over non-food categories
    - Products where the ingredient name appears in the product name
    - Available products over out-of-stock ones
    - Organic products (if prefer_organic=True or smart_organic=True)
    - Cheaper products (if prefer_budget=True)

    When allergies or dietary restrictions are specified, uses a hybrid approach:
    1. Phase 1: Filter out unsafe products
    2. Phase 2: If all filtered, try alternative search (e.g., "laktosefri mælk")
    3. Phase 3: If still nothing, show warning with best available match

    Args:
        api: NemligAPI instance
        ingredient_name: Name of ingredient to match
        quantity: Scaled quantity needed
        ingredient_unit: Unit from recipe (e.g., "g", "ml") for package calculation
        max_alternatives: Maximum alternative products to return
        prefer_organic: Boost organic products in scoring
        prefer_budget: Boost cheaper products in scoring
        smart_organic: Prefer organic only if price diff < organic_price_threshold
        organic_price_threshold: Max extra cost for organic (default 15 DKK)
        meal_context: Optional meal context for better matching (e.g., "mexicansk")
        allergies: List of allergen types to avoid (e.g., ["lactose", "gluten"])
        dietary: List of dietary restrictions (e.g., ["vegan", "vegetarian"])

    Returns:
        ProductMatch with best match and alternatives
    """
    queries = generate_search_queries(ingredient_name, meal_context=meal_context)
    all_products: list[dict[str, Any]] = []
    used_query = queries[0] if queries else ingredient_name

    # Collect products from multiple queries for better selection
    seen_ids: set[int] = set()
    for query_idx, query in enumerate(queries):
        try:
            # Get more results to have a better selection pool
            products = api.search_products(query, limit=max_alternatives * 3 + 5)
            if products:
                for product in products:
                    product_id = product.get("id")
                    if product_id and product_id not in seen_ids:
                        seen_ids.add(product_id)
                        # Store the query that found this product for scoring
                        product["_search_query"] = query
                        # Mark products from context-specific query (first query)
                        product["_is_context_match"] = query_idx == 0 and meal_context is not None
                        all_products.append(product)
                if not used_query or used_query == ingredient_name:
                    used_query = query
        except NemligAPIError:
            continue

    if all_products:
        # Apply smart organic preference if enabled
        if smart_organic:
            all_products = _apply_smart_organic_preference(all_products, organic_price_threshold)

        # Score and sort products by relevance
        scored_products = [
            (
                product,
                score_product_match(
                    product,
                    ingredient_name,
                    product.get("_search_query", used_query),
                    prefer_organic=prefer_organic,
                    prefer_budget=prefer_budget,
                )
                + product.get("_organic_bonus", 0)  # Add smart organic bonus
                + (200 if product.get("_is_context_match") else 0),  # Boost context matches
            )
            for product in all_products
        ]
        scored_products.sort(key=lambda x: x[1], reverse=True)

        # Clean up internal fields and extract sorted products
        sorted_products = []
        for product, _score in scored_products:
            product.pop("_search_query", None)
            product.pop("_organic_bonus", None)
            product.pop("_is_context_match", None)
            sorted_products.append(product)

        # === PHASE 1: Filter by dietary requirements ===
        excluded_count = 0
        dietary_warnings: list[str] | None = None
        is_dietary_safe = True

        if allergies or dietary:
            safe_products, excluded = filter_by_dietary_requirements(
                sorted_products, allergies, dietary
            )
            excluded_count = len(excluded)

            if safe_products:
                # Use only safe products
                sorted_products = safe_products
            else:
                # === PHASE 2: Try alternative search with dietary modifiers ===
                alt_query = _get_dietary_alternative_query(ingredient_name, allergies, dietary)
                if alt_query:
                    try:
                        alt_products = api.search_products(alt_query, limit=max_alternatives + 2)
                        if alt_products:
                            # Filter the alternative results too
                            safe_alt, _ = filter_by_dietary_requirements(
                                alt_products, allergies, dietary
                            )
                            if safe_alt:
                                sorted_products = safe_alt
                                used_query = alt_query
                            else:
                                # === PHASE 3: No safe products found, warn user ===
                                is_dietary_safe = False
                                dietary_warnings = [
                                    f"No {'/'.join((allergies or []) + (dietary or []))}-safe "
                                    f"products found for '{ingredient_name}'"
                                ]
                        else:
                            is_dietary_safe = False
                            dietary_warnings = [
                                f"No {'/'.join((allergies or []) + (dietary or []))}-safe "
                                f"products found for '{ingredient_name}'"
                            ]
                    except NemligAPIError:
                        is_dietary_safe = False
                        dietary_warnings = [
                            f"No {'/'.join((allergies or []) + (dietary or []))}-safe "
                            f"products found for '{ingredient_name}'"
                        ]
                else:
                    # No alternative query available
                    is_dietary_safe = False
                    dietary_warnings = [
                        f"No {'/'.join((allergies or []) + (dietary or []))}-safe "
                        f"products found for '{ingredient_name}'"
                    ]

        # Best match is highest scored result
        best_match = sorted_products[0]
        alternatives = sorted_products[1 : max_alternatives + 1]

        # Calculate quantity using product's unit_size for accurate package count
        product_unit_size = best_match.get("unit_size")
        qty_to_buy = calculate_product_quantity(quantity, ingredient_unit, product_unit_size)

        return ProductMatch(
            ingredient_name=ingredient_name,
            product=best_match,
            quantity=qty_to_buy,
            matched=True,
            search_query=used_query,
            alternatives=alternatives,
            is_dietary_safe=is_dietary_safe,
            dietary_warnings=dietary_warnings,
            excluded_count=excluded_count,
        )

    # No products found - use fallback quantity calculation
    qty_to_buy = calculate_product_quantity(quantity, ingredient_unit, None)
    return ProductMatch(
        ingredient_name=ingredient_name,
        product=None,
        quantity=qty_to_buy,
        matched=False,
        search_query=used_query,
        alternatives=[],
    )


def match_ingredients(
    api: NemligAPI,
    scaled_ingredients: list[ScaledIngredient],
    max_alternatives: int = 3,
    *,
    prefer_organic: bool = False,
    prefer_budget: bool = False,
    smart_organic: bool = False,
    organic_price_threshold: float = 15.0,
    meal_context: str | None = None,
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> list[ProductMatch]:
    """
    Match all ingredients to products.

    Args:
        api: NemligAPI instance
        scaled_ingredients: List of scaled ingredients
        max_alternatives: Maximum alternatives per ingredient
        prefer_organic: Boost organic products in scoring
        prefer_budget: Boost cheaper products in scoring
        smart_organic: Prefer organic only if price diff < threshold
        organic_price_threshold: Max extra cost for organic (default 15 DKK)
        meal_context: Optional meal context for context-aware matching
        allergies: List of allergen types to avoid (e.g., ["lactose", "gluten"])
        dietary: List of dietary restrictions (e.g., ["vegan", "vegetarian"])

    Returns:
        List of ProductMatch objects
    """
    matches = []

    for ingredient in scaled_ingredients:
        match = match_ingredient(
            api,
            ingredient.name,
            ingredient.scaled_quantity,
            ingredient.unit,
            max_alternatives,
            prefer_organic=prefer_organic,
            prefer_budget=prefer_budget,
            smart_organic=smart_organic,
            organic_price_threshold=organic_price_threshold,
            meal_context=meal_context,
            allergies=allergies,
            dietary=dietary,
        )
        matches.append(match)

    return matches


def select_alternative(match: ProductMatch, index: int) -> ProductMatch:
    """
    Replace the main product with an alternative.

    Args:
        match: The ProductMatch to modify
        index: Index of alternative to select (0-based)

    Returns:
        New ProductMatch with alternative as main product
    """
    if not match.alternatives or index >= len(match.alternatives):
        return match

    new_product = match.alternatives[index]
    new_alternatives = [match.product] if match.product else []
    new_alternatives.extend(alt for i, alt in enumerate(match.alternatives) if i != index)

    return ProductMatch(
        ingredient_name=match.ingredient_name,
        product=new_product,
        quantity=match.quantity,
        matched=True,
        search_query=match.search_query,
        alternatives=new_alternatives,
    )


def calculate_total_cost(matches: list[ProductMatch]) -> float:
    """
    Calculate total cost of all matched products.

    Args:
        matches: List of product matches

    Returns:
        Total cost in DKK
    """
    total = 0.0

    for match in matches:
        if match.matched and match.price:
            total += match.price * match.quantity

    return total


def get_unmatched_ingredients(matches: list[ProductMatch]) -> list[str]:
    """
    Get list of ingredients that couldn't be matched.

    Args:
        matches: List of product matches

    Returns:
        List of unmatched ingredient names
    """
    return [m.ingredient_name for m in matches if not m.matched]


def prepare_cart_items(matches: list[ProductMatch]) -> list[dict[str, Any]]:
    """
    Prepare matched products for adding to cart.

    Args:
        matches: List of product matches

    Returns:
        List of dicts with product_id and quantity
    """
    items = []

    for match in matches:
        if match.matched and match.product_id:
            items.append({"product_id": match.product_id, "quantity": match.quantity})

    return items
