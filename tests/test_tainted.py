import io
import os
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import minsky  # noqa: E402
import taintednetes  # noqa: E402
import tainted  # noqa: E402


def run(source, runs=0):
    out = io.StringIO()
    world = tainted.World(tainted.compile_program(source), runs=runs, out=out,
                          err=io.StringIO())
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


class Rules(unittest.TestCase):
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
        for name in sorted(os.listdir(os.path.join(ROOT, "examples"))):
            if not name.endswith(".tainted"):
                continue
            src = example(name)
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


class Taintednetes(unittest.TestCase):
    def test_example_cluster(self):
        with open(os.path.join(ROOT, "examples", "cluster.taintednetes")) as f:
            pods, nodes = taintednetes.parse(f.read())
        placement, _, world = taintednetes.settle(pods, nodes)
        self.assertEqual(placement, {"web": "beta", "db": "alpha", "cache": "gamma"})
        self.assertEqual(world.rel("cache", "beta").scars, ["wounded by beta"])

    def test_random_clusters_settle_into_stable_matchings(self):
        rng = random.Random(83)
        for _ in range(40):
            pod_names = [f"p{i}" for i in range(rng.randint(1, 5))]
            node_names = [f"n{i}" for i in range(rng.randint(1, 5))]
            pods = {p: rng.sample(node_names, rng.randint(0, len(node_names)))
                    for p in pod_names}
            nodes = {n: rng.sample(pod_names, rng.randint(0, len(pod_names)))
                     for n in node_names}
            placement, _, _ = taintednetes.settle(pods, nodes)
            self.assertEqual(placement, taintednetes.gale_shapley(pods, nodes))


if __name__ == "__main__":
    unittest.main()
