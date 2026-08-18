import uuid
import pytest


def test_create_and_list_competitor(client, auth_headers):
    payload = {
        "name": "Stripe",
        "company_url": "https://stripe.com",
        "pricing_url": "https://stripe.com/pricing",
        "description_text": "Payment processing infrastructure",
        "news_keywords": ["Stripe", "fintech"],
    }
    create_res = client.post("/competitors/", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    comp_data = create_res.json()
    assert comp_data["name"] == "Stripe"
    assert comp_data["company_url"] == "https://stripe.com"
    assert comp_data["domain"] == "stripe.com"
    comp_id = comp_data["id"]

    # List competitors
    list_res = client.get("/competitors/", headers=auth_headers)
    assert list_res.status_code == 200
    comps = list_res.json()
    assert len(comps) >= 1
    assert any(c["id"] == comp_id for c in comps)

    # Get details
    detail_res = client.get(f"/competitors/{comp_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["company_url"] == "https://stripe.com"


def test_duplicate_competitor_conflict(client, auth_headers):
    payload = {
        "name": "Linear App",
        "company_url": "https://linear.app",
        "pricing_url": "https://linear.app/pricing",
    }
    res1 = client.post("/competitors/", json=payload, headers=auth_headers)
    assert res1.status_code == 201

    # Attempt to create duplicate with same domain
    res2 = client.post("/competitors/", json=payload, headers=auth_headers)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_delete_competitor(client, auth_headers):
    payload = {
        "name": "To Delete Inc",
        "company_url": "https://todelete.example.com",
        "pricing_url": "https://todelete.example.com/pricing",
    }
    create_res = client.post("/competitors/", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    comp_id = create_res.json()["id"]

    del_res = client.delete(f"/competitors/{comp_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Verify deleted
    get_res = client.get(f"/competitors/{comp_id}", headers=auth_headers)
    assert get_res.status_code == 404
