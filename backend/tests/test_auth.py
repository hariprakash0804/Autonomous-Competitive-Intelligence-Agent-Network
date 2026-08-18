import uuid
import pytest
from app.config import settings


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Autonomous Competitive Intelligence Agent Network API"}


def test_user_signup_and_login(client):
    unique_email = f"signup_{uuid.uuid4().hex[:6]}@example.com"
    signup_data = {
        "email": unique_email,
        "password": "securepassword123",
        "name": "New Tester",
    }
    signup_res = client.post("/auth/signup", json=signup_data)
    assert signup_res.status_code in (200, 201)
    data = signup_res.json()
    assert "access_token" in data

    # Login
    login_data = {
        "email": unique_email,
        "password": "securepassword123",
    }
    login_res = client.post("/auth/login", json=login_data)
    assert login_res.status_code == 200
    login_json = login_res.json()
    assert "access_token" in login_json
    assert login_json["token_type"] == "bearer"


def test_auth_me_endpoint(client, auth_headers, test_user):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["email"] == test_user.email
    assert json_data["name"] == test_user.name


def test_arbitrary_api_key_is_strictly_rejected(client):
    """
    Security regression test: Verifies that arbitrary 8+ char X-Internal-Api-Key headers
    are NOT allowed to bypass authentication and receive HTTP 401.
    """
    response = client.get("/competitors/", headers={"X-Internal-Api-Key": "12345678"})
    assert response.status_code == 401

    response2 = client.get("/competitors/", headers={"X-Internal-Api-Key": "any_random_string_greater_than_8"})
    assert response2.status_code == 401
