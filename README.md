# CRM: Celery + Celery Beat Weekly Report

This document describes how to install Redis and project dependencies, run migrations, start Celery worker and Celery Beat, and verify the weekly CRM report log.

Prerequisites
- Redis server (local or remote)
- Python and pip

1. Install Redis and dependencies
- On macOS (Homebrew):
  - brew install redis
  - brew services start redis
- On Debian/Ubuntu:
  - sudo apt-get update
  - sudo apt-get install redis-server
  - sudo systemctl enable --now redis
- Or use Docker:
  - docker run -d --name redis -p 6379:6379 redis:6

Install Python dependencies:
- From the project root:
  - pip install -r requirements.txt

2. Run migrations
- python manage.py migrate

3. Start the Django development server (optional)
- python manage.py runserver

4. Start Celery worker
- From the project root:
  - celery -A crm worker -l info

5. Start Celery Beat (scheduler)
- From the project root:
  - celery -A crm beat -l info

6. Verify logs
- The weekly CRM report is appended to: `/tmp/crm_report_log.txt`
- The Celery Beat schedule is configured to run weekly on Monday at 06:00 (server timezone).

Notes
- The Celery broker is configured to use Redis at `redis://localhost:6379/0`. If your Redis instance is elsewhere, update `crm/celery.py` and/or add `CELERY_BROKER_URL` in your Django settings.
- The Celery task `generate_crm_report` obtains the aggregated data by executing the project's GraphQL schema query (`crmReport`), so keep the schema file in sync when models change.
```