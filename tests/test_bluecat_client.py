import pytest
import responses

from apps.integrations.bluecat import BluecatClient, BluecatError


@pytest.fixture
def client():
    return BluecatClient(
        base_url="https://bluecat.test/api/v2",
        username="svc",
        password="pw",
        verify_tls=False,
    )


@responses.activate
def test_login_sets_token(client):
    responses.add(
        responses.POST,
        "https://bluecat.test/api/v2/sessions",
        json={"apiToken": "abc123"},
        status=200,
    )
    client.login()
    assert client._session.headers["Authorization"] == "Basic abc123"


@responses.activate
def test_login_failure_raises(client):
    responses.add(
        responses.POST,
        "https://bluecat.test/api/v2/sessions",
        json={"error": "bad creds"},
        status=401,
    )
    with pytest.raises(BluecatError):
        client.login()


@responses.activate
def test_get_configuration_id(client):
    responses.add(
        responses.POST,
        "https://bluecat.test/api/v2/sessions",
        json={"apiToken": "tok"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bluecat.test/api/v2/configurations",
        json={"data": [{"id": 7, "name": "Production"}]},
        status=200,
    )
    assert client.get_configuration_id("Production") == 7


@responses.activate
def test_next_available_address(client):
    responses.add(
        responses.POST,
        "https://bluecat.test/api/v2/sessions",
        json={"apiToken": "tok"},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://bluecat.test/api/v2/networks/42/nextAvailableAddress",
        json={"id": 999, "address": "10.0.0.5", "prefixLength": 32},
        status=201,
    )
    out = client.next_available_address(
        "42", name="rtr01:Loopback0", hostname="rtr01"
    )
    assert out["address"] == "10.0.0.5"
