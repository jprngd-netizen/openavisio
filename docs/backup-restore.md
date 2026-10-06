# Backup and restore

Backups run in the `backup` service (`deploy/backup/`), nightly at `BACKUP_HOUR`
(default 03:00) and once on start. Everything is encrypted to an **age public
key**; the private key is held out-of-band and never touches the server.

## What is written

`$BACKUP_DIR` (default `/opt/openavisio-backups`) on the host:

| File | Contains | Retention |
|---|---|---|
| `clinical-YYYY-MM-DD.sql.age` | `vaultdb` **without** `patient_keys` | `RETENTION_CLINICAL_DAYS` (90) |
| `keystore-YYYY-MM-DD.sql.age` | **only** `patient_keys` | `RETENTION_KEYSTORE_DAYS` (7) |
| `documents-YYYY-MM-DD.tar.gz.age` | the encrypted blobs from `/data/documents` | `RETENTION_CLINICAL_DAYS` (90) |

**Why the keystore is separate and short-lived (ADR-031):** erasing a patient
deletes their per-patient KEK, which makes their documents unrecoverable — but
only if the KEK cannot be fetched back out of a backup. Once the erased
patient's KEK has aged out of every keystore backup (7 days), the clinical
backups still holding their ciphertext are permanently undecryptable. That is
what makes crypto-shredding reach backups instead of just live data.

A consequence you must internalise: **a restore needs the clinical and the
keystore dump of the same date.** A 30-day-old clinical dump alone is not
restorable — its keystore partner is long gone. Restores are for "the server
burned down last night", not for "undo something from last month".

## PrescriptionDocument retention

The signed PDF of an issued Prescription (`PrescriptionDocument`) is a **legal
record** and is **excluded from the automatic retention purge** that applies to
other clinical data categories (see `governance.py`). It is retained
indefinitely and is only removed through the **patient erasure cascade** (GDPR
Art. 17 right-to-erasure):

- The erasure cascade hard-deletes the `PrescriptionDocument` row, its storage
  blob, and all related `Prescription` / `PrescriptionItem` rows.
- The storage blob is deleted from disk before the DB transaction commits; if
  storage deletion fails, the transaction is rolled back and erasure is aborted.
- The keystore's short retention (7 days) ensures that once the erased patient's
  KEK has aged out of every keystore backup, the clinical backups holding the
  prescription ciphertext are permanently undecryptable — crypto-shredding
  reaches backups within ~14 days (7 days in the mirror + up to 7 more in
  snapshots).

This policy is enforced by:
1. `governance.py` — `CATEGORY_MODELS` explicitly excludes `prescription` from
   the retention purge targets.
2. `erasure.py` — the patient erasure cascade collects `PrescriptionDocument`
   storage paths, deletes the blobs, and hard-deletes all prescription rows.
3. `test_prescription_erasure.py` — tests verify that the blob survives the
   normal lifecycle and is removed on erasure cascade.

## What you need to restore — and where it lives

| Secret | Without it | Where it must live |
|---|---|---|
| age private key (`AGE-SECRET-KEY-1…`) | backups are noise | password manager / paper, **not the server** |
| `DOCUMENT_ENCRYPTION_KEY` (master KEK) | every document and every extracted text stays ciphertext, forever | password manager / paper, **not only the server's `.env`** |
| `APP_SECRET` | sessions invalid (users log in again — annoying, not fatal) | `.env` is enough |

Losing the age key or the master KEK is unrecoverable. There is no reset, no
support, no vendor. This is the price of the encryption that makes the product
worth using.

## Private-key guardianship

The age private key (`AGE-SECRET-KEY-1…`) is the **single point of failure for
every backup**. Losing it makes every encrypted backup permanently unreadable.
If an attacker obtains it, they can decrypt any backup they exfiltrate.

### Where the private key lives

The private key **must never** enter:

- A versioned `.env` file
- A log file or console output
- A backup artifact encrypted by itself (circular protection)
- The server's filesystem (except transiently during a restore)

It must be stored **out-of-band**, off the host it protects:

| Store | Suitable for | Notes |
|---|---|---|
| Password manager (Bitwarden, 1Password, KeePassXC) | Primary store | Export the key as a text note; tag it with the hostname and date |
| Encrypted USB drive in a safe | Cold backup | Write the key to a plain text file, encrypt the USB with a different key |
| Paper printout of the base64-encoded key | Last resort | Store in a fireproof safe; test that you can retype it correctly |

### Guardian

The **guardian** is the person responsible for safekeeping the private key and
for producing it during a restore. The guardian must be:

- **Named explicitly** in the organization's operational records (not in this
  repo). For the OpenAvisio homelab deployment, the guardian is the
  **orchestrator/owner** (Gabriel Salem).
- Reachable within the restore SLA (see Restore below).
- The **only** person who can authorise a restore. No restore runs without the
  guardian's explicit approval.

### Restore procedure (guardian-gated)

