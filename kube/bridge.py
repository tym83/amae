#!/usr/bin/env python3
"""Run taintednetes.tainted as the scheduler of a real Kubernetes cluster.

The bridge only carries messages. It reads pending pods and nodes through
kubectl, describes them to taintednetes.tainted as plain text, and binds
every pod to the node the Tainted program says it lives on. Every decision
about who lives where is made in Tainted.

What the bridge does decide is who may meet whom at all: a pod only likes
nodes it fits on (free resources, node selector, taints it tolerates), and a
node only offers as many seats as it can hold of the largest pod that wants it.
A node annotated taintednetes.io/seats: "N" hosts at most N pods of this
scheduler.

Preferences:
  pod annotation  taintednetes.io/likes: "node-a node-b"   nodes it wants first
  node annotation taintednetes.io/likes: "ns/pod ns/pod"   pods it wants first
Everyone else is ordered the ordinary way: pods prefer nodes with more free
whole cores, and where the nodes are equal every pod has its own lasting
taste, so a crowd of identical pods spreads out. Nodes prefer pods with higher
priority, then the ones waiting longest.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIKES = "taintednetes.io/likes"
SEATS = "taintednetes.io/seats"
UNITS = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40,
         "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}


def cpu(q):
    q = str(q)
    return int(q[:-1]) if q.endswith("m") else int(float(q) * 1000)


def memory(q):
    q = str(q)
    for suffix in sorted(UNITS, key=len, reverse=True):
        if q.endswith(suffix):
            return int(float(q[:-len(suffix)]) * UNITS[suffix])
    return int(float(q))


def requests(pod):
    """What the kubelet will hold for the pod, counted the way the kubelet
    counts it: app containers and sidecars run together, every other init
    container runs alone next to the sidecars started before it, the pod
    takes the larger of the two, and the runtime's overhead comes on top.
    Resources set for the pod as a whole replace the containers' own."""
    spec = pod["spec"]

    def own(container):
        req = container.get("resources", {}).get("requests", {})
        return cpu(req.get("cpu", 0)), memory(req.get("memory", 0))

    pod_level = spec.get("resources", {}).get("requests")
    if pod_level:
        c, m = cpu(pod_level.get("cpu", 0)), memory(pod_level.get("memory", 0))
    else:
        side_c = side_m = peak_c = peak_m = 0
        for init in spec.get("initContainers", []):
            ic, im = own(init)
            if init.get("restartPolicy") == "Always":
                side_c, side_m = side_c + ic, side_m + im
                peak_c, peak_m = max(peak_c, side_c), max(peak_m, side_m)
            else:
                peak_c, peak_m = max(peak_c, side_c + ic), max(peak_m, side_m + im)
        app = [own(x) for x in spec.get("containers", [])]
        c = max(peak_c, side_c + sum(x[0] for x in app))
        m = max(peak_m, side_m + sum(x[1] for x in app))
    overhead = spec.get("overhead", {})
    return c + cpu(overhead.get("cpu", 0)), m + memory(overhead.get("memory", 0))


def tolerates(pod, taint):
    if taint.get("effect") not in ("NoSchedule", "NoExecute"):
        return True
    for tol in pod["spec"].get("tolerations", []):
        if tol.get("effect") and tol["effect"] != taint["effect"]:
            continue
        if tol.get("operator") == "Exists":
            if not tol.get("key") or tol["key"] == taint["key"]:
                return True
        elif tol.get("key") == taint["key"] and tol.get("value") == taint.get("value"):
            return True
    return False


def taste(pod, node):
    """A preference that is the pod's own and stays the same between runs."""
    return hashlib.sha256(f"{pod} {node}".encode()).hexdigest()


def ready(node):
    if node["spec"].get("unschedulable"):
        return False
    return any(c["type"] == "Ready" and c["status"] == "True"
               for c in node["status"].get("conditions", []))


def compiled(source):
    """The program a Tainted source compiles to, built once next to it in build/."""
    out = os.path.join(ROOT, "build", os.path.basename(source)[:-len(".tainted")])
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(source):
        subprocess.run([os.path.join(ROOT, "bin", "tc"), source, "-o", out], check=True)
    return out


