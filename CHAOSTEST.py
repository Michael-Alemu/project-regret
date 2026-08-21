# ==========================================================
# 💀 CHAOSTEST.py — The Kill-A-Node Graduation Exam
# ==========================================================
# SMOKETEST's older, meaner sibling. No phantom nodes, no mercy.
# Boots a REAL coordinator + 4 REAL node pairs as subprocesses, then:
#
#   1. 🥾 BOOT       — raise the republic from nothing (every node behind a GREMLIN)
#   2. 🔁 ROUND-TRIP — upload, verify 3x replication, download, byte-compare
#   3. 👯 COLLISION  — upload a second file; the first must survive (fratricide probe)
#   4. 🔪 KILL       — execute a node; healing must restore 3 DISTINCT replicas
#   5. 🔄 RESTART    — bounce the coordinator; keys persist, nodes re-enlist
#   6. 🌩️ THE STORM  — latency, unreachable replicas, full partition + rejoin
#
# If all six pass, the Manifest of Chunkdependence is law, not poetry.
# Run it: python CHAOSTEST.py   (needs requirements.txt installed)
# ==========================================================
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import requests

from GREMLIN import Gremlin  # 👹 the storm-bringer reports for duty

REPO = os.path.dirname(os.path.abspath(__file__))  # where the constitution lives
COORD_PORT = int(os.environ.get("CHAOS_COORD_PORT", "18000"))  # off the beaten 8000
COORD = f"http://localhost:{COORD_PORT}"
NODE_PORTS = [15001, 15002, 15003, 15004]  # four citizens
SERVE_GREMLIN_OFFSET = 1000  # gremlin doorway for coordinator->node traffic
HB_GREMLIN_OFFSET = 2000     # gremlin doorway for node->coordinator traffic
REDUNDANCY = 3  # must match Coordinator.CHUNK_REDUNDANCY

procs = []           # every subprocess we owe a funeral to
node_procs = {}      # node_id -> [server_proc, client_proc]
serve_gremlins = {}  # node_id -> Gremlin guarding the node's front door
hb_gremlins = {}     # node_id -> Gremlin guarding the node's line to the boss
results = []         # (label, passed)


