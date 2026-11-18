import contextlib
import queue
import threading
import time
import io
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "kube"))

import bridge  # noqa: E402
import world as kube_world  # noqa: E402
import minsky  # noqa: E402
import tainted  # noqa: E402


def run(source, runs=0, given=""):
    out = io.StringIO()
    world = tainted.World(tainted.compile_program(source), runs=runs, out=out,
                          err=io.StringIO(), inp=io.StringIO(given))
    code = world.run()
    return code, out.getvalue().splitlines(), world


def example(name):
    with open(os.path.join(ROOT, "examples", name)) as f:
        return f.read()


class Examples(unittest.TestCase):
    def test_hello(self):
        code, lines, _ = run(example("hello.tainted"))
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["bob heard: hello", "alice heard: hello to you",
                                 "alice and bob: infatuation"])

    def test_courtship_reaches_consummate_love(self):
        code, lines, world = run(example("courtship.tainted"))
        self.assertEqual(lines, ["alice feels consummate love"])
        self.assertEqual(tainted.bond_name(world.rel("bob", "alice")), "romantic love")

    def test_rush_frightens(self):
        code, lines, _ = run(example("rush.tainted"))
        self.assertEqual(code, 0)
        self.assertIn("bob is afraid: 1", lines)
        self.assertIn("bob's passion: 2", lines)

    def test_heart_and_knife_survives_the_wound(self):
        code, lines, _ = run(example("heart-and-knife.tainted"))
        self.assertEqual(code, 0)
        self.assertIn("alice heard: I know", lines)
        self.assertIn("the scar: wounded by bob", lines)

    def test_calculation_closes_after_the_wound(self):
        code, lines, world = run(example("calculation.tainted"))
        self.assertEqual(code, 2)
        self.assertTrue(world.rel("alice", "bob").closed)

    def test_breakup_leaves_scars(self):
        code, lines, world = run(example("breakup.tainted"))
        self.assertEqual(code, 2)
        self.assertEqual(lines, ["alice keeps 2 scars: morning, love, sleep well"])
        self.assertEqual(world.rel("bob", "alice").scars[-1], "alice left")

    def test_first_time_happens_once(self):
        _, first, _ = run(example("first-time.tainted"), runs=0)
        _, third, _ = run(example("first-time.tainted"), runs=2)
        self.assertEqual(first, ["I have never done this before."])
        self.assertEqual(third, ["We have been here 2 times before."])

    def test_penelope_forgets_digits(self):
        _, lines, _ = run(example("penelope.tainted"))
        self.assertEqual(lines, ["penelope remembers 1234000"])

    def test_multiply(self):
        _, lines, _ = run(example("multiply.tainted"))
        self.assertIn("c = 42", lines)


class ALife(unittest.TestCase):
    def test_every_rule_changes_the_story(self):
        code, lines, _ = run(example("a-life.tainted"))
        self.assertEqual(code, 2)
        self.assertEqual(lines[0], "ana: I have never met anyone like this.")
        self.assertIn("ana sees ben: infatuation", lines)
        self.assertIn("ana is afraid of ben: 1", lines)
        self.assertIn("ana's calculated trust in ben is 0 now", lines)
        self.assertIn("ana remembers they met in 1990", lines)
        self.assertEqual(lines[-1], "ana keeps 12 scars; the last one says: ben left")
        _, again, _ = run(example("a-life.tainted"), runs=3)
        self.assertEqual(again[0], "ana: it feels as if this has happened 3 times before.")


