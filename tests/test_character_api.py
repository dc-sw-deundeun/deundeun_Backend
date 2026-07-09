from fastapi.testclient import TestClient

from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user


def _access_token(client: TestClient, email_client: CapturingEmailClient) -> str:
    signup_user(client, email_client, email="character-api@example.com")
    return login_user(client, email="character-api@example.com").json()["data"]["access_token"]


def test_get_my_character_requires_auth(client: TestClient) -> None:
    res = client.get("/api/v1/characters/me")
    assert res.status_code == 401


def test_get_my_character_returns_default_profile_with_owned_animals(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    access = _access_token(client, email_client)

    res = client.get("/api/v1/characters/me", headers={"Authorization": f"Bearer {access}"})

    assert res.status_code == 200
    data = res.json()["data"]
    assert "current_animal" not in data
    assert "unlocked_animals" not in data
    assert data["level"] == 1
    assert data["total_exp"] == 0
    assert data["current_level_exp"] == 0
    assert data["exp_to_next_level"] > 0
    assert data["progress_ratio"] == 0
    assert [a["animal_code"] for a in data["owned_animals"]] == ["frog"]
    assert data["owned_animals"][0]["unlocked_level"] == 1
    assert data["owned_animals"][0]["image_urls"] == [
        "/api/v1/media/images/by-key/animal/frog_1",
        "/api/v1/media/images/by-key/animal/frog_2",
    ]


def test_list_animals_returns_locked_and_unlocked_catalog(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    access = _access_token(client, email_client)

    res = client.get("/api/v1/characters/animals", headers={"Authorization": f"Bearer {access}"})

    assert res.status_code == 200
    animals = res.json()["data"]["animals"]
    assert [animal["animal_code"] for animal in animals] == [
        "frog",
        "chick",
        "penguin",
        "dog",
        "cat",
        "tiger",
        "panda",
        "monkey",
    ]
    assert animals[0]["is_unlocked"] is True
    assert animals[0]["required_total_exp"] == 0
    assert animals[0]["image_urls"] == [
        "/api/v1/media/images/by-key/animal/frog_1",
        "/api/v1/media/images/by-key/animal/frog_2",
    ]
    assert animals[0]["unlocked_at"] is not None
    assert animals[1]["is_unlocked"] is False
    assert animals[1]["required_total_exp"] == 235
    assert animals[1]["unlocked_at"] is None
