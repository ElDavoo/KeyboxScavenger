# Keybox Scavenger Backend

Telegram userbot that watches selected groups/channels for XML keyboxes, validates them, and stores only valid ones.

## What It Does

- Monitors configured Telegram chats/channels (user account, not bot token).
- Accepts XML documents and validates them with the same keybox checks used in this project.
- Normalizes XML before validation/storage (removes comments, standard formatting) to avoid duplicate files caused only by formatting differences.
- Stores valid files in a dedicated folder:
  - `<sha256>.xml` (content-addressed)
  - `keybox.xml` (latest valid snapshot)

## Prerequisites

- Docker and Docker Compose
- Nix (with flakes enabled) if you want the Nix-based workflow
- Telegram user API credentials from https://my.telegram.org:
  - `SCAVENGER_API_ID`
  - `SCAVENGER_API_HASH`

## Nix Workflow

If you use Nix, this repository now provides a flake with a Python 3.14 dev shell.

### Enter the dev shell

```bash
nix develop path:.
```

Inside the shell:

```bash
pdm install --prod
pdm run scavenger
```

### Run flake checks/evaluation

```bash
nix flake show path:.
nix flake check path:.
```

## First-Time Setup (Recommended Path)

### 1) Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `SCAVENGER_API_ID`
- `SCAVENGER_API_HASH`
- `SCAVENGER_TARGETS` (CSV of chat IDs/usernames)

Examples for `SCAVENGER_TARGETS`:

- `-1001234567890`
- `@my_channel,my_group,-1001234567890`

### 2) Build image

```bash
docker compose build
```

### 3) One-time authorization: generate `SCAVENGER_SESSION_STRING`

This project expects an already authorized Telethon session.

Run:

```bash
docker compose run --rm -it --entrypoint python keybox-scavenger - <<'PY'
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

api_id = int(os.environ["SCAVENGER_API_ID"])
api_hash = os.environ["SCAVENGER_API_HASH"]

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nSCAVENGER_SESSION_STRING=" + client.session.save())
PY
```

- Telegram will ask for your phone/code (and 2FA password if enabled).
- Copy the printed value into `.env` as `SCAVENGER_SESSION_STRING=...`.

### 4) Start the service

```bash
docker compose up -d
```

### 5) Check logs

```bash
docker compose logs -f keybox-scavenger
```

You should see target resolution logs and then message scanning activity.

## Alternative: Session File Instead of Session String

If you do not want `SCAVENGER_SESSION_STRING`, leave it empty and create an authorized session file once:

```bash
docker compose run --rm -it --entrypoint python keybox-scavenger - <<'PY'
from telethon.sync import TelegramClient
import os

api_id = int(os.environ["SCAVENGER_API_ID"])
api_hash = os.environ["SCAVENGER_API_HASH"]
session_name = os.environ.get("SCAVENGER_SESSION_NAME", "/app/data/session/scavenger")

with TelegramClient(session_name, api_id, api_hash) as client:
    client.start()
    print("Authorized session file created:", session_name + ".session")
PY
```

Then run normally with:

```bash
docker compose up -d
```

## Where Output Is Stored

Inside container:

- `/app/data/keyboxes/<sha256>.xml`
- `/app/data/keyboxes/keybox.xml`

Compose persists these in the `keybox_data` volume.

## Common First-Run Issues

- `The Telegram session is not authorized...`
  - Create `SCAVENGER_SESSION_STRING` (recommended) or session file using the commands above.
- `SCAVENGER_TARGETS must contain at least one target`
  - Set `SCAVENGER_TARGETS` in `.env`.
- `No target chats resolved from SCAVENGER_TARGETS`
  - Verify IDs/usernames, and that your Telegram account can access those chats.

## Updating

After config or code changes:

```bash
docker compose up -d --build
```

## Stopping

```bash
docker compose down
```