class Rituals(unittest.TestCase):
    def test_recursion_and_values(self):
        src = ("ritual f n\n if n <= 1\n give back 1\n end\n"
               " perform f with n - 1 into m\n give back n * m\nend\n"
               "soul s\n perform f with 12 into x\n say x\nend\n")
        self.assertEqual(run(src)[1], ["479001600"])

    def test_memories_outside_are_held(self):
        src = ("ritual long\n let i = 0\n while i < 200\n i = i + 1\n end\nend\n"
               "soul s\n let year = 1999\n perform long\n say year\nend\n")
        self.assertEqual(run(src)[1], ["1999"])

    def test_wrong_number_of_things(self):
        with self.assertRaisesRegex(tainted.TaintedError, "takes 1 things"):
            run("ritual r a\nend\nsoul s\n perform r with 1, 2\nend\n")


class Rules(unittest.TestCase):
    def test_passion_cools_while_apart(self):
        """Two strangers meet at first sight (passion 3), then live apart:
        one degree is lost every fifty steps of each one's own life."""
        src = ("soul a\n meet b\n let i = 0\n while i < 60\n  i = i + 1\n end\n"
               " say passion b\nend\nsoul b\n meet a\nend\n")
        code, lines, _ = run(src)
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["0"])
        src = src.replace("i < 60", "i < 20")
        self.assertEqual(run(src)[1], ["2"])

    def test_cannot_tell_a_stranger(self):
        with self.assertRaisesRegex(tainted.TaintedError, "never met"):
            run("soul a\n tell b 1\nend\nsoul b\n hear a into x\nend\n")

    def test_confide_needs_the_heart(self):
        with self.assertRaisesRegex(tainted.TaintedError, "gave their heart"):
            run("soul a\n meet b\n confide b 1\nend\nsoul b\n meet a\n hear a into x\nend\n")

    def test_leaving_is_irreversible(self):
        with self.assertRaisesRegex(tainted.TaintedError, "nothing more"):
            run("soul a\n meet b\n leave b\n meet b\nend\nsoul b\n meet a\nend\n")

    def test_forgiveness_reopens_but_keeps_the_scar(self):
        src = ("soul a\n meet b\n wound b\n hear b into x\n say x\nend\n"
               "soul b\n meet a\n forgive a\n tell a \"still here\"\n say scars of a\nend\n")
        code, lines, _ = run(src)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(lines), ["1", "still here"])

    def test_waiting_has_no_timeout(self):
        code, _, _ = run("soul a\n meet b\nend\nsoul b\n goodbye\nend\n")
        self.assertEqual(code, 2)

    def test_runs_are_counted_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h.json"))
            path = os.path.join(ROOT, "examples", "first-time.tainted")
            outs = [subprocess.run([sys.executable, os.path.join(ROOT, "tainted.py"), path],
                                   env=env, capture_output=True, text=True).stdout
                    for _ in range(2)]
        self.assertEqual(outs[0], "I have never done this before.\n")
        self.assertEqual(outs[1], "We have been here 1 times before.\n")


class TuringCompleteness(unittest.TestCase):
    """Random two-counter machines give the same answer in Tainted."""

    def random_machine(self, rng):
        size = rng.randint(2, 7)
        labels = [f"s{i}" for i in range(size)] + ["stop"]
        prog = {}
        for i in range(size):
            target = lambda: rng.choice(labels)  # noqa: E731
            if rng.random() < 0.5:
                prog[f"s{i}"] = ("inc", rng.choice("xy"), target())
            else:
                prog[f"s{i}"] = ("dec", rng.choice("xy"), target(), target())
        prog["stop"] = ("halt",)
        init = {"x": rng.randint(0, 6), "y": rng.randint(0, 6)}
        return ["x", "y"], init, prog, "s0"

    def test_random_machines(self):
        rng = random.Random(1978)
        checked = 0
        while checked < 60:
            machine = self.random_machine(rng)
            expected = minsky.simulate(*machine, limit=2000)
            if expected is None:
                continue
            _, lines, _ = run(minsky.compile_machine(*machine))
            self.assertEqual(lines, [f"{c} = {v}" for c, v in expected.items()])
            checked += 1


