# Global Express Logistics — Shipment Management Starter

## What it includes
- Public tracking lookup
- Admin login
- Create shipment with generated tracking number
- Add tracking status events
- SQLite database for development/testing

## Important deployment notes
This is a starter, not yet a production-ready carrier system. Do not store unnecessary sensitive customer data. Use HTTPS, strong credentials, backups, and a persistent database volume or managed PostgreSQL before handling real shipments. Render's ordinary ephemeral filesystem can lose SQLite data on redeploy/restart. Configure persistent storage before real use.

## Deploy on Render
This version is a Python Flask web service, not a Static Site. Create a **New Web Service** connected to this repository. Build command: `pip install -r requirements.txt`; Start command: `gunicorn app:app`.

Environment variables:
- `SECRET_KEY`: long random secret (Render can generate this)
- `ADMIN_USERNAME`: chosen admin username
- `ADMIN_PASSWORD_HASH`: Werkzeug password hash, not plaintext. Generate it locally with:
  `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('REPLACE_WITH_A_STRONG_PASSWORD'))"`
Set these in Render's Environment settings. Never commit passwords or secret keys to GitHub.

The current database default is a local SQLite file for testing only. Configure a persistent disk mounted at a stable path and set `DATABASE_PATH` accordingly, or use managed PostgreSQL, before real customer use.
