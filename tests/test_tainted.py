"""Tests of Tainted as the compiler builds it.

Every program here is compiled by build/tc-core (made from the seed by
`make`), built with the runtime and run. tests/golden.sh checks the recorded
programs byte for byte; these tests check what the programs mean.
"""
import contextlib
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "kube"))

import bridge  # noqa: E402
import minsky  # noqa: E402

CORE = os.path.join(ROOT, "build", "tc-core")
CACHE = os.path.join(ROOT, "build", "tests")
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c11", "-D_POSIX_C_SOURCE=200809L", "-D_DEFAULT_SOURCE", "-O1", "-w", "-I" + os.path.join(ROOT, "runtime")]


def setUpModule():
    subprocess.run(["make", "-s", "-C", ROOT], check=True)
    os.makedirs(CACHE, exist_ok=True)
    runtime = os.path.join(CACHE, "runtime.o")
    subprocess.run([CC, *FLAGS, "-c", os.path.join(ROOT, "runtime", "tainted.c"), "-o", runtime],
                   check=True)


def source_key(source):
    """What the compiled program calls itself in the history of runs."""
    lines = source.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def compile_source(source, history=None):
    """Compile with the Tainted compiler; returns (program, None) or (None, (code, error))."""
    key = hashlib.sha256(source.encode()).hexdigest()[:16]
    program = os.path.join(CACHE, key)
    if os.path.exists(program):
        return program, None
    with tempfile.TemporaryDirectory() as d:
        res = subprocess.run([CORE], input=source, capture_output=True, text=True,
                             env=dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h.json")))
        if res.returncode:
            return None, (res.returncode, res.stderr)
        c = os.path.join(d, "p.c")
        with open(c, "w") as f:
            f.write(res.stdout)
        subprocess.run([CC, *FLAGS, c, os.path.join(CACHE, "runtime.o"), "-o", program, "-lm"], check=True)
    return program, None


class Life:
    """What a run of a program left behind: how it ended, what it said and felt."""

    def __init__(self, code, out, err):
        self.code = code
        self.lines = out.splitlines()
        self.err = err
        self.feelings = {}
        for line in err.splitlines():
            m = re.match(r"(\S+) -> (\S+): ([^;]+); trust (\d+), intimacy (\d+), passion (\d+), "
                         r"commitment (\d+), scars (\d+)(.*)", line)
            if m:
                self.feelings[(m[1], m[2])] = {
                    "bond": m[3], "trust": int(m[4]), "intimacy": int(m[5]), "passion": int(m[6]),
                    "commitment": int(m[7]), "scars": int(m[8]),
                    "closed": "closed" in m[9], "gift": "heart given" in m[9],
                    "left": ", left" in m[9]}


def run(source, runs=0, given="", flags=()):
    program, failed = compile_source(source)
    if failed:
        return Life(failed[0], "", failed[1])
    with tempfile.TemporaryDirectory() as d:
        history = os.path.join(d, "history.json")
        if runs:
            with open(history, "w") as f:
                json.dump({source_key(source): runs}, f)
        res = subprocess.run([program, "--feelings", *flags], input=given, capture_output=True,
                             text=True, env=dict(os.environ, TAINTED_HISTORY=history))
    return Life(res.returncode, res.stdout, res.stderr)


def example(name):
    with open(os.path.join(ROOT, "examples", name)) as f:
        return f.read()


class Examples(unittest.TestCase):
    def test_hello(self):
        life = run(example("hello.tainted"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, ["bob heard: hello", "alice heard: hello to you",
                                      "alice and bob: infatuation"])

    def test_courtship_reaches_consummate_love(self):
        life = run(example("courtship.tainted"))
        self.assertEqual(life.lines, ["alice feels consummate love"])
        self.assertEqual(life.feelings[("bob", "alice")]["bond"], "romantic love")

    def test_rush_frightens(self):
        life = run(example("rush.tainted"))
        self.assertEqual(life.code, 0)
        self.assertIn("bob is afraid: 1", life.lines)
        self.assertIn("bob's passion: 2", life.lines)

    def test_heart_and_knife_survives_the_wound(self):
        life = run(example("heart-and-knife.tainted"))
        self.assertEqual(life.code, 0)
        self.assertIn("alice heard: I know", life.lines)
        self.assertIn("the scar: wounded by bob", life.lines)

    def test_calculation_closes_after_the_wound(self):
        life = run(example("calculation.tainted"))
        self.assertEqual(life.code, 2)
        self.assertTrue(life.feelings[("alice", "bob")]["closed"])

    def test_breakup_leaves_scars(self):
        life = run(example("breakup.tainted"))
        self.assertEqual(life.code, 2)
        self.assertEqual(life.lines, ["alice keeps 2 scars: morning, love, sleep well"])
        self.assertIn("bob is still waiting for alice, who left", life.err)

    def test_first_time_happens_once(self):
        self.assertEqual(run(example("first-time.tainted")).lines, ["I have never done this before."])
        self.assertEqual(run(example("first-time.tainted"), runs=2).lines,
                         ["We have been here 2 times before."])

    def test_penelope_forgets_digits(self):
        self.assertEqual(run(example("penelope.tainted")).lines, ["penelope remembers 1234000"])

    def test_multiply(self):
        self.assertIn("c = 42", run(example("multiply.tainted")).lines)


class ALife(unittest.TestCase):
    def test_every_rule_changes_the_story(self):
        life = run(example("a-life.tainted"))
        self.assertEqual(life.code, 2)
        lines = life.lines
        self.assertEqual(lines[0], "ana: I have never met anyone like this.")
        self.assertIn("ana sees ben: infatuation", lines)
        self.assertIn("ana is afraid of ben: 1", lines)
        self.assertIn("ana's calculated trust in ben is 0 now", lines)
        self.assertIn("ana remembers they met in 1990", lines)
        self.assertEqual(lines[-1], "ana keeps 12 scars; the last one says: ben left")
        again = run(example("a-life.tainted"), runs=3).lines
        self.assertEqual(again[0], "ana: it feels as if this has happened 3 times before.")


class Rituals(unittest.TestCase):
    def test_recursion_and_values(self):
        src = ("ritual f n\n if n <= 1\n give back 1\n end\n"
               " perform f with n - 1 into m\n give back n * m\nend\n"
               "soul s\n perform f with 12 into x\n say x\nend\n")
        self.assertEqual(run(src).lines, ["479001600"])

    def test_memories_outside_are_held(self):
        src = ("ritual long\n let i = 0\n while i < 200\n i = i + 1\n end\nend\n"
               "soul s\n let year = 1999\n perform long\n say year\nend\n")
        self.assertEqual(run(src).lines, ["1999"])

    def test_wrong_number_of_things(self):
        life = run("ritual r a\nend\nsoul s\n perform r with 1, 2\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("takes 1 things", life.err)


class Rules(unittest.TestCase):
    def test_passion_cools_while_apart(self):
        src = ("soul a\n meet b\n let i = 0\n while i < 60\n  i = i + 1\n end\n"
               " say passion b\nend\nsoul b\n meet a\nend\n")
        self.assertEqual(run(src).lines, ["0"])
        self.assertEqual(run(src.replace("i < 60", "i < 20")).lines, ["2"])

    def errs(self, src, text):
        life = run(src)
        self.assertEqual(life.code, 1)
        self.assertIn(text, life.err)

    def test_cannot_tell_a_stranger(self):
        self.errs("soul a\n tell b 1\nend\nsoul b\n hear a into x\nend\n", "never met")

    def test_confide_needs_the_heart(self):
        self.errs("soul a\n meet b\n confide b 1\nend\nsoul b\n meet a\n hear a into x\nend\n",
                  "gave their heart")

    def test_leaving_is_irreversible(self):
        self.errs("soul a\n meet b\n leave b\n meet b\nend\nsoul b\n meet a\nend\n", "nothing more")

    def test_forgiveness_reopens_but_keeps_the_scar(self):
        src = ("soul a\n meet b\n wound b\n hear b into x\n say x\nend\n"
               "soul b\n meet a\n forgive a\n tell a \"still here\"\n say scars of a\nend\n")
        life = run(src)
        self.assertEqual(life.code, 0)
        self.assertEqual(sorted(life.lines), ["1", "still here"])

    def test_waiting_has_no_timeout(self):
        self.assertEqual(run("soul a\n meet b\nend\nsoul b\n goodbye\nend\n").code, 2)

    def test_numbers_are_64_bits(self):
        self.errs("soul s\n say 9223372036854775807 + 1\nend\n", "too large to hold")

    def test_cry_and_the_ending(self):
        life = run("soul s\n cry \"it hurts\"\n goodbye with 3\n say \"never\"\nend\n")
        self.assertEqual(life.code, 3)
        self.assertEqual(life.lines, [])
        self.assertIn("it hurts", life.err)

    def test_escapes_are_read_once(self):
        life = run('soul s\n say "a\\\\nb"\n say "q\\"q"\n say "x\\ny"\nend\n')
        self.assertEqual(life.lines, ["a\\nb", 'q"q', "x", "y"])

    def test_runs_are_counted_on_disk(self):
        program, _ = compile_source(example("first-time.tainted"))
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h.json"))
            outs = [subprocess.run([program], env=env, capture_output=True, text=True).stdout
                    for _ in range(2)]
        self.assertEqual(outs, ["I have never done this before.\n",
                                "We have been here 1 times before.\n"])


class Values(unittest.TestCase):
    def test_lists_maps_and_decimals(self):
        src = """soul s
    let xs = [3, 1, 2]
    put 10 into xs
    xs[2] = 5
    say xs
    say length of xs
    say xs[4] + 0.5
    let m = {"name": "ana", "age": 30}
    m["city"] = "Lisbon"
    remove "age" from m
    say m
    say keys of m
    say place of "city" in m
    say whole of 7.9
    say 1 / 4.0
    say 7 / 2
    say [1, 2] + [3]
    say [1, [2, 3]] == [1, [2, 3]]
    say 1 == 1.0
    say "pod"[2]
    let grid = [[1, 2], [3, 4]]
    grid[2][1] = 9
    put 5 into grid[1]
    say grid
    say number of "3.75" * 2
end
"""
        self.assertEqual(run(src).lines, [
            "[3, 5, 2, 10]", "4", "10.5", '{"name": "ana", "city": "Lisbon"}', '["name", "city"]',
            "2", "7", "0.25", "3", "[1, 2, 3]", "1", "1", "o", "[[1, 2, 5], [9, 4]]", "7.5"])

    def test_json_both_ways(self):
        src = """soul s
    say json of [1, "two", {"three": 3.25, "q": "a\\"b"}]
    let parsed = meaning of "{\\"pods\\": [{\\"name\\": \\"web\\", \\"ready\\": true}], \\"n\\": 2.5}"
    say parsed["pods"][1]["name"] + " " + parsed["pods"][1]["ready"] + " " + parsed["n"]
    endure
        say meaning of "{nope"
    when it hurts as pain
        say pain
    end
end
"""
        self.assertEqual(run(src).lines, ['[1, "two", {"three": 3.25, "q": "a\\"b"}]', "web 1 2.5",
                                          "this is not json: {nope"])

    def test_values_fade_too(self):
        src = """soul s
    let xs = [1, 2, 3, 4]
    let d = 3.14159
    let i = 0
    while i < 40
        i = i + 1
    end
    say xs
    say d
end
"""
        self.assertEqual(run(src).lines, ["[1, 2]", "3.141"])

    def test_items_that_are_not_there(self):
        life = run("soul s\n say [1][2]\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("there is no item 2 in a list of 1", life.err)


class TheWorld(unittest.TestCase):
    def test_asking_listening_files_and_time(self):
        with tempfile.TemporaryDirectory() as d:
            src = """soul s
    ask world "echo hello; echo world" into said
    say said
    ask world "tr a-z A-Z" telling "quiet words" into loud
    say loud
    write "first\\n" to file world "OUT"
    append "second\\n" to file world "OUT"
    read file world "OUT" into text
    say lines of text
    say world "MOOD"
    let t0 = now
    wait 0.2 seconds
    say now - t0 >= 0.2
    say fate 1
    listen to world "printf 'a\\nb\\n'; sleep 0.3; echo c"
    hear world into x
    hear world into y
    hear world into z
    say x + y + z
    hear world into last
    say last
end
"""
            program, failed = compile_source(src)
            self.assertIsNone(failed)
            res = subprocess.run([program], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                 env=dict(os.environ, OUT=os.path.join(d, "out"), MOOD="calm",
                                          TAINTED_HISTORY=os.path.join(d, "h")))
        self.assertEqual(res.stdout.splitlines(), ["hello\nworld"[:5], "world", "QUIET WORDS",
                                                   '["first", "second"]', "calm", "1", "0", "abc", "0"])

    def test_enduring_what_hurts(self):
        src = """ritual risky depth
    if depth == 0
        let nothing = [1][5]
    end
    perform risky with depth - 1
end

soul s
    endure
        ask world "echo broken >&2; exit 3" into never
        say "never here"
    when it hurts as pain
        say "it hurt: " + pain
    end
    endure
        perform risky with 3
    when it hurts as pain
        say "deep: " + pain
    end
    say "still alive"
end
"""
        self.assertEqual(run(src).lines, ["it hurt: the world said no to echo broken >&2; exit 3 (3): broken",
                                          "deep: there is no item 5 in a list of 1", "still alive"])


class Learning(unittest.TestCase):
    def test_a_program_learns_from_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "greetings.tainted"), "w") as f:
                f.write("ritual greet name\n give back \"hello, \" + name\nend\n"
                        "ritual broken\n say [1][2]\nend\n")
            main = os.path.join(d, "main.tainted")
            with open(main, "w") as f:
                f.write('learn "greetings.tainted"\nlearn "greetings.tainted"\n'
                        "soul s\n perform greet with \"ana\" into g\n say g\n perform broken\nend\n")
            out = os.path.join(d, "main")
            subprocess.run([os.path.join(ROOT, "bin", "tc"), main, "-o", out], check=True)
            res = subprocess.run([out], capture_output=True, text=True,
                                 env=dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h")))
        self.assertEqual(res.stdout, "hello, ana\n")
        self.assertIn("line 5 of greetings.tainted, s: there is no item 2", res.stderr)

    def test_a_file_that_is_not_there(self):
        life = run('learn "nowhere.tainted"\nsoul s\nend\n')
        self.assertEqual(life.code, 1)
        self.assertIn("there is no file to learn from: nowhere.tainted", life.err)


class Feelings(unittest.TestCase):
    def test_remembering_rewrites(self):
        src = ("soul a\n meet b\n let year = 1999\n hear b into n\n let i = 0\n"
               " while i < 20\n i = i + 1\n end\n say year\nend\nsoul b\n meet a\n tell a 47\nend\n")
        self.assertEqual(run(src).lines, ["1997"])

    def test_wounds_apologies_tenderness_and_letters(self):
        life = run(example("feelings/apology.tainted"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, [
            "ana remembers 1997", "ben is ashamed: 1", "resentment toward ben: 1", "ben is ashamed: 0",
            "after the apology: 0, trust 1, scars 2", "ben apologized for: wounded by ben",
            "intimacy after tenderness: 4", "a letter: from far away"])
        self.assertEqual(life.feelings[("ben", "ana")]["commitment"], 1)

    def test_an_apology_names_the_wound(self):
        life = run("soul a\n meet b\n apologize to b\nend\nsoul b\n meet a\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("an apology names the wound", life.err)

    def test_letters_from_the_gone_become_scars(self):
        life = run(example("feelings/grief.tainted"))
        self.assertEqual(life.feelings[("a", "b")]["scars"], 2)

    def test_hope_and_jealousy_and_distance(self):
        self.assertIn("a is still waiting for b, and still hopes", run(example("feelings/hope.tainted")).err)
        lines = run(example("feelings/jealousy.tainted")).lines
        self.assertIn("carol is jealous: 1", lines)
        self.assertIn("eve, far from dan: distance 4, longing 0", lines)

    def test_words_take_longer_after_a_long_silence(self):
        src = ("soul a\n meet b\n let i = 0\n while i < 100\n i = i + 1\n end\n"
               " say distance from b\n tell b 1\n meet b\n say distance from b\nend\n"
               "soul b\n meet a\n hear a into x\n meet a\nend\n")
        self.assertEqual(run(src).lines, ["6", "3"])


class Consent(unittest.TestCase):
    def test_together_and_apart(self):
        life = run(example("consent/together.tainted"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, ["ana: one, two, three", "ana: the first dance is done",
                                      "ana: ben withdrew, so we both stopped", "ben: I withdrew"])

    def test_nothing_together_without_consent(self):
        life = run("soul a\n meet b\n consent to b\n together with b\n say 1\n end\nend\n"
                   "soul b\n meet a\n together with a\n say 2\n end\nend\n")
        self.assertEqual(life.code, 2)
        self.assertEqual(life.lines, [])

    def test_boundaries(self):
        lines = run(example("consent/boundaries.tainted")).lines
        self.assertIn("ben crosses ana's boundary: the sea", lines)
        self.assertIn("crossings with ana: 1", lines)
        self.assertIn("cal: ana keeps fear behind a boundary cal may not cross", lines)


class TuringCompleteness(unittest.TestCase):
    """Random two-counter machines give the same answer in Tainted."""

    def test_random_machines(self):
        rng = random.Random(1978)
        checked = 0
        while checked < 25:
            size = rng.randint(2, 7)
            labels = [f"s{i}" for i in range(size)] + ["stop"]
            prog = {}
            for i in range(size):
                if rng.random() < 0.5:
                    prog[f"s{i}"] = ("inc", rng.choice("xy"), rng.choice(labels))
                else:
                    prog[f"s{i}"] = ("dec", rng.choice("xy"), rng.choice(labels), rng.choice(labels))
            prog["stop"] = ("halt",)
            machine = (["x", "y"], {"x": rng.randint(0, 6), "y": rng.randint(0, 6)}, prog, "s0")
            expected = minsky.simulate(*machine, limit=2000)
            if expected is None:
                continue
            self.assertEqual(run(minsky.compile_machine(*machine)).lines,
                             [f"{c} = {v}" for c, v in expected.items()])
            checked += 1


class SelfHosting(unittest.TestCase):
    """The compiler is a Tainted program; built from the seed, it builds itself."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "compiler.tainted")) as f:
            cls.compiler = f.read()
        with open(os.path.join(ROOT, "boot", "tc.c")) as f:
            cls.seed = f.read()

    def compile_with(self, core, source):
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run([core], input=source, capture_output=True, text=True,
                                  env=dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h.json")))

    def test_the_seed_is_what_the_compiler_says_of_itself(self):
        res = self.compile_with(CORE, self.compiler)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, self.seed)

    def test_without_recall_the_compiler_forgets(self):
        forgetful = "\n".join(line for line in self.compiler.splitlines()
                              if line.strip() != "recall name result") + "\n"
        res = self.compile_with(CORE, forgetful)
        self.assertEqual(res.returncode, 0, res.stderr)
        with tempfile.TemporaryDirectory() as d:
            c = os.path.join(d, "forgetful.c")
            with open(c, "w") as f:
                f.write(res.stdout)
            core = os.path.join(d, "forgetful")
            subprocess.run([CC, *FLAGS, c, os.path.join(CACHE, "runtime.o"), "-o", core, "-lm"], check=True)
            again = self.compile_with(core, self.compiler)
        self.assertNotEqual(again.stdout, self.seed)
        self.assertRegex(again.stdout, r"Value v = E\(w, s\)|\.a=E,")


def classic(name, given=""):
    return run(example(f"classics/{name}.tainted"), given=given)


class Classics(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(classic("hello-world").lines, ["Hello, world"])

    def test_fizzbuzz(self):
        want = ["FizzBuzz" if n % 15 == 0 else "Fizz" if n % 3 == 0 else
                "Buzz" if n % 5 == 0 else str(n) for n in range(1, 31)]
        self.assertEqual(classic("fizzbuzz").lines, want)

    def test_factorial(self):
        self.assertEqual(classic("factorial").lines,
                         [f"{n}! = {math.factorial(n)}" for n in range(1, 21)])

    def test_fibonacci(self):
        a, b, want = 0, 1, []
        for _ in range(30):
            want.append(str(a))
            a, b = b, a + b
        self.assertEqual(classic("fibonacci").lines, want)

    def test_primes(self):
        want = [str(n) for n in range(2, 100) if all(n % d for d in range(2, n))]
        self.assertEqual(classic("primes").lines, want)

    def test_gcd(self):
        self.assertEqual(classic("gcd").lines, ["gcd(1071, 462) = 21"])

    def test_cat_reverse_wc(self):
        text = "first line\nsecond one\n\nlast\n"
        self.assertEqual(classic("cat", text).lines, text.splitlines())
        self.assertEqual(classic("reverse", text).lines, [l[::-1] for l in text.splitlines()])
        self.assertEqual(classic("wc", text).lines, ["4 5 28"])

    def test_bottles(self):
        lines = classic("bottles").lines
        self.assertEqual(len(lines), 99 * 3 + 2)
        self.assertEqual(lines[-7], "Take one down and pass it around, 1 bottle of beer on the wall.")

    def test_sort(self):
        numbers = [5, 3, 10, 1, 42, 7, 7, 0]
        self.assertEqual(classic("sort", "\n".join(map(str, numbers)) + "\n").lines,
                         [str(n) for n in sorted(numbers)])

    def test_sleep_sort(self):
        life = classic("sleep-sort")
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, ["1", "2", "3", "5", "7", "8", "9"])

    def test_ping_pong(self):
        lines = classic("ping-pong").lines
        self.assertEqual(lines[:5], [f"pong {n}" for n in range(5)])
        self.assertEqual(lines[-1], "ping and pong: romantic love")

    def test_producer_consumer(self):
        self.assertEqual(classic("producer-consumer").lines, ["sum 45, afraid of the producer: 1"])

    def test_hanoi(self):
        lines = classic("hanoi").lines
        self.assertEqual(len(lines), 15)
        self.assertEqual(lines[7], "disk 4: A -> C")

    def test_philosophers(self):
        life = classic("philosophers")
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines[-1], "everyone has eaten")
        for i in range(1, 6):
            self.assertEqual([l for l in life.lines if l.startswith(f"philosopher {i} ")],
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
        life = run(f.read(), given="\n".join(lines) + "\n")
    placement = {}
    for line in life.lines:
        words = line.split()
        if words[1:3] == ["lives", "on"]:
            placement[words[0]] = words[3]
        elif words[1:4] == ["has", "nowhere", "to"] and len(words) == 5:
            placement[words[0]] = None
    return life.code, placement, life.lines, life


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
        self.assertEqual(world.feelings[("cache", "beta")]["scars"], 1)

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
        b.last_story = None
        with open(os.path.join(ROOT, "taintednetes.tainted")) as f:
            b.program, _ = compile_source(f.read())
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
        with open(os.path.join(ROOT, "kube", "parting.tainted")) as f:
            program, _ = compile_source(f.read())
        d = tempfile.mkdtemp()
        life = subprocess.Popen([program], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, bufsize=1,
                                env=dict(os.environ, TAINTED_HISTORY=os.path.join(d, "h.json")))
        history, born = [], 0
        self.logs = []
        try:
            for tick in range(1, ticks + 1):
                for line in (["tick %d" % tick]
                             + ["node %s %s" % (k, " ".join(v)) for k, v in nodes.items()]
                             + ["pod %s %s" % (k, " ".join(v)) for k, v in pods.items()]
                             + ["end"]):
                    life.stdin.write(line + "\n")
                life.stdin.flush()
                said = []
                while True:
                    line = life.stdout.readline()
                    self.assertTrue(line, "the operator stopped before it was done")
                    if line.strip() == "done":
                        break
                    said.append(line.rstrip("\n"))
                cmds = [c for c in said if not c.startswith("log ")]
                history.append(cmds)
                self.logs.extend(c for c in said if c.startswith("log "))
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
        finally:
            life.stdin.close()
            life.wait(timeout=10)
            shutil.rmtree(d, ignore_errors=True)
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
        """A block followed by its output is a program; a block that is not
        is a file a program learns from, named in its first comment."""
        with open(os.path.join(ROOT, "docs", name)) as f:
            text = f.read()
        blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.S)
        checked = 0
        with tempfile.TemporaryDirectory() as d:
            for i, (lang, body) in enumerate(blocks):
                if lang != "tainted":
                    continue
                given, j = "", i + 1
                if blocks[j][0] == "input":
                    given, j = blocks[j][1], j + 1
                if blocks[j][0] != "output":
                    module = re.match(r"# (\S+?):", body).group(1)
                    with open(os.path.join(d, module), "w") as f:
                        f.write(body)
                    continue
                source = os.path.join(d, f"program{checked}.tainted")
                with open(source, "w") as f:
                    f.write(body)
                program = os.path.join(d, f"program{checked}")
                subprocess.run([os.path.join(ROOT, "bin", "tc"), source, "-o", program], check=True)
                res = subprocess.run([program], input=given, capture_output=True, text=True, cwd=d,
                                     env=dict(os.environ, TAINTED_HISTORY=os.path.join(d, f"h{checked}")))
                self.assertEqual(res.returncode, 0, body[:40] + res.stderr)
                self.assertEqual(res.stdout.splitlines(), blocks[j][1].splitlines(), body[:40])
                checked += 1
        self.assertGreaterEqual(checked, 17)

    def test_tutorial_programs(self):
        self.check("tutorial.md")

    def test_translated_tutorial_programs(self):
        self.check("tutorial.ru.md")

class Golden(unittest.TestCase):
    def test_every_recorded_program(self):
        res = subprocess.run(["sh", os.path.join(ROOT, "tests", "golden.sh"), CORE],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:])


if __name__ == "__main__":
    unittest.main()
