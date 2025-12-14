# Database Schema Modernization Walkthrough

## Overview
We have successfully modernized the database schema from a simple 4-table structure to a production-ready 12-table architecture supporting:
- **Multi-tenancy**: Users, Campaigns, Platforms.
- **Advanced Publishing**: Batch Runs (`PublishingRun`) and individual Posts (`PublishingPost`).
- **Anti-Detect Profile Management**: `DummyAccount` per platform with personas.
- **Asset Management**: Centralized `Asset` table with metadata.

## Schema Changes
The schema now uses `JSON().with_variant(JSONB, 'postgresql')` to support:
- **Production**: Optimized `JSONB` on PostgreSQL (AWS RDS).
- **Development/Verification**: `JSON` (Text) on SQLite (Local).

### Key Entities Added
- `User` (RBAC)
- `Platform` (Instagram, TikTok, YouTube)
- `Campaign` (Grouping assets/runs)
- `DummyAccountPersona` (AI personality config)
- `PublishingRunEvent` (Audit trail)

## Migration Strategy
We implemented a **data-preserving migration** (`01c7e01ae621_schema_v2_modernization.py`):
1. **Renames**:
   - `accounts` -> `dummy_accounts`
   - `uploaded_assets` -> `assets`
   - `publishing_run_posts` -> `legacy_publishing_run_posts` (Archived)
2. **Seeding**:
   - Created admin user `admin@example.com`.
   - Seeded standard platforms (Instagram, TikTok, YouTube).
   - Created a "Legacy Campaign" to house existing assets.
3. **Linking**:
   - Existing accounts linked to platform `Instagram` (Default).
   - Existing assets linked to Admin user and Legacy Campaign.
4. **Compatibility**:
   - Used `batch_alter_table` to support SQLite's limited `ALTER TABLE` capabilities during verification.

## Verification Results (Local SQLite)
Due to network restrictions connecting to AWS RDS, we performed a full verification cycle locally:
1. **Baseline**: Applied initial migration (`79e40a331383`).
2. **Seeding**: Inserted legacy test data (`accounts`, `uploaded_assets`).
3. **Upgrade**: Applied modernization migration (`head`).
4. **Validation**: Ran `scripts/verify_migration.py`.

### Results
```
PASS: Admin user exists
PASS: Platforms seeded (3)
PASS: Dummy accounts migrated (1)
PASS: Username preserved as email (Got: test@example.com)
PASS: Platform ID defaulted to 1 (Instagram)
PASS: is_active defaulted to true (Got: 'true')
PASS: Assets migrated (1)
PASS: Original name preserved (Got: test_video.mp4)
PASS: User ID set to Admin
PASS: Campaign ID set to Default Legacy
ALL CHECKS PASSED
```

## Codebase Updates
Refactored the application layer to match the new schema:
- **`src/agent/services/publishing_runs.py`**: Updated to split logic into `PublishingRun` (Batch) and `PublishingPost` (Item).
- **`src/agent/jobs/publishing.py`**: Updated job runner to fetch `PublishingPost` items and traverse new relationships (`run.dummy_account`, `run.assets[0]`).

## Next Steps
1. **Manual Action**: Connect to AWS RDS from a whitelisted IP and run `alembic upgrade head`.
2. **Manual Action**: Log into GoLogin profiles physically to establish sessions.
3. **E2E Test**: Trigger a `PublishingJob` run to verify full pipeline with GoLogin.
