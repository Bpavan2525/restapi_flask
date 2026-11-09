# Shop Orders API

A REST API for a local restaurant or shop, built with **Python and Flask**. Customers browse the menu and place orders; every order is validated, totalled, and returned with a **WhatsApp link** that sends it straight to the shop owner's phone. The owner can list orders and move them through `received → preparing → ready → delivered`.

**Live demo:** LIVE_URL (open it and press the button to place a test order)

## Features

- Product catalogue with category filter
- Order creation with field-level validation errors (`422` with a `details` object)
- Totals calculated on the server, never trusted from the client
- WhatsApp deep link for each order (`https://wa.me/<shop number>?text=...`)
- Shop-owner endpoints protected by an `X-API-Key` header
- Order status workflow that rejects invalid moves with `409`
- JSON errors for 404 and 405, never HTML
- 13 pytest tests covering the happy path, validation, auth and status rules

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/products?category=mains` | List products |
| GET | `/api/products/<id>` | One product |
| POST | `/api/orders` | Place an order |
| GET | `/api/orders/<id>` | Track an order |
| GET | `/api/orders?status=received` | All orders (needs `X-API-Key`) |
| PATCH | `/api/orders/<id>` | Change status (needs `X-API-Key`) |

```bash
curl -X POST LIVE_URL/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Ravi","phone":"9876543210","items":[{"product_id":1,"qty":2}]}'
```

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python app.py          # http://127.0.0.1:5000
pytest                 # run the tests
```

Settings come from environment variables: `SHOP_WHATSAPP` (the shop's number with country code, e.g. `919876543210`) and `ADMIN_KEY` (the key for owner endpoints).

## Project layout

```
shop_api/__init__.py      app factory, routes and validation
shop_api/templates/       interactive docs page served at /
app.py                    entry point (local and Vercel)
tests/test_api.py         pytest suite
notebooks/                Flask and REST concept notes
```

## Notes

The demo stores orders in memory so it needs no database. For a real shop, swap the `orders` dict for SQLite or Postgres (SQLAlchemy); the routes stay the same.