def run_tas(tas, source, runs=0):
    out = io.StringIO()
    world = tainted.World(tainted.load_tas(tas), runs=runs, out=out,
                          err=io.StringIO(), inp=io.StringIO(source))
    code = world.run()
    return code, out.getvalue()


def body(tas):
    return [line for line in tas.splitlines() if not line.startswith("#")]


class SelfHosting(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "compiler.tainted")) as f:
            self.compiler = f.read()

    def test_bootstrap_reaches_a_fixed_point_in_code(self):
        c1 = tainted.to_tas(self.compiler)
        code, c2 = run_tas(c1, self.compiler)
        self.assertEqual(code, 0)
        _, c3 = run_tas(c2, self.compiler)
        self.assertEqual(body(c1), body(c2))
        self.assertEqual(c2, c3)

    def test_but_never_in_memory(self):
        c2 = run_tas(tainted.to_tas(self.compiler), self.compiler)[1]
        again = run_tas(c2, self.compiler, runs=1)[1]
        self.assertEqual(body(c2), body(again))
        self.assertNotEqual(c2.splitlines()[0], again.splitlines()[0])

    def test_compiles_every_example_like_the_reference(self):
        c2 = run_tas(tainted.to_tas(self.compiler), self.compiler)[1]
        names = sorted(n for n in os.listdir(os.path.join(ROOT, "examples"))
                       if n.endswith(".tainted"))
        names += sorted("classics/" + n
                        for n in os.listdir(os.path.join(ROOT, "examples", "classics")))
        for name in names + ["../taintednetes.tainted", "../compiler.tainted"]:
            src = example(name)
            if "hear world" in src:
                self.assertEqual(body(run_tas(c2, src)[1]), body(tainted.to_tas(src)), name)
                continue
            self.assertEqual(body(run_tas(c2, src)[1]), body(tainted.to_tas(src)), name)
            direct = run(src)
            via = tainted.World(tainted.load_tas(tainted.to_tas(src)), out=io.StringIO(),
                                err=io.StringIO())
            self.assertEqual(via.run(), direct[0], name)
            self.assertEqual(via.out.getvalue().splitlines(), direct[1], name)

    def test_without_recall_the_compiler_forgets(self):
        forgetful = "\n".join(line for line in self.compiler.splitlines()
                              if "recall stack blocks" not in line)
        _, out = run_tas(tainted.to_tas(forgetful), self.compiler)
        self.assertNotEqual(body(out), body(tainted.to_tas(self.compiler)))


def classic(name, given=""):
    return run(example(f"classics/{name}.tainted"), given=given)


