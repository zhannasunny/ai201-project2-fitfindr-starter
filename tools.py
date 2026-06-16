"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # 1. Load all listings
    listings = load_listings()

    # 2. Filter by max_price and size (if provided)
    candidates = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        candidates.append(listing)

    # 3. Score each remaining listing by keyword overlap with `description`
    keywords = set(description.lower().split())

    def score(listing: dict) -> int:
        tags_expanded = " ".join(
            word for tag in listing.get("style_tags", []) for word in tag.split()
        )
        searchable = " ".join([
            listing.get("title", "") or "",
            listing.get("description", "") or "",
            listing.get("category", "") or "",
            listing.get("brand", "") or "",
            tags_expanded,
            " ".join(listing.get("colors", [])),
            listing.get("condition", "") or "",
        ]).lower()
        tokens = set(searchable.split())
        base_score = len(keywords & tokens)

        # Bonus: extra point for each keyword that appears in the title
        title_tokens = set((listing.get("title", "") or "").lower().split())
        title_bonus = len(keywords & title_tokens)

        return base_score + title_bonus

    scored = [(score(listing), listing) for listing in candidates]

    # 4. Drop listings with a score of 0
    scored = [(s, item) for s, item in scored if s > 0]

    # 5. Sort by score descending and return listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    item_summary = (
        f"{new_item.get('title', 'item')} — "
        f"{new_item.get('description', '')} "
        f"(style tags: {', '.join(new_item.get('style_tags', []))}; "
        f"colors: {', '.join(new_item.get('colors', []))})"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        # Empty wardrobe — ask for general styling advice
        prompt = (
            f"I just thrifted this item: {item_summary}\n\n"
            f"I don't have any other clothes to pair it with yet. "
            f"Suggest 1-2 complete outfits from scratch that would work well "
            f"with this piece. Be specific about what types of items, colors, "
            f"and shoes would complement it. Keep it casual and practical."
        )
    else:
        # Format wardrobe items into a readable list
        wardrobe_summary = "\n".join(
            f"- {w.get('name', 'item')} ({w.get('color', '')})"
            for w in wardrobe_items
        )
        prompt = (
            f"I just thrifted this item: {item_summary}\n\n"
            f"Here's what I already own:\n{wardrobe_summary}\n\n"
            f"Suggest 1-2 complete outfit combinations using the thrifted item "
            f"paired with specific pieces from my wardrobe. Only use items from "
            f"the wardrobe list above — don't invent new pieces. "
            f"Be specific and keep the suggestions practical."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )

    result = response.choices[0].message.content.strip()
    return result if result else f"Try pairing this {new_item.get('title', 'item')} with neutral basics."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Replace this with your implementation
    return ""
