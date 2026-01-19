"""Nemlig Shopper - Recipe-to-Cart CLI Tool for Nemlig.com."""

__version__ = "1.0.0"

from .api import NemligAPI, NemligAPIError
from .matcher import ProductMatch, match_ingredients
from .recipe_parser import Ingredient, Recipe, parse_recipe_text, parse_recipe_url
from .scaler import ScaledIngredient, scale_recipe

__all__ = [
    "NemligAPI",
    "NemligAPIError",
    "Recipe",
    "Ingredient",
    "parse_recipe_url",
    "parse_recipe_text",
    "scale_recipe",
    "ScaledIngredient",
    "match_ingredients",
    "ProductMatch",
]
