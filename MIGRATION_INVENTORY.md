# Migration Inventory: family-tree → Member Account 453914762633

> **Purpose**: Catalogue every AWS-coupled reference in this repository so the
> follow-up parameterisation task can replace them systematically.
>
> **Scope**: Documentation only — no behaviour changes.
>
> **Management account**: 181691141781
> **Target member account**: 453914762633

---

## 1. Hardcoded Management-Account References

`git grep -n 181691141781` returns **zero results**. The management account ID
does not appear anywhere in committed source, IaC, workflows, or scripts.

However, the account is implicitly assumed in several places via:

| What | File:Line | Detail |
|------|-----------|--------|
| STS region assumption | `src/anthropic_client.py:32` | `_STS_REGION = "us-east-1"` — hardcoded region for STS `GetWebIdentityToken`. Must match whichever region the member account's STS endpoint is configured in. |
| Secrets Manager region | `scripts/cleanup_zombie_sync_runs.py:60` | `region_name="us-west-2"` — hardcoded twice (lines 60, 66). |
| Secrets Manager region | `scripts/cleanup_zombie_sync_runs.py:66` | Same `us-west-2` on the fallback path. |
| EC2 Instance Connect region | `deploy/deploy.sh:42-43` | Template variables `AZ=""` and `REGION=""` — not hardcoded to a value, but the deploy script assumes the server runs in a single AWS region. |
| S3 client default region | `src/storage.py:129` | `boto3.client("s3")` with no explicit region — uses the SDK default chain. Will resolve differently in the member account if the default region changes. |

**Hardcoded region assumptions (us-west-2)**:
- `scripts/cleanup_zombie_sync_runs.py:60` — `boto3.client("secretsmanager", region_name="us-west-2")`
- `scripts/cleanup_zombie_sync_runs.py:66` — same

**Hardcoded region assumptions (us-east-1)**:
- `src/anthropic_client.py:32` — `_STS_REGION = "us-east-1"`
- `src/anthropic_client.py:65` — `boto3.client("sts", region_name=_STS_REGION)`
- `src/anthropic_client.py:74` — same

---

## 2. AWS Resources Referenced

### 2.1 Compute — EC2 (bare metal deploy, not ECS)

The family-tree app deploys to a **single EC2 instance** via SSH/rsync, not ECS.

| Resource | Referenced in | Notes |
|----------|---------------|-------|
| EC2 instance | `deploy/deploy.sh`, `.github/workflows/deploy-reusable.yml` | Host IP/DNS stored in GitHub secret `DEPLOY_HOST`; SSH key in `DEPLOY_SSH_KEY`. Instance ID stored in deploy script template vars. |
| systemd service `familytree` | `deploy/familytree.service` | Gunicorn on port 8000, user `ec2-user`. |
| systemd timer `familytree-backup` | `deploy/familytree-backup.timer` | Nightly backup at 09:13 UTC. |
| nginx reverse proxy | `deploy/nginx.conf` | TLS termination, proxy to 127.0.0.1:8000. |

### 2.2 Storage — S3

| Resource | Referenced in | Notes |
|----------|---------------|-------|
| Photo bucket (`S3_BUCKET` env var) | `src/storage.py:218`, `deploy/.env.example:45` | Bucket name is runtime config, not hardcoded. Used for photo upload/download. |
| Backup bucket (`BACKUP_S3_BUCKET` / `S3_BUCKET`) | `deploy/backup.sh:36`, `deploy/BACKUPS.md` | pg_dump output uploaded here. Falls back to `S3_BUCKET`. |
| S3 API calls | `deploy/backup.sh:72-84` | `aws s3 cp`, `s3api head-object`, `s3api list-objects-v2`, `aws s3 rm` for backup lifecycle. |
| S3 API calls | `src/storage.py:141-192` | `put_object`, `get_object`, `head_object`, `delete_object`, `list_objects_v2` via boto3. |

### 2.3 Database — PostgreSQL (RDS or local)

| Resource | Referenced in | Notes |
|----------|---------------|-------|
| Production PostgreSQL | `src/database/connection.py:87` | DSN from `DATABASE_URL` env var. No hardcoded endpoint. |
| SQLite fallback | `src/database/connection.py:57` | `data/family.db` — local dev only. |
| family-org production DB | `scripts/cleanup_zombie_sync_runs.py:68` | Cross-project: connects to family-organization's RDS via Secrets Manager secret `family-org-production-db-credentials`. |
| Backup/restore | `deploy/backup.sh:61-62` | `pg_dump --dbname="$DATABASE_URL"` |

### 2.4 Secrets Manager

| Secret | Referenced in | Notes |
|--------|---------------|-------|
| `family-org-production-db-credentials` | `scripts/cleanup_zombie_sync_runs.py:68` | Cross-project secret (lives in management account). Used to connect to the family-organization database. |
| `FAMILY_ORG_DB_SECRET_ARN` (env var) | `scripts/cleanup_zombie_sync_runs.py:54` | Alternative: pass a custom secret ARN. |

