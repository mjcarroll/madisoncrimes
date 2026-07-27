from madisoncrimes.build import canon_location, case_key, display_location


def test_case_key():
    assert case_key("B11-000726") == ("B", 2011, 726)
    assert case_key("18-000057") == ("#", 2018, 57)
    assert case_key("26M003276") == ("M", 2026, 3276)
    assert case_key("garbage") is None


def test_canon_location_merges_eras():
    assert canon_location("8000 Block of Madison Blvd") == canon_location(
        "8000 Block of MADISON BLVD MAD"
    )
    assert canon_location("100 Block of Liberty Dr Madison") == canon_location(
        "100 Block of LIBERTY DR"
    )
    # Huntsville stays distinct from the Madison default
    assert canon_location("9000 Block of MADISON BLVD HSV") != canon_location(
        "9000 Block of MADISON BLVD"
    )


def test_display_location():
    assert display_location("8000 Block of MADISON BLVD MAD") == "8000 Block of Madison Blvd"
    assert display_location("100 Block of Hughes Rd Madison") == "100 Block of Hughes Rd"
