"""Tests for the food tiles in the monthly "What you had" section."""

import unittest

from views.monthly_view import FoodGallery


def food(kind="neutral", source="rule", image_url=None):
    return {
        "name": "Whey <protein>",
        "count": 12,
        "days": 1,
        "totals": {"calories": 1440, "protein_g": 300, "carbs_g": 36, "fat_g": 18, "added_sugar_g": 2.4},
        "protein_share": 0.83,
        "verdict": {"kind": kind, "source": source},
        "image_url": image_url,
    }


class FoodGalleryTests(unittest.TestCase):
    def test_tile_shows_the_four_macro_chips(self):
        html = FoodGallery.tile_html(food())
        for chip in ("Protein<b>300 g", "Carbs<b>36 g", "Fat<b>18 g", "Sugar<b>2 g"):
            self.assertIn(chip, html)
        self.assertIn("1 day · 1,440 kcal", html)
        self.assertIn("Whey &lt;protein&gt;", html)

    def test_verdict_tints_the_tile_and_labels_overrides(self):
        html = FoodGallery.tile_html(food("avoid", "override"))
        self.assertIn('class="food-tile avoid"', html)
        self.assertIn("Avoid (your rating)", html)
        self.assertNotIn("food-tile-verdict", FoodGallery.tile_html(food()))

    def test_food_without_a_photo_gets_an_icon_tile(self):
        self.assertIn("food-tile-empty", FoodGallery.tile_html(food()))
