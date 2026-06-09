# Backups & Restore

Family tree data is irreplaceable. Two things need protecting: the
**Postgres database** (people, events, sources, photo metadata) and the
**S3 photo bucket** (original images and documents).

## Database: nightly pg_dump → S3

`deploy/backup.sh` dumps the database (`pg_dump --format=custom`), uploads it
to `s3://$BACKUP_S3_BUCKET/backups/db/familytree-<timestamp>.dump`, verifies
the upload, and prunes copies older than 30 days. It runs nightly via a
systemd timer installed by `deploy/setup.sh`.

### Setup

1. Add to the server's `.env` (falls back to `S3_BUCKET` if unset):

   ```
   BACKUP_S3_BUCKET=your-bucket
   # optional overrides:
   # BACKUP_S3_PREFIX=backups/db
   # BACKUP_RETENTION_DAYS=30
   ```

2. The EC2 instance role (or `aws configure` credentials) needs
   `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, and `s3:ListBucket`
   on the bucket.

3. Either run `sudo bash deploy/setup.sh` (installs everything), or install
   just the timer on an existing server:

   ```bash
   sudo dnf install -y postgresql16   # provides pg_dump
   sudo cp deploy/familytree-backup.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now familytree-backup.timer
   ```

### Verify it's working

```bash
systemctl list-timers familytree-backup.timer   # next/last run
sudo systemctl start familytree-backup.service  # run one now
journalctl -u familytree-backup -n 50           # logs
aws s3 ls s3://your-bucket/backups/db/          # the dumps
```

Do this once after setup, and again any time you change the database
instance or bucket.

### Restore

```bash
# 1. Find the backup you want
aws s3 ls s3://your-bucket/backups/db/

# 2. Download it
aws s3 cp s3://your-bucket/backups/db/familytree-<timestamp>.dump /tmp/restore.dump

# 3. Stop the app so nothing writes during the restore
sudo systemctl stop familytree

# 4. Restore. --clean --if-exists drops and recreates objects, so this
#    OVERWRITES the current database contents.
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="$DATABASE_URL" /tmp/restore.dump

# 5. Restart and check
sudo systemctl start familytree
curl -fsS localhost:8000/healthz
```

To inspect a backup without touching prod, restore into a scratch database
first: `createdb scratch && pg_restore --dbname=postgresql://.../scratch ...`

## Photos: S3 bucket versioning

Photos are only ever added, but versioning protects against accidental
deletes and overwrites (e.g. a bad migration script). Enable it once:

```bash
aws s3api put-bucket-versioning --bucket your-bucket \
  --versioning-configuration Status=Enabled
```

To recover a deleted object, list its versions and copy the prior one back:

```bash
aws s3api list-object-versions --bucket your-bucket --prefix photos/<key>
aws s3api copy-object --bucket your-bucket --key photos/<key> \
  --copy-source "your-bucket/photos/<key>?versionId=<old-version-id>"
```

Optionally add a lifecycle rule to expire noncurrent versions after ~90 days
so versioning doesn't grow the bucket forever.
