"""Guards on the calendar reader, none of which touch the network.

Every fixture below is a JSON string pasted from the shape verified live on
2026-08-19. A test that fetched the real feed would fail on a weekend, would
fail behind a proxy, and would change its own answer every Monday - and the one
assumption most worth pinning here (the UTC offset in winter) cannot be fetched
in August at all.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json

from app.news import NewsEvent, parse, select
from app.providers import ProviderError

# The same wall-clock release on the two offsets New York actually uses. Summer
# is what every live row showed; winter has NEVER been observed from here,
# because only the current week is fetchable, so this fixture is the only place
# the -05:00 case exists.
TWO_OFFSETS = """
[
  {"title": "Non-Farm Employment Change", "country": "USD",
   "date": "2026-08-17T08:30:00-04:00", "impact": "High",
   "forecast": "0.4%", "previous": "-0.4%"},
  {"title": "Non-Farm Employment Change", "country": "USD",
   "date": "2026-08-17T08:30:00-05:00", "impact": "High",
   "forecast": "0.4%", "previous": "-0.4%"}
]
"""

WEEK = """
[
  {"title": "French Final CPI m/m", "country": "EUR",
   "date": "2026-08-17T04:00:00-04:00", "impact": "Low",
   "forecast": "", "previous": "0.2%"},
  {"title": "Non-Farm Employment Change", "country": "USD",
   "date": "2026-08-17T08:30:00-04:00", "impact": "High",
   "forecast": "0.4%", "previous": "-0.4%"},
  {"title": "FOMC Meeting Minutes", "country": "USD",
   "date": "2026-08-19T14:00:00-04:00", "impact": "High",
   "forecast": "", "previous": ""},
  {"title": "BOE Gov Bailey Speaks", "country": "GBP",
   "date": "2026-08-19T14:00:00-04:00", "impact": "Medium",
   "forecast": "", "previous": ""}
]
"""


def test_a_release_is_timed_from_its_own_offset_and_never_from_a_constant():
    """The assumption that would otherwise rot, asserted directly.

    Every row on the live sample read `-04:00`, so an implementation that
    hard-coded it would pass every test written in August and be exactly one
    hour wrong from November - the same half-the-year failure `app/clock.py`
    exists to prevent, and nothing on a chart says which half you are looking
    at. The two rows below are the SAME wall time on the two offsets New York
    uses; if the offset is being read, they are an hour apart.
    """
    events = parse(json.loads(TWO_OFFSETS)).events

    assert events[0].time == 1786969800  # 08:30 -04:00 == 12:30 UTC
    assert events[1].time == 1786973400  # 08:30 -05:00 == 13:30 UTC
    assert events[1].time - events[0].time == 3600, (
        "the two offsets produced the same instant: the offset is being ignored"
    )


def test_an_absent_forecast_stays_absent_rather_than_becoming_a_number():
    """The feed publishes no forecast for a speech or a meeting minute. An
    empty string means the calendar printed nothing; 0 would be a figure this
    module invented and every reader downstream would treat as published."""
    week = parse(json.loads(WEEK))
    minutes = next(e for e in week.events if e.title == "FOMC Meeting Minutes")

    assert minutes.forecast == ""
    assert minutes.previous == ""
    assert minutes.forecast is not None and minutes.forecast != 0

    nfp = next(e for e in week.events if e.title.startswith("Non-Farm"))
    assert nfp.forecast == "0.4%" and nfp.previous == "-0.4%"


def test_the_feed_carries_no_outcome_field_so_nothing_can_leak_backwards():
    """Structural, not incidental. This engine computes from closed bars and
    nothing after them; a calendar that published the actual result could put a
    number into a bar that had not seen it. The feed has no `actual`, and this
    guard fails the day someone adds one."""
    fields = {f.name for f in dataclasses.fields(NewsEvent)}
    assert "actual" not in fields and "result" not in fields


def test_the_impact_filter_keeps_only_what_was_asked_for_and_defaults_to_all():
    """`impact` is the FEED'S label for attention, not a measured effect - so
    the default is no filter at all. Defaulting to High would be this module
    ranking labels nobody here has measured."""
    week = parse(json.loads(WEEK))

    assert len(select(week.events)) == 4, "a default filter appeared"
    high = select(week.events, impact="High")
    assert {e.title for e in high} == {
        "Non-Farm Employment Change",
        "FOMC Meeting Minutes",
    }
    assert len(select(week.events, impact=["High", "Medium"])) == 3
    # A bare string is one label, not a bag of letters.
    assert select(week.events, impact="high") == high
    assert select(week.events, impact="Holiday") == ()


def test_the_currency_filter_reads_the_field_the_feed_calls_country():
    """The feed's `country` holds USD, GBP, EUR - a currency code, not a
    nation. Filtering a gold chart by "US" would return nothing forever."""
    week = parse(json.loads(WEEK))

    assert len(select(week.events, currency="USD")) == 2
    assert len(select(week.events, currency=("USD", "GBP"))) == 3
    assert len(select(week.events, currency="usd", impact="High")) == 2
    assert select(week.events, currency="US") == ()


def test_a_malformed_row_is_skipped_by_name_and_does_not_cost_the_other_rows():
    """One bad row out of ninety-eight must not empty the calendar, and it must
    not vanish quietly either: a shape change upstream has to show up as text
    rather than as a week that silently got shorter.

    The naive-timestamp row is the important one. Guessing an offset for it is
    the exact failure this module exists to prevent, so it is REFUSED.
    """
    rows = json.loads(WEEK)
    rows.append({"title": "No date at all", "country": "USD", "impact": "High"})
    rows.append({"title": "Naive stamp", "country": "USD", "impact": "High",
                 "date": "2026-08-17T08:30:00"})
    rows.append({"country": "USD", "date": "2026-08-17T08:30:00-04:00", "impact": "Low"})
    rows.append("not an object at all")

    week = parse(rows)

    assert len(week.events) == 4, "a bad row took good ones with it"
    assert len(week.skipped) == 4
    assert any("no UTC offset" in reason for reason in week.skipped)
    assert any("unreadable date" in reason for reason in week.skipped)
    assert any("no title" in reason for reason in week.skipped)
    assert week.error == "", "skipped rows are not a failed read"

    # A payload that is not a list at all is a refusal, not a crash.
    broken = parse({"error": "rate limited"})
    assert broken.events == () and "not a list" in broken.error


def test_the_covered_window_is_read_from_the_data_not_assumed_to_be_seven_days():
    """There is no history on this feed - `nextweek`, `lastweek`, `thismonth`
    and `thisyear` all 404 - so the only honest statement about coverage is the
    span of the rows that actually arrived. Assuming a week would let a caller
    believe Friday is covered when the feed stopped on Wednesday.
    """
    week = parse(json.loads(WEEK))

    assert week.covers_from == 1786953600  # 2026-08-17T04:00-04:00, the first row
    assert week.covers_to == 1787162400  # 2026-08-19T14:00-04:00, the last row
    assert week.covers_to - week.covers_from < 7 * 86400
    assert week.events[0].time <= week.events[-1].time, "events are not in order"

    empty = parse([])
    assert empty.covers_from is None and empty.covers_to is None, (
        "an empty feed claimed to cover something"
    )


def test_an_unreachable_feed_returns_nothing_with_a_reason(monkeypatch):
    """A provider failure surfaces its own words here rather than an empty
    chart, and the calendar is held to the same rule: no events, but the
    upstream's reason travels with the emptiness."""
    from app import news

    async def refuse(url, params=None):
        raise ProviderError("network error contacting the feed: ConnectTimeout")

    monkeypatch.setattr(news, "_get_json", refuse)
    monkeypatch.setattr(news, "_cache", None)

    week = asyncio.run(news.read())

    assert week.events == ()
    assert "ConnectTimeout" in week.error
    assert week.covers_from is None and week.covers_to is None