A restore requires **both** the guardian (who holds the age private key) and an
operator (who has access to the server). They must act together:

1. **Guardian** retrieves the age private key from the password manager and
   transfers it to the operator via an out-of-band channel (encrypted message,
   not email). The key is used once and never stored on the server.
2. **Operator** follows the restore steps below, using the key only transiently
   via `AGE_KEY=/path/to/age-key.txt`.
3. **Guardian** confirms the operator has deleted the key file after the restore
   completes.

```bash
# Guardian provides the key; operator runs:
export AGE_KEY=/path/to/age-key.txt   # brought in by hand, deleted after restore
D=2026-07-13                          # the date you are restoring

# ... restore steps below ...
```

### AGE_PUBKEY fail-closed

The backup script (`deploy/backup/backup.sh`) uses the shell idiom
`: "${AGE_PUBKEY:?set AGE_PUBKEY (age1...) in deploy/.env}"` at line 25. This
means:

- If `AGE_PUBKEY` is **unset or empty**, the script **exits immediately** with a
  non-zero status and a clear error message. It will not produce an unencrypted
  backup or silently skip encryption.
- This is verified by the `set -eu` at line 14 (exit on unset variable) combined
  with the explicit `:?` message.

**The live `.env` must have `AGE_PUBKEY` set to a valid age public key.**
Generate one with `age-keygen` on any machine, keep the private key out-of-band
(see above), and put the public key in `.env`:

```bash
age-keygen -o /tmp/age-key.txt       # generates key pair
cat /tmp/age-key.txt                  # shows both public and private
# Copy the public key line (age1...) into .env as AGE_PUBKEY=age1...
# Store the private key in your password manager
rm /tmp/age-key.txt                   # never leave it on the server
```

## Restore

On a clean host with the stack checked out and `.env` in place (same
`DOCUMENT_ENCRYPTION_KEY` as the dead machine!):

```bash
export AGE_KEY=/path/to/age-key.txt        # the private key, brought in by hand
D=2026-07-13                               # the date you are restoring

# 1. Postgres up, empty
docker compose up -d postgres
docker compose exec -T postgres psql -U "$POSTGRES_USER" -c 'DROP DATABASE IF EXISTS vaultdb;'
docker compose exec -T postgres psql -U "$POSTGRES_USER" -c 'CREATE DATABASE vaultdb;'

# 2. Clinical data, then the keystore — same date, both required
age -d -i "$AGE_KEY" clinical-$D.sql.age \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d vaultdb
age -d -i "$AGE_KEY" keystore-$D.sql.age \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d vaultdb

# 3. Document blobs back into the volume
age -d -i "$AGE_KEY" documents-$D.tar.gz.age \
  | docker run --rm -i -v openavisio_document-data:/data/documents -w /data/documents \
      alpine:3.21 tar -xz

# 4. Bring the rest up (migrations run on backend start)
docker compose up -d
```

Then verify — **do not trust an exit code of 0**:

```bash
# a document must decrypt end to end, not merely exist as a row
docker compose exec -T backend uv run python -c "
import asyncio, json
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.document import DocumentReference
from app.core.patient_keys import get_patient_kek
from app.core.encryption import decrypt_document
from app.core.storage import get_storage

async def main():
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(select(DocumentReference).limit(1))).scalars().first()
        kek = await get_patient_kek(db, doc.patient_id)
        data = decrypt_document(get_storage().read(doc.storage_path), doc.encrypted_dek, kek)
        print('OK', doc.file_name, len(data), 'bytes', data[:5])
asyncio.run(main())
"
```

If that prints `OK … b'%PDF-'`, the restore is real: the database, the blobs,
the keystore and the master KEK all agree.

## Drill

An untested restore is a rumour. Run the drill **on a scratch host**, not on
production, and write the date and the wall-clock time it took into this file:

| Date | By | Duration | Outcome |
|---|---|---|---|
| 2026-07-14 | Claude, scratch host | ~4 min (copy 1s, restore 9s, backend build + decrypt 162s) | **Passed.** 1 patient, 21 documents, 20 conditions, 5 medications, 34 encrypted blobs. Three PDFs decrypted end to end (`%PDF-`, 2.3 MB / 936 KB / 640 KB) with their extracted text. |

**What the drill found before it even started:** the backup script was silently
destroying good backups. A `pg_dump` that died (Postgres briefly down during a
restart) still produced a file, because `pg_dump | age > f` exits with *age's*
status and there was no `pipefail` — and age of an empty stream is ~200 bytes,
which sails through an `[ -s "$f" ]` check. That 200-byte nothing then
overwrote a good 25 MB backup of the same day, and the run logged "ok".

Fixed (`set -o pipefail`, wait for `pg_isready`, a plausible-size floor per
stream). But the lesson is the drill itself: the bug had been sitting there for
a day, the logs said "ok", and only a restore would ever have found it.

## Off-server sync (#144)

