# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Project Regret** (working name: **IonNet**) is a prototype peer-to-peer encrypted chunked storage network in Python. Files uploaded to a central coordinator are split into 100KB chunks, Fernet-encrypted, replicated across storage nodes, and self-heal when nodes die. Everything talks plain HTTP.

Requires Python 3.9+. No CI or unit test framework; the test story is the two end-to-end scripts below.

```
pip install -r requirements.txt
```

## Commands

```bash
# Coordinator (FastAPI, port 8000 — node_config.py's default COORDINATOR_URL expects it there)
uvicorn Coordinator:app --port 8000

# Storage node (Flask). Configure via env: NODE_ID, NODE_PORT (default 5001),
# CHUNK_FOLDER, COORDINATOR_URL — so N real nodes can run side by side
NODE_ID=node-5001 NODE_PORT=5001 python node_server.py

# Node heartbeat client (same env vars; registers + heartbeats every 5s, re-registers on 404)
NODE_ID=node-5001 NODE_PORT=5001 python client_node.py

# THE test: full chaos exam — boots a real coordinator + 4 real node pairs as
# subprocesses, tests round-trip, upload collision, node-kill healing, and
# coordinator restart. Self-cleaning; uses ports 18000/15001-15004.
python CHAOSTEST.py

# Legacy quick smoke test (phantom nodes, needs a coordinator already running on 8000)
python SMOKETEST.py
```

There are no unit tests — CHAOSTEST.py is the acceptance gate; run it after any change to the chunk lifecycle, healing, or manifests. The closest thing to "one test" is a single stage function in it, or e.g. `python -c "import SMOKETEST; SMOKETEST.verify_status()"`.

Runtime state lands in `work_dir/` (created at import time by `config.py`) and `chunks/` (created by `node_server.py`); both are gitignored. `work_dir/manifest_master.key` is the coordinator's manifest encryption key — deleting it permanently orphans every stored file.

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

## Known rough edges

(The Phase 0 bug wave — chunk-ID collisions between uploads, the ephemeral manifest key, nodes never re-registering after coordinator restart, healer double-counting replicas, cwd-relative chunk folders — was fixed and is guarded by CHAOSTEST.py.)

- A chunk with zero surviving replicas is declared unhealable and **silently dropped** from the healing queue; `/status` does not surface it.
- The healer re-uploads chunks with `files={"chunk": res.content}` (bare bytes, no filename tuple like the upload path uses) — works, but relies on requests' default part naming.
- The coordinator is a single point of failure and its `nodes`/`chunk_map` registries are RAM-only (manifests are the durable record).
- Per-file encryption keys are stored in plaintext inside the (master-key-encrypted) manifests.

## Docs and conventions

- `chunkboard.md` — the project status board: feature table, roadmap (finish encryption → auto-rebalancing → "ChunkCompute" engine → Python SDK → Mininet emulation), and team conventions, notably *"Code ugly now, refine later. Freedom > premature optimization."*
- `MANIFEST_OF_CHUNKDEPENDENCE.md` — a parody Declaration of Independence that doubles as the design-principles doc; its seven Articles map to real invariants (redundancy + healing, per-owner keys, nodes never inspect chunk contents, manifest-as-a-chunk).
- **Commit-message vocabulary:** "plymouth rock" commits are milestones (founding-fathers theme); "crypteia" refers to the encryption workstream. The codebase is written in an emoji-heavy, jokey comment voice (`# ====== 📤 Upload + Chunkify + Encrypt ======`) — match the surrounding style when editing.
- History trivia: commit `07b146b` ("oops") removed `Mondays_back_up`, an accidentally committed private chat log. It remains recoverable from git history — don't commit chat logs or other private files here.