### 2.5 STS (Workload Identity Federation)

| Resource | Referenced in | Notes |
|----------|---------------|-------|
| STS `GetWebIdentityToken` | `src/anthropic_client.py:75` | Mints JWT for Anthropic WIF. Uses the ECS task role (or `ANTHROPIC_STS_ROLE_ARN`). |
| STS `AssumeRole` | `src/anthropic_client.py:65` | Optional: for local dev with an explicit role ARN. |

### 2.6 Resources NOT in this repo but referenced in docs

These resources are described in investigation/fix markdown files and belong to
the **family-organization** repo's infrastructure (management account):

| Resource | Doc file | Notes |
|----------|----------|-------|
| CloudWatch alarm `family-org-production-app-errors-high` | `APP_ERROR_SPIKE_FIX.md:11` | In management account. |
| CloudWatch log group `/ecs/family-org-production/web` | `APP_ERROR_SPIKE_FIX.md:17` | In management account. |
| CloudWatch metric filter `family-org-production-app-errors` | `APP_ERROR_SPIKE_FIX.md:26` | In management account. |
| SNS topic `family-org-production-alerts` | `APP_ERROR_SPIKE_FIX.md:65` | In management account. |
| ECS service/tasks (family-org) | `APP_ERROR_SPIKE_FIX.md:22` | In management account — this is family-org's ECS, not family-tree's. |
| EventBridge rule + SQS `family-org-production-asana-sync` | `ASANA_SYNC_ORPHAN_FIX.md:70-72` | In management account. |
| SQS `family-org-production-contacts-sync` | `CONTACTS_SYNC_FIX.md:13` | In management account. |
| Lambda `oauth-token-rotation` + EventBridge schedule | `ASANA_OAUTH_REFRESH_FIX.md:12` | In management account. |
| IAM roles `letta-task-role`, `crucible-remote-agent-analysis-task-role` | `APP_ERROR_SPIKE_FIX.md:70,84` | In management account. |

---

## 3. Data Stores and Migration Methods

| Data Store | Current Location | Migration Method | Notes |
|------------|-----------------|------------------|-------|
| **PostgreSQL (RDS)** — production DB | Management account (endpoint in `DATABASE_URL` env var) | **Cross-account RDS snapshot** — create encrypted snapshot, share with member account 453914762633, restore in target VPC. Alternatively, use **pg_dump/pg_restore** for a clean migration with schema replay. | Schema has 20+ migrations (`src/database/schema.py`). The SQLAlchemy/Alembic chain caveat from family-org does NOT apply here — family-tree uses raw SQL migrations. |
| **S3 bucket** — photos | Management account (bucket name in `S3_BUCKET` env var) | **S3 cross-account sync** — `aws s3 sync` from source to a new bucket in 453914762633. Enable bucket versioning on the target. | S3Storage falls back to local disk for legacy photos. |
| **S3 bucket** — backups | Management account (bucket name in `BACKUP_S3_BUCKET` env var) | **S3 cross-account sync** — same approach. Lower priority since backups are regenerated nightly. | Could simply start fresh backups in the new account. |
| **SQLite** — local dev | Local filesystem only | N/A — not deployed. | `data/family.db` is gitignored. |
| **Secrets Manager** — `family-org-production-db-credentials` | Management account, `us-west-2` | **Do not migrate** — this is a cross-project secret. The cleanup_zombie_sync_runs script needs cross-account access or a new secret in the member account. | See cross-project dependencies. |
| **GitHub Secrets** — `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, `ANTHROPIC_API_KEY` | GitHub repo settings | **Re-create** in GitHub with new values pointing to member-account infrastructure. | No migration needed — just create new secrets. |

---

## 4. Cross-Project Dependencies (Migration Blockers)

### 4.1 family-organization database (BLOCKER)

`scripts/cleanup_zombie_sync_runs.py` directly connects to the **family-organization
production database** to clean up zombie sync_runs.

- **Secret**: `family-org-production-db-credentials` in Secrets Manager (us-west-2)
- **Lines**: 54-68
- **Impact**: After migration, the family-tree member account must either:
  1. Have cross-account Secrets Manager access to the management account, or
  2. Use a cross-account IAM role to assume into the management account, or
  3. Remove this script (it arguably belongs in the family-organization repo)
- **Recommendation**: Move this script to family-organization. It operates on
  family-org's database and only lives here for historical reasons.

### 4.2 Scaffold/crucible infrastructure references (NON-BLOCKER)

Documentation and dispatch code reference scaffold infrastructure, but these are
name-string references, not AWS resource ARNs:

| Reference | File | Impact |
|-----------|------|--------|
| `crucible-remote-agent-analysis-task-role` | `APP_ERROR_SPIKE_FIX.md:84` | Doc only — describes an IAM role in the management account. |
| `claude-code-scaffold` executor | `scripts/executor_registry.py:50-54` | String-based routing — no AWS dependency. |
| `claude-code-scaffold` dispatcher | `scripts/task_dispatcher.py:25` | String-based routing — no AWS dependency. |

### 4.3 Letta server (NON-BLOCKER for this repo)

`scripts/fix_letta_embedding_config.py` connects to a Letta server
(`LETTA_BASE_URL`, default `http://localhost:8283`). This is a network dependency
on the Letta sidecar, which runs on scaffold infrastructure.

