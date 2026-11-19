"""
scrapers.py — Part 1, Step 2: one scraper per rival café.

Each scraper is handed a Playwright `page` (an open browser tab) and returns a
list of dicts, one per menu item *and size*, all with the same keys:

    {"cafe": ..., "category": ..., "item": ..., "size": ..., "price": ...}

Every café names its drink sizes S, M and L — Lakeshore pours only S and L — and
food has one price, "Each".

The three sites are built differently on purpose, so each scraper uses a
different technique from Unit 5. Before you write one, open the café in Chrome
(settings.cafe_url) and right-click → Inspect the parts you need.

The steps are described in words. You write the code.
"""

from io import StringIO
from urllib.parse import urljoin

import pandas as pd

from .cleaning import card_rows, clean_price
from .settings import CANAL_SHOP, cafe_url


def scrape_lakeshore(page) -> list[dict]:
    """Lakeshore Lattes: section headings, each followed by a grid of menu cards.

    Returns card_rows() for every card — one row per size.

    The page, simplified:

        <h2 class="menu-section__title">Tea & More</h2>
        <p class="menu-section__note">Swap in oat milk for 60¢.</p>
        <div class="menu-grid">
            <article class="menu-card"> ... </article>
            ...
    """
    cafe = "Lakeshore Lattes"
    page.goto(cafe_url(cafe))
    rows = []
    for heading in page.query_selector_all("h2.menu-section__title"):
        category = heading.inner_text().strip()
        grid = heading.query_selector("~ div.menu-grid")
        for card in grid.query_selector_all("article.menu-card"):
            rows.extend(card_rows(cafe, category, card.inner_text()))
    return rows


def scrape_hilltop(page) -> list[dict]:
    """Hilltop Grind: inside `<div id="menu">`, an `<h2>` and a `<table>` per category.

    Drink tables have a column per size; food tables have one "Each" column:

        Item           Description                  S      M      L
        Drip Coffee    Our rotating single-origin…  $2.15  $2.60  $3.05

        Item           Description                  Each
        Avocado Toast  Smashed avocado, lemon…      $7.95
    """
    cafe = "Hilltop Grind"
    page.goto(cafe_url(cafe))
    categories = [h2.inner_text().strip() for h2 in page.query_selector_all("#menu h2")]
    tables = pd.read_html(StringIO(page.content()))
    rows = []
    for category, table in zip(categories, tables):
        long = table.drop(columns="Description").melt(
            id_vars="Item", var_name="size", value_name="price"
        )
        for _, r in long.dropna(subset=["price"]).iterrows():
            rows.append(
                {
                    "cafe": cafe,
                    "category": category,
                    "item": r["Item"],
                    "size": r["size"],
                    "price": clean_price(str(r["price"])),
                }
            )
    return rows


def scrape_canal(page, shop: str = CANAL_SHOP) -> list[dict]:
    """Canal Street Coffee: an order-ahead app. The menu is not in the HTML.

    A person has to choose a shop, ask for the menu, and click "Show more" until
    every item is listed. The list shows only names — each item's sizes and
    prices are on its own page. The page's JavaScript draws all of it, slowly,
    so your code has to wait for it.
    """
    cafe = "Canal Street Coffee"
    base_url = cafe_url(cafe)
    page.goto(base_url)
    page.get_by_label("Choose your shop").select_option(shop)
    page.get_by_role("button", name="Show full menu").click()
    page.wait_for_selector("a.result-card")

    show_more = page.get_by_role("button", name="Show more")
    while show_more.is_visible():
        count = page.locator("a.result-card").count()
        show_more.click()
        page.wait_for_function(
            f"document.querySelectorAll('a.result-card').length > {count}"
        )

    links = [a.get_attribute("href") for a in page.query_selector_all("a.result-card")]

    rows = []
    for href in links:
        page.goto(urljoin(base_url, href))
        page.wait_for_selector("#sizes")
        item = page.inner_text("#item-name").strip()
        category = page.inner_text("#item-category").split(" · ")[0].strip()
        for tr in page.query_selector_all("#sizes tbody tr"):
            size_cell, price_cell = tr.query_selector_all("td")[:2]
            rows.append(
                {
                    "cafe": cafe,
                    "category": category,
                    "item": item,
                    "size": size_cell.inner_text().strip(),
                    "price": clean_price(price_cell.inner_text()),
                }
            )
    return rows
