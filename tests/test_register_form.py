"""What a rejected registration hands back to the form."""

import html


def test_a_rejected_registration_keeps_everything_you_typed(client, csrf, register):
    """A taken username should cost you the username, not the whole form."""
    register(username="claimed", email="claimed@example.com")
    client.post("/logout", data={"csrf_token": csrf()})

    response = client.post("/register", data={
        "csrf_token": csrf("/register"),
        "username": "claimed",
        "email": "someone@example.com",
        "password": "Jetage1965!",
        "confirm": "Jetage1965!",
    })
    assert response.status_code == 400

    body = response.get_data(as_text=True)
    assert 'value="someone@example.com"' in body
    assert body.count('value="Jetage1965!"') == 2      # password and confirm


def test_that_page_is_not_written_to_any_cache(client, csrf, register):
    """It carries a password in its markup, so it must not be stored."""
    register(username="cached")
    client.post("/logout", data={"csrf_token": csrf()})

    response = client.post("/register", data={
        "csrf_token": csrf("/register"), "username": "cached",
        "email": "new@example.com", "password": "Jetage1965!", "confirm": "Jetage1965!"})
    assert response.status_code == 400
    assert response.headers.get("Cache-Control") == "no-store"


def test_a_successful_page_load_is_not_marked_no_store(client):
    assert client.get("/register").headers.get("Cache-Control") != "no-store"


def test_the_error_says_which_field_clashed(client, csrf, register):
    register(username="dupe", email="dupe@example.com")
    client.post("/logout", data={"csrf_token": csrf()})

    response = client.post("/register", data={
        "csrf_token": csrf("/register"), "username": "dupe",
        "email": "fresh@example.com", "password": "Jetage1965!",
        "confirm": "Jetage1965!"})
    assert "That username is already registered" in html.unescape(
        response.get_data(as_text=True))
