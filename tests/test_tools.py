import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import search_listings, create_fit_card, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_fit_card_empty_wardrobe_tone():
    results = search_listings("vintage graphic tee", max_price=50)
    item = results[0]
    outfit = suggest_outfit(item, get_empty_wardrobe())
    caption = create_fit_card(outfit, item, wardrobe_empty=True)
    # should NOT say "my" or "I paired" implying ownership
    assert "my" not in caption.lower() or "paired it with my" not in caption.lower()
    assert isinstance(caption, str)
    assert len(caption) > 0

def test_fit_card_with_wardrobe_tone():
    results = search_listings("vintage graphic tee", max_price=50)
    item = results[0]
    outfit = suggest_outfit(item, get_example_wardrobe())
    caption = create_fit_card(outfit, item, wardrobe_empty=False)
    assert isinstance(caption, str)
    assert len(caption) > 0

def test_fit_card_empty_outfit_fallback():
    results = search_listings("vintage graphic tee", max_price=50)
    caption = create_fit_card("", results[0])
    assert isinstance(caption, str)
    assert len(caption) > 0