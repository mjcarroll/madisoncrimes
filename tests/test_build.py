from madisoncrimes.build import canon_location, display_location


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
