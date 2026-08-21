# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Project Regret** (working name: **IonNet**) is a prototype peer-to-peer encrypted chunked storage network in Python. Files uploaded to a central coordinator are split into 100KB chunks, Fernet-encrypted, replicated across storage nodes, and self-heal when nodes die. Everything talks plain HTTP.

There is no package manifest, no lockfile, no CI, no unit test framework, and no `.gitignore`. Dependencies must be installed manually:

```
pip install fastapi uvicorn pydantic flask requests cryptography python-multipart
```

## Commands

```bash
# Coordinator (FastAPI, port 8000 — node_config.py expects it there)
uvicorn Coordinator:app --port 8000

# Storage node (Flask, port hardcoded to 5001 in node_config.py)
python node_server.py

# Node heartbeat client (registers with coordinator, heartbeats every 5s)
python client_node.py

# The only test harness: end-to-end smoke test (upload → manifest → status → download)
python SMOKETEST.py
```

There are no unit tests, so there is no "run a single test" — the closest is calling one smoke-test step directly, e.g. `python -c "import SMOKETEST; SMOKETEST.verify_status()"`.

**Smoke test gotchas:**
- `SMOKETEST.py` hardcodes `TEST_FILE_PATH` to an absolute path *outside this repo*; it cannot run as-is unless that file exists (or the path is edited).
- It assumes three nodes on ports 5001–5003, but `node_config.py` hardcodes `PORT = 5001` and a random `NODE_ID` per process — you cannot start three real nodes without editing `node_config.py`. The smoke test registers phantom nodes with the coordinator regardless.
- Runtime state lands in `work_dir/` (created at import time by `config.py`) and `chunks/` (created by `node_server.py`). Neither is gitignored — don't commit them.

## Architecture

Two tiers: **one coordinator** (control plane + data broker) and **N storage nodes** (dumb blob stores that never see plaintext).

- **`Coordinator.py`** — the bulk of the system. FastAPI app holding two in-RAM dicts: `nodes` (node_id → ip/port/storage/last_seen) and `chunk_map` (chunk_id → node_ids). Endpoints: `/register`, `/heartbeat`, `/nodes`, `/chunk/{id}`, `/chunk`, `/keys`, `/manifest/{file_id}`, `/upload_file`, `/download_file/{file_id}`, `/status`, `/heal_now`.
- **`node_server.py`** — Flask blob store: only `POST /store_chunk` and `GET /chunk/<chunk_id>`. Stores whatever encrypted bytes it's handed. Node identity/heartbeat is a separate process (`client_node.py`).
- **Upload path:** temp save → per-file Fernet key → `split_file()` into 100KB chunks (`chunk_utils.py`) → encrypt each chunk → replicate to `CHUNK_REDUNDANCY = 3` random nodes → save manifest (`{original_filename, chunks, encryption_key}`) → clean temp files.
- **Download path:** load manifest → for each chunk try each holding node until one answers → decrypt → reassemble → `FileResponse` with cleanup queued as a FastAPI `BackgroundTask`.
- **Manifest v2** (`manifest_utils.py`, `ManifestChunkManager`): the manifest is *itself* chunked and encrypted — JSON → 4096-byte slices → Fernet-encrypted → `work_dir/manifests/{file_id}_manifest_chunk_{idx:04d}.bin`. This implements "Manifest as a Chunk" (Article VII of `MANIFEST_OF_CHUNKDEPENDENCE.md`). Writes are guarded by a single `threading.Lock`; `update_manifest` is a destructive rewrite.
- **Encryption** (`crypto_utils.py`): Fernet throughout. `generate_key()` deliberately returns a base64 **str** so keys are JSON-serializable inside manifests; `_normalize_key()` coerces str-or-bytes back to valid Fernet bytes. Two key layers: a per-file key stored inside the manifest (encrypts data chunks), and a coordinator-wide manifest key generated at import time in `Coordinator.py`.
- **Healing:** heartbeats reap nodes not seen for `HEARTBEAT_TIMEOUT = 30`s; `mark_node_dead()` strips the node from every manifest and queues under-replicated chunks in `healing_queue`; a daemon thread (`heal_chunks`, started at module import) copies still-encrypted chunks from a surviving donor to fresh nodes until redundancy is restored.
- **Config split:** `config.py` is coordinator-side (`work_dir` layout, `CHUNK_SIZE_BYTES`, import-time mkdirs); `node_config.py` is node-side (`NODE_ID`, `PORT`, `COORDINATOR_URL`). `chunk_utils.py` and `crypto_utils.py` are leaf utilities with no project imports.

## Known landmines

- **The manifest encryption key is ephemeral.** `manifest_encryption_key` is regenerated at every coordinator start and never persisted, so manifests written by a previous run cannot be decrypted after a restart — despite the commit history claiming restart survival. `/status` swallows these failures into a `manifest_errors` list instead of crashing. This is the biggest latent bug.
- `POST /heal_now` spawns an additional competing healer daemon on every call.
- The healer re-uploads chunks with `files={"chunk": res.content}` (no filename tuple, unlike the upload path).
- A chunk with zero surviving replicas is declared unhealable and silently dropped from the queue.

## Docs and conventions

- `chunkboard.md` — the project status board: feature table, roadmap (finish encryption → auto-rebalancing → "ChunkCompute" engine → Python SDK → Mininet emulation), and team conventions, notably *"Code ugly now, refine later. Freedom > premature optimization."*
- `MANIFEST_OF_CHUNKDEPENDENCE.md` — a parody Declaration of Independence that doubles as the design-principles doc; its seven Articles map to real invariants (redundancy + healing, per-owner keys, nodes never inspect chunk contents, manifest-as-a-chunk).
- **Commit-message vocabulary:** "plymouth rock" commits are milestones (founding-fathers theme); "crypteia" refers to the encryption workstream. The codebase is written in an emoji-heavy, jokey comment voice (`# ====== 📤 Upload + Chunkify + Encrypt ======`) — match the surrounding style when editing.
- History trivia: commit `07b146b` ("oops") removed `Mondays_back_up`, an accidentally committed private chat log. It remains recoverable from git history — don't commit chat logs or other private files here.
