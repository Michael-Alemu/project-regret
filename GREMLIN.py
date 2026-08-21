# ==========================================================
# 👹 GREMLIN.py — The Storm-Bringer
# ==========================================================
# A tiny TCP chaos proxy. Park one between the coordinator and a node,
# then make the weather: latency, jitter, dropped connections, or a full
# partition blackout. Reality WILL do all of this to us eventually —
# GREMLIN just lets us schedule the suffering.
#
# Zero dependencies. Pure sockets and spite.
#
# In code (how CHAOSTEST uses it):
#     g = Gremlin(16001, "127.0.0.1", 15001, name="node-15001").start()
#     g.latency = 0.5          # every new connection waits half a second
#     g.jitter = 0.2           # ...plus up to 200ms of random mood
#     g.drop = 0.25            # 25% of new connections die at the door
#     g.partitioned = True     # total blackout. the node is an island
#     g.calm()                 # the storm passes, all settings reset
#
# From the CLI (manual mischief):
#     python GREMLIN.py 16001 127.0.0.1:15001 --latency 0.5
# ==========================================================
import random
import socket
import sys
import threading
import time


class Gremlin:
    """👹 One gremlin, one doorway. It decides who gets through and how late."""

    def __init__(self, listen_port, target_host, target_port, name="gremlin"):
        self.listen_port = listen_port
        self.target = (target_host, target_port)
        self.name = name
        # 🌦️ The weather dials. All calm by default — gremlins are lazy until provoked.
        self.latency = 0.0      # seconds added before each new connection
        self.jitter = 0.0       # extra random delay, 0..jitter seconds
        self.drop = 0.0         # probability a new connection is refused at the door
        self.partitioned = False  # ☠️ blackout: nothing gets in, in-flight pipes die
        self._server = None
        self._alive = False

    # ---------- lifecycle ----------
    def start(self):
        """🚪 Open the doorway and lurk."""
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", self.listen_port))
        self._server.listen(64)
        self._alive = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self  # chainable, because we're fancy

    def stop(self):
        """🪦 The gremlin retires. The doorway closes."""
        self._alive = False
        try:
            self._server.close()
        except Exception:
            pass

    def calm(self):
        """🌤️ Reset all weather to clear skies. The network never knew."""
        self.latency = self.jitter = self.drop = 0.0
        self.partitioned = False

    # ---------- the mischief ----------
    def _accept_loop(self):
        while self._alive:
            try:
                client, _ = self._server.accept()
            except OSError:
                return  # doorway closed, shift's over
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client):
        try:
            if self.partitioned or (self.drop and random.random() < self.drop):
                client.close()  # 🚫 not today. or possibly ever
                return
            if self.latency or self.jitter:
                # 🐌 make them feel the distance
                time.sleep(self.latency + random.uniform(0, self.jitter))
            upstream = socket.create_connection(self.target, timeout=10)
        except Exception:
            try:
                client.close()
            except Exception:
                pass
            return
        # 🔁 two pumps, one pipe each direction. bytes flow until they don't.
        threading.Thread(target=self._pump, args=(client, upstream), daemon=True).start()
        self._pump(upstream, client)

    def _pump(self, src, dst):
        try:
            while True:
                if self.partitioned:
                    break  # ⚡ blackout mid-conversation. brutal. realistic.
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass  # pipes break. that's the whole point of us
        finally:
            for s in (src, dst):
                try:
                    s.close()
                except Exception:
                    pass


# ==========================================================
# 🕹️ CLI mode — summon a lone gremlin by hand
# ==========================================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python GREMLIN.py <listen_port> <target_host:port> [--latency S] [--jitter S] [--drop P]")
        sys.exit(1)
    listen = int(sys.argv[1])
    host, port = sys.argv[2].split(":")
    g = Gremlin(listen, host, int(port)).start()
    args = sys.argv[3:]
    for flag, attr in (("--latency", "latency"), ("--jitter", "jitter"), ("--drop", "drop")):
        if flag in args:
            setattr(g, attr, float(args[args.index(flag) + 1]))
    print(f"👹 Gremlin lurking on :{listen} -> {host}:{port} "
          f"(latency={g.latency}s jitter={g.jitter}s drop={g.drop})")
    print("Ctrl+C to banish.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        g.stop()
        print("\n👹 Banished.")
