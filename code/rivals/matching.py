"""
matching.py — Part 2: which of their items are ours?

Lakeshore calls it a "Caffe Mocha", Hilltop a "Mocha Cappuccino", Canal Street a
"Mochaccino", and we call it a "Mocha Latte". Before anyone can compare prices,
every rival item needs one name — ours when it is something we sell, its own
when it is not.

No score can do that alone. Fuzzy matching scores how alike two *strings* are, not
whether two *drinks* are the same: "Matcha Latte" scores 87 against "Mocha Latte"
and is a different drink; "PSL" scores 0 against "Pumpkin Spice Latte" and is the
same one. So the code proposes and the owner decides:

- a score of settings.AUTO_MATCH or more is matched automatically;
- anything lower waits for the owner, who sees the top suggestions on the Review
  page and picks one, or says it is a new item;
- the owner's decisions are saved (data/item_matches.csv) and win every time,
  so next month's scrape does not ask the same questions again.

The steps are described in words. You write the code.
"""

import re
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process

from .settings import (
    AUTO_MATCH,
    DECISION_COLUMNS,
    FILLER_WORDS,
    NEW_ITEM,
    OUR_CAFE,
    REVIEW,
)


def normalize_name(name: str) -> str:
    """A menu name reduced to the words that tell items apart.

        normalize_name("Caffè Americano")    ->  "americano"
        normalize_name("Cold-Brew Coffee")   ->  "cold brew"
        normalize_name("Bagel w/ Cream Cheese") -> "bagel cream cheese"
    """
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    words = [w for w in text.split() if w not in FILLER_WORDS]
    return " ".join(words)


def top_candidates(name: str, choices: list[str], limit: int = 3) -> list[tuple]:
    """The `limit` choices most like `name`, best first, as (choice, score) pairs.

        top_candidates("Americano, Iced", ["Americano", "Iced Americano", "Latte"])
        -> [("Iced Americano", 100), ("Americano", 78), ("Latte", 24)]

    Scores are whole numbers 0–100 from rapidfuzz's `fuzz.token_sort_ratio`, which
    ignores word order ("Croissant, Almond" = "Almond Croissant"). Both sides are
    compared *normalized*, but the pairs hold the original choice names. No
    choices gives an empty list.
    """
    normalized_choices = [normalize_name(c) for c in choices]
    found = process.extract(
        normalize_name(name),
        normalized_choices,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
    )
    return [(choices[index], round(score)) for _, score, index in found]


def match_band(score: float) -> str:
    """How sure a score is: "auto" at settings.AUTO_MATCH or more, "review" at
    settings.REVIEW or more, otherwise "unlikely".

    The Review page preselects the top suggestion for "review" and NEW_ITEM for
    "unlikely"; "auto" never reaches the owner.
    """
    if score >= AUTO_MATCH:
        return "auto"
    if score >= REVIEW:
        return "review"
    return "unlikely"


def match_items(menus: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """One row per rival item: what it is called on our list, and who decided.

    `menus` is the dataset from build_dataset; `decisions` is data/item_matches.csv
    (columns `cafe`, `item`, `matched_to`). Returns, one row per distinct
    (`cafe`, `item`) that is not ours, in the order they first appear in `menus`:

        cafe  item  kind  status  matched_to  score  suggestions

    - `suggestions`: top_candidates(item, the names on the list so far of the same
      `kind`) — a list of (name, score) pairs. `score` is the first pair's score
      (0 when there are no suggestions).
    - `status` and `matched_to`:
        - "owner" when the owner has decided this (cafe, item): `matched_to` is
          their answer — or the item's own name when they answered NEW_ITEM.
        - otherwise "auto" when `score` is AUTO_MATCH or more: the top suggestion.
        - otherwise "unreviewed", and `matched_to` is None.

    "The list" starts as our own item names (with their kinds) and grows: an item
    that ends up matched to a name not yet on the list adds it. Unreviewed items
    add nothing.
    """
    ours = menus[menus["cafe"] == OUR_CAFE]
    pool = dict(zip(ours["item"], ours["kind"]))

    answers = {}
    for row in decisions.to_dict("records"):
        answers[(row["cafe"], row["item"])] = row["matched_to"]

    theirs = menus[menus["cafe"] != OUR_CAFE]
    rivals = theirs[["cafe", "item", "kind"]].drop_duplicates()

    rows = []
    for cafe, item, kind in rivals.itertuples(index=False):
        choices = [name for name, k in pool.items() if k == kind]
        suggestions = top_candidates(item, choices)
        score = suggestions[0][1] if suggestions else 0

        if (cafe, item) in answers:
            status = "owner"
            answer = answers[(cafe, item)]
            matched_to = item if answer == NEW_ITEM else answer
        elif score >= AUTO_MATCH:
            status = "auto"
            matched_to = suggestions[0][0]
        else:
            status = "unreviewed"
            matched_to = None

        if matched_to is not None and matched_to not in pool:
            pool[matched_to] = kind

        rows.append(
            {
                "cafe": cafe,
                "item": item,
                "kind": kind,
                "status": status,
                "matched_to": matched_to,
                "score": score,
                "suggestions": suggestions,
            }
        )

    columns = ["cafe", "item", "kind", "status", "matched_to", "score", "suggestions"]
    return pd.DataFrame(rows, columns=columns)


def record_decision(decisions: pd.DataFrame, cafe: str, item: str,
                    matched_to: str) -> pd.DataFrame:
    """`decisions` with the owner's answer for (cafe, item) — replacing any earlier
    answer for the same item, never duplicating it.

    Returns a new DataFrame with columns settings.DECISION_COLUMNS (`cafe`, `item`,
    `matched_to`), the new answer last, plain index. `decisions` is not changed.
    """
    new_row = pd.DataFrame([[cafe, item, matched_to]], columns=DECISION_COLUMNS)
    is_this_item = (decisions["cafe"] == cafe) & (decisions["item"] == item)
    kept = decisions[~is_this_item]
    if kept.empty:
        return new_row
    return pd.concat([kept[DECISION_COLUMNS], new_row], ignore_index=True)
