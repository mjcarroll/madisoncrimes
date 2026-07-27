from madisoncrimes.categorize import categorize, split_degree
from madisoncrimes.geocode import in_bounds, to_query


def test_curated_mapping():
    assert categorize("DOMESTIC VIOLENCE 3") == ("DOMESTIC VIOLENCE", 3)
    assert categorize("BURGLARY 3") == ("BURGLARY", 3)


def test_rule_fallbacks():
    assert categorize("POSSESSION OF MARIJUANA 2") == ("DRUGS", 2)
    assert categorize("DRIVING UNDER THE INFLUENCE MISDEMEANOR (ALCOHOL)")[0] == (
        "DRIVING UNDER INFLUENCE"
    )
    assert categorize("FAILURE TO APPEAR TRAFFIC")[0] == "FAILURE TO APPEAR"
    assert categorize("THEFT OF PROPERTY 4 MISCELLANEOUS ($500 OR LESS)")[0] == "THEFT"


def test_split_degree():
    assert split_degree("THEFT 4 DEGREE") == ("THEFT", 4)
    assert split_degree("BAIL JUMPING SECOND DEGREE") == ("BAIL JUMPING", 2)
    assert split_degree("HARASSMENT") == ("HARASSMENT", None)


def test_to_query():
    assert to_query("100 Block of Westscott Dr") == "100 Westscott Dr, Madison, AL"
    assert to_query("8000 Block of MADISON BLVD MAD") == "8000 MADISON BLVD, Madison, AL"
    assert to_query("9000 Block of MADISON BLVD HSV") == "9000 MADISON BLVD, Huntsville, AL"
    assert to_query("Walmart Super Center #2690, 8650 Madison Blvd") == (
        "8650 Madison Blvd, Madison, AL"
    )
    assert to_query("Liberty Dr / Wall Triana Hwy, Madison, Al") is None
    assert to_query("i565 mm 10") is None
    assert to_query("#Error") is None


def test_in_bounds():
    assert in_bounds(34.70, -86.75)
    assert not in_bounds(33.5, -86.75)
