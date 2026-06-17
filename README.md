# FitFindr

FitFindr is a multi-tool AI agent that helps you find secondhand clothing and figure out how to wear it. You describe what you're looking for in plain English, and the agent searches a dataset of thrifted listings, suggests outfit combinations based on your wardrobe, and generates a shareable fit card caption — all in one interaction.

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's query.

**Inputs:**
- `description` (str): Keywords describing the item (e.g. "vintage graphic tee")
- `size` (str or None): Clothing size to filter by, case-insensitive. `None` skips size filtering.
- `max_price` (float or None): Maximum price inclusive. `None` skips price filtering.

**Returns:** A list of listing dicts sorted by relevance (keyword overlap score, with title matches weighted higher). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — does not raise an exception.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given a thrifted item and the user's existing wardrobe, suggests 1–2 complete outfit combinations.

**Inputs:**
- `new_item` (dict): A listing dict returned by `search_listings`
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty.

**Returns:** A non-empty string with outfit suggestions. If the wardrobe is empty, returns general styling advice from scratch rather than referencing owned pieces.

---

### `create_fit_card(outfit, new_item, wardrobe_empty)`

**Purpose:** Generates a short, casual Instagram-style caption for the thrifted outfit.

**Inputs:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict): The listing dict for the thrifted item
- `wardrobe_empty` (bool): If `True`, the caption uses language like "would look great with" instead of "I paired it with my" — since the user doesn't own the suggested pieces

**Returns:** A 2–4 sentence string suitable for an Instagram or TikTok caption. Mentions the item name, price, and platform once each. Returns a generic fallback string if `outfit` is empty — does not raise an exception.

---

## Planning Loop

The agent uses a conditional planning loop in `run_agent()` that decides what to do based on what each tool returns — it does not call all three tools unconditionally.

**Step 1 — Parse the query:** The agent sends the user's natural language query to the LLM and extracts three parameters: `description`, `size`, and `max_price`. The LLM returns a JSON object. If parsing fails, the whole query is used as the description and size/price filters are skipped.

**Step 2 — Search listings:** `search_listings()` is called with the parsed parameters. The agent then checks: if the result list is empty, it sets `session["error"]` to a specific message telling the user what failed and what to adjust, then returns early. `suggest_outfit` and `create_fit_card` are never called with empty input.

**Step 3 — Suggest outfit (only if results found):** The top result from `search_listings` is passed into `suggest_outfit` along with the user's wardrobe. This only runs if Step 2 returned at least one result.

**Step 4 — Create fit card (only if outfit generated):** The outfit suggestion string is passed into `create_fit_card`. The `wardrobe_empty` flag is set based on whether the user's wardrobe has items, so the caption tone adjusts accordingly.

**What happens when search returns nothing:** The agent sets a specific error message — for example: "No listings found for 'designer ballgown' in size XXS under $5.0. Try adjusting your size or price." — and returns immediately. The outfit and fit card fields in the session remain `None`.

---

## State Management

All state is stored in a single session dict initialized at the start of each interaction:

```python
session = {
    "query": query,           # original user input
    "parsed": {},             # extracted description, size, max_price
    "search_results": [],     # all matching listings
    "selected_item": None,    # top result — passed into suggest_outfit
    "wardrobe": wardrobe,     # user's wardrobe — passed into suggest_outfit
    "outfit_suggestion": None,# suggest_outfit output — passed into create_fit_card
    "fit_card": None,         # final caption
    "error": None,            # set on early termination
}
```

Each tool writes its output to the session, and the next tool reads from it — the user never re-enters information between steps. Specifically:
- `search_listings` → writes to `session["search_results"]`, top result stored in `session["selected_item"]`
- `suggest_outfit` reads `session["selected_item"]` and `session["wardrobe"]` → writes to `session["outfit_suggestion"]`
- `create_fit_card` reads `session["outfit_suggestion"]` and `session["selected_item"]` → writes to `session["fit_card"]`

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query | Sets `session["error"]` with a specific message naming what failed (description, size, price) and telling the user what to adjust. Returns early — `suggest_outfit` is never called. |
| `suggest_outfit` | Wardrobe is empty | Calls the LLM with a prompt for general styling advice from scratch. Returns a non-empty string — never crashes or returns an empty string. |
| `create_fit_card` | `outfit` string is empty or whitespace | Returns a generic fallback: `"just thrifted this {title} - love it! 🛍️"` — does not raise an exception. |

**Concrete example from testing:**

Running the agent with query `"designer ballgown size XXS under $5"` and example wardrobe returns:

```
Error: No listings found for 'designer ballgown' in size XXS under $5.0. Try adjusting your size or price.
```

`session["fit_card"]` is `None` — the agent stopped after `search_listings` returned an empty list.

---

## Spec Reflection

**One thing the spec helped with:** Writing out the planning loop conditions in `planning.md` before coding made it straightforward to implement the early-return branch in `run_agent()`. Having the exact conditional logic written out ("if results is empty, set error and return") meant there was no ambiguity when translating it to code.

**One divergence from the spec:** The original planning.md said to ask the user which outfit suggestion they want before generating the fit card. In the Gradio interface, this isn't possible, as Gradio is a single input → output flow with no mid-interaction prompts. Instead, the full outfit suggestion string is passed directly into `create_fit_card`, and the LLM synthesizes it into a caption. This produces good results and keeps the UI simple.

---

## AI Usage

**Instance 1 — `search_listings` implementation:**
I gave Claude the Tool 1 spec from `planning.md` (inputs, return value, failure mode) and asked it to implement `search_listings()` using `load_listings()` from the data loader. The generated code had the right structure but built the searchable string using `item.get("brand", "")` which returned `None` for listings with a null brand field, causing a `TypeError`. I caught this by running the function and reading the traceback, then added `or ""` to every `.get()` call to handle null fields. I also identified that style tags like `"graphic tee"` were being treated as single tokens, so I added a tag-splitting step and a title bonus to improve relevance ordering — neither of which was in the generated code.

**Instance 2 — `run_agent()` planning loop:**
I gave Claude the Planning Loop and State Management sections from `planning.md` along with the architecture diagram and asked it to implement `run_agent()`. The generated code matched the spec well — it branched on the `search_listings` result and stored values in the session dict correctly. I added `_parse_query()` as a separate function (the generated code had parsing inlined), and I verified the early-return branch by running the no-results test case (`"designer ballgown size XXS under $5"`) and confirming `session["fit_card"]` was `None` and `session["error"]` contained a specific, actionable message.