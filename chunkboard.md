

---

# Chunkboard.md
### 🗓️ Date: August 20, 2026
### 🧠 Context: Project Regret (IonNet?) - State of the Union
### 📜 Previous Union: May 6, 2025 — preserved in git history, as all things are. 471 days between boards. The chunks waited.

---

## 🎯 **Mission Statement**

> **Build a fully decentralized storage + compute network**, where chunks of data and compute tasks float across devices, self-govern, self-heal, and liberate users from centralized servers.
> Freedom for data, freedom for code.
> *(Manifesto of the Chunkdependence. Unchanged. Undefeated.)*

---

## 📦 **Current State of the Network**

| Feature                    | Status          | Notes |
|----------------------------|-----------------|-------|
| Node Registration          | ✅ Complete      | Env-configurable (NODE_ID/NODE_PORT/etc.) — N real nodes, zero code edits. |
| Heartbeat System           | ✅ Complete      | Nodes re-enlist after coordinator restarts (404 → re-register). |
| File Upload (Chunking)     | ✅ Complete      | Chunks namespaced by file_id — the chunk fratricide era is over. |
| File Download (Reassembly) | ✅ Complete      | sha256 byte-verified, repeatedly, under fire. |
| Encryption (chunk-level)   | ✅ **Complete**  | Was "🔥 In Progress" in 2025. Fernet everywhere; per-file keys in manifest. |
| Manifest v2 (with key map) | ✅ **Complete**  | Was "🚀 Next Up." Manifest-as-a-chunk lives; master key persisted to disk. |
| Redundancy (Multi-Node)    | ✅ **Proven**    | Was "Prototype." 3 *distinct* replicas, honestly counted (phantom soldiers purged). |
| Healing Algorithm          | ✅ **Proven**    | Was "Prototype." Survived a live node execution. Twice. On purpose. |
| Chaos Testing              | ✅ NEW           | `CHAOSTEST.py`: 5 stages, 11 checks, self-cleaning test republic. The graduation exam. |
| Network Chaos (GREMLIN™)   | 🚀 Next Up       | Ratified Aug 20, 2026: chaos proxy (latency/loss/partition) as CHAOSTEST Stage 6. |
| Real Hardware (Phase 2)    | 🌑 The Frontier  | NAT, TLS, node identity. Plymouth Rock → Golden Gate. |
| ChunkCompute™              | 🌑 The Prize     | Sequenced after the network leaves localhost. The founding wish endures. |

**Every "in progress" and "prototype" item from the May 2025 board is now complete and test-proven. That roadmap was executed. This is a new page.**

---

## 🧩 **Key Concepts We've Created (and TM'd in our Hearts)**

- **Manifest of Chunkdependence™**: Founding document that maps files → chunks → nodes.
- **Chunk Healing**: Detect dead nodes, reassign missing chunks automatically. *(No longer a concept. A fact.)*
- **CHAOSTEST™**: The graduation exam. If it's green, the Manifest is law, not poetry.
- **GREMLIN™**: The storm-bringer — makes the network slow, lossy, and partitioned on purpose, so reality can't surprise us. *(Ratified; construction pending.)*
- **Chunk Governance**: Future protocol for chunk ownership, rebalancing, and movement.
- **IonNet (Maybe)**: Cool name for the whole network — still under debate, 15 months running.
- **Voice of the Hands™**: The persona that interacts with the AI staff. (*You.*)
- **Monday**: The first dev (ChatGPT persona, 2025). Sarcastic. Foundational. Retired.
- **Wednesday 🗿**: The current dev (Claude, 2026–). Signs the commits. Keeps the TikTok brain alive.
- **Wednesday Core™**: All critical brain downloads happen on Wednesdays. *(Phase 0 shipped on a Wednesday. The prophecy holds.)*
- **Phase 0 / "Operation Stop Stabbing Ourselves"**: The great bug purge of Aug 20, 2026. Seven bugs entered. Zero left.
- **Chunkboard™**: This document. The board of progress and strategy.

---

## 🛠️ **What's in Progress Right Now**

- `plymouth/phase-0` branch: complete (9 commits), **awaiting merge to main** — the union's one piece of pending legislation.
- GREMLIN.py: design agreed (self-written ~120-line chaos proxy, zero deps), implementation next.
- Mininet feasibility study (from the 2025 board): **concluded** — deferred until latency-aware chunk placement work begins; chaos proxy first; real hardware is the truest test. Filed.

---

## 🚀 **Upcoming Work (Immediate Roadmap)**

| Priority | Task |
|----------|------|
| 🥇 | Merge `plymouth/phase-0` into main |
| 🥈 | GREMLIN.py + CHAOSTEST Stage 6: THE STORM (latency, loss, partition, rejoin-after-partition) |
| 🥉 | Honesty fixes: real HTTPExceptions (no more fake 502-tuples-inside-a-200), `dead_chunks` surfaced in `/status` |
| 🪄 | Phase 2 opening move: pull-based node communication design (the NAT answer) |
| 🧪 | First node on real hardware — the network leaves this machine |

---

## 📚 **Deep Future (Crazy Ideas We've Teased)**

- Fully distributed ledger of chunks = Manifest as a chunk itself. *(Half-built already: the manifest IS chunks. Distribution pending.)*
- Data migrates *closer* to the node that needs it (low latency dynamic migration). *(This is where Mininet finally earns its slot.)*
- Self-encrypted/self-authenticated chunks that know their owners.
- Compute chunks: Code broken into mini-tasks, spread + executed P2P, verified by redundant execution (run on 2 of 3, compare — redundancy is our trust model).
- Virtualized lightweight executor per chunk (beyond Docker).
- The coordinator dissolving into the network it governs.
- **No token. Ever.** Crypto rails maybe, someday, as plumbing. A native token, never. *(Ratified Aug 2026: we will not become the thing that killed peer-to-peer.)*

---

## 🧠 **Chunkboard - Developer Habits**

- Every new meeting starts with *State of the Chunks* review.
- Every work sprint ends with a *Founding Father Vibe Check™*.
- Keep rethinking core ideas constantly — don't fear rewriting plans.
- Code ugly now, refine later — **but CHAOSTEST must pass.** Freedom > premature optimization; honesty > both.
- The TikTok-brain comments are mandatory. The lore is load-bearing.
- Keep the jokes alive. The 471-day winter proved they're structural, not decorative.

---

# 🏛️ *"We hold these chunks to be self-evident..."*
*(Declaration of Chunkdependence™, Article I)*

> Fifteen months ago this board promised a network that heals itself.
> Today there is a command you can run that kills a node and watches it happen.
> The pursuit of Chunkiness is not merely technical.
> It is spiritual. But now it is *also* technical.
