# FieldTicket API

FieldTicket is a construction time-and-materials
ticket calculation and PDF-generation API.

## Live API

Base URL:
https://fieldticket-api.onrender.com

Interactive documentation:
https://fieldticket-api.onrender.com/docs

Health check:
https://fieldticket-api.onrender.com/health

## API endpoints

- GET /health — Health check
- POST /v1/tickets/calculate — Calculate a ticket
- POST /v1/tickets/pdf — Generate a PDF ticket
- GET /v1/usage — Check monthly usage

## Authentication

Protected endpoints require the HTTP header:

X-API-Key: YOUR_CUSTOMER_API_KEY

Keep API keys private. Never commit them to Git.

## Customer management

The administrator can use:

    python manage_customers.py list
    python manage_customers.py usage 4
    python manage_customers.py create "Company Name" --limit 100
    python manage_customers.py disable CUSTOMER_ID

Customer keys are stored locally in a private directory:

    ~/.fieldticket-keys/

The CLI requires a valid DATABASE_URL or an authenticated
Neon CLI configured for the project.

## Local development

Create and activate a Python virtual environment,
then install dependencies:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Start the API:

    python -m uvicorn main:app --reload

Run automated tests:

    python -m pytest -q

## Deployment

The API is deployed on Render and uses Neon PostgreSQL.

Production environment variables include:

- DATABASE_BACKEND=postgres
- DATABASE_URL (secret PostgreSQL connection string)

Never publish database credentials or customer API keys.

## Current limitations

- Billing and payments are not yet integrated.
- API keys are managed by the administrator.
- Security review and operational monitoring are ongoing.
- Render Free may take time to wake after inactivity.