class Classics(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(classic("hello-world")[1], ["Hello, world"])

    def test_fizzbuzz(self):
        want = ["FizzBuzz" if n % 15 == 0 else "Fizz" if n % 3 == 0 else
                "Buzz" if n % 5 == 0 else str(n) for n in range(1, 31)]
        self.assertEqual(classic("fizzbuzz")[1], want)

    def test_factorial(self):
        import math
        self.assertEqual(classic("factorial")[1],
                         [f"{n}! = {math.factorial(n)}" for n in range(1, 21)])

    def test_fibonacci(self):
        a, b, want = 0, 1, []
        for _ in range(30):
            want.append(str(a))
            a, b = b, a + b
        self.assertEqual(classic("fibonacci")[1], want)

    def test_primes(self):
        want = [str(n) for n in range(2, 100) if all(n % d for d in range(2, n))]
        self.assertEqual(classic("primes")[1], want)

    def test_gcd(self):
        self.assertEqual(classic("gcd")[1], ["gcd(1071, 462) = 21"])

    def test_cat_reverse_wc(self):
        text = "first line\nsecond one\n\nlast\n"
        self.assertEqual(classic("cat", text)[1], text.splitlines())
        self.assertEqual(classic("reverse", text)[1], [l[::-1] for l in text.splitlines()])
        self.assertEqual(classic("wc", text)[1], ["4 5 28"])

    def test_bottles(self):
        lines = classic("bottles")[1]
        self.assertEqual(len(lines), 99 * 3 + 2)
        self.assertEqual(lines[-7], "Take one down and pass it around, 1 bottle of beer on the wall.")
        self.assertEqual(lines[-4], "Take one down and pass it around, no more bottles of beer on the wall.")

    def test_sort(self):
        numbers = [5, 3, 10, 1, 42, 7, 7, 0]
        self.assertEqual(classic("sort", "\n".join(map(str, numbers)) + "\n")[1],
                         [str(n) for n in sorted(numbers)])

    def test_sleep_sort(self):
        code, lines, _ = classic("sleep-sort")
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["1", "2", "3", "5", "7", "8", "9"])

    def test_ping_pong(self):
        lines = classic("ping-pong")[1]
        self.assertEqual(lines[:5], [f"pong {n}" for n in range(5)])
        self.assertEqual(lines[-1], "ping and pong: romantic love")

    def test_producer_consumer(self):
        self.assertEqual(classic("producer-consumer")[1],
                         ["sum 45, afraid of the producer: 1"])

    def test_hanoi(self):
        lines = classic("hanoi")[1]
        self.assertEqual(len(lines), 15)
        self.assertEqual(lines[7], "disk 4: A -> C")

    def test_philosophers(self):
        code, lines, _ = classic("philosophers")
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], "everyone has eaten")
        for i in range(1, 6):
            self.assertEqual([l for l in lines if l.startswith(f"philosopher {i} ")],
                             [f"philosopher {i} eats, meal {m}" for m in range(1, 4)])


def gale_shapley(pods, nodes, seats):
    """Reference: pod-proposing deferred acceptance with node capacities."""
    rank = {n: {p: i for i, p in enumerate(prefs)} for n, prefs in nodes.items()}
    held = {n: [] for n in nodes}
    nxt, free = {p: 0 for p in pods}, list(pods)
    while free:
        p = free.pop(0)
        while nxt[p] < len(pods[p]):
            n = pods[p][nxt[p]]
            nxt[p] += 1
            if p not in rank[n] or seats[n] == 0:
                continue
            if len(held[n]) < seats[n]:
                held[n].append(p)
                break
            worst = max(held[n], key=lambda q: rank[n][q])
            if rank[n][p] < rank[n][worst]:
                held[n].remove(worst)
                held[n].append(p)
                free.append(worst)
                break
    placement = {p: None for p in pods}
    for n, ps in held.items():
        for p in ps:
            placement[p] = n
    return placement


def schedule(pods, nodes, seats):
    lines = [f"pod {p} {' '.join(likes)}" for p, likes in pods.items()]
    lines += [f"node {n} {seats[n]} {' '.join(likes)}" for n, likes in nodes.items()]
    with open(os.path.join(ROOT, "taintednetes.tainted")) as f:
        program = tainted.compile_program(f.read())
    out = io.StringIO()
    world = tainted.World(program, out=out, err=io.StringIO(),
                          inp=io.StringIO("\n".join(lines) + "\n"))
    code = world.run()
    placement = {}
    for line in out.getvalue().splitlines():
        words = line.split()
        if words[1:3] == ["lives", "on"]:
            placement[words[0]] = words[3]
        elif words[1:4] == ["has", "nowhere", "to"] and len(words) == 5:
            placement[words[0]] = None
    return code, placement, out.getvalue().splitlines(), world


