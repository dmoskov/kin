"""Clean up zombie sync_runs stuck in 'running' status.

Zombie sync_runs accumulate when ECS rolling deployments SIGTERM the
worker process mid-sync.  The worker creates a sync_run row with
status='running' at startup, but if it is killed before completion the
row is never updated — it remains 'running' with no completed_at forever.

This script:
  1. Connects to the family-org production database
  2. Marks any sync_run that has been 'running' longer than a timeout as 'failed'
  3. Logs what it cleaned up

The same logic is available as the database function
``cleanup_zombie_sync_runs(max_age_minutes)`` for use by Lambdas and
other callers that already hold a connection.

Usage::

    python scripts/cleanup_zombie_sync_runs.py           # default 60-min timeout
    python scripts/cleanup_zombie_sync_runs.py --timeout 30  # custom timeout

See: Asana task 1217954466850987
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 60


def _get_family_org_connection():
    """Connect to the family-org production database."""
    import psycopg2
    import psycopg2.extras

    db_secret_arn = os.environ.get("FAMILY_ORG_DB_SECRET_ARN")
    db_creds_json = os.environ.get("FAMILY_ORG_DB_CREDENTIALS_JSON")

    if db_secret_arn:
        import boto3

        client = boto3.client("secretsmanager", region_name="us-west-2")
        db_creds_json = client.get_secret_value(SecretId=db_secret_arn)["SecretString"]
    elif not db_creds_json:
        try:
            import boto3

            client = boto3.client("secretsmanager", region_name="us-west-2")
            db_creds_json = client.get_secret_value(
                SecretId="family-org-production-db-credentials"
            )["SecretString"]
        except Exception:
            pass

    if not db_creds_json:
        print("ERROR: No database credentials available.", file=sys.stderr)
        print(
            "Set FAMILY_ORG_DB_SECRET_ARN or FAMILY_ORG_DB_CREDENTIALS_JSON.",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = json.loads(db_creds_json)
    return psycopg2.connect(
        host=creds["host"],
        port=creds.get("port", 5432),
        user=creds["username"],
        password=creds["password"],
        dbname=creds.get("database", "family_org"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def cleanup_zombies(timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> int:
    """Mark zombie sync_runs as failed.  Returns count of cleaned rows."""
    conn = _get_family_org_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cleanup_zombie_sync_runs(%s)", (timeout_minutes,))
        result = cur.fetchone()
        conn.commit()

        cleaned = result["cleaned_count"]
        ids = result["cleaned_ids"] or []
        if cleaned:
            logger.info(
                "Cleaned %d zombie sync_runs (ids=%s, timeout=%dm)",
                cleaned,
                ids,
                timeout_minutes,
            )
        else:
            logger.info("No zombie sync_runs found (timeout=%dm)", timeout_minutes)
        return cleaned
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_MINUTES,
        help=f"Minutes after which a running sync_run is considered a zombie (default: {DEFAULT_TIMEOUT_MINUTES})",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cleaned = cleanup_zombies(args.timeout)
    print(f"Cleaned {cleaned} zombie sync_run(s)")


if __name__ == "__main__":
    main()