Backups on the app server's own disk die with the app server. And a copy on
another container of the same Proxmox host shares its power supply, its disk
shelf and its house fire — off-site is the goal.

The invariant, whatever the target: **whoever compromises the app server must
not be able to destroy the copies.** Two ways to get it:

| Target | Mechanism | Why it holds |
|---|---|---|
| Any box with SSH + cron (A) | **Pull** with a read-only key | No credential for the target exists on the app server |
| Hetzner Storage Box (B) | **Push** + auto-snapshots | The box cannot pull (no shell, no cron); snapshots are immutable even with the box's own credential, so a stolen push key wipes at most the current files |

### Variant A: pull to a self-hosted box

Any plain Debian/Ubuntu/Alpine machine or LXC **off-site** (a VPS, a box at a
relative's house) — it needs rsync, cron and a disk.

On the **target** machine:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/openavisio-pull -N "" -C openavisio-backup-pull
```

On the **app server**, authorize that key read-only, jailed to the backup dir
(`rrsync` ships with rsync — Debian: `apt install rrsync`):

```
# /root/.ssh/authorized_keys
command="rrsync -ro /opt/openavisio-backups",restrict ssh-ed25519 AAAA… openavisio-backup-pull
```

On the **target**, `/etc/cron.d/openavisio-backup-pull` (backups finish ~03:00,
pull at 04:17):

```
17 4 * * * root rsync -a -e "ssh -i /root/.ssh/openavisio-pull" root@APP_SERVER:/ /srv/openavisio-backups/ && find /srv/openavisio-backups -name 'keystore-*' -mtime +7 -delete && find /srv/openavisio-backups \( -name 'clinical-*' -o -name 'documents-*' \) -mtime +90 -delete
```

Two deliberate choices in that line:

- **No `--delete`.** A mirror faithfully copies sabotage: whoever wipes
  `/opt/openavisio-backups` on the app server would wipe the copies on the next
  pull. The target does its own pruning instead —
- **which must match the source retention, because of ADR 031.** Crypto-shredding
  only reaches backups if an erased patient's KEK ages out of *every* keystore
  copy. A sync target that hoards keystore dumps forever quietly breaks the
  erasure guarantee. The `find -mtime +7` on `keystore-*` **is** that guarantee —
  do not "improve" it to keep more.

Freshness check (cron mails stderr): the newest clinical dump on the target must
be younger than 26 h —

```
0 6 * * * root find /srv/openavisio-backups -name 'clinical-*' -mmin -1560 | grep -q . || echo "openavisio backup pull is STALE" >&2
```

If the target's filesystem is ZFS or btrfs, add a daily snapshot of the backup
dataset — that upgrades variant A to the same stolen-credential immunity as
variant B.

### Variant B: push to a Hetzner Storage Box

A BX11 (1 TB, ~€4/mo) is more than enough. Setup in the Hetzner Robot panel:

1. Order the Storage Box; enable **SSH support** in its settings.
2. Create a **sub-account** scoped to a directory (e.g. `openavisio`) — the app
   server gets only this, never the main account.
3. Upload the app server's public key (`ssh-keygen -t ed25519 -f
   /root/.ssh/storagebox -N ""`, then paste the `.pub` via the panel or
   `ssh -p23 uXXXXXX@uXXXXXX.your-storagebox.de install-ssh-key` — check
   Hetzner's current docs, the mechanism has changed before).
4. Enable the **automatic snapshot plan**: daily, keep 7. This step is not
   optional — without snapshots, push is strictly worse than pull.

On the **app server**, `/etc/cron.d/openavisio-backup-push` (backups finish
~03:00, push at 04:17; Storage Box SSH listens on **port 23**):

```
17 4 * * * root rsync -a --delete -e "ssh -p23 -i /root/.ssh/storagebox" /opt/openavisio-backups/ uXXXXXX-sub1@uXXXXXX.your-storagebox.de:./
0 6 * * * root find /opt/openavisio-backups -name 'clinical-*' -mmin -1560 | grep -q . || echo "openavisio backup is STALE" >&2
```

`--delete` is correct **here** (and wrong in variant A): the source dir is
already retention-pruned by `backup.sh`, so mirroring it propagates the ADR-031
aging to the box — and sabotage-by-mirror is what the snapshots are for.

**ADR-031 consequence of snapshots:** a keystore dump lives 7 days in the
mirror plus up to 7 more in snapshots. An erased patient's KEK is therefore
gone from *everything* after ~14 days, not 7. That is acceptable — but it is
the number to quote when someone asks how long erasure takes to reach backups.

### Either way

Verify the same way the drill does: once, run a restore **from the target's
copies** on a scratch host. A synced file that never restored is still a rumour.

## Monitoring

The `backup` container's healthcheck turns **unhealthy** when `.last-success` is
older than 26 hours, so a silently dead backup shows up in `docker compose ps`.
That is the floor, not a substitute for real alerting (#115).