- **Impact**: If VSM agents run from the member account, the Letta server
  endpoint must be reachable. This is a network/VPC concern, not an account-ID
  concern.
- **Lines**: 32-33

### 4.4 Asana project (NON-BLOCKER)

`scripts/asana_path_liveness.py:39` hardcodes `PROBE_PROJECT_GID = "1211710875848660"`.
This is an Asana project ID, not an AWS resource — no migration impact.

---

## 5. CI/CD Authentication

### Current state: SSH key-based deploy (no OIDC to AWS)

The GitHub Actions workflows do **not** use `aws-actions/configure-aws-credentials`
or OIDC federation to authenticate to AWS. Deployment works via:

1. **SSH key** — `DEPLOY_SSH_KEY` repo secret contains a private key.
2. **SSH host** — `DEPLOY_HOST` repo secret contains the EC2 instance IP/hostname.
3. **rsync** — Files are synced to the server over SSH.
4. **systemctl** — The service is restarted via SSH.

| Workflow | Auth method | What must change |
|----------|-------------|-----------------|
| `deploy-reusable.yml` | SSH key (`DEPLOY_SSH_KEY` secret) | Update `DEPLOY_HOST` to point to the new EC2 instance in member account 453914762633. Generate a new SSH key pair for the new instance. |
| `ci.yml` | No AWS auth needed | No changes — runs entirely on GitHub-hosted runners with no AWS calls. |
| `auto-merge.yml` | `GITHUB_TOKEN` only | No changes — GitHub-internal operations only. |
| `sync-task-branches.yml` | `GITHUB_TOKEN` only | No changes. |

### What must change for the member account

1. **New EC2 instance** in account 453914762633 — provision via the same
   `deploy/setup.sh` script.
2. **Update GitHub secrets**:
   - `DEPLOY_HOST` → new instance IP/DNS
   - `DEPLOY_SSH_KEY` → new private key for the new instance
3. **S3 bucket** — create in the member account, update the server's `.env` file
   with the new bucket name for `S3_BUCKET` / `BACKUP_S3_BUCKET`.
4. **RDS instance** — provision in member account, set `DATABASE_URL` in `.env`.
5. **If adding OIDC later**: Create an IAM OIDC provider for GitHub Actions in
   453914762633 and add `aws-actions/configure-aws-credentials` to the deploy
   workflow. Not required for the current SSH-based deploy model.
6. **Anthropic WIF** — The `ANTHROPIC_STS_ROLE_ARN` (if used) must be an IAM
   role in 453914762633 with the federation rule configured for the new account.

---

## 6. Readiness Verdict

### Ready — with one blocker to resolve first

**Status: BLOCKED on cross-account database dependency**

The family-tree stack is architecturally simple (single EC2 + RDS + S3) with no
hardcoded account IDs, no ECR images, no ECS task definitions, no Lambdas, and
no EventBridge schedules in this repo. The deploy model is SSH-based, not
OIDC-based, so there is no IAM role ARN to change in workflows.

**Blocker**:
- `scripts/cleanup_zombie_sync_runs.py` connects to the family-organization
  production database using a Secrets Manager secret (`family-org-production-db-credentials`)
  in the management account's us-west-2 region. After migration, this script
  will fail unless cross-account Secrets Manager access is configured or the
  script is moved to the family-organization repo where it belongs.

**Pre-migration punch list**:
1. Decide: move `cleanup_zombie_sync_runs.py` to family-org, or set up
   cross-account secret access.
2. Provision in 453914762633: EC2 instance, RDS, S3 bucket (photos), S3 bucket
   (backups, or reuse photos bucket with prefix).
3. Run `deploy/setup.sh` on the new instance.
4. Migrate data: pg_dump/pg_restore for PostgreSQL, `aws s3 sync` for photos.
5. Update GitHub secrets: `DEPLOY_HOST`, `DEPLOY_SSH_KEY`.
6. Update server `.env`: `DATABASE_URL`, `S3_BUCKET`, `BACKUP_S3_BUCKET`,
   `SECRET_KEY`, `GOOGLE_CLIENT_ID`.
7. Parameterise hardcoded regions (`us-west-2`, `us-east-1`) — follow-up task.
8. DNS: Point the domain at the new instance's IP / update nginx TLS certs.
9. Verify: nightly backup timer fires, photos upload to the new S3 bucket,
   Anthropic WIF still works (STS region may need adjustment).

**Low-risk items** (no changes needed):
- CI workflow (`ci.yml`) — runs on GitHub runners, no AWS calls.
- Auto-merge and branch-sync workflows — GitHub-internal only.
- All application code — config-driven via environment variables.
- Dockerfile and docker-compose.yml — no account-specific references.
