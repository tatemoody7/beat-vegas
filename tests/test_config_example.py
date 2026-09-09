"""config.example.yaml IS the production Odds API config: the GitHub Actions jobs
have no config.yaml, so a stray edit here silently drops Hard Rock (us2) or
switches the 1H market — or breaks the ten-book list that makes every per-event
1H call cost 1 credit instead of 2. Pin the values prod relies on."""

from pathlib import Path

import yaml

from beatvegas.hardrock import HR_BOOK_KEY, normalize_book
from beatvegas.sources.odds import MAX_BOOKMAKERS_ONE_REGION

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _odds_api():
    return yaml.safe_load(EXAMPLE.read_text())["odds_api"]


def test_regions_include_us2_for_hard_rock():
    regions = [r.strip() for r in _odds_api()["regions"].split(",")]
    assert "us2" in regions


def test_market_is_first_half_totals():
    assert _odds_api()["markets"] == "totals_h1"


def test_bookmakers_1h_is_exactly_ten_distinct_keys():
    """Ten is the billing boundary: <= 10 named books cost one region (1 credit
    per event), an 11th costs two. Fewer than ten is money left on the table,
    so pin the intent in both directions."""
    books = _odds_api()["bookmakers_1h"]
    assert len(books) == MAX_BOOKMAKERS_ONE_REGION
    assert len(set(books)) == len(books), "duplicate key wastes a paid slot"


def test_hard_rock_is_in_the_list():
    """Without it every card reads "no Hard Rock line" — the only bettable book
    from Florida — and nothing else about the run would look wrong."""
    assert HR_BOOK_KEY in _odds_api()["bookmakers_1h"]


def test_every_requested_key_is_the_key_we_store():
    """normalize_book runs on the way into odds_snapshots. If a requested key
    normalizes to something else, we would pay for a book and then fail to find
    its rows again."""
    for key in _odds_api()["bookmakers_1h"]:
        assert normalize_book(key) == key, key


def test_enough_books_survive_the_fair_price_exclusions():
    """card.py builds the market's no-vig fair price from the median over the
    comparable books, dropping Hard Rock itself, the sweepstakes book and the
    exchanges. If too few of the ten survive, every game falls to
    `no_fair_price` and the price gate can never be judged."""
    from beatvegas import card

    surviving = [b for b in _odds_api()["bookmakers_1h"] if b not in card.FAIR_PRICE_EXCLUDED]
    assert len(surviving) >= 3, surviving
