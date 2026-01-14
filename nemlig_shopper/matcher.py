"""Ingredient to product matching logic."""

from dataclasses import dataclass
from typing import Any

from .api import NemligAPI, NemligAPIError
from .preferences import is_preferred_product
from .scaler import ScaledIngredient, calculate_product_quantity

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
    # Dairy
    "milk": "mælk",
    "butter": "smør",
    "cheese": "ost",
    "cream": "fløde",
    "egg": "æg",
    "eggs": "æg",
    "yogurt": "yoghurt",
    "sour cream": "creme fraiche",
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


@dataclass
class ProductMatch:
    """A matched product for an ingredient."""

    ingredient_name: str
    product: dict[str, Any] | None
    quantity: int
    matched: bool
    search_query: str
    alternatives: list[dict[str, Any]]

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


def score_product_match(product: dict[str, Any], ingredient_name: str, search_query: str) -> int:
    """
    Score a product match based on relevance to the ingredient.

    Higher scores indicate better matches. Products that the user has
    previously purchased receive a boost to prefer familiar items.

    Args:
        product: Product dict from API
        ingredient_name: Original ingredient name
        search_query: The query used to find this product

    Returns:
        Integer score (higher is better)
    """
    score = 0
    product_name = product.get("name", "").lower()
    category = product.get("category", "")
    ingredient_lower = ingredient_name.lower()
    query_lower = search_query.lower()

    # Boost products the user has purchased before
    product_id = product.get("id")
    if product_id and is_preferred_product(product_id):
        score += 75

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

    # Boost for each word of the ingredient that appears in product name
    ingredient_words = set(ingredient_lower.split())
    for word in ingredient_words:
        if len(word) > 2 and word in product_name:
            score += 30

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
    flavor_indicators = ["&", " m. ", " med ", " smag "]
    for flavor_indicator in flavor_indicators:
        if flavor_indicator in product_name:
            before, after = product_name.split(flavor_indicator, 1)
            if any(word in after for word in ingredient_words):
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


def generate_search_queries(ingredient_name: str) -> list[str]:
    """
    Generate multiple search queries for an ingredient.

    Prioritizes Danish translations for better results on Nemlig.com.

    Args:
        ingredient_name: The ingredient name

    Returns:
        List of search queries to try, in order of preference
    """
    queries = []

    # Try Danish translation first (most likely to get good results)
    danish = translate_ingredient(ingredient_name)
    if danish:
        queries.append(danish)

    # Original name (cleaned)
    cleaned = clean_ingredient_name(ingredient_name)
    if cleaned and cleaned not in queries:
        queries.append(cleaned)

    # Original name as-is if different from cleaned
    if ingredient_name.lower() != cleaned and ingredient_name.lower() not in queries:
        queries.append(ingredient_name.lower())

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


def match_ingredient(
    api: NemligAPI, ingredient_name: str, quantity: float | None = None, max_alternatives: int = 3
) -> ProductMatch:
    """
    Find matching products for a single ingredient.

    Uses smart scoring to find the best match, prioritizing:
    - Danish translations of English ingredients
    - Food categories over non-food categories
    - Products where the ingredient name appears in the product name

    Args:
        api: NemligAPI instance
        ingredient_name: Name of ingredient to match
        quantity: Scaled quantity needed
        max_alternatives: Maximum alternative products to return

    Returns:
        ProductMatch with best match and alternatives
    """
    queries = generate_search_queries(ingredient_name)
    all_products: list[dict[str, Any]] = []
    used_query = queries[0] if queries else ingredient_name

    # Collect products from multiple queries for better selection
    seen_ids: set[int] = set()
    for query in queries:
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
                        all_products.append(product)
                if not used_query or used_query == ingredient_name:
                    used_query = query
        except NemligAPIError:
            continue

    # Calculate quantity to buy
    qty_to_buy = calculate_product_quantity(quantity)

    if all_products:
        # Score and sort products by relevance
        scored_products = [
            (
                product,
                score_product_match(
                    product, ingredient_name, product.get("_search_query", used_query)
                ),
            )
            for product in all_products
        ]
        scored_products.sort(key=lambda x: x[1], reverse=True)

        # Clean up the internal field and extract sorted products
        sorted_products = []
        for product, _score in scored_products:
            product.pop("_search_query", None)
            sorted_products.append(product)

        # Best match is highest scored result
        best_match = sorted_products[0]
        alternatives = sorted_products[1 : max_alternatives + 1]

        return ProductMatch(
            ingredient_name=ingredient_name,
            product=best_match,
            quantity=qty_to_buy,
            matched=True,
            search_query=used_query,
            alternatives=alternatives,
        )

    return ProductMatch(
        ingredient_name=ingredient_name,
        product=None,
        quantity=qty_to_buy,
        matched=False,
        search_query=used_query,
        alternatives=[],
    )


def match_ingredients(
    api: NemligAPI, scaled_ingredients: list[ScaledIngredient], max_alternatives: int = 3
) -> list[ProductMatch]:
    """
    Match all ingredients to products.

    Args:
        api: NemligAPI instance
        scaled_ingredients: List of scaled ingredients
        max_alternatives: Maximum alternatives per ingredient

    Returns:
        List of ProductMatch objects
    """
    matches = []

    for ingredient in scaled_ingredients:
        match = match_ingredient(api, ingredient.name, ingredient.scaled_quantity, max_alternatives)
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
