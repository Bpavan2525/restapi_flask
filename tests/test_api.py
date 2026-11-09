import pytest

from shop_api import create_app

KEY = {"X-API-Key": "test-key"}


@pytest.fixture
def client():
    return create_app(shop_whatsapp="919999999999", admin_key="test-key").test_client()


def place(client, **overrides):
    body = {"customer_name": "Ravi", "phone": "98765 43210", "items": [{"product_id": 1, "qty": 2}]}
    body.update(overrides)
    return client.post("/api/orders", json=body)


def test_docs_page_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_products_filter_and_lookup(client):
    mains = client.get("/api/products?category=mains").get_json()
    assert mains["count"] == 3 and all(p["category"] == "mains" for p in mains["products"])
    assert client.get("/api/products/4").get_json()["name"] == "Butter Naan"
    assert client.get("/api/products/999").status_code == 404


def test_create_order_totals_and_whatsapp_link(client):
    r = place(client, items=[{"product_id": 1, "qty": 2}, {"product_id": 6, "qty": 1}], note="Less spicy")
    assert r.status_code == 201
    order = r.get_json()
    assert order["total"] == 249 * 2 + 30
    assert order["phone"] == "9876543210"
    assert order["status"] == "received"
    assert order["whatsapp_url"].startswith("https://wa.me/919999999999?text=")
    assert client.get(f"/api/orders/{order['id']}").get_json() == order


@pytest.mark.parametrize("override,field", [
    ({"customer_name": ""}, "customer_name"),
    ({"phone": "12ab"}, "phone"),
    ({"items": []}, "items"),
    ({"items": [{"product_id": 42}]}, "items[0].product_id"),
    ({"items": [{"product_id": 1, "qty": 0}]}, "items[0].qty"),
    ({"items": [{"product_id": 1, "qty": True}]}, "items[0].qty"),
])
def test_order_validation(client, override, field):
    r = place(client, **override)
    assert r.status_code == 422
    assert field in r.get_json()["details"]


def test_non_json_body_rejected(client):
    r = client.post("/api/orders", data="hello", content_type="text/plain")
    assert r.status_code == 400


def test_admin_endpoints_need_key(client):
    oid = place(client).get_json()["id"]
    assert client.get("/api/orders").status_code == 401
    assert client.patch(f"/api/orders/{oid}", json={"status": "preparing"}).status_code == 401
    assert client.get("/api/orders", headers=KEY).get_json()["count"] == 1


def test_status_transitions(client):
    oid = place(client).get_json()["id"]
    assert client.patch(f"/api/orders/{oid}", json={"status": "delivered"}, headers=KEY).status_code == 409
    for s in ["preparing", "ready", "delivered"]:
        r = client.patch(f"/api/orders/{oid}", json={"status": s}, headers=KEY)
        assert r.status_code == 200 and r.get_json()["status"] == s
    assert client.patch(f"/api/orders/{oid}", json={"status": "bogus"}, headers=KEY).status_code == 422
    assert client.get("/api/orders?status=delivered", headers=KEY).get_json()["count"] == 1


def test_unknown_route_and_method_return_json(client):
    assert client.get("/nope").get_json() == {"error": "Not found"}
    assert client.delete("/api/products").status_code == 405
