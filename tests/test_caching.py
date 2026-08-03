"""Assets are cached for a year, which is only safe because their URLs change
whenever the file does.

The two halves have to stay together: a long max-age without the version stamp
serves stale CSS for a year, and the stamp without the max-age refetches every
asset on every navigation -- which is what made the deployed site render
unstyled, since a small host drops some of that burst.
"""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"

A_YEAR = 31536000


def test_static_assets_are_cached_for_a_year(client):
    response = client.get("/static/css/retro.css")
    assert response.status_code == 200
    assert f"max-age={A_YEAR}" in response.headers["Cache-Control"]


def test_the_stylesheet_and_scripts_are_versioned(client):
    """Every URL the long cache applies to has to carry a stamp, or an edit
    would never reach anyone who had already loaded the page."""
    body = client.get("/flights").get_data(as_text=True)

    urls = re.findall(r'(?:href|src)="(/static/[^"]+)"', body)
    assert urls, "no versioned assets found on the departures page"

    for url in urls:
        assert re.search(r"\?v=\d+$", url), url


def test_the_stamp_is_the_files_own_mtime(client):
    """So editing a file changes its URL, and the old one is never asked for."""
    body = client.get("/flights").get_data(as_text=True)

    match = re.search(r'/static/css/retro\.css\?v=(\d+)', body)
    assert match, "stylesheet link not found"

    assert int(match.group(1)) == int((STATIC / "css" / "retro.css").stat().st_mtime)
