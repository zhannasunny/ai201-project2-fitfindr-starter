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
    # Step 1: guard against empty outfit string
    if not outfit or not outfit.strip():
        title = new_item.get("title", "this piece")
        return f"I just thrifted this {title} - I am obsessed!!"

    client = _get_groq_client()

    title    = new_item.get("title", "thrifted item")
    price    = new_item.get("price", "")
    platform = new_item.get("platform", "")

    prompt = (
        f"Write a 2-4 sentence Instagram caption for this thrifted outfit.\n\n"
        f"Thrifted item: {title}\n"
        f"Price: ${price}\n"
        f"Platform: {platform}\n"
        f"Outfit: {outfit}\n\n"
        f"The caption should:\n"
        f"- Sound casual and authentic, like a real person posting an OOTD\n"
        f"- Mention the item name, price, and platform once each, naturally\n"
        f"- Capture the specific vibe of the outfit (not generic)\n"
        f"- NOT sound like a product description or an ad\n"
        f"- Be 2-4 sentences only, no hashtags"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=1.4,   # higher = more variation between runs
    )

    result = response.choices[0].message.content.strip()
    return result if result else f"I just thrifted this {title} - I am obsessed!!"
