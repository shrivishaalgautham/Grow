from tests.api.support import start_session


def test_like_wildcards_are_escaped(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/symbols/search", params={"q": "%"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_query_longer_than_32_chars_is_rejected(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/symbols/search", params={"q": "a" * 33}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_search_matches_name_substring_case_insensitively(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/symbols/search", params={"q": "adani ent"}, headers=headers)

    assert response.status_code == 200
    assert [row["symbol"] for row in response.json()] == ["ADANIENT.NS"]
    assert set(response.json()[0]) == {"symbol", "name", "industry"}