class Taintednetes(unittest.TestCase):
    def test_example_cluster(self):
        pods, nodes, seats = {}, {}, {}
        with open(os.path.join(ROOT, "examples", "cluster.txt")) as f:
            for line in f:
                w = line.split()
                if w[0] == "pod":
                    pods[w[1]] = w[2:]
                else:
                    nodes[w[1]], seats[w[1]] = w[3:], int(w[2])
        code, placement, lines, world = schedule(pods, nodes, seats)
        self.assertEqual(code, 0)
        self.assertEqual(placement, {"web": "beta", "db": "alpha", "cache": "gamma"})
        self.assertEqual(lines[-1], "the cluster is at rest")
        self.assertEqual(world.rel("cache", "beta").scars, ["wounded by beta"])

    def test_random_clusters_settle_into_stable_matchings(self):
        rng = random.Random(83)
        for _ in range(40):
            pod_names = [f"p{i}" for i in range(rng.randint(1, 7))]
            node_names = [f"n{i}" for i in range(rng.randint(1, 4))]
            pods = {p: rng.sample(node_names, rng.randint(0, len(node_names)))
                    for p in pod_names}
            nodes = {n: rng.sample(pod_names, rng.randint(0, len(pod_names)))
                     for n in node_names}
            seats = {n: rng.randint(0, 3) for n in node_names}
            code, placement, _, _ = schedule(pods, nodes, seats)
            self.assertEqual(code, 0)
            self.assertEqual(placement, gale_shapley(pods, nodes, seats))


def fake_node(name, seats=None, likes=None, taint=False):
    annotations = {}
    if seats is not None:
        annotations[bridge.SEATS] = str(seats)
    if likes:
        annotations[bridge.LIKES] = likes
    return {"metadata": {"name": name, "annotations": annotations, "labels": {}},
            "spec": {"taints": [{"key": "role", "effect": "NoSchedule"}] if taint else []},
            "status": {"allocatable": {"cpu": "4", "memory": "8Gi", "pods": "110"},
                       "conditions": [{"type": "Ready", "status": "True"}]}}


def fake_pod(name, likes=None, node=None, created="2026-11-17T00:00:00Z"):
    return {"metadata": {"name": name, "namespace": "ns", "creationTimestamp": created,
                         "annotations": {bridge.LIKES: likes} if likes else {}},
            "spec": {"schedulerName": "taintednetes", "nodeName": node,
                     "containers": [{"resources": {"requests": {"cpu": "100m",
                                                                "memory": "16Mi"}}}]},
            "status": {"phase": "Running" if node else "Pending"}}


class Bridge(unittest.TestCase):
    def test_decisions_come_from_tainted(self):
        nodes = [fake_node("a", seats=2, likes="ns/db"), fake_node("b", seats=1),
                 fake_node("master", taint=True)]
        pods = [fake_pod("old", node="a"), fake_pod("web", likes="a"),
                fake_pod("db", likes="a"), fake_pod("cache", likes="a")]
        b = bridge.Bridge.__new__(bridge.Bridge)
        b.scheduler = "taintednetes"
        with open(os.path.join(ROOT, "taintednetes.tainted")) as f:
            b.source = f.read()
        b.program = tainted.compile_program(b.source)
        b.get = lambda kind, *rest: pods if kind == "pods" else nodes
        bound = []
        b.bind = lambda pod, node: bound.append((pod["metadata"]["name"], node))
        old = os.environ.get("TAINTED_HISTORY")
        with tempfile.TemporaryDirectory() as d:
            os.environ["TAINTED_HISTORY"] = os.path.join(d, "h.json")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    b.once()
            finally:
                if old is None:
                    del os.environ["TAINTED_HISTORY"]
                else:
                    os.environ["TAINTED_HISTORY"] = old
        placed = dict(bound)
        self.assertNotIn("master", placed.values())
        self.assertEqual(placed["db"], "a")
        self.assertEqual(sum(1 for n in placed.values() if n == "a"), 1)
        self.assertEqual(sum(1 for n in placed.values() if n == "b"), 1)

    def test_a_pass_that_changes_nothing_is_not_told_again(self):
        b = bridge.Bridge.__new__(bridge.Bridge)
        b.last_story = None
        b.describe = lambda: ("text", {})
        b.decide = lambda text: ["pod:ns/web has nowhere to live", "the cluster is at rest"]
        told = []
        for _ in range(3):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                b.once()
            told.append(out.getvalue())
        self.assertEqual(told, ["ns/web has nowhere to live\nthe cluster is at rest\n", "", ""])

    def test_requests_count_init_containers_like_the_kubelet(self):
        def box(cpu, always=False):
            c = {"resources": {"requests": {"cpu": cpu}}}
            if always:
                c["restartPolicy"] = "Always"
            return c
        pod = {"spec": {"initContainers": [box("500m")], "containers": [box("100m")]}}
        self.assertEqual(bridge.requests(pod)[0], 500)
        pod["spec"]["initContainers"] = [box("200m", always=True), box("400m")]
        self.assertEqual(bridge.requests(pod)[0], 600)
        pod["spec"]["containers"] = [box("500m")]
        self.assertEqual(bridge.requests(pod)[0], 700)
        pod["spec"]["overhead"] = {"cpu": "50m"}
        self.assertEqual(bridge.requests(pod)[0], 750)
        pod["spec"]["resources"] = {"requests": {"cpu": "1"}}
        self.assertEqual(bridge.requests(pod)[0], 1050)

    def test_binding_needs_no_more_rights_than_binding(self):
        """kubectl create -f validates against the CRD list, which a scheduler
        running with least privilege may not read; the binding subresource
        is posted raw instead."""
        b = bridge.Bridge.__new__(bridge.Bridge)
        calls = []
        b.kubectl = lambda *args, stdin=None: calls.append((args, json.loads(stdin)))
        b.bind(fake_pod("web"), "a")
        (args, body), = calls
        self.assertEqual(args, ("create", "--raw", "/api/v1/namespaces/ns/pods/web/binding",
                                "-f", "-"))
        self.assertEqual(body["target"]["name"], "a")


