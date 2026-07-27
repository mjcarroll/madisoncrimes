from datetime import date, datetime

from madisoncrimes.parse import (
    clean_lines,
    extract_arrests,
    extract_incidents,
    normalize_incident,
    split_fields,
)

OLD_INCIDENT = """\
                                Madison Police Department
                                         Incident Report
                                       ( Mar 27, 2011 To Apr 02, 2011 )

   Case No.:   B11-000726               Time: 11:30 am                    Shift: I
Date Reported: March 27, 2011      Location: 100 Block of Westscott Dr
     Incident: BURGLARY-3RD
     Incident: THEFT 2ND DEGREE

   Case No.:   B11-000728               Time: 3:05 pm                     Shift: II
Date Reported: March 27, 2011      Location: City Of Madison, 365 Shelton Rd
     Incident: DISCHARGING FIREARM IN CITY LIMITS
"""

OLD_ARREST = """\
Madison Police Department
Arrest Report
( Jan 12, 2018 To Jan 18, 2018 )

Date

01/12/18

Arrest Information
Mica Michelle-Marie Hunt, Madison, AL was arrested at Liberty Dr / Wall Triana Hwy, Madison, Al on \
the
charge(s) of:

Arrest

18-000057

MARIJUANA-POSSESSION 2
"""


def test_extract_incidents_old_format():
    records = extract_incidents(split_fields(clean_lines(OLD_INCIDENT)))
    assert len(records) == 2
    assert records[0].case == "B11-000726"
    assert records[0].when == datetime(2011, 3, 27, 11, 30)
    assert records[0].shift == 1
    assert records[0].location == "100 Block of Westscott Dr"
    assert records[0].incidents == ["BURGLARY 3", "THEFT 2 DEGREE"]
    assert records[1].shift == 2


def test_extract_arrests_old_format_hyphenated_name():
    records = extract_arrests(clean_lines(OLD_ARREST))
    assert len(records) == 1
    assert records[0].case == "18-000057"
    assert records[0].when == date(2018, 1, 12)
    assert records[0].name == "Mica Michelle-Marie Hunt"
    assert records[0].charges == ["MARIJUANA POSSESSION 2"]


def test_normalize_incident():
    assert normalize_incident("BURGLARY-3RD") == "BURGLARY 3"
    assert normalize_incident("THEFT  2ND   DEGREE.") == "THEFT 2 DEGREE"