class Bridge:
    def __init__(self, context, scheduler, program=None):
        self.context = context
        self.scheduler = scheduler
        self.program = program or compiled(os.path.join(ROOT, "taintednetes.tainted"))
        self.last_story = None

    def kubectl(self, *args, stdin=None):
        cmd = ["kubectl", "--context", self.context, *args]
        res = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
        if res.returncode:
            raise RuntimeError(f"{' '.join(cmd)}: {res.stderr.strip()}")
        return res.stdout

    def get(self, *args):
        return json.loads(self.kubectl("get", *args, "-o", "json"))["items"]

    def describe(self):
        """Turn the cluster into the text taintednetes.tainted hears."""
        pods = self.get("pods", "-A")
        nodes = [n for n in self.get("nodes") if ready(n)]
        pending = [p for p in pods
                   if p["spec"].get("schedulerName") == self.scheduler
                   and not p["spec"].get("nodeName")
                   and p["status"].get("phase") == "Pending"
                   and not p["metadata"].get("deletionTimestamp")]
        if not pending or not nodes:
            return None, {}
        free, ours = {}, {}
        for n in nodes:
            alloc = n["status"]["allocatable"]
            free[n["metadata"]["name"]] = [cpu(alloc.get("cpu", 0)),
                                           memory(alloc.get("memory", 0)),
                                           int(alloc.get("pods", 0))]
        for p in pods:
            where = p["spec"].get("nodeName")
            if where in free and p["status"].get("phase") not in ("Succeeded", "Failed"):
                c, m = requests(p)
                free[where][0] -= c
                free[where][1] -= m
                free[where][2] -= 1
                if p["spec"].get("schedulerName") == self.scheduler:
                    ours[where] = ours.get(where, 0) + 1

        pid = {f"pod:{p['metadata']['namespace']}/{p['metadata']['name']}": p for p in pending}
        nid = {f"node:{n['metadata']['name']}": n for n in nodes}

        def fits(p, n):
            c, m = requests(p)
            f = free[n["metadata"]["name"]]
            labels = n["metadata"].get("labels", {})
            selector = p["spec"].get("nodeSelector", {})
            return (c <= f[0] and m <= f[1] and f[2] > 0
                    and all(labels.get(k) == v for k, v in selector.items())
                    and all(tolerates(p, t) for t in n["spec"].get("taints", [])))

        lines = []
        for pk, p in pid.items():
            wanted = p["metadata"].get("annotations", {}).get(LIKES, "").split()
            candidates = [nk for nk, n in nid.items() if fits(p, n)]
            candidates.sort(key=lambda nk: (
                wanted.index(nk[5:]) if nk[5:] in wanted else len(wanted),
                -(free[nk[5:]][0] // 1000), taste(pk, nk)))
            lines.append(f"pod {pk} {' '.join(candidates)}")
        for nk, n in nid.items():
            wanted = n["metadata"].get("annotations", {}).get(LIKES, "").split()
            suitors = [pk for pk, p in pid.items() if fits(p, n)]
            suitors.sort(key=lambda pk: (
                wanted.index(pk[4:]) if pk[4:] in wanted else len(wanted),
                -pid[pk]["spec"].get("priority", 0),
                pid[pk]["metadata"]["creationTimestamp"], pk))
            f = free[nk[5:]]
            seats = f[2]
            limit = n["metadata"].get("annotations", {}).get(SEATS)
            if limit is not None:
                seats = min(seats, int(limit) - ours.get(nk[5:], 0))
            for p in suitors:
                c, m = requests(pid[p])
                if c:
                    seats = min(seats, f[0] // c)
                if m:
                    seats = min(seats, f[1] // m)
            lines.append(f"node {nk} {max(seats, 0)} {' '.join(suitors)}")
        return "\n".join(lines) + "\n", pid

    def decide(self, text):
        res = subprocess.run([self.program], input=text, capture_output=True, text=True)
        if res.returncode:
            raise RuntimeError(f"taintednetes ended with exit code {res.returncode}: "
                               f"{res.stderr.strip()}")
        return res.stdout.splitlines()

    def bind(self, pod, node):
        binding = {"apiVersion": "v1", "kind": "Binding",
                   "metadata": {"name": pod["metadata"]["name"],
                                "namespace": pod["metadata"]["namespace"]},
                   "target": {"apiVersion": "v1", "kind": "Node", "name": node}}
        ns, name = pod["metadata"]["namespace"], pod["metadata"]["name"]
        self.kubectl("create", "--raw", f"/api/v1/namespaces/{ns}/pods/{name}/binding",
                     "-f", "-", stdin=json.dumps(binding))

    def once(self):
        """Schedule what is pending. A pass that changes nothing and tells the
        same story as the one before it is not told again."""
        text, pid = self.describe()
        if text is None:
            self.last_story = None
            return 0
        bound, story = 0, []
        for line in self.decide(text):
            words = line.split()
            if words[1:3] == ["lives", "on"] and words[0] in pid:
                node = words[3][len("node:"):]
                self.bind(pid[words[0]], node)
                print(f"{words[0][4:]} lives on {node}", flush=True)
                bound += 1
            else:
                story.append(line.replace("pod:", "").replace("node:", ""))
        if bound or story != self.last_story:
            for line in story:
                print(line, flush=True)
        self.last_story = None if bound else story
        return bound


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--context", required=True, help="kubectl context of the cluster")
    ap.add_argument("--scheduler-name", default="taintednetes")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--once", action="store_true", help="schedule what is pending and exit")
    ap.add_argument("--program", help="taintednetes, already compiled")
    args = ap.parse_args()
    bridge = Bridge(args.context, args.scheduler_name, args.program)
    while True:
        try:
            bridge.once()
        except RuntimeError as err:
            print(f"taintednetes: {err}", file=sys.stderr, flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