class Parting(unittest.TestCase):
    """The operator in kube/parting.tainted, against a cluster that is only imagined."""

    def live(self, nodes, pods, ticks, slow=0, refuse=0, same_name=False):
        lines = []
        hands = kube_world.Hands("none", log=lines.append)
        said = []
        hands.act = lambda line: said.append(line)
        voice = queue.Queue()
        with open(os.path.join(ROOT, "kube", "parting.tainted")) as f:
            program = tainted.compile_program(f.read())
        w = tainted.World(program, out=hands, inp=voice, err=io.StringIO(),
                          patience=float("inf"))
        threading.Thread(target=w.run, daemon=True).start()
        history, born = [], 0
        self.logs = []
        for tick in range(1, ticks + 1):
            for line in (["tick %d" % tick]
                         + ["node %s %s" % (k, " ".join(v)) for k, v in nodes.items()]
                         + ["pod %s %s" % (k, " ".join(v)) for k, v in pods.items()]
                         + ["end"]):
                voice.put(line)
            deadline = time.time() + 10
            while "done" not in said and time.time() < deadline:
                time.sleep(0.005)
            self.assertIn("done", said)
            cmds = [c for c in said if c != "done" and not c.startswith("log ")]
            history.append(cmds)
            self.logs.extend(c for c in said if c.startswith("log "))
            said.clear()
            for c in cmds:
                w_ = c.split()
                if w_[0] == "cordon":
                    nodes[w_[1]][1] = "cordoned"
                elif w_[0] == "evict":
                    if refuse:
                        refuse -= 1
                        continue
                    owner = pods.pop(w_[1])[2]
                    born += 1
                    pods[w_[1] if same_name else "a/new%d" % born] = ["w1", "waiting", owner]
                elif w_[0] == "annotate":
                    nodes[w_[2]][2] = "left"
            for pod in [p for p in pods if pods[p][1] == "waiting" and tick % (slow + 1) == 0]:
                pods[pod][1] = "ready"
        voice.put(None)
        return history

    def test_lets_go_one_at_a_time_and_leaves(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "schedulable", "leaving"]}
        pods = {"a/x": ["w2", "ready", "a/RS/x"], "a/y": ["w2", "ready", "a/RS/x"]}
        history = self.live(nodes, pods, 5)
        self.assertEqual(history[0], ["cordon w2", "evict a/x"])
        self.assertEqual(history[1], ["evict a/y"])
        self.assertEqual(history[2], ["annotate node w2 taintednetes.io/left=true"])
        self.assertEqual(history[3:], [[], []])

    def test_waits_for_the_replacement(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/x": ["w2", "ready", "a/RS/x"], "a/y": ["w2", "ready", "a/RS/x"]}
        history = self.live(nodes, pods, 6, slow=2)
        evictions = [i for i, h in enumerate(history) if any(c.startswith("evict") for c in h)]
        self.assertEqual(len(evictions), 2)
        self.assertGreaterEqual(evictions[1] - evictions[0], 2)
        waiting = [l for l in self.logs if "replacement" in l]
        self.assertEqual(waiting, ["log w2 waits for a/RS/x to bring a replacement up"])

    def test_a_crowded_cluster_does_not_make_it_forget(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/p%02d" % i: ["w1", "ready", "a/RS/p"] for i in range(40)}
        pods["a/p00"] = ["w2", "ready", "a/RS/q"]
        pods["a/p01"] = ["w2", "ready", "a/RS/q"]
        history = self.live(nodes, pods, 4)
        self.assertEqual(history[0], ["evict a/p00"])
        self.assertEqual(history[1], ["evict a/p01"])
        self.assertEqual(history[2], ["annotate node w2 taintednetes.io/left=true"])

    def test_does_not_send_away_a_pod_with_no_owner(self):
        nodes = {"w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/bare": ["w2", "ready", "none"]}
        self.assertEqual(self.live(nodes, pods, 3), [[], [], []])

    def test_asks_again_when_an_eviction_is_refused(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/x": ["w2", "ready", "a/RS/x"]}
        history = self.live(nodes, pods, 12, refuse=1)
        evictions = [i for i, h in enumerate(history) if "evict a/x" in h]
        self.assertEqual(len(evictions), 2)
        self.assertIn(["annotate node w2 taintednetes.io/left=true"], history)

    def test_a_pod_that_comes_back_under_its_own_name(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/db-0": ["w2", "ready", "a/StatefulSet/db"],
                "a/db-1": ["w2", "ready", "a/StatefulSet/db"]}
        history = self.live(nodes, pods, 6, same_name=True)
        self.assertEqual(history[0], ["evict a/db-0"])
        self.assertEqual(history[1], ["evict a/db-1"])
        self.assertEqual(history[2], ["annotate node w2 taintednetes.io/left=true"])

    def test_says_why_it_is_stuck_once(self):
        nodes = {"w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/bare": ["w2", "ready", "none"]}
        self.live(nodes, pods, 4)
        self.assertEqual(self.logs,
                         ["log w2 cannot leave: its last pod has nowhere to come back from"])



class Documentation(unittest.TestCase):
    """Every program in the tutorial prints what the tutorial says it prints."""

    def check(self, name):
        import re
        with open(os.path.join(ROOT, "docs", name)) as f:
            text = f.read()
        blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.S)
        checked = 0
        for i, (lang, body) in enumerate(blocks):
            if lang != "tainted":
                continue
            given, j = "", i + 1
            if blocks[j][0] == "input":
                given, j = blocks[j][1], j + 1
            self.assertEqual(blocks[j][0], "output", body[:40])
            code, lines, _ = run(body, given=given)
            self.assertEqual(code, 0, body[:40])
            self.assertEqual(lines, blocks[j][1].splitlines(), body[:40])
            checked += 1
        self.assertGreaterEqual(checked, 14)

    def test_tutorial_programs(self):
        self.check("tutorial.md")

    def test_translated_tutorial_programs(self):
        self.check("tutorial.ru.md")

if __name__ == "__main__":
    unittest.main()
