from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape

from bs4 import BeautifulSoup

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_DATE = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    r")\.?\s+(\d{1,2}),\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"\$(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2})")
_ORDER_ID = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
_ASIN_HREF = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)")
_QTY = re.compile(r"\bQty:\s*(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class HistoryOrder:
    order_id: str
    purchased_on: str | None


@dataclass(frozen=True)
class HistoryPage:
    orders: list[HistoryOrder]
    next_path: str | None


@dataclass(frozen=True)
class ParsedItem:
    order_id: str | None
    purchased_on: str | None
    asin: str | None
    title: str | None
    quantity: int | None
    price_paid_cents: int | None
    seller_name: str | None
    fulfilled_by: str | None
    condition: str | None
    delivered_on: str | None
    return_eligible: bool | None
    return_window_end: str | None
    product_url: str | None


@dataclass(frozen=True)
class ProductOffer:
    title: str | None
    price_cents: int | None
    unavailable: bool


def parse_usd_cents(text: str) -> int | None:
    match = _MONEY.search(text.replace("\xa0", " "))
    if match is None:
        return None
    return int(match.group(1).replace(",", "")) * 100 + int(match.group(2))


def parse_human_date(text: str) -> str | None:
    match = _DATE.search(text)
    if match is None:
        return None
    month = _MONTHS[match.group(1).lower().rstrip(".")]
    return date(int(match.group(3)), month, int(match.group(2))).isoformat()


def _date_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    upper = text.upper()
    for label in labels:
        index = upper.find(label.upper())
        if index == -1:
            continue
        found = parse_human_date(text[index : index + 80])
        if found:
            return found
    return None


def parse_order_history(html: str) -> HistoryPage:
    soup = BeautifulSoup(html, "html.parser")
    orders: list[HistoryOrder] = []
    for card in soup.select(".order-card"):
        text = card.get_text(" ", strip=True)
        found = _ORDER_ID.search(text)
        if found is None:
            continue
        purchased = _date_after_label(text, ("ORDER PLACED", "Order placed"))
        orders.append(HistoryOrder(found.group(1), purchased))
    next_path = None
    link = soup.select_one("a.a-pagination-next")
    if link is not None and link.get("href"):
        next_path = unescape(str(link["href"]))
    return HistoryPage(orders, next_path)


def _labeled(node, selector: str, prefix: str) -> str | None:
    found = node.select_one(selector)
    if found is None:
        return None
    text = found.get_text(" ", strip=True)
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix) :].strip(" :")
    return text or None


def _return_facts(node) -> tuple[bool | None, str | None]:
    box = node.select_one(".return-window")
    if box is None:
        return None, None
    text = box.get_text(" ", strip=True)
    lowered = text.lower()
    if "not returnable" in lowered:
        return False, None
    window = parse_human_date(text)
    if window is None:
        return None, None
    return True, window


def parse_order_detail(html: str) -> list[ParsedItem]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (".displayAddress", ".pmts-instrument-box", "input"):
        for node in soup.select(selector):
            node.decompose()
    page_text = soup.get_text(" ", strip=True)
    order_match = _ORDER_ID.search(page_text)
    order_id = order_match.group(1) if order_match else None
    date_node = soup.select_one(".order-date")
    purchased = parse_human_date(date_node.get_text(" ", strip=True)) if date_node else None
    items: list[ParsedItem] = []
    for node in soup.select(".yohtmlc-item"):
        link = node.find("a", href=True)
        href = str(link["href"]) if link is not None else ""
        asin_match = _ASIN_HREF.search(href)
        raw_asin = node.get("data-asin") or (asin_match.group(1) if asin_match else None)
        asin = str(raw_asin) if raw_asin and re.fullmatch(r"[A-Z0-9]{10}", str(raw_asin)) else None
        title = link.get_text(" ", strip=True) if link is not None else None
        price_node = node.select_one(".item-price")
        price = parse_usd_cents(price_node.get_text(" ", strip=True)) if price_node else None
        quantity = None
        qty_node = node.select_one(".item-quantity")
        if qty_node is not None:
            qty_match = _QTY.search(qty_node.get_text(" ", strip=True))
            if qty_match is not None:
                quantity = int(qty_match.group(1))
        fulfilled_node = node.select_one(".fulfilled")
        fulfilled = None
        if fulfilled_node is not None:
            fulfilled = fulfilled_node.get_text(" ", strip=True).replace("Fulfilled by", "").strip(" :") or None
        delivery = node.select_one(".delivery-status")
        delivered = parse_human_date(delivery.get_text(" ", strip=True)) if delivery else None
        eligible, window = _return_facts(node)
        items.append(
            ParsedItem(
                order_id=order_id,
                purchased_on=purchased,
                asin=asin,
                title=title or None,
                quantity=quantity,
                price_paid_cents=price,
                seller_name=_labeled(node, ".seller", "Sold by:"),
                fulfilled_by=fulfilled,
                condition=_labeled(node, ".condition", "Condition:"),
                delivered_on=delivered,
                return_eligible=eligible,
                return_window_end=window,
                product_url=f"https://www.amazon.com/dp/{asin}" if asin else None,
            )
        )
    return items


def parse_product_price(html: str) -> ProductOffer:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("#productTitle")
    title = title_node.get_text(" ", strip=True) if title_node else None
    price_node = soup.select_one(".a-price .a-offscreen")
    price = parse_usd_cents(price_node.get_text(" ", strip=True)) if price_node else None
    unavailable = price is None and "currently unavailable" in soup.get_text(" ", strip=True).lower()
    return ProductOffer(title=title or None, price_cents=price, unavailable=unavailable)
