"""
cleaning.py — Part 1, Step 1: turn scraped text into clean values.

A scraper hands you whatever the page shows a person, and pages are written for
people. Lakeshore Lattes' menu cards are a good example — `inner_text()` on one
card gives you:

    NEW!
    Matcha Latte
    V
    S $5.05 · L $6.25
    Ceremonial-grade matcha whisked with steamed milk.

A badge, a dietary tag, two sizes and two prices crammed onto one line. These
functions turn that into rows a DataFrame can hold. They are plain Python — no
browser — so they are quick to test and quick to fix.

Every café names its drink sizes S, M and L (Lakeshore pours only S and L); food
has one price, which we call "Each".

This step is walked through line by line. The scrapers give you less help.
"""

import re

# Lines on a menu card that are decoration, not data.
NOISE = {"NEW!", "NEW", "V", "GF"}


def clean_price(text: str) -> float:
    """A price as a number: "$4.75" -> 4.75, " $1,029.00 " -> 1029.0."""
    return float(text.replace("$", "").replace(",", "").strip())


def clean_card_lines(text: str) -> list[str]:
    """The useful lines of a menu card, in order, with the decoration removed.

        clean_card_lines("NEW!\\n\\nAvocado Toast\\nV GF\\n$8.50\\nToast.")
        -> ["Avocado Toast", "$8.50", "Toast."]

    Remove: blank lines, and lines made only of NOISE words (badges like "NEW!"
    and dietary tags like "V" or "V GF").
    """
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if all(w in NOISE for w in line.split()):
            continue
        lines.append(line)
    return lines


def parse_price_line(line: str) -> list[tuple[str, float]]:
    """Every (size, price) pair on a price line.

        parse_price_line("S $5.05 · L $6.25")
        -> [("S", 5.05), ("L", 6.25)]
        parse_price_line("S $2.15 · M $2.60 · L $3.05")
        -> [("S", 2.15), ("M", 2.60), ("L", 3.05)]
        parse_price_line("$8.50")
        -> [("Each", 8.50)]

    A price with no size in front of it is "Each".
    """
    pairs = []
    for size, price in re.findall(r"([SML])?\s*(\$[\d.,]+)", line):
        pairs.append((size or "Each", clean_price(price)))
    return pairs


def card_rows(cafe: str, category: str, card_text: str) -> list[dict]:
    """One row per size for one menu card.

        card_rows("Lakeshore Lattes", "Tea & More", "NEW!\\nMatcha Latte\\nV\\n"
                  "S $5.05 · L $6.25\\nMatcha.")
        -> [{"cafe": "Lakeshore Lattes", "category": "Tea & More",
             "item": "Matcha Latte", "size": "S", "price": 5.05},
            {... "size": "L", "price": 6.25}]
    """
    lines = clean_card_lines(card_text)
    item = lines[0]
    price_line = next(line for line in lines if "$" in line)
    return [
        {"cafe": cafe, "category": category, "item": item, "size": size, "price": price}
        for size, price in parse_price_line(price_line)
    ]
