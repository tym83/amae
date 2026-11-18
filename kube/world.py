#!/usr/bin/env python3
"""Let a Tainted program live inside a Kubernetes cluster as an operator.

The cluster becomes the world of the program. Every tick the world tells it,
line by line, what it looks like now:

    tick 7
    node worker-1 ready schedulable staying
    node worker-2 ready cordoned leaving       (staying | leaving | left)
    pod shop/web-5d8f worker-2 ready shop/ReplicaSet/web-5d8f
    pod shop/debug worker-2 waiting none       (ready | waiting; owner or none)
    end

and the program, which hears it with `hear world`, answers with `say`.
Only these answers change the cluster:

    cordon NODE
    uncordon NODE
    evict NAMESPACE/POD
    annotate node NODE KEY=VALUE
    log TEXT

Everything else the program says, `done` included, is printed as it is.
DaemonSet pods and mirror pods are not shown: they belong to their nodes.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time


LEAVING = "taintednetes.io/leaving"
LEFT = "taintednetes.io/left"


def snapshot(nodes, pods, tick):
    lines = [f"tick {tick}"]
    for n in nodes:
        meta, spec = n["metadata"], n["spec"]
        ann = meta.get("annotations", {})
        ready = any(c["type"] == "Ready" and c["status"] == "True"
                    for c in n["status"].get("conditions", []))
        state = ("left" if ann.get(LEFT) == "true" else
                 "leaving" if ann.get(LEAVING) == "true" else "staying")
        lines.append(f"node {meta['name']} {'ready' if ready else 'notready'} "
                     f"{'cordoned' if spec.get('unschedulable') else 'schedulable'} {state}")
    for p in pods:
        meta, status = p["metadata"], p["status"]
        if status.get("phase") in ("Succeeded", "Failed"):
            continue
        owners = meta.get("ownerReferences", [])
        if owners and owners[0]["kind"] in ("DaemonSet", "Node"):
            continue
        ready = (not meta.get("deletionTimestamp") and any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in status.get("conditions", [])))
        owner = (f"{meta['namespace']}/{owners[0]['kind']}/{owners[0]['name']}"
                 if owners else "none")
        lines.append(f"pod {meta['namespace']}/{meta['name']} "
                     f"{p['spec'].get('nodeName') or '-'} "
                     f"{'ready' if ready else 'waiting'} {owner}")
    lines.append("end")
    return lines


class Hands:
    """Carries out what the program says. Nothing outside the list is run."""

    def __init__(self, context, dry_run=False, log=print):
        self.context = context
        self.dry_run = dry_run
        self.log = log
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.act(line)

    def flush(self):
        pass

    def kubectl(self, *args, stdin=None):
        cmd = ["kubectl", "--context", self.context, *args]
        if self.dry_run:
            self.log("would run: " + " ".join(cmd[3:]))
            return
        res = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
        if res.returncode:
            self.log(f"failed: {' '.join(cmd[3:])}: {res.stderr.strip()}")

    def act(self, line):
        w = line.split()
        if not w:
            return
        if w[0] in ("cordon", "uncordon") and len(w) == 2:
            self.kubectl(w[0], w[1])
        elif w[0] == "evict" and len(w) == 2 and "/" in w[1]:
            ns, name = w[1].split("/", 1)
            body = {"apiVersion": "policy/v1", "kind": "Eviction",
                    "metadata": {"name": name, "namespace": ns}}
            self.kubectl("create", "--raw",
                         f"/api/v1/namespaces/{ns}/pods/{name}/eviction",
                         "-f", "-", stdin=json.dumps(body))
        elif w[:2] == ["annotate", "node"] and len(w) == 4 and "=" in w[3]:
            self.kubectl("annotate", "node", w[2], w[3], "--overwrite")
        elif w[0] == "log":
            self.log(line[4:])
            return
        elif line != "done":
            self.log(line)
            return
        if line != "done":
            self.log("> " + line)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--context", required=True)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--ticks", type=int, default=0, help="stop after this many ticks")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("program", help="a .tainted source, or the program it compiled to")
    args = ap.parse_args()

    program = args.program
    if program.endswith(".tainted"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from bridge import compiled
        program = compiled(program)
    log = lambda text: print(time.strftime("%H:%M:%S ") + text, flush=True)  # noqa: E731
    hands = Hands(args.context, args.dry_run, log)
    life = subprocess.Popen([program], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                            bufsize=1)

    def listen():
        for line in life.stdout:
            hands.write(line)

    ears = threading.Thread(target=listen, daemon=True)
    ears.start()

    def get(*what):
        res = subprocess.run(["kubectl", "--context", args.context, "get", *what,
                              "-o", "json"], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)["items"]

    tick = 0
    try:
        while life.poll() is None and (not args.ticks or tick < args.ticks):
            tick += 1
            for line in snapshot(get("nodes"), get("pods", "-A"), tick):
                life.stdin.write(line + "\n")
            life.stdin.flush()
            time.sleep(args.interval)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    try:
        life.stdin.close()
    except BrokenPipeError:
        pass
    code = life.wait(timeout=30)
    ears.join(timeout=5)
    return code


if __name__ == "__main__":
    sys.exit(main())
