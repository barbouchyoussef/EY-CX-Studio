"""Covers the Google Maps location filter.

The regression that motivated this: a scrape for 'Mytek' (a Tunisian electronics retailer)
returned 236 reviews from ten same-named businesses in the US, Canada, Guatemala and Mexico
-- an IT firm in Phoenix, a tool wholesaler, appliance repairers -- and none from Tunisia.
The report then opened with "86.7% positive, 4.48/5", describing other companies entirely.

Name matching cannot fix this: every one of those places legitimately contains "mytek".
Geography is the only discriminator.
"""

from __future__ import annotations

import pytest

from app.services.scraping.scraping_service import _location_matches


def _place(**kwargs) -> dict:
    base = {"title": "X", "countryCode": None, "address": None, "city": None,
            "state": None, "neighborhood": None, "street": None}
    base.update(kwargs)
    return base


# The real contaminating places from the Mytek run.
_PHOENIX = _place(title="MyTek | IT Services & IT Support Company | Phoenix",
                  countryCode="US", city="Scottsdale",
                  address="7500 N Dobson Rd Ste 100, Scottsdale, AZ 85256")
_MEXICO = _place(title="Mytek Cedis Ciudad de México", countryCode="MX", city="Tijuana",
                 address="Av. Cochimies 18480, 22216 Tijuana, B.C., Mexique")
_GUATEMALA = _place(title="MYTEK LAB", countryCode="GT", city="Guatemala City",
                    address="13 Calle 1-89, Cdad. de Guatemala 01009, Guatemala")
_CANADA = _place(title="MYTEK TOOLS & SUPPLIES", countryCode="CA", city="Navan",
                 address="5425 Boundary Rd, Navan, ON K0A 3H0, Canada")
_TUNIS = _place(title="Mytek Lac 2", countryCode="TN", city="Tunis",
                address="Rue du Lac, Tunis 1053, Tunisie")


def test_the_real_contamination_is_rejected():
    for place in (_PHOENIX, _MEXICO, _GUATEMALA, _CANADA):
        assert not _location_matches(place, "Tunisie"), place["title"]


def test_the_genuine_place_is_kept():
    assert _location_matches(_TUNIS, "Tunisie")


def test_the_english_spelling_also_matches():
    assert _location_matches(_TUNIS, "Tunisia")


def test_a_city_matches_its_country_code():
    """A consultant may type the city rather than the country."""
    assert _location_matches(_TUNIS, "Tunis")


def test_matching_is_case_and_accent_insensitive():
    assert _location_matches(_TUNIS, "TUNISIE")
    assert _location_matches(_TUNIS, "tunisie")
    assert _location_matches(_MEXICO, "mexique")


def test_an_empty_location_keeps_everything():
    """No filter requested means no filtering -- the caller warns instead."""
    for place in (_PHOENIX, _TUNIS):
        assert _location_matches(place, "")
        assert _location_matches(place, "   ")


def test_a_place_with_no_geodata_is_matched_on_address_text():
    unknown = _place(title="Mytek", address="Avenue Habib Bourguiba, Tunisie")
    assert _location_matches(unknown, "Tunisie")


def test_a_place_with_no_geodata_at_all_is_excluded():
    """23 of the Mytek items carried no location fields; they must not slip through."""
    blank = _place(title="Mytek")
    assert not _location_matches(blank, "Tunisie")


@pytest.mark.parametrize(
    "location,expected_title",
    [("United States", "MyTek | IT Services & IT Support Company | Phoenix"),
     ("Mexique", "Mytek Cedis Ciudad de México"),
     ("Canada", "MYTEK TOOLS & SUPPLIES")],
)
def test_the_filter_works_for_any_country_not_just_tunisia(location, expected_title):
    places = [_PHOENIX, _MEXICO, _GUATEMALA, _CANADA, _TUNIS]
    kept = [p for p in places if _location_matches(p, location)]
    assert [p["title"] for p in kept] == [expected_title]


def test_a_location_that_also_contains_the_brand_still_works():
    """Consultants type "Mytek Tunisie" into the location box; requiring the whole string
    to match rejected every genuine place and returned an empty scrape."""
    assert _location_matches(_TUNIS, "mytek tunisie")
    assert not _location_matches(_PHOENIX, "mytek tunisie")


def test_a_city_and_country_pair_matches():
    assert _location_matches(_TUNIS, "Tunis, Tunisia")
    assert _location_matches(_PHOENIX, "Scottsdale, United States")


def test_noise_only_locations_do_not_match_everything():
    """A location with no usable token must not silently disable the filter."""
    assert not _location_matches(_PHOENIX, "mytek")