# ==========================================================
# 🧰 Tiny helpers (the interns of this operation)
# ==========================================================
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(label, ok, detail=""):
    """📋 The examiner's red pen. Records and announces."""
    results.append((label, bool(ok)))
    print(f"{'✅ PASS' if ok else '❌ FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
    return ok


def wait_for(what, fn, timeout, interval=2):
    """⏳ Poll fn() until truthy or the clock runs out. Patience, but with limits."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if fn():
                return True
        except Exception:
            pass  # the network is young and fragile, forgive it
        time.sleep(interval)
    print(f"⌛ Gave up waiting for: {what}")
    return False


def get_manifest(file_id):
    return requests.get(f"{COORD}/manifest/{file_id}", timeout=5).json()


def download(file_id):
    r = requests.get(f"{COORD}/download_file/{file_id}", timeout=30)
    return r.status_code, r.content


def spawn(cmd, cwd, env_extra=None):
    """🐣 Hatch a subprocess and remember it for the inevitable purge."""
    env = dict(os.environ, PYTHONPATH=REPO, **(env_extra or {}))
    p = subprocess.Popen(cmd, cwd=cwd, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p


def start_coordinator(cwd):
    return spawn([sys.executable, "-m", "uvicorn", "Coordinator:app",
                  "--port", str(COORD_PORT)], cwd=cwd)


def start_node(node_id, port, node_dir):
    """🏠 One node = a Flask blob store + a heartbeat client, roommates forever.

    Every node lives behind TWO gremlins from birth:
    - serve gremlin: coordinator -> node (the advertised port is the gremlin's)
    - heartbeat gremlin: node -> coordinator (COORDINATOR_URL points at it)
    Calm gremlins are invisible. Stormy gremlins are Stage 6.
    """
    serve_g = Gremlin(port + SERVE_GREMLIN_OFFSET, "127.0.0.1", port,
                      name=f"{node_id}-door").start()
    hb_g = Gremlin(port + HB_GREMLIN_OFFSET, "localhost", COORD_PORT,
                   name=f"{node_id}-bossline").start()
    serve_gremlins[node_id] = serve_g
    hb_gremlins[node_id] = hb_g

    env = {"NODE_ID": node_id, "NODE_PORT": str(port),
           "ADVERTISE_PORT": str(port + SERVE_GREMLIN_OFFSET),  # 📣 the doorway, not the room
           "CHUNK_FOLDER": os.path.join(node_dir, "chunks"),
           "COORDINATOR_URL": f"http://localhost:{port + HB_GREMLIN_OFFSET}"}
    server = spawn([sys.executable, os.path.join(REPO, "node_server.py")], node_dir, env)
    client = spawn([sys.executable, os.path.join(REPO, "client_node.py")], node_dir, env)
    node_procs[node_id] = [server, client]


def execute_node(node_id):
    """🔪 A public execution. The healer's moment to shine."""
    for p in node_procs[node_id]:
        p.terminate()
    print(f"🔪 {node_id} has been executed at {time.strftime('%H:%M:%S')}.")


# ==========================================================
# 🎓 The Exam
# ==========================================================
def main():
    run_dir = tempfile.mkdtemp(prefix="chaostest_")
    coord_dir = os.path.join(run_dir, "coord")
    os.makedirs(coord_dir)

    # ---------- 🥾 STAGE 1: BOOT ----------
    print("\n🥾 STAGE 1: BOOT — raising the republic")
    start_coordinator(coord_dir)
    for port in NODE_PORTS:
        node_dir = os.path.join(run_dir, f"node{port}")
        os.makedirs(node_dir)
        start_node(f"node-{port}", port, node_dir)

    ok = wait_for("4 nodes registered",
                  lambda: len(requests.get(f"{COORD}/nodes", timeout=3).json()) == 4,
                  timeout=30)
    if not check("boot: coordinator up, 4 real nodes registered", ok):
        return  # no republic, no exam

    # ---------- 🔁 STAGE 2: ROUND-TRIP ----------
    print("\n🔁 STAGE 2: ROUND-TRIP — the sacred loop")
    rng = random.Random(1776)  # seeded, because chaos should be reproducible
    payload_a = bytes(rng.getrandbits(8) for _ in range(350 * 1024))  # 4 chunks
    digest_a = sha256(payload_a)

    r = requests.post(f"{COORD}/upload_file",
                      files={"file": ("declaration.bin", payload_a)}, timeout=30)
    file_a = r.json()["file_id"]
    check("upload accepted (4 chunks)", r.status_code == 200 and r.json()["chunks_stored"] == 4,
          str(r.json()))

    man = get_manifest(file_a)
    reps = [c["node_ids"] for c in man["chunks"]]
    check("every chunk on 3 distinct nodes",
          all(len(n) == REDUNDANCY and len(set(n)) == REDUNDANCY for n in reps), f"{reps}")

    code, body = download(file_a)
    check("download is byte-identical", code == 200 and sha256(body) == digest_a,
          f"{len(body)} bytes")

    # ---------- 👯 STAGE 3: COLLISION PROBE ----------
    print("\n👯 STAGE 3: COLLISION — two files must coexist (no fratricide)")
    payload_b = bytes(rng.getrandbits(8) for _ in range(250 * 1024))  # 3 chunks
    r = requests.post(f"{COORD}/upload_file",
                      files={"file": ("federalist.bin", payload_b)}, timeout=30)
    file_b = r.json()["file_id"]

    code, body = download(file_a)
    check("first file survives second upload", code == 200 and sha256(body) == digest_a)
    code, body = download(file_b)
    check("second file intact too", code == 200 and sha256(body) == sha256(payload_b))

    # ---------- 🔪 STAGE 4: KILL-A-NODE ----------
    print("\n🔪 STAGE 4: KILL-A-NODE — the core promise, tested in blood")
    man = get_manifest(file_a)
    holders = [nid for c in man["chunks"] for nid in c["node_ids"]]
    victim = max(set(holders), key=holders.count)  # the busiest citizen dies (drama)
    execute_node(victim)

    def healed():
        m = get_manifest(file_a)
        chunks = m.get("chunks", [])
        return chunks and all(
            victim not in c["node_ids"]
            and len(c["node_ids"]) == REDUNDANCY
            and len(set(c["node_ids"])) == REDUNDANCY  # DISTINCT — no phantom soldiers
            for c in chunks)

    check("healing restored 3 distinct replicas, victim purged",
          wait_for("healing to finish", healed, timeout=120, interval=3),
          json.dumps({c["chunk_id"]: c["node_ids"] for c in get_manifest(file_a)["chunks"]}))

    code, body = download(file_a)
    check("post-heal download is byte-identical", code == 200 and sha256(body) == digest_a)

    # ---------- 🔄 STAGE 5: RESTART EXAM ----------
    print("\n🔄 STAGE 5: RESTART — the republic must remember")
    coord_proc = procs[0]
    coord_proc.terminate()
    coord_proc.wait(timeout=10)
    print("🪦 Coordinator buried. Resurrecting...")
    start_coordinator(coord_dir)  # same cwd -> same work_dir -> same master key

    ok = wait_for("coordinator back up",
                  lambda: requests.get(f"{COORD}/status", timeout=3).status_code == 200,
                  timeout=30)
    status = requests.get(f"{COORD}/status", timeout=5).json() if ok else {}
    check("manifests survive the restart (no amnesia)",
          ok and status.get("manifest_errors") == [], f"errors={status.get('manifest_errors')}")

    # survivors should notice the 404s and re-enlist (3 nodes still alive)
    check("nodes re-register after restart",
          wait_for("3 nodes to re-enlist",
                   lambda: len(requests.get(f"{COORD}/nodes", timeout=3).json()) >= 3,
                   timeout=45))

    code, body = download(file_a)
    check("file downloadable after full restart", code == 200 and sha256(body) == digest_a)

    # ---------- 🌩️ STAGE 6: THE STORM ----------
    print("\n🌩️ STAGE 6: THE STORM — the gremlins wake up")
    survivors = sorted(requests.get(f"{COORD}/nodes", timeout=5).json().keys())

    # 6a: 🐌 latency storm — every node's door gets 500ms slower. Truth must survive lag.
    print("  🐌 6a: latency storm (500ms on every door)")
    for nid in survivors:
        serve_gremlins[nid].latency = 0.5
    code, body = download(file_a)
    check("storm: download intact through 500ms latency",
          code == 200 and sha256(body) == digest_a)
    for nid in survivors:
        serve_gremlins[nid].calm()

    # 6b: 🙈 unreachable replica — one node alive (still heartbeating) but its
    # door is bricked. Downloads must fall through to the other replicas.
    blindfolded = survivors[0]
    print(f"  🙈 6b: {blindfolded} is alive but unreachable (asymmetric partition)")
    serve_gremlins[blindfolded].partitioned = True
    code, body = download(file_a)
    check("storm: download survives an unreachable-but-alive replica",
          code == 200 and sha256(body) == digest_a)
    serve_gremlins[blindfolded].calm()

    # 6c: 🏝️ full partition + rejoin — a node becomes an island: no serving, no
    # heartbeats. The republic must bury it, limp on 2 replicas, then — when the
    # island reconnects — re-enlist it and let the Patrol restore full redundancy.
    castaway = survivors[1]
    print(f"  🏝️ 6c: {castaway} is fully partitioned (the island years)")
    serve_gremlins[castaway].partitioned = True
    hb_gremlins[castaway].partitioned = True

    check("storm: partitioned node declared dead",
          wait_for(f"{castaway} to be buried",
                   lambda: castaway not in requests.get(f"{COORD}/nodes", timeout=3).json(),
                   timeout=60))
    check("storm: castaway purged from manifest",
          wait_for("manifest purge",
                   lambda: all(castaway not in c["node_ids"]
                               for c in get_manifest(file_a)["chunks"]),
                   timeout=30))
    code, body = download(file_a)
    check("storm: download intact on 2 replicas (degraded but honest)",
          code == 200 and sha256(body) == digest_a)

    print(f"  🛶 6c: the island reconnects — {castaway} paddles home")
    serve_gremlins[castaway].calm()
    hb_gremlins[castaway].calm()

    check("storm: castaway re-enlists after rejoin",
          wait_for(f"{castaway} to re-register",
                   lambda: castaway in requests.get(f"{COORD}/nodes", timeout=3).json(),
                   timeout=45))

    def fully_replicated():
        chunks = get_manifest(file_a).get("chunks", [])
        return chunks and all(len(set(c["node_ids"])) == REDUNDANCY for c in chunks)

    check("storm: Patrol restores 3 distinct replicas after rejoin",
          wait_for("the Patrol to finish its rounds", fully_replicated, timeout=90, interval=5),
          json.dumps({c["chunk_id"]: c["node_ids"] for c in get_manifest(file_a)["chunks"]}))

    code, body = download(file_a)
    check("storm: final download byte-identical after the storm passes",
          code == 200 and sha256(body) == digest_a)

    return run_dir


if __name__ == "__main__":
    run_dir = None
    try:
        run_dir = main()
    finally:
        # ---------- 🧹 TEARDOWN: leave no orphans, take no prisoners ----------
        print("\n🧹 TEARDOWN — burying the test republic")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass
        if run_dir:
            shutil.rmtree(run_dir, ignore_errors=True)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{'🏛️' if passed == len(results) else '🔥'} VERDICT: {passed}/{len(results)} checks passed.")
    if results and passed == len(results):
        print("The Manifest of Chunkdependence is LAW. Class dismissed. 🎓")
    sys.exit(0 if (results and passed == len(results)) else 1)
