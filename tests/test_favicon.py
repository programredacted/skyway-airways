"""The tab icon: every file the page points at has to actually be there."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_every_icon_the_page_links_to_exists(client):
    body = client.get("/flights").get_data(as_text=True)

    linked = re.findall(r'rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', body)
    assert len(linked) == 3, linked

    for href in linked:
        assert client.get(href).status_code == 200, href


def test_the_svg_icon_is_served_as_an_svg(client):
    response = client.get("/static/favicon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["Content-Type"]
    assert b"<svg" in response.data


def test_favicon_ico_is_served_at_the_root(client):
    """Asked for by convention whether or not the link tags exist."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    # a real ICO container: reserved 0, type 1 (icon), one image
    assert response.data[:6] == b"\x00\x00\x01\x00\x01\x00"


def test_the_rasters_are_the_sizes_they_claim():
    """PNG dimensions live in the IHDR chunk, bytes 16-24."""
    expected = {"favicon-32.png": 32, "apple-touch-icon.png": 180,
                "favicon-192.png": 192}
    for name, size in expected.items():
        data = (STATIC / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", name
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        assert (width, height) == (size, size), (name, width, height)


def test_the_icon_flies_the_same_aeroplane_as_the_route_map():
    """One shape, not a lookalike: if the map's plane is redrawn, this fails
    and the icon gets redrawn with it."""
    icon = (STATIC / "favicon.svg").read_text(encoding="utf-8")
    routemap = (STATIC.parent / "templates" / "_routemap.html").read_text(encoding="utf-8")

    def outline(text):
        match = re.search(r'd="(M 4\.4 0.*?Z)"', text, re.S)
        assert match, "no aeroplane path found"
        return " ".join(match.group(1).split())

    assert outline(icon) == outline(routemap)


def test_the_tile_uses_the_brand_colours():
    icon = (STATIC / "favicon.svg").read_text(encoding="utf-8")
    css = (STATIC / "css" / "retro.css").read_text(encoding="utf-8")

    teal_dk = re.search(r"--teal-dk:\s*(#[0-9a-fA-F]{6})", css).group(1)
    gold = re.search(r"--gold:\s*(#[0-9a-fA-F]{6})", css).group(1)

    assert teal_dk in icon, "tile should be the header's teal"
    assert gold in icon, "aeroplane should be the wordmark's gold"
