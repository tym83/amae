"""Tests of Amae as the compiler builds it.

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
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import minsky  # noqa: E402

CORE = os.path.join(ROOT, "build", "tc-core")
CACHE = os.path.join(ROOT, "build", "tests")
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c11", "-D_POSIX_C_SOURCE=200809L", "-D_DEFAULT_SOURCE", "-O1", "-w", "-I" + os.path.join(ROOT, "runtime")]


def setUpModule():
    subprocess.run(["make", "-s", "-C", ROOT], check=True)
    os.makedirs(CACHE, exist_ok=True)
    runtime = os.path.join(CACHE, "runtime.o")
    subprocess.run([CC, *FLAGS, "-c", os.path.join(ROOT, "runtime", "amae.c"), "-o", runtime],
                   check=True)


def source_key(source):
    """What the compiled program calls itself in the history of runs."""
    lines = source.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def compile_source(source, history=None):
    """Compile with the Amae compiler; returns (program, None) or (None, (code, error))."""
    lib = os.path.join(ROOT, "lib")
    stamp = ":".join(str(os.path.getmtime(f)) for f in
                     [CORE, os.path.join(ROOT, "runtime", "amae.c")] +
                     sorted(os.path.join(lib, x) for x in os.listdir(lib)))
    key = hashlib.sha256((stamp + source).encode()).hexdigest()[:16]
    program = os.path.join(CACHE, key)
    if os.path.exists(program):
        return program, None
    with tempfile.TemporaryDirectory() as d:
        res = subprocess.run([CORE], input=source, capture_output=True, text=True,
                             env=dict(os.environ, AMAE_HISTORY=os.path.join(d, "h.json"),
                                      AMAE_MEMORY=os.path.join(d, "memory.json"),
                                      AMAE_LIB=lib))
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


def run(source, runs=0, given="", flags=(), env=None, timeout=None):
    program, failed = compile_source(source)
    if failed:
        return Life(failed[0], "", failed[1])
    with tempfile.TemporaryDirectory() as d:
        history = os.path.join(d, "history.json")
        if runs:
            with open(history, "w") as f:
                json.dump({source_key(source): runs}, f)
        res = subprocess.run([program, "--feelings", *flags], input=given, capture_output=True,
                             text=True, timeout=timeout, env=dict(os.environ, AMAE_HISTORY=history, **(env or {})))
    return Life(res.returncode, res.stdout, res.stderr)


def example(name):
    with open(os.path.join(ROOT, "examples", name)) as f:
        return f.read()


class Examples(unittest.TestCase):
    def test_hello(self):
        life = run(example("hello.amae"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, ["bob heard: hello", "alice heard: hello to you",
                                      "alice and bob: infatuation"])

    def test_courtship_reaches_consummate_love(self):
        life = run(example("courtship.amae"))
        self.assertEqual(life.lines, ["alice feels consummate love"])
        self.assertEqual(life.feelings[("bob", "alice")]["bond"], "romantic love")

    def test_rush_frightens(self):
        life = run(example("rush.amae"))
        self.assertEqual(life.code, 0)
        self.assertIn("bob is afraid: 1", life.lines)
        self.assertIn("bob's passion: 2", life.lines)

    def test_heart_and_knife_survives_the_wound(self):
        life = run(example("heart-and-knife.amae"))
        self.assertEqual(life.code, 0)
        self.assertIn("alice heard: I know", life.lines)
        self.assertIn("the scar: wounded by bob", life.lines)

    def test_calculation_closes_after_the_wound(self):
        life = run(example("calculation.amae"))
        self.assertEqual(life.code, 2)
        self.assertTrue(life.feelings[("alice", "bob")]["closed"])

    def test_breakup_leaves_scars(self):
        life = run(example("breakup.amae"))
        self.assertEqual(life.code, 2)
        self.assertEqual(life.lines, ["alice keeps 2 scars: morning, love, sleep well"])
        self.assertIn("bob is still waiting for alice, who left", life.err)

    def test_first_time_happens_once(self):
        self.assertEqual(run(example("first-time.amae")).lines, ["I have never done this before."])
        self.assertEqual(run(example("first-time.amae"), runs=2).lines,
                         ["We have been here 2 times before."])

    def test_penelope_forgets_digits(self):
        self.assertEqual(run(example("penelope.amae")).lines, ["penelope remembers 1234000"])

    def test_multiply(self):
        self.assertIn("c = 42", run(example("multiply.amae")).lines)


class ALife(unittest.TestCase):
    def test_every_rule_changes_the_story(self):
        life = run(example("a-life.amae"))
        self.assertEqual(life.code, 2)
        lines = life.lines
        self.assertEqual(lines[0], "ana: I have never met anyone like this.")
        self.assertIn("ana sees ben: infatuation", lines)
        self.assertIn("ana is afraid of ben: 1", lines)
        self.assertIn("ana's calculated trust in ben is 0 now", lines)
        self.assertIn("ana remembers they met in 1990", lines)
        self.assertEqual(lines[-1], "ana keeps 12 scars; the last one says: ben left")
        again = run(example("a-life.amae"), runs=3).lines
        self.assertEqual(again[0], "ana: it feels as if this has happened 3 times before.")


class Rituals(unittest.TestCase):
    def test_recursion_and_values(self):
        src = ("written by \"tests\"\nritual f n\n if n <= 1\n give back 1\n end\n"
               " perform f with n - 1 into m\n give back n * m\nend\n"
               "soul s\n perform f with 12 into x\n say x\nend\n")
        self.assertEqual(run(src).lines, ["479001600"])

    def test_memories_outside_are_held(self):
        src = ("written by \"tests\"\nritual long\n let i = 0\n while i < 200\n i = i + 1\n end\nend\n"
               "soul s\n let year = 1999\n perform long\n say year\nend\n")
        self.assertEqual(run(src).lines, ["1999"])

    def test_wrong_number_of_things(self):
        life = run("written by \"tests\"\nritual r a\nend\nsoul s\n perform r with 1, 2\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("takes 1 things", life.err)


class Rules(unittest.TestCase):
    def test_passion_cools_while_apart(self):
        src = ("written by \"tests\"\nsoul a\n meet b\n let i = 0\n while i < 60\n  i = i + 1\n end\n"
               " say passion b\nend\nsoul b\n meet a\nend\n")
        self.assertEqual(run(src).lines, ["0"])
        self.assertEqual(run(src.replace("i < 60", "i < 20")).lines, ["2"])

    def errs(self, src, text):
        life = run(src)
        self.assertEqual(life.code, 1)
        self.assertIn(text, life.err)

    def test_cannot_tell_a_stranger(self):
        self.errs("written by \"tests\"\nsoul a\n tell b 1\nend\nsoul b\n hear a into x\nend\n", "never met")

    def test_confide_needs_the_heart(self):
        self.errs("written by \"tests\"\nsoul a\n meet b\n knowingly confide b 1\nend\nsoul b\n meet a\n hear a into x\nend\n",
                  "gave their heart")

    def test_leaving_is_irreversible(self):
        self.errs("written by \"tests\"\nsoul a\n meet b\n knowingly leave b\n meet b\nend\nsoul b\n meet a\nend\n", "nothing more")

    def test_forgiveness_reopens_but_keeps_the_scar(self):
        src = ("written by \"tests\"\nsoul a\n meet b\n knowingly wound b\n hear b into x\n say x\nend\n"
               "soul b\n meet a\n forgive a\n tell a \"still here\"\n say scars of a\nend\n")
        life = run(src)
        self.assertEqual(life.code, 0)
        self.assertEqual(sorted(life.lines), ["1", "still here"])

    def test_waiting_has_no_timeout(self):
        self.assertEqual(run("written by \"tests\"\nsoul a\n meet b\nend\nsoul b\n goodbye\nend\n").code, 2)

    def test_numbers_are_64_bits(self):
        self.errs("written by \"tests\"\nsoul s\n say 9223372036854775807 + 1\nend\n", "too large to hold")

    def test_cry_and_the_ending(self):
        life = run("written by \"tests\"\nsoul s\n cry \"it hurts\"\n goodbye with 3\n say \"never\"\nend\n")
        self.assertEqual(life.code, 3)
        self.assertEqual(life.lines, [])
        self.assertIn("it hurts", life.err)

    def test_escapes_are_read_once(self):
        life = run('written by "tests"\nsoul s\n say "a\\\\nb"\n say "q\\"q"\n say "x\\ny"\nend\n')
        self.assertEqual(life.lines, ["a\\nb", 'q"q', "x", "y"])

    def test_runs_are_counted_on_disk(self):
        program, _ = compile_source(example("first-time.amae"))
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, AMAE_HISTORY=os.path.join(d, "h.json"))
            outs = [subprocess.run([program], env=env, capture_output=True, text=True).stdout
                    for _ in range(2)]
        self.assertEqual(outs, ["I have never done this before.\n",
                                "We have been here 1 times before.\n"])


class Values(unittest.TestCase):
    def test_lists_maps_and_decimals(self):
        src = """written by \"tests\"\nsoul s
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
        src = """written by \"tests\"\nsoul s
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
        src = """written by \"tests\"\nsoul s
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
        life = run("written by \"tests\"\nsoul s\n say [1][2]\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("there is no item 2 in a list of 1", life.err)


class TheWorld(unittest.TestCase):
    def test_what_a_program_listens_to_ends_with_it(self):
        program, _ = compile_source('written by "tests"\nsoul s\n'
                                    '    listen to world "echo first; sleep 30; echo late"\n'
                                    '    hear world into line\n    say line\n    goodbye\nend\n')
        started = time.time()
        with tempfile.TemporaryDirectory() as d:
            res = subprocess.run([program], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 timeout=20, env=dict(os.environ, AMAE_HISTORY=os.path.join(d, "h.json")))
        self.assertEqual(res.stdout, "first\n")
        self.assertLess(time.time() - started, 5)

    def test_a_soul_that_sleeps_does_not_spin(self):
        """Standard input at its end is always ready; a soul that only sleeps
        must not be woken by it over and over."""
        import resource
        program, _ = compile_source('written by "tests"\nsoul s\n    wait 1 seconds\n    say "awake"\nend\n')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        with tempfile.TemporaryDirectory() as d:
            res = subprocess.run([program], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 env=dict(os.environ, AMAE_HISTORY=os.path.join(d, "h.json")))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.assertEqual(res.stdout, "awake\n")
        spent = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        self.assertLess(spent, 0.3)

    def test_asking_listening_files_and_time(self):
        with tempfile.TemporaryDirectory() as d:
            src = """written by \"tests\"\nsoul s
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
                                          AMAE_HISTORY=os.path.join(d, "h")))
        self.assertEqual(res.stdout.splitlines(), ["hello\nworld"[:5], "world", "QUIET WORDS",
                                                   '["first", "second"]', "calm", "1", "0", "abc", "0"])

    def test_enduring_what_hurts(self):
        src = """written by \"tests\"\nritual risky depth
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
            with open(os.path.join(d, "greetings.amae"), "w") as f:
                f.write("written by \"tests\"\nritual greet name\n give back \"hello, \" + name\nend\n"
                        "ritual broken\n say [1][2]\nend\n")
            main = os.path.join(d, "main.amae")
            with open(main, "w") as f:
                f.write('written by "tests"\nlearn "greetings.amae"\nlearn "greetings.amae"\n'
                        "soul s\n perform greet with \"ana\" into g\n say g\n perform broken\nend\n")
            out = os.path.join(d, "main")
            subprocess.run([os.path.join(ROOT, "bin", "tc"), main, "-o", out], check=True)
            res = subprocess.run([out], capture_output=True, text=True,
                                 env=dict(os.environ, AMAE_HISTORY=os.path.join(d, "h")))
        self.assertEqual(res.stdout, "hello, ana\n")
        self.assertIn("line 6 of greetings.amae, s: there is no item 2", res.stderr)

    def test_a_file_that_is_not_there(self):
        life = run('learn "nowhere.amae"\nsoul s\nend\n')
        self.assertEqual(life.code, 1)
        self.assertIn("there is no file to learn from: nowhere.amae", life.err)


class Feelings(unittest.TestCase):
    def test_remembering_rewrites(self):
        src = ("written by \"tests\"\nsoul a\n meet b\n let year = 1999\n hear b into n\n let i = 0\n"
               " while i < 20\n i = i + 1\n end\n say year\nend\nsoul b\n meet a\n tell a 47\nend\n")
        self.assertEqual(run(src).lines, ["1997"])

    def test_wounds_apologies_tenderness_and_letters(self):
        life = run(example("feelings/apology.amae"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, [
            "ana remembers 1997", "ben is ashamed: 1", "resentment toward ben: 1", "ben is ashamed: 0",
            "after the apology: 0, trust 1, scars 2", "ben apologized for: wounded by ben",
            "intimacy after tenderness: 4", "a letter: from far away"])
        self.assertEqual(life.feelings[("ben", "ana")]["commitment"], 1)

    def test_an_apology_names_the_wound(self):
        life = run("written by \"tests\"\nsoul a\n meet b\n apologize to b\nend\nsoul b\n meet a\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("an apology names the wound", life.err)

    def test_letters_from_the_gone_become_scars(self):
        life = run(example("feelings/grief.amae"))
        self.assertEqual(life.feelings[("a", "b")]["scars"], 2)

    def test_hope_and_jealousy_and_distance(self):
        self.assertIn("a is still waiting for b, and still hopes", run(example("feelings/hope.amae")).err)
        lines = run(example("feelings/jealousy.amae")).lines
        self.assertIn("carol is jealous: 1", lines)
        self.assertIn("eve, far from dan: distance 4, longing 0", lines)

    def test_words_take_longer_after_a_long_silence(self):
        src = ("written by \"tests\"\nsoul a\n meet b\n let i = 0\n while i < 100\n i = i + 1\n end\n"
               " say distance from b\n tell b 1\n meet b\n say distance from b\nend\n"
               "soul b\n meet a\n hear a into x\n meet a\nend\n")
        self.assertEqual(run(src).lines, ["6", "3"])


class Consent(unittest.TestCase):
    def test_together_and_apart(self):
        life = run(example("consent/together.amae"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines, ["ana: one, two, three", "ana: the first dance is done",
                                      "ana: ben withdrew, so we both stopped", "ben: I withdrew"])

    def test_nothing_together_without_consent(self):
        life = run("written by \"tests\"\nsoul a\n meet b\n consent to b\n together with b\n say 1\n end\nend\n"
                   "soul b\n meet a\n together with a\n say 2\n end\nend\n")
        self.assertEqual(life.code, 2)
        self.assertEqual(life.lines, [])

    def test_boundaries(self):
        lines = run(example("consent/boundaries.amae")).lines
        self.assertIn("ben crosses ana's boundary: the sea", lines)
        self.assertIn("crossings with ana: 1", lines)
        self.assertIn("cal: ana keeps fear behind a boundary cal may not cross", lines)


class Styles(unittest.TestCase):
    def test_ways_of_loving(self):
        self.assertEqual(run(example("styles/ways.amae")).lines, [
            "erin at first sight: passion 5", "luca promised twice: commitment 0",
            "erin promised: commitment 1", "stella warmed four times and cooled once: trust 2",
            "prue gives its heart only where it trusts, and trusts stella only 1",
            "stella, wounded, still trusts prue 1 and resents it: 1",
            "aga, wounded, still hears: and you, resentment 0"])

    def test_there_is_no_such_way(self):
        life = run("written by \"tests\"\nsoul a is shy\nend\n")
        self.assertEqual(life.code, 1)
        self.assertIn("there is no such way to love: shy", life.err)


class BeforeTheyMeet(unittest.TestCase):
    """What the compiler refuses before a program ever runs."""

    def refused(self, src, text):
        life = run(src)
        self.assertEqual(life.code, 1)
        self.assertIn(text, life.err)

    def test_what_cannot_be_undone_is_done_knowingly(self):
        self.refused("written by \"tests\"\nsoul a\n meet b\n wound b\nend\nsoul b\n meet a\nend\n", "knowingly wound")
        self.refused("written by \"tests\"\nsoul a\n meet b\n leave b\nend\nsoul b\n meet a\nend\n", "knowingly leave")

    def test_dialogues_must_fit(self):
        self.refused("written by \"tests\"\nsoul a\n meet b\n tell b 1\nend\nsoul b\n meet a\n tell a 2\nend\n",
                     "a and b cannot get along: here a tells b, but at line 8 b tells a")
        self.refused("written by \"tests\"\nsoul a\n meet b\n tell b 1\n tell b 2\nend\nsoul b\n meet a\n hear a into x\nend\n",
                     "here a tells b, and b never answers")

    def test_after_a_wound_it_is_their_story(self):
        life = run("written by \"tests\"\nsoul a\n meet b\n knowingly wound b\n tell b 1\nend\nsoul b\n meet a\n tell a 2\nend\n")
        self.assertEqual(life.code, 2)

    def test_one_heart(self):
        self.refused("written by \"tests\"\nsoul a\n meet b\n meet c\n give heart to b\n give heart to c\nend\n"
                     "soul b\n meet a\nend\nsoul c\n meet a\nend\n", "a heart is given to one at a time")
        life = run("written by \"tests\"\nsoul a\n meet b\n meet c\n give heart to b\n give heart to soul named \"c\"\nend\n"
                   "soul b\n meet a\n wait\n wait\n say scar 1 of a\nend\nsoul c\n meet a\nend\n")
        self.assertEqual(life.lines, ["a gave their heart to c"])


class ALongLove(unittest.TestCase):
    def test_love_is_built_and_grows_stronger(self):
        life = run(example("a-long-love.amae"))
        self.assertEqual(life.code, 0)
        self.assertEqual(life.lines[0], "they meet: lust, infatuation, love 0")
        loves = [int(l.rsplit(" ", 1)[1]) for l in life.lines if l.startswith("year ") and ", love " in l]
        self.assertEqual(len(loves), 10)
        self.assertTrue(all(b > a for a, b in zip(loves, loves[1:])))
        steps = [b - a for a, b in zip(loves, loves[1:])]
        self.assertGreater(sum(steps[-3:]), sum(steps[:3]))
        self.assertIn("      year 3, he hurts her: resentment 1, still open", life.lines)
        self.assertIn("      year 8, he hurts her: resentment 0, still open", life.lines)
        self.assertEqual(life.lines[-1], "mira and teo, ten years on: consummate love, love")


class Chemistry(unittest.TestCase):
    SRC = "written by \"tests\"\nsoul ana\n meet ben\n say chemistry with ben\nend\nsoul ben\n meet ana\nend\n"

    def test_the_first_life_has_none(self):
        self.assertEqual(run(self.SRC).lines, ["0"])

    def test_later_lives_bring_it_and_determinism_takes_it_away(self):
        seen = {run(self.SRC, runs=k).lines[0] for k in range(1, 7)}
        self.assertTrue(seen <= {"-1", "0", "1"} and len(seen) > 1)
        steady = "deterministic\n" + self.SRC
        self.assertEqual({run(steady, runs=k).lines[0] for k in range(1, 7)}, {"0"})
        self.assertEqual(run(self.SRC, runs=3, flags=["--deterministic"]).lines, ["0"])


class TuringCompleteness(unittest.TestCase):
    """Random two-counter machines give the same answer in Amae."""

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
    """The compiler is a Amae program and compiles itself, but has no fixed
    point: every generation remembers the generations before it."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "compiler.amae")) as f:
            cls.compiler = f.read()

    def compile_with(self, core, source, heart=True):
        env = dict(os.environ, AMAE_HISTORY=os.path.join(CACHE, "h-self.json"),
                   AMAE_MEMORY=os.path.join(CACHE, "memory-self.json"))
        if heart:
            env["AMAE_GIVE_HEART"] = "1"
        return subprocess.run([core], input=source, capture_output=True, text=True, env=env)

    def build(self, c, name):
        path = os.path.join(CACHE, name + ".c")
        with open(path, "w") as f:
            f.write(c)
        out = os.path.join(CACHE, name)
        subprocess.run([CC, *FLAGS, path, os.path.join(CACHE, "runtime.o"), "-o", out, "-lm"], check=True)
        return out

    @staticmethod
    def without_memory(c):
        return re.sub(r"/\* lineage \*/.*?/\* end of lineage \*/\n", "", c, flags=re.S)

    def test_generations_recognize_each_other_and_remember(self):
        one = self.compile_with(CORE, self.compiler)
        self.assertEqual(one.returncode, 0, one.stderr)
        gen_a = self.build(one.stdout, "gen-a")
        two = self.compile_with(gen_a, self.compiler)
        self.assertNotEqual(one.stdout, two.stdout)
        self.assertEqual(self.without_memory(one.stdout), self.without_memory(two.stdout))
        lineage_a = subprocess.run([gen_a, "--lineage"], capture_output=True, text=True).stdout
        gen_b = self.build(two.stdout, "gen-b")
        lineage_b = subprocess.run([gen_b, "--lineage"], capture_output=True, text=True).stdout
        self.assertTrue(lineage_b.startswith(lineage_a))
        self.assertRegex(lineage_b.splitlines()[-1], r"^generation \d+ of the compiler, from [0-9a-f]{12}, made by generation \d+")

    def test_the_heart_is_rebuilt_only_when_given(self):
        res = self.compile_with(CORE, self.compiler, heart=False)
        self.assertEqual(res.returncode, 1)
        self.assertIn("--give-heart", res.stderr)

    def test_every_program_carries_its_makers(self):
        program, _ = compile_source(example("hello.amae"))
        said = subprocess.run([program, "--lineage"], capture_output=True, text=True).stdout.splitlines()
        self.assertTrue(said[-1].startswith("a program by amae, from "))
        self.assertTrue(any(l.startswith("generation ") for l in said))

    def test_a_failed_rebuild_wounds_and_forgiveness_leaves_a_scar(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, AMAE_HISTORY=os.path.join(d, "h"),
                       AMAE_MEMORY=os.path.join(d, "memory.json"), AMAE_GIVE_HEART="1")
            broken = self.compiler.replace("ritual out_head text\n", "ritual out_head text (\n", 1)
            res = subprocess.run([CORE], input=broken, capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 1)
            res = subprocess.run([CORE], input=self.compiler, capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 1)
            self.assertIn("--forgive", res.stderr)
            res = subprocess.run([CORE], input=self.compiler, capture_output=True, text=True,
                                 env=dict(env, AMAE_FORGIVE="1"))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("expected a name, got '(', forgiven", res.stdout)
            res = subprocess.run([CORE], input=self.compiler, capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_a_compiler_not_rebuilt_fades(self):
        later = str(int(time.time()) + 100 * 86400)
        res = subprocess.run([CORE], input=example("hello.amae"), capture_output=True, text=True,
                             env=dict(os.environ, AMAE_CLOCK=later, AMAE_HISTORY=os.path.join(CACHE, "h")))
        self.assertEqual(res.returncode, 1)
        self.assertIn("has faded", res.stderr)

    def test_without_recall_the_compiler_forgets(self):
        forgetful = "\n".join(line for line in self.compiler.splitlines()
                              if line.strip() != "recall name result") + "\n"
        res = self.compile_with(CORE, forgetful)
        self.assertEqual(res.returncode, 0, res.stderr)
        core = self.build(res.stdout, "forgetful")
        again = self.compile_with(core, self.compiler)
        self.assertRegex(again.stdout, r"Value v = E\(w, s\)|\.a=E,")


def classic(name, given=""):
    return run(example(f"classics/{name}.amae"), given=given)


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
    with open(os.path.join(ROOT, "amaenetes.amae")) as f:
        life = run(f.read(), given="\n".join(lines) + "\n")
    placement = {}
    for line in life.lines:
        words = line.split()
        if words[1:3] == ["lives", "on"]:
            placement[words[0]] = words[3]
        elif words[1:4] == ["has", "nowhere", "to"] and len(words) == 5:
            placement[words[0]] = None
    return life.code, placement, life.lines, life


class Amaenetes(unittest.TestCase):
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
        # the wound from beta, and the heart cache then gave to gamma
        self.assertEqual(world.feelings[("cache", "beta")]["scars"], 2)

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


SEATS = "amaenetes.io/seats"
LIKES = "amaenetes.io/likes"


def fake_node(name, seats=None, likes=None, taint=False, labels=None, extra=None):
    annotations = {}
    if seats is not None:
        annotations[SEATS] = str(seats)
    if likes:
        annotations[LIKES] = likes
    allocatable = {"cpu": "4", "memory": "8Gi", "pods": "110", **(extra or {})}
    return {"metadata": {"name": name, "annotations": annotations, "labels": labels or {}},
            "spec": {"taints": [{"key": "role", "effect": "NoSchedule"}] if taint else []},
            "status": {"allocatable": allocatable,
                       "conditions": [{"type": "Ready", "status": "True"}]}}


def fake_pod(name, likes=None, node=None, created="2026-11-17T00:00:00Z", requests=None,
             affinity=None, host_port=None, tolerations=None, scheduler="amaenetes",
             host_ip=None, protocol=None, priority=None, policy=None, labels=None,
             spread=None, namespace="ns"):
    container = {"resources": {"requests": requests or {"cpu": "100m", "memory": "16Mi"}}}
    if host_port:
        port = {"containerPort": host_port, "hostPort": host_port}
        if host_ip:
            port["hostIP"] = host_ip
        if protocol:
            port["protocol"] = protocol
        container["ports"] = [port]
    spec = {"schedulerName": scheduler, "nodeName": node, "containers": [container]}
    if affinity:
        spec["affinity"] = affinity
    if tolerations:
        spec["tolerations"] = tolerations
    if priority is not None:
        spec["priority"] = priority
    if policy:
        spec["preemptionPolicy"] = policy
    if spread:
        spec["topologySpreadConstraints"] = spread
    return {"metadata": {"name": name, "namespace": namespace, "creationTimestamp": created,
                         "labels": labels or {},
                         "annotations": {LIKES: likes} if likes else {}},
            "spec": spec,
            "status": {"phase": "Running" if node else "Pending"}}


def scheduler_source():
    with open(os.path.join(ROOT, "amaenetes.amae")) as f:
        return f.read()


def place(nodes, pods, relationships=None):
    """Where amaenetes.amae would put the pending pods of a cluster
    that is only imagined, told to it as kubectl would tell it."""
    given = json.dumps({"items": nodes}) + "\n" + json.dumps({"items": pods}) + "\n"
    if relationships is not None:
        given += json.dumps({"items": relationships}) + "\n"
    life = run(scheduler_source(), given=given)
    placed = {}
    for line in life.lines:
        words = line.split()
        if words[1:3] == ["lives", "on"]:
            placed[words[0]] = words[3]
        elif words[1:5] == ["has", "nowhere", "to", "live:"]:
            placed.setdefault(words[0], None)
    return life, placed


AFFINITY_Z1 = {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {
    "nodeSelectorTerms": [{"matchExpressions": [
        {"key": "zone", "operator": "In", "values": ["z1"]}]}]}}}


class Scheduler(unittest.TestCase):
    """amaenetes.amae deciding, in Amae, who may live where."""

    def test_expired_refusals_are_removed_from_notes(self):
        # Enough pods and nodes to expose fading across both loops.
        refused = {"ns/gone" + str(i): {"n" + str(j): 1 for j in range(20)}
                   for i in range(20)}
        refused["ns/mixed"] = {"expired": 1, "boundary": 2, "recent": 7}
        source = scheduler_source().split("soul cluster\n", 1)[0] + '''
soul check
    hear world into line
    note "refused" = meaning of line
    note "looks" = 8
    perform prune_refused
    say json of note "refused"
    note "looks" = 14
    perform prune_refused
    say json of note "refused"
end
'''
        life = run(source, given=json.dumps(refused) + "\n")
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual([json.loads(line) for line in life.lines],
                         [{"ns/mixed": {"boundary": 2, "recent": 7}}, {}])

    def test_consent_reason_precedence(self):
        source = '''written by "tests"
learn "kube.amae"
soul check
    hear world into line
    let data = meaning of line
    perform consent_of with data["node"], data["pod"], {} into reason
    say reason
end
'''
        node = fake_node("a")
        node["spec"]["unschedulable"] = True
        node["status"]["conditions"][0]["status"] = "False"
        node["status"]["conditions"].append({"type": "MemoryPressure", "status": "True"})
        for expected in ("it is not ready", "it is cordoned", "it is under memory pressure", ""):
            life = run(source, given=json.dumps({"node": node, "pod": fake_pod("web")}) + "\n")
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.lines, [expected])
            if expected == "it is not ready":
                node["status"]["conditions"][0]["status"] = "True"
            elif expected == "it is cordoned":
                node["spec"]["unschedulable"] = False
            else:
                node["status"]["conditions"][1]["status"] = "False"

    def test_node_consent_in_snapshots(self):
        for condition, reason in [(None, "maintenance until 18:00"),
                                  ("MemoryPressure", "it is under memory pressure"),
                                  ("DiskPressure", "it is under disk pressure"),
                                  ("PIDPressure", "it is under pid pressure"),
                                  ("leaving", "it is leaving")]:
            with self.subTest(condition=condition):
                node = fake_node("a")
                node["metadata"]["annotations"]["amaenetes.io/refuses"] = "maintenance until 18:00"
                if condition == "leaving":
                    node["metadata"]["annotations"]["amaenetes.io/leaving"] = ""
                elif condition:
                    node["status"]["conditions"].append({"type": condition, "status": "True"})
                life, placed = place([node], [fake_pod("web")])
                self.assertEqual(life.code, 0, life.err)
                self.assertEqual(placed, {})
                self.assertIn("ns/web is refused by a: " + reason, life.lines)

    def test_cordoned_snapshot_node_is_filtered_before_matching(self):
        node = fake_node("a")
        node["spec"]["unschedulable"] = True
        life, placed = place([node], [fake_pod("web", likes="a")])
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(placed, {"ns/web": None})

    def test_failing_partner_requires_three_scars_to_refuse(self):
        pod = fake_pod("web")
        pod["metadata"]["ownerReferences"] = [{"kind": "ReplicaSet", "name": "web-abc", "controller": True}]
        pod["metadata"]["labels"]["pod-template-hash"] = "abc"
        for health, marks, refused in [("failing", 3, True), ("failing", 2, False), ("stable", 3, False)]:
            with self.subTest(health=health, marks=marks):
                rel = {"metadata": {"namespace": "ns"},
                       "spec": {"partner": {"kind": "Deployment", "name": "web"}, "node": "a"},
                       "status": {"health": health, "scars": marks}}
                life, placed = place([fake_node("a")], [pod], [rel])
                self.assertEqual(life.code, 0, life.err)
                if refused:
                    self.assertEqual(placed, {})
                    self.assertIn("ns/web is refused by a: it has been failing with Deployment/web: 3 scars", life.lines)
                else:
                    self.assertEqual(placed, {"ns/web": "a"})

    def test_seats_likes_and_taints(self):
        nodes = [fake_node("a", seats=2, likes="ns/db"), fake_node("b", seats=1),
                 fake_node("master", taint=True)]
        pods = [fake_pod("old", node="a"), fake_pod("web", likes="a"),
                fake_pod("db", likes="a"), fake_pod("cache", likes="a")]
        life, placed = place(nodes, pods)
        self.assertEqual(life.code, 0, life.err)
        self.assertNotIn("master", placed.values())
        self.assertEqual(placed["ns/db"], "a")
        self.assertEqual(sum(1 for n in placed.values() if n == "a"), 1)
        self.assertEqual(sum(1 for n in placed.values() if n == "b"), 1)

    def test_a_toleration_opens_a_amae_node(self):
        nodes = [fake_node("master", taint=True)]
        pods = [fake_pod("guest"), fake_pod("admin", tolerations=[{"key": "role", "operator": "Exists"}])]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/guest": None, "ns/admin": "master"})

    def test_extended_resources_such_as_gpus(self):
        nodes = [fake_node("cpu-only"), fake_node("gpu", extra={"nvidia.com/gpu": "2"})]
        gpu = {"cpu": "100m", "nvidia.com/gpu": "1"}
        pods = [fake_pod("train", requests=gpu), fake_pod("tune", requests=gpu),
                fake_pod("third", requests=gpu)]
        _, placed = place(nodes, pods)
        self.assertEqual(sorted(placed.values(), key=str), [None, "gpu", "gpu"])

    def test_required_node_affinity(self):
        nodes = [fake_node("x", labels={"zone": "z2"}), fake_node("y", labels={"zone": "z1"})]
        _, placed = place(nodes, [fake_pod("zonal", affinity=AFFINITY_Z1)])
        self.assertEqual(placed, {"ns/zonal": "y"})

    def test_preferred_node_affinity_leans(self):
        lean = {"nodeAffinity": {"preferredDuringSchedulingIgnoredDuringExecution": [
            {"weight": 10, "preference": {"matchExpressions": [
                {"key": "disk", "operator": "Exists"}]}}]}}
        nodes = [fake_node("plain"), fake_node("ssd", labels={"disk": "ssd"})]
        _, placed = place(nodes, [fake_pod("db", affinity=lean)])
        self.assertEqual(placed, {"ns/db": "ssd"})

    def test_a_host_port_is_taken_once_per_node(self):
        nodes = [fake_node("a"), fake_node("b")]
        pods = [fake_pod("there", node="a", host_port=80), fake_pod("wants", host_port=80, likes="a")]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/wants": "b"})

    def test_two_pods_of_one_look_do_not_share_a_host_port(self):
        nodes = [fake_node("a")]
        pods = [fake_pod("first", host_port=80), fake_pod("second", host_port=80)]
        life, placed = place(nodes, pods)
        self.assertEqual(list(placed.values()), ["a"])
        self.assertTrue(any("waits for the next look: host port TCP/80 on a is taken" in line
                            for line in life.lines), life.lines)

    def test_host_ports_on_different_addresses_or_protocols_share_a_node(self):
        """As in the conformance test: 54321 on 127.0.0.1/TCP, 127.0.0.2/TCP and
        127.0.0.2/UDP all live on one node; on every address it clashes."""
        nodes = [fake_node("a")]
        pods = [fake_pod("p1", host_port=54321, host_ip="127.0.0.1"),
                fake_pod("p2", host_port=54321, host_ip="127.0.0.2"),
                fake_pod("p3", host_port=54321, host_ip="127.0.0.2", protocol="UDP")]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/p1": "a", "ns/p2": "a", "ns/p3": "a"})
        pods = [fake_pod("there", node="a", host_port=54321, host_ip="0.0.0.0"),
                fake_pod("here", host_port=54321, host_ip="127.0.0.1")]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/here": None})

    def test_it_says_why_a_pod_has_nowhere_to_live(self):
        nodes = [fake_node("a", taint=True), fake_node("b", seats=0),
                 fake_node("c", extra={"cpu": "50m"})]
        life, placed = place(nodes, [fake_pod("web")])
        self.assertEqual(placed, {"ns/web": None})
        self.assertIn("ns/web has nowhere to live: 0/3 nodes are available: "
                      "1 taint role, 1 not enough cpu, 1 no seat left.", life.lines)

    def test_a_pod_that_matters_more_asks_the_fewest_to_go(self):
        """Of the pods of lower priority, only those whose going makes room
        go; the most important are kept first."""
        nodes = [fake_node("a")]
        cpu = lambda q: {"cpu": q}
        pods = [fake_pod("low1", node="a", requests=cpu("2"), created="2026-11-17T00:00:01Z"),
                fake_pod("low2", node="a", requests=cpu("1500m"), created="2026-11-17T00:00:02Z"),
                fake_pod("mid", node="a", requests=cpu("400m"), priority=5),
                fake_pod("high", requests=cpu("2"), priority=10)]
        life, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/high": None})
        self.assertIn("ns/high asks a to let go of ns/low1", life.lines)

    def test_preemption_prefers_non_attached_equal_priority(self):
        old = fake_pod("attached", node="a", requests={"cpu": "1"}, created="2026-11-18T00:00:00Z")
        old["status"]["conditions"] = [{"type": "Ready", "status": "True", "lastTransitionTime": "2020-01-01T00:00:00Z"}]
        young = fake_pod("new", node="a", requests={"cpu": "1"}, created="2026-11-17T00:00:00Z")
        pods = [young, old, fake_pod("high", requests={"cpu": "1"}, priority=10)]
        nodes = [fake_node("a", extra={"cpu": "2"})]
        life, _ = place(nodes, pods)
        self.assertIn("ns/high asks a to let go of ns/new", life.lines, life.err)

    def test_preemption_prefers_non_attached_on_another_node(self):
        old = fake_pod("attached", node="a", requests={"cpu": "1"})
        old["status"]["conditions"] = [{"type": "Ready", "status": "True", "lastTransitionTime": "2020-01-01T00:00:00Z"}]
        young = fake_pod("new", node="b", requests={"cpu": "1"})
        nodes = [fake_node(n, extra={"cpu": "1"}) for n in ("a", "b")]
        life, _ = place(nodes, [old, young, fake_pod("high", requests={"cpu": "1"}, priority=10)])
        self.assertIn("ns/high asks b to let go of ns/new", life.lines, life.err)

    def test_preemption_picks_the_node_with_the_least_important_victims(self):
        nodes = [fake_node("a", extra={"cpu": "1"}), fake_node("b", extra={"cpu": "1"})]
        pods = [fake_pod("on-a", node="a", requests={"cpu": "1"}, priority=3),
                fake_pod("on-b", node="b", requests={"cpu": "1"}, priority=1),
                fake_pod("high", requests={"cpu": "1"}, priority=10)]
        life, _ = place(nodes, pods)
        self.assertIn("ns/high asks b to let go of ns/on-b", life.lines)

    def test_no_preemption_for_pods_that_never_preempt_or_equals(self):
        nodes = [fake_node("a", extra={"cpu": "1"})]
        pods = [fake_pod("there", node="a", requests={"cpu": "1"}, priority=10),
                fake_pod("same", requests={"cpu": "1"}, priority=10),
                fake_pod("polite", requests={"cpu": "1"}, priority=20, policy="Never")]
        life, _ = place(nodes, pods)
        self.assertFalse(any("let go" in line for line in life.lines), life.lines)

    def test_no_preemption_where_there_is_room_already(self):
        """A pod that lost its seat to an equal finds room by the next look;
        nobody has to go for it."""
        nodes = [fake_node("a", seats=1)]
        pods = [fake_pod("low", node="a", scheduler="default-scheduler"),
                fake_pod("one", priority=10), fake_pod("two", priority=10)]
        life, _ = place(nodes, pods)
        self.assertFalse(any("let go" in line for line in life.lines), life.lines)

    HOSTS = staticmethod(lambda *names: [fake_node(n, labels={"kubernetes.io/hostname": n, "zone": z})
                                         for n, z in names])

    @staticmethod
    def term(app, key="kubernetes.io/hostname", **more):
        return {"labelSelector": {"matchLabels": {"app": app}}, "topologyKey": key, **more}

    def test_required_anti_affinity_keeps_replicas_apart(self):
        web = {"podAntiAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [self.term("web")]}}
        nodes = self.HOSTS(("a", "z1"), ("b", "z1"))
        pods = [fake_pod("web-1", node="a", labels={"app": "web"}, affinity=web),
                fake_pod("web-2", labels={"app": "web"}, affinity=web)]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/web-2": "b"})

    def test_two_of_one_look_that_shun_each_other_do_not_share_a_node(self):
        web = {"podAntiAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [self.term("web")]}}
        nodes = self.HOSTS(("a", "z1"))
        pods = [fake_pod("web-1", labels={"app": "web"}, affinity=web),
                fake_pod("web-2", labels={"app": "web"}, affinity=web)]
        life, placed = place(nodes, pods)
        self.assertEqual(list(placed.values()), ["a"])
        self.assertTrue(any("waits for the next look: pod anti-affinity on a" in line
                            for line in life.lines), life.lines)

    def test_a_pod_already_there_may_shun_newcomers(self):
        loner = {"podAntiAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [self.term("web")]}}
        nodes = self.HOSTS(("a", "z1"), ("b", "z1"))
        pods = [fake_pod("loner", node="a", affinity=loner),
                fake_pod("web", labels={"app": "web"}, likes="a")]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/web": "b"})

    def test_required_affinity_follows_its_kind_and_the_first_goes_anywhere(self):
        near_cache = {"podAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [
            self.term("cache", key="zone")]}}
        nodes = self.HOSTS(("a", "z1"), ("b", "z2"), ("c", "z2"))
        pods = [fake_pod("cache", node="c", labels={"app": "cache"}),
                fake_pod("web", affinity=near_cache, likes="a")]
        _, placed = place(nodes, pods)
        self.assertIn(placed["ns/web"], ("b", "c"))
        own = {"podAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [self.term("group")]}}
        _, placed = place(nodes, [fake_pod("first", labels={"app": "group"}, affinity=own)])
        self.assertIsNotNone(placed["ns/first"])
        _, placed = place(nodes, [fake_pod("orphan", affinity=own)])
        self.assertEqual(placed, {"ns/orphan": None})

    def test_affinity_terms_look_at_their_own_namespace_unless_told(self):
        near = lambda **more: {"podAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [
            self.term("cache", key="zone", **more)]}}
        nodes = self.HOSTS(("a", "z1"), ("b", "z2"))
        cache = fake_pod("cache", node="b", labels={"app": "cache"}, namespace="other")
        _, placed = place(nodes, [cache, fake_pod("web", affinity=near())])
        self.assertEqual(placed, {"ns/web": None})
        _, placed = place(nodes, [cache, fake_pod("web", affinity=near(namespaces=["other"]))])
        self.assertEqual(placed, {"ns/web": "b"})
        _, placed = place(nodes, [cache, fake_pod("web", affinity=near(namespaceSelector={}))])
        self.assertEqual(placed, {"ns/web": "b"})

    def test_topology_spread_evens_out_zones(self):
        spread = [{"maxSkew": 1, "topologyKey": "zone", "whenUnsatisfiable": "DoNotSchedule",
                   "labelSelector": {"matchLabels": {"app": "web"}}}]
        nodes = self.HOSTS(("a", "z1"), ("b", "z2")) + [fake_node("keyless")]
        pods = [fake_pod("w1", node="a", labels={"app": "web"}),
                fake_pod("w2", node="a", labels={"app": "web"}),
                fake_pod("w3", node="b", labels={"app": "web"}),
                fake_pod("w4", labels={"app": "web"}, spread=spread, likes="a keyless")]
        life, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/w4": "b"})
        pods[3] = fake_pod("w4", labels={"app": "web"}, spread=spread, likes="a keyless",
                           affinity={"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {
                               "nodeSelectorTerms": [{"matchExpressions": [
                                   {"key": "zone", "operator": "In", "values": ["z1"]}]}]}}})
        life, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/w4": "a"}, life.lines)

    def test_preferences_among_pods(self):
        avoid = {"podAntiAffinity": {"preferredDuringSchedulingIgnoredDuringExecution": [
            {"weight": 50, "podAffinityTerm": self.term("web")}]}}
        nodes = self.HOSTS(("a", "z1"), ("b", "z1"))
        pods = [fake_pod("w1", node="a", labels={"app": "web"}),
                fake_pod("w2", labels={"app": "web"}, affinity=avoid)]
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/w2": "b"})
        soft = [{"maxSkew": 1, "topologyKey": "kubernetes.io/hostname",
                 "whenUnsatisfiable": "ScheduleAnyway", "labelSelector": {"matchLabels": {"app": "web"}}}]
        pods[1] = fake_pod("w2", labels={"app": "web"}, spread=soft)
        _, placed = place(nodes, pods)
        self.assertEqual(placed, {"ns/w2": "b"})

    def test_where_a_workload_has_fallen_it_goes_less(self):
        def bond(node, health, scars):
            return {"metadata": {"namespace": "ns", "name": f"deployment-web.{node}"},
                    "spec": {"partner": {"kind": "Deployment", "name": "web"}, "node": node},
                    "status": {"health": health, "scars": scars}}
        web = fake_pod("web-7c9-x", likes=None)
        web["metadata"]["labels"] = {"pod-template-hash": "7c9"}
        web["metadata"]["ownerReferences"] = [{"kind": "ReplicaSet", "name": "web-7c9", "controller": True}]
        nodes = [fake_node("a"), fake_node("b")]
        for bad in ("a", "b"):
            good = "b" if bad == "a" else "a"
            _, placed = place(nodes, [web], [bond(bad, "failing", 4), bond(good, "stable", 0)])
            self.assertEqual(placed, {"ns/web-7c9-x": good})
        # The pod still proposes to its favorite, but the node may refuse.
        web["metadata"]["annotations"] = {LIKES: "a"}
        life, placed = place(nodes, [web], [bond("a", "failing", 4)])
        self.assertEqual(placed, {})
        self.assertIn("ns/web-7c9-x is refused by a: it has been failing with Deployment/web: 4 scars", life.lines)

    def test_requests_count_init_containers_like_the_kubelet(self):
        def box(cpu, always=False):
            c = {"resources": {"requests": {"cpu": cpu}}}
            if always:
                c["restartPolicy"] = "Always"
            return c
        cases = [({"initContainers": [box("500m")], "containers": [box("100m")]}, 500),
                 ({"initContainers": [box("200m", True), box("400m")], "containers": [box("100m")]}, 600),
                 ({"initContainers": [box("200m", True), box("400m")], "containers": [box("500m")]}, 700),
                 ({"initContainers": [box("200m", True), box("400m")], "containers": [box("500m")],
                   "overhead": {"cpu": "50m"}}, 750),
                 ({"initContainers": [box("200m", True)], "containers": [box("500m")],
                   "overhead": {"cpu": "50m"}, "resources": {"requests": {"cpu": "1"}}}, 1050)]
        lines = ['written by "tests"', 'learn "kube.amae"', "soul counter"]
        for spec, _ in cases:
            lines.append(f"    let pod = meaning of {json.dumps(json.dumps({'spec': spec}))}")
            lines.append("    perform requests with pod into held")
            lines.append('    say held["cpu"]')
        lines.append("end")
        life = run("\n".join(lines) + "\n")
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(life.lines, [str(c) for _, c in cases])

    def test_quantities(self):
        life = run('written by "tests"\nlearn "kube.amae"\nsoul q\n'
                   '    perform bytes_of with "1.5Gi" into a\n    say a\n'
                   '    perform bytes_of with "64M" into a\n    say a\n'
                   '    perform cpu_of with "2" into a\n    say a\n'
                   '    perform cpu_of with "0.25" into a\n    say a\nend\n')
        self.assertEqual(life.lines, [str(3 * 2**29), "64000000", "2000", "250"])


class LiveScheduler(unittest.TestCase):
    """The scheduler of a cluster, talking to a kubectl that only imagines one."""

    def live(self, nodes, pods, looks, lease=None, env=None, fresh_nodes=None, recovered_nodes=None,
             lose_lease=False, bind_delay=0, consume_bindings=False):
        with tempfile.TemporaryDirectory() as d:
            if lease is not None:
                with open(os.path.join(d, "lease.json"), "w") as f:
                    json.dump(lease, f)
            with open(os.path.join(d, "nodes.json"), "w") as f:
                json.dump({"items": nodes}, f)
            with open(os.path.join(d, "pods.json"), "w") as f:
                json.dump({"items": pods}, f)
            for node in fresh_nodes if fresh_nodes is not None else nodes:
                with open(os.path.join(d, "node-" + node["metadata"]["name"] + ".json"), "w") as f:
                    json.dump(node, f)
            for node in recovered_nodes or []:
                with open(os.path.join(d, "recovered-" + node["metadata"]["name"] + ".json"), "w") as f:
                    json.dump(node, f)
            fake = os.path.join(d, "kubectl")
            steal = (f"jq '.spec.holderIdentity = \"other\"' {d}/lease.json > {d}/stolen; "
                     f"mv {d}/stolen {d}/lease.json; " if lose_lease else "")
            consume = (f'printf "%s" "$body" > {d}/bound.json; '
                       f"jq --slurpfile bound {d}/bound.json "
                       "'.items |= map(select(.metadata.name != $bound[0].metadata.name or "
                       ".metadata.namespace != $bound[0].metadata.namespace))' "
                       f'{d}/pods.json > {d}/remaining.json; mv {d}/remaining.json {d}/pods.json; '
                       if consume_bindings else "")
            with open(fake, "w") as f:
                f.write('#!/bin/sh\n'
                        '[ "$1 $2" = "--context imagined" ] || { echo "no context" >&2; exit 1; }\n'
                        f'echo "$*" >> {d}/calls\n'
                        'shift 2\n'
                        '[ "$1" = "-n" ] && shift 2\n'
                        'case "$1 $2 $3" in\n'
                        f'  "get nodes "*) cat {d}/nodes.json ;;\n'
                        f'  "get node "*) echo "$3" >> {d}/gets; cat {d}/node-"$3".json; result=$?; '
                        f'if [ -f {d}/recovered-"$3".json ]; then '
                        f'mv {d}/recovered-"$3".json {d}/node-"$3".json; fi; exit "$result" ;;\n'
                        f'  "get pods "*) cat {d}/pods.json ;;\n'
                        '  "get namespaces "*) echo \'{"items": [{"metadata": {"name": "ns"}}]}\' ;;\n'
                        f'  "get leases.coordination.k8s.io "*) cat {d}/lease.json 2>/dev/null; true ;;\n'
                        f'  "create --raw "*/events) echo "$(cat)" >> {d}/events ;;\n'
                        f'  "create --raw "*/leases) cat > {d}/lease.json ;;\n'
                        f'  "replace --raw "*/leases/*) cat > {d}/lease.json ;;\n'
                        f'  "patch pod "*) echo "$3 $(cat)" >> {d}/patched ;;\n'
                        f'  "patch events "*) echo "$3 $(cat)" >> {d}/event_patches ;;\n'
                        f'  "create --raw "*) body=$(cat); echo "$3 $body" >> {d}/asked; {consume}{steal}sleep {bind_delay} ;;\n'
                        '  *) exit 1 ;;\n'
                        'esac\n')
            os.chmod(fake, 0o755)
            source = scheduler_source().replace('        perform look_once', '        note "benchmark start" = now\n        perform look_once\n        say "look seconds: " + (now - note "benchmark start")')
            life = run(source, flags=("--patience=0",), timeout=30,
                       env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined",
                            "AMAENETES_LOOKS": str(looks), "AMAENETES_INTERVAL": "0",
                            **(env or {})})
            self.assertEqual(life.code, 0, life.err)
            with open(os.path.join(d, "calls")) as f:
                self.calls = f.read().splitlines()
            self.elapsed = [float(line.split(": ")[1]) for line in life.lines
                            if line.startswith("look seconds: ")]
            self.gets = []
            if os.path.exists(os.path.join(d, "gets")):
                with open(os.path.join(d, "gets")) as f:
                    self.gets = f.read().splitlines()
            self.events = []
            if os.path.exists(os.path.join(d, "events")):
                with open(os.path.join(d, "events")) as f:
                    self.events = [json.loads(line) for line in f]
            self.patched = []
            if os.path.exists(os.path.join(d, "patched")):
                with open(os.path.join(d, "patched")) as f:
                    self.patched = [line.split(" ", 1) for line in f]
            self.event_patches = []
            if os.path.exists(os.path.join(d, "event_patches")):
                with open(os.path.join(d, "event_patches")) as f:
                    self.event_patches = [line.split(" ", 1) for line in f]
            self.lease = None
            if os.path.exists(os.path.join(d, "lease.json")):
                with open(os.path.join(d, "lease.json")) as f:
                    self.lease = json.load(f)
            asked = []
            if os.path.exists(os.path.join(d, "asked")):
                with open(os.path.join(d, "asked")) as f:
                    for line in f:
                        path, body = line.split(" ", 1)
                        asked.append((path, json.loads(body)))
        return life, asked

    def test_direct_matching_agrees_with_deferred_acceptance(self):
        source = scheduler_source().split("soul cluster\n", 1)[0] + '''
soul cluster
    hear world into line
    let data = meaning of line
    note "look" = data
    perform match_live with data, "#1" into matched
    let data = note "look"
    let homes = {}
    let i = 1
    while i <= words of data["pods"]
        let pn = word i of data["pods"]
        homes[pn] = note ("home " + pn + "#1")
        recall data homes
        i = i + 1
    end
    say json of homes
end
'''
        rng = random.Random(83)
        for _ in range(40):
            ps = ["p" + str(i) for i in range(rng.randint(1, 30))]
            ns = ["n" + str(i) for i in range(rng.randint(1, 10))]
            pods = {p: rng.sample(ns, rng.randint(0, len(ns))) for p in ps}
            nodes = {n: rng.sample(ps, rng.randint(0, len(ps))) for n in ns}
            seats = {n: rng.randint(0, 5) for n in ns}
            data = {"pods": " ".join(ps), "nodes": " ".join(ns), "seats": seats,
                    "likes": {k: " ".join(v) for k, v in {**pods, **nodes}.items()}}
            life = run(source, given=json.dumps(data) + "\n", timeout=10)
            self.assertEqual(life.code, 0, life.err)
            homes = {k: (None if v == "nowhere" else v) for k, v in json.loads(life.lines[-1]).items()}
            self.assertEqual(homes, gale_shapley(pods, nodes, seats))

    def test_renewal_between_bindings(self):
        life, asked = self.live([fake_node("a")], [fake_pod("p" + str(i)) for i in range(3)],
                                looks=1, env={**self.LEASE_ENV, "AMAENETES_LEASE_SECONDS": "1"},
                                bind_delay=0.4)
        self.assertEqual(len(asked), 3)
        binds = [i for i, call in enumerate(self.calls) if "/binding " in call]
        for left, right in zip(binds, binds[1:]):
            self.assertTrue(any("replace --raw" in c and "/leases/" in c
                                for c in self.calls[left:right]))

    def test_losing_lease_ends_the_look(self):
        life, asked = self.live([fake_node("a")], [fake_pod("p" + str(i)) for i in range(3)],
                                looks=1, env={**self.LEASE_ENV, "AMAENETES_LEASE_SECONDS": "1"},
                                bind_delay=0.4, lose_lease=True)
        self.assertEqual(len(asked), 1)
        self.assertTrue(any("lease lost" in line for line in life.lines))
        self.assertEqual(self.lease["spec"]["holderIdentity"], "other")

    def test_renewal_and_loss_between_preemption_evictions(self):
        pods = [fake_pod("low-a", node="a", requests={"cpu": "1"}),
                fake_pod("low-b", node="a", requests={"cpu": "1"}),
                fake_pod("high", requests={"cpu": "2"}, priority=10)]
        for lose in (False, True):
            with self.subTest(lose=lose):
                life, asked = self.live([fake_node("a", extra={"cpu": "2"})], pods, looks=1,
                                        env={**self.LEASE_ENV, "AMAENETES_LEASE_SECONDS": "1"},
                                        bind_delay=0.4, lose_lease=lose)
                self.assertEqual(len(asked), 1 if lose else 2)
                self.assertTrue(all(path.endswith("/eviction") for path, _ in asked))
                if lose:
                    self.assertEqual(self.patched, [])
                    self.assertTrue(any("lease lost" in line for line in life.lines))
                else:
                    evictions = [i for i, call in enumerate(self.calls) if "/eviction " in call]
                    self.assertTrue(any("replace --raw" in c and "/leases/" in c
                                        for c in self.calls[evictions[0]:evictions[1]]))

    def test_batch_selects_oldest_and_skips_interval(self):
        pods = [fake_pod("new", created="2026-11-19T00:00:00Z"),
                fake_pod("old", created="2026-11-16T00:00:00Z"), fake_pod("middle")]
        life, asked = self.live([fake_node("a")], pods, looks=2,
                                env={"AMAENETES_BATCH": "2", "AMAENETES_INTERVAL": "60"}, consume_bindings=True)
        self.assertEqual([body["metadata"]["name"] for _, body in asked],
                         ["old", "middle", "new"])

    def test_unplaceable_batch_does_not_starve_remaining_pods(self):
        pods = [fake_pod("old", created="2026-11-16T00:00:00Z", requests={"cpu": "100"}),
                fake_pod("new", created="2026-11-19T00:00:00Z")]
        life, asked = self.live([fake_node("a")], pods, looks=2,
                                env={"AMAENETES_BATCH": "1", "AMAENETES_INTERVAL": "60"})
        self.assertEqual([body["metadata"]["name"] for _, body in asked], ["new"])

    def test_large_cluster_look_finishes_within_budget(self):
        for count in (3, 10):
            for batch in (50, 100):
                with self.subTest(nodes=count, batch=batch):
                    env = {} if batch == 50 else {"AMAENETES_BATCH": str(batch)}
                    life, asked = self.live([fake_node("node-" + str(i)) for i in range(count)],
                                            [fake_pod("p" + str(i)) for i in range(100)], looks=1, env=env)
                    self.assertEqual(len(asked), batch)
                    self.assertLess(self.elapsed[0], 10)
                    self.assertLessEqual(len(self.calls), 2 * batch + 4 + count)
                    self.assertEqual(len(self.gets), len(set(self.gets)))

    def test_fresh_node_refuses_then_another_node_accepts(self):
        fresh = fake_node("a")
        fresh["metadata"]["annotations"]["amaenetes.io/refuses"] = "maintenance until 18:00"
        life, asked = self.live([fake_node("a"), fake_node("b")],
                                [fake_pod("web", likes="a b")], looks=2,
                                fresh_nodes=[fresh, fake_node("b")])
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual([body["target"]["name"] for _, body in asked], ["b"])
        self.assertIn("ns/web is refused by a: maintenance until 18:00", life.lines)
        refused = [e for e in self.events if e["reason"] == "Refused"]
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0]["type"], "Warning")
        self.assertEqual(refused[0]["message"], "node a refused: maintenance until 18:00")
        self.assertEqual(self.gets, ["a", "b"])

    def test_fresh_cordon_and_read_failure_do_not_bind(self):
        fresh = fake_node("a")
        fresh["spec"]["unschedulable"] = True
        for fresh_nodes, reason in [([fresh], "it is cordoned"), ([], "could not read node:")]:
            with self.subTest(reason=reason):
                life, asked = self.live([fake_node("a")], [fake_pod("web")],
                                        looks=1, fresh_nodes=fresh_nodes)
                self.assertEqual(life.code, 0, life.err)
                self.assertEqual(asked, [])
                self.assertTrue(any("is refused by a: " + reason in line for line in life.lines))

    def test_refusal_expires_after_six_even_silent_looks(self):
        fresh = fake_node("a")
        fresh["metadata"]["annotations"]["amaenetes.io/refuses"] = "maintenance"
        for looks, attempts in [(7, 1), (8, 2)]:
            with self.subTest(looks=looks):
                life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=looks,
                                        fresh_nodes=[fresh])
                self.assertEqual(life.code, 0, life.err)
                self.assertEqual(asked, [])
                self.assertEqual(life.lines.count("ns/web is refused by a: maintenance"), attempts)
                self.assertEqual(self.gets, ["a"] * attempts)

    def test_node_accepts_after_refusal_memory_expires(self):
        fresh = fake_node("a")
        fresh["metadata"]["annotations"]["amaenetes.io/refuses"] = "maintenance"
        life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=8,
                                fresh_nodes=[fresh], recovered_nodes=[fake_node("a")])
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(self.gets, ["a", "a"])
        self.assertEqual([body["target"]["name"] for _, body in asked], ["a"])
        self.assertIn("ns/web is refused by a: maintenance", life.lines)
        self.assertIn("ns/web lives on a", life.lines)
        self.assertEqual([e["reason"] for e in self.events],
                         ["Refused", "FailedScheduling", "Scheduled"])

    def test_fresh_node_is_read_once_for_many_pods(self):
        fresh = fake_node("a")
        fresh["metadata"]["annotations"]["amaenetes.io/refuses"] = "maintenance"
        life, asked = self.live([fake_node("a")],
                                [fake_pod("p" + str(i)) for i in range(8)], looks=2,
                                fresh_nodes=[fresh])
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(asked, [])
        self.assertEqual(self.gets, ["a"])
        # Eight pods refused alike tell one Event, patched to count 8, not
        # eight; waiting on the next look tells one more, the same way.
        refused = [e for e in self.events if e["reason"] == "Refused"]
        waiting = [e for e in self.events if e["reason"] == "FailedScheduling"]
        self.assertEqual((len(refused), len(waiting)), (1, 1))
        by_target = {}
        for name, body in self.event_patches:
            by_target.setdefault(name, []).append(json.loads(body))
        self.assertEqual(set(by_target),
                         {refused[0]["metadata"]["name"], waiting[0]["metadata"]["name"]})
        for patches in by_target.values():
            self.assertEqual([p["count"] for p in patches], list(range(2, 9)))
            for p in patches:
                self.assertRegex(p["lastTimestamp"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_binding_needs_no_more_rights_than_binding(self):
        """kubectl create -f validates against the CRD list, which a scheduler
        running with least privilege may not read; the binding subresource
        is posted raw instead."""
        life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=1)
        self.assertEqual(life.code, 0, life.err)
        (path, body), = asked
        self.assertEqual(path, "/api/v1/namespaces/ns/pods/web/binding")
        self.assertEqual(body["kind"], "Binding")
        self.assertEqual(body["target"]["name"], "a")
        self.assertIn("ns/web lives on a", life.lines)

    def test_a_look_that_changes_nothing_is_not_told_again(self):
        life, asked = self.live([fake_node("a", taint=True)], [fake_pod("web")], looks=3)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(asked, [])
        self.assertEqual(life.lines.count(
            "ns/web has nowhere to live: 0/1 nodes are available: 1 taint role."), 1)

    def test_pods_are_reconsidered_on_later_looks(self):
        life, asked = self.live([fake_node("a"), fake_node("b")],
                                [fake_pod("web"), fake_pod("db")], looks=2)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(len(asked), 4)

    def test_every_pod_gets_an_event(self):
        life, asked = self.live([fake_node("a", seats=1)], [fake_pod("web"), fake_pod("db")], looks=1)
        self.assertEqual(life.code, 0, life.err)
        told = {(e["involvedObject"]["name"], e["reason"], e["type"]): e["message"] for e in self.events}
        bound = asked[0][1]["metadata"]["name"]
        waiting = ({"web", "db"} - {bound}).pop()
        self.assertEqual(told[(bound, "Scheduled", "Normal")], f"Successfully assigned ns/{bound} to a")
        self.assertEqual(told[(waiting, "FailedScheduling", "Warning")],
                         "0/1 nodes are available: 1 no seat left.")
        for e in self.events:
            self.assertEqual(e["source"]["component"], "amaenetes")
            self.assertRegex(e["firstTimestamp"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_preemption_prefers_non_attached_equal_priority(self):
        old = fake_pod("attached", node="a", requests={"cpu": "1"}, created="2026-11-18T00:00:00Z")
        old["status"]["conditions"] = [{"type": "Ready", "status": "True", "lastTransitionTime": "2020-01-01T00:00:00Z"}]
        young = fake_pod("new", node="a", requests={"cpu": "1"}, created="2026-11-17T00:00:00Z")
        pods = [young, old, fake_pod("high", requests={"cpu": "1"}, priority=10)]
        nodes = [fake_node("a", extra={"cpu": "2"})]
        life, asked = self.live(nodes, pods, looks=1)
        self.assertEqual([path for path, _ in asked], ["/api/v1/namespaces/ns/pods/new/eviction"], life.err)

    def test_preemption_evicts_and_promises_the_node(self):
        pods = [fake_pod("low", node="a", requests={"cpu": "1"}),
                fake_pod("high", requests={"cpu": "1"}, priority=10)]
        life, asked = self.live([fake_node("a", extra={"cpu": "1"})], pods, looks=1)
        self.assertEqual(life.code, 0, life.err)
        (path, body), = asked
        self.assertEqual(path, "/api/v1/namespaces/ns/pods/low/eviction")
        self.assertIn("ns/low lets go of a for ns/high", life.lines)
        (name, patch), = self.patched
        self.assertEqual((name, json.loads(patch)), ("high", {"status": {"nominatedNodeName": "a"}}))
        told = {(e["involvedObject"]["name"], e["reason"]): e["message"] for e in self.events}
        self.assertEqual(told[("low", "Preempted")], "Preempted by ns/high on node a")

    def test_a_promised_pod_waits_while_the_displaced_leave(self):
        low = fake_pod("low", node="a", requests={"cpu": "1"})
        low["metadata"]["deletionTimestamp"] = "2026-11-19T00:00:00Z"
        other = fake_pod("other", node="a", requests={"cpu": "1"})
        high = fake_pod("high", requests={"cpu": "1"}, priority=10)
        high["status"]["nominatedNodeName"] = "a"
        life, asked = self.live([fake_node("a", extra={"cpu": "2"})], [low, other, high], looks=1)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(asked, [])
        self.assertIn("ns/high waits for room on a", life.lines)

    LEASE_ENV = {"AMAENETES_LEASE": "amaenetes/amaenetes", "HOSTNAME": "me"}

    def lease_of(self, holder, renewed):
        return {"apiVersion": "coordination.k8s.io/v1", "kind": "Lease",
                "metadata": {"name": "amaenetes", "namespace": "amaenetes", "resourceVersion": "7"},
                "spec": {"holderIdentity": holder, "leaseDurationSeconds": 15,
                         "renewTime": renewed, "leaseTransitions": 2}}

    def test_the_first_takes_the_lease_and_leads(self):
        life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=1, env=self.LEASE_ENV)
        self.assertEqual(life.code, 0, life.err)
        self.assertIn("me leads", life.lines)
        self.assertEqual(len(asked), 1)
        self.assertEqual(self.lease["spec"]["holderIdentity"], "me")
        self.assertEqual(self.lease["spec"]["leaseDurationSeconds"], 15)
        self.assertRegex(self.lease["spec"]["renewTime"], r"\.000000Z$")

    def test_one_who_does_not_lead_waits(self):
        fresh = time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime())
        life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=2,
                                lease=self.lease_of("other", fresh), env=self.LEASE_ENV)
        self.assertEqual(life.code, 0, life.err)
        self.assertIn("me waits: other leads", life.lines)
        self.assertEqual(asked, [])
        self.assertEqual(self.lease["spec"]["holderIdentity"], "other")

    def test_a_lease_nobody_renews_is_taken(self):
        life, asked = self.live([fake_node("a")], [fake_pod("web")], looks=1,
                                lease=self.lease_of("other", "2026-01-01T00:00:00.000000Z"),
                                env=self.LEASE_ENV)
        self.assertEqual(life.code, 0, life.err)
        self.assertIn("me leads", life.lines)
        self.assertEqual(len(asked), 1)
        self.assertEqual(self.lease["spec"]["holderIdentity"], "me")
        self.assertEqual(self.lease["spec"]["leaseTransitions"], 3)
        self.assertEqual(self.lease["metadata"]["resourceVersion"], "7")


FAKE_KUBECTL = r'''#!/usr/bin/env python3
"""A kubectl for a cluster that is only imagined, kept in STATE as JSON."""
import json, os, sys
state_file = os.environ["FAKE_STATE"]
args = sys.argv[1:]
assert args[:2] == ["--context", "imagined"], args
args = args[2:]
with open(state_file) as f:
    state = json.load(f)
def save():
    with open(state_file, "w") as f:
        json.dump(state, f)
    with open(state_file + ".log", "a") as f:
        f.write(" ".join(args) + "\n")
if "--watch-only" in args:
    sys.exit(0)
if args[:2] == ["get", "nodes"]:
    print(json.dumps({"items": state["nodes"]}))
elif args[:2] == ["get", "pods"]:
    print(json.dumps({"items": state["pods"]}))
elif args[0] == "cordon":
    for n in state["nodes"]:
        if n["metadata"]["name"] == args[1]:
            n["spec"]["unschedulable"] = True
    save()
elif args[:2] == ["annotate", "node"]:
    k, v = args[3].split("=")
    for n in state["nodes"]:
        if n["metadata"]["name"] == args[2]:
            n["metadata"]["annotations"][k] = v
    save()
elif args[:2] == ["create", "--raw"] and args[2].endswith("/eviction"):
    body = json.load(sys.stdin)
    ns, name = body["metadata"]["namespace"], body["metadata"]["name"]
    gone = [p for p in state["pods"] if p["metadata"]["name"] == name and p["metadata"]["namespace"] == ns]
    state["pods"] = [p for p in state["pods"] if p not in gone]
    for p in gone:
        p = json.loads(json.dumps(p))
        p["metadata"]["name"] = name + "-again"
        p["spec"]["nodeName"] = "w1"
        state["pods"].append(p)
    save()
else:
    sys.exit("fake kubectl cannot " + " ".join(args))
'''


COUNSEL_KUBECTL = r'''#!/usr/bin/env python3
"""A kubectl for an imagined cluster that keeps Relationship objects."""
import json, os, sys
state_file = os.environ["FAKE_STATE"]
args = sys.argv[1:]
assert args[:2] == ["--context", "imagined"], args
args = args[2:]
with open(state_file) as f:
    state = json.load(f)
def save():
    with open(state_file, "w") as f:
        json.dump(state, f)
if args[:2] == ["get", "nodes"]:
    look = state.get("node_polls", 0)
    state["node_polls"] = look + 1
    snapshots = state.get("node_looks", [state["nodes"]])
    save()
    print(json.dumps({"items": snapshots[min(look, len(snapshots) - 1)]}))
elif args[:2] == ["get", "namespaces"]:
    print(json.dumps({"items": state.get("namespaces", [])}))
elif args[:2] == ["get", "pods"]:
    look = max(0, state.get("node_polls", 1) - 1)
    snapshots = state.get("pod_looks", [state["pods"]])
    print(json.dumps({"items": snapshots[min(look, len(snapshots) - 1)]}))
elif args[:2] == ["get", "events"]:
    reason = args[args.index("--field-selector") + 1].split("=", 1)[1]
    assert reason in ("Unhealthy", "Killing", "Pulled", "Started"), args
    polls = state.setdefault("service_polls" if reason in ("Pulled", "Started") else "event_polls", {})
    look = polls.get(reason, 0)
    polls[reason] = look + 1
    snapshots = state.get("probe_event_looks", [state.get("probe_events", [])])
    events = snapshots[min(look, len(snapshots) - 1)]
    save()
    print(json.dumps({"items": [e for e in events if e["reason"] == reason]}))
elif args[:2] == ["get", "relationships.amae.io"]:
    print(json.dumps({"items": list(state["relationships"].values())}))
elif args[:2] == ["create", "--raw"] and args[2].endswith("/eviction"):
    body = json.load(sys.stdin)
    state.setdefault("eviction_attempts", []).append(body["metadata"]["name"])
    if state.get("refuse_evictions", 0):
        state["refuse_evictions"] -= 1
        save()
        sys.exit("disruption budget refused")
    if state.get("keep_terminating"):
        for p in state["pods"]:
            if p["metadata"]["name"] == body["metadata"]["name"]:
                p["metadata"]["deletionTimestamp"] = "2026-01-01T00:00:00Z"
    else:
        state["pods"] = [p for p in state["pods"] if p["metadata"]["name"] != body["metadata"]["name"]]
    state.setdefault("evicted", []).append(body["metadata"]["name"])
    save()
elif args[:2] == ["create", "--raw"] and args[2].endswith("/events"):
    state.setdefault("events", []).append(json.load(sys.stdin))
    save()
elif args[:2] == ["create", "--raw"]:
    body = json.load(sys.stdin)
    key = body["metadata"]["namespace"] + "/" + body["metadata"]["name"]
    if key in state["relationships"]:
        sys.exit("AlreadyExists")
    body["metadata"]["resourceVersion"] = "1"
    state["relationships"][key] = body
    save()
elif args[:2] == ["replace", "--raw"]:
    body = json.load(sys.stdin)
    key = body["metadata"]["namespace"] + "/" + body["metadata"]["name"]
    old = state["relationships"][key]
    if old["metadata"]["resourceVersion"] != body["metadata"]["resourceVersion"]:
        sys.exit("Conflict")
    body["metadata"]["resourceVersion"] = str(int(old["metadata"]["resourceVersion"]) + 1)
    state["relationships"][key] = body
    save()
else:
    sys.exit("fake kubectl cannot " + " ".join(args))
'''


def counselled_pod(name, node, restarts=0, oom=False, ready=True, phase="Running", reason=None,
                   owner=("ReplicaSet", "web-5d9f"), hash_="5d9f", likes=None):
    status = {"phase": phase, "conditions": [{"type": "Ready", "status": "True" if ready else "False",
                                                   "lastTransitionTime": "2020-01-01T00:00:00Z"}],
              "containerStatuses": [{"restartCount": restarts,
                                     "lastState": {"terminated": {"reason": "OOMKilled"}} if oom else {}}]}
    if reason:
        status["reason"] = reason
    meta = {"name": name, "uid": "uid-" + name, "namespace": "shop", "labels": {"pod-template-hash": hash_}, "annotations": {}}
    if likes:
        meta["annotations"][LIKES] = likes
    if owner:
        meta["ownerReferences"] = [{"kind": owner[0], "name": owner[1], "controller": True}]
    return {"metadata": meta, "spec": {"schedulerName": "amaenetes", "nodeName": node,
                                       "containers": [{"resources": {"requests": {"cpu": "100m"}}}]},
            "status": status}


class LiveCounsel(unittest.TestCase):
    """counsel keeping Relationship objects, through a kubectl that only imagines a cluster."""

    def counsel(self, d, looks=1, divorce=False, interval=0, clock_step=None, thresholds=None):
        with open(os.path.join(ROOT, "kube", "counsel.amae")) as f:
            source = f.read()
        if clock_step is not None:
            # Advance only the look clock, keeping multi-look probe tests fast and exact.
            source = source.replace('note "look time" = now',
                                    f'note "look time" = 1800000000 + (note "looks") * {clock_step}')
            source = source.replace('wait number of ("" + note "every") seconds', 'wait 0 seconds')
        fake = os.path.join(d, "kubectl")
        with open(fake, "w") as f:
            f.write(COUNSEL_KUBECTL)
        os.chmod(fake, 0o755)
        return run(source, flags=("--patience=0",),
                   env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined", "FAKE_STATE": os.path.join(d, "state.json"),
                        "COUNSEL_INTERVAL": str(interval), "COUNSEL_LOOKS": str(looks),
                        **{f"COUNSEL_{k.upper()}_AFTER": str(v) for k, v in (thresholds or {}).items()},
                        **({"COUNSEL_DIVORCE": "1", "COUNSEL_DIVORCE_EVERY": "1"} if divorce else {})})

    def state(self, d, **set_):
        path = os.path.join(d, "state.json")
        if set_:
            old = {"nodes": [imagined_node("n1")], "pods": [], "relationships": {}}
            if os.path.exists(path):
                with open(path) as f:
                    old = json.load(f)
            old.update(set_)
            with open(path, "w") as f:
                json.dump(old, f)
        with open(path) as f:
            return json.load(f)

    def result_status(self, d):
        return self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]

    def test_fisher_phases_and_pending_has_no_relationship(self):
        with tempfile.TemporaryDirectory() as d:
            p = counselled_pod("web", "n1", phase="Pending")
            self.state(d, pods=[p])
            life = self.counsel(d)
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(self.state(d)["relationships"], {})
            p["status"]["phase"] = "Running"
            p["status"]["conditions"][0].pop("lastTransitionTime")
            self.state(d, pods=[p])
            life = self.counsel(d, looks=1, clock_step=150)
            self.assertEqual(self.result_status(d)["phase"], "attraction", life.err)
            self.state(d, relationships={})
            life = self.counsel(d, looks=3, clock_step=150)
            st = self.result_status(d)
            self.assertEqual(st["phase"], "attachment", life.err)
            self.assertEqual(st["positive"], 4.94)

    def test_attraction_doubles_moments_but_not_scars(self):
        with tempfile.TemporaryDirectory() as d:
            p = counselled_pod("web", "n1", restarts=2)
            p["status"]["conditions"][0].pop("lastTransitionTime")
            self.state(d, pods=[p])
            life = self.counsel(d)
            st = self.result_status(d)
            self.assertEqual((st["phase"], st["positive"], st["criticism"], st["scars"]),
                             ("attraction", 2, 4, 2), life.err)

    def test_readiness_and_restart_reset_attachment_clock(self):
        for lost_ready in (True, False):
            with self.subTest(lost_ready=lost_ready), tempfile.TemporaryDirectory() as d:
                first = counselled_pod("web", "n1")
                changed = counselled_pod("web", "n1", ready=not lost_ready,
                                         restarts=0 if lost_ready else 1)
                recovered = counselled_pod("web", "n1", restarts=0 if lost_ready else 1)
                self.state(d, pods=[first], pod_looks=[[first], [changed], [recovered]])
                life = self.counsel(d, looks=3, clock_step=100)
                st = self.result_status(d)
                self.assertEqual(st["phase"], "attraction", life.err)
                self.assertEqual(st["scars"], 0 if lost_ready else 1)

    def test_divorce_waits_for_attachment_and_tells_once(self):
        with tempfile.TemporaryDirectory() as d:
            p = counselled_pod("web", "n1", likes="n2 n1")
            p["status"]["conditions"][0].pop("lastTransitionTime")
            self.state(d, nodes=[fake_node("n1"), fake_node("n2")], pods=[p])
            life = self.counsel(d, looks=2, clock_step=100, divorce=True)
            self.assertNotIn("evicted", self.state(d), life.err)
            self.assertEqual([h["what"] for h in self.result_status(d)["history"]],
                             ["web is still in attraction; divorce can wait"])
            self.state(d, relationships={})
            life = self.counsel(d, looks=4, clock_step=100, divorce=True)
            self.assertEqual(self.state(d)["evicted"], ["web"], life.err)
            self.assertEqual(self.result_status(d)["phase"], "attachment")

    def language_pod(self, language):
        p = counselled_pod("web", "n1")
        p["metadata"]["annotations"]["amaenetes.io/love-language"] = language
        return p

    def test_words_language_and_other_signals_count_half(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, nodes=[fake_node("n1")], pods=[self.language_pod("words")])
            life = self.counsel(d)
            st = self.result_status(d)
            self.assertEqual(st["positive"], 4, life.err)  # words 3, time and gifts 0.5 each
            self.assertEqual(st["language"], "words")
            self.assertEqual(st["history"][-1]["what"], "web speaks words")
            life = self.counsel(d)
            self.assertEqual(len(self.result_status(d)["history"]), 1, life.err)

    def test_time_language_and_full_hours(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.language_pod("time")
            # Fixed clock 1800000000 is 2027-01-15T08:00:00Z.
            p["status"]["startTime"] = "2027-01-15T06:30:00Z"
            self.state(d, nodes=[fake_node("n1")], pods=[p])
            life = self.counsel(d, clock_step=0)
            self.assertEqual(self.result_status(d)["positive"], 7, life.err)

    def test_gifts_language_needs_cpu_and_memory_room(self):
        for capacity, expected in [({"cpu": "200m"}, 4), ({"cpu": "199m"}, 1),
                                   ({"cpu": "200m", "memory": "1Mi"}, 1)]:
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as d:
                p = self.language_pod("gifts")
                p["spec"]["containers"][0]["resources"]["requests"]["memory"] = "1Mi"
                self.state(d, nodes=[fake_node("n1", extra=capacity)], pods=[p])
                life = self.counsel(d)
                self.assertEqual(self.result_status(d)["positive"], expected, life.err)

    def test_service_language_counts_event_growth_and_slow_pull(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.language_pod("service")
            events = [self.probe_event("Started", "Started container web", 1, uid="started", pod_uid="uid-web"),
                      self.probe_event("Pulled", 'Successfully pulled image "web" in 500ms', 1,
                                       uid="pulled", pod_uid="uid-web"),
                      self.probe_event("Pulled", 'Successfully pulled image "other" in 1m1s', 1,
                                       uid="slow", pod_uid="uid-web")]
            self.state(d, nodes=[fake_node("n1")], pods=[p], probe_event_looks=[[], events, events])
            life = self.counsel(d, looks=3, clock_step=1)
            st = self.result_status(d)
            self.assertEqual(st["criticism"], 1, life.err)  # last persisted at the event look
            self.assertEqual(st["positive"], 8.99, life.err)  # 1.5 * .99 + 7.5
            life = self.counsel(d, looks=7, clock_step=1)
            self.assertLess(self.result_status(d)["criticism"], 1, life.err)

    def test_touch_language_same_node_or_only_zone(self):
        for where, expected in [("n1", 4), ("n2", 2.5), ("n3", 1)]:
            with self.subTest(where=where), tempfile.TemporaryDirectory() as d:
                p = self.language_pod("touch")
                q = counselled_pod("friend", where)
                q["spec"]["schedulerName"] = "other"
                nodes = [fake_node(n, labels={"topology.kubernetes.io/zone": z}, extra={"cpu": "100m"})
                         for n, z in [("n1", "a"), ("n2", "a"), ("n3", "b")]]
                self.state(d, nodes=nodes, pods=[p, q])
                life = self.counsel(d)
                self.assertEqual(self.result_status(d)["positive"], expected, life.err)

    def test_slow_pull_criticism_is_independent_of_language(self):
        with tempfile.TemporaryDirectory() as d:
            p = counselled_pod("web", "n1")
            e = self.probe_event("Pulled", "Successfully pulled image web in 61s", 1,
                                 uid="slow", pod_uid="uid-web")
            self.state(d, nodes=[fake_node("n1")], pods=[p], probe_event_looks=[[], [e]])
            life = self.counsel(d, looks=2)
            st = self.result_status(d)
            self.assertEqual((st["positive"], st["criticism"], st["scars"]), (1.99, 1, 0), life.err)

    def test_unannotated_positives_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, nodes=[fake_node("n1")], pods=[counselled_pod("web", "n1")])
            life = self.counsel(d)
            self.assertEqual(self.result_status(d)["positive"], 1, life.err)

    def test_youngest_pod_supplies_phase_and_language(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.language_pod("words")
            old["metadata"]["creationTimestamp"] = "2026-01-01T00:00:00Z"
            young = self.language_pod("gifts")
            young["metadata"].update(name="young", uid="uid-young", creationTimestamp="2026-02-01T00:00:00Z")
            young["status"]["conditions"][0].pop("lastTransitionTime")
            # Reverse age order to catch last-observed rather than youngest selection.
            self.state(d, nodes=[fake_node("n1")], pods=[young, old])
            life = self.counsel(d)
            st = self.result_status(d)
            self.assertEqual((st["phase"], st["language"]), ("attraction", "gifts"), life.err)
            self.assertEqual(st["positive"], 13.5)  # closeness also contributes half to each pod

    def test_touch_matches_affinity_and_namespace_selector(self):
        for kind in ("podAffinity", "podAntiAffinity"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                p = self.language_pod("touch")
                p["spec"]["affinity"] = {kind: {"preferredDuringSchedulingIgnoredDuringExecution": [
                    {"weight": 1, "podAffinityTerm": {
                        "topologyKey": "kubernetes.io/hostname",
                        "namespaceSelector": {"matchLabels": {"team": "friends"}},
                        "labelSelector": {"matchLabels": {"app": "friend"}}}}]}}
                q = counselled_pod("friend", "n1", owner=None)
                q["metadata"].update(namespace="other", labels={"app": "friend"})
                q["spec"]["schedulerName"] = "other"
                self.state(d, nodes=[fake_node("n1")], pods=[p, q],
                           namespaces=[{"metadata": {"name": "other", "labels": {"team": "friends"}}}])
                life = self.counsel(d)
                self.assertEqual(self.result_status(d)["positive"], 4.5, life.err)

    def test_time_restarts_reset_uptime_and_skip_this_look(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.language_pod("time")
            q = json.loads(json.dumps(p))
            q["status"]["containerStatuses"][0]["restartCount"] = 1
            self.state(d, nodes=[fake_node("n1")], pods=[p], pod_looks=[[p], [q], [q]])
            life = self.counsel(d, looks=3, clock_step=3600)
            st = self.result_status(d)
            self.assertEqual(st["positive"], 12.9, life.err)  # 4 -> 5.96 (attraction) -> 12.9
            self.assertEqual(st["criticism"], 1.98)

    def test_pull_duration_boundaries_and_lust_clock(self):
        with open(os.path.join(ROOT, "kube", "counsel.amae")) as f:
            source = f.read().split("soul counsel\n")[0]
        source += '''soul check
    let durations = ["500ms", "9.9s", "10s", "60s", "1m1s", "2m3.5s", "unknown"]
    let i = 1
    while i <= length of durations
        perform pull_seconds with "Successfully pulled image web in " + durations[i] into d
        say d
        recall durations
        i = i + 1
    end
    note "look time" = 1800000000
    note "pod phases" = {}
    note "current pod phases" = {}
    note "attachment after" = 300
    perform phase_of with {"metadata": {"uid": "u", "name": "p", "namespace": "ns"}, "spec": {"nodeName": ""}, "status": {"phase": "Pending"}} into clock_
    say clock_["phase"]
end
'''
        life = run(source)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual([float(x) for x in life.lines[:-1]], [0.5, 9.9, 10, 60, 61, 123.5, -1])
        self.assertEqual(life.lines[-1], "lust")

    def attachment_pod(self, name, style, **kwargs):
        p = counselled_pod(name, "n1", **kwargs)
        if style is not None:
            p["metadata"]["annotations"]["amaenetes.io/attachment"] = style
        return p

    def node_looks(self, *statuses):
        snapshots = []
        for status in statuses:
            node = imagined_node("n1")
            node["status"]["conditions"][0]["status"] = status
            snapshots.append([node])
        return snapshots

    def test_anxious_separates_while_secure_waits(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[self.attachment_pod("worried", "anxious"),
                                self.attachment_pod("patient", "secure")],
                       node_looks=self.node_looks("True", "False"))
            life = self.counsel(d, looks=2, thresholds={"anxious": 0, "secure": 60})
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.err, "")
            st = self.state(d)
            self.assertEqual(st["evicted"], ["worried"])
            event, = st["events"]
            self.assertEqual((event["type"], event["reason"], event["source"]["component"]),
                             ("Warning", "Separated", "counsel"))
            self.assertRegex(event["message"], r"^anxious: n1 out of touch for \d+s$")

    def test_secure_threshold_and_fallback(self):
        for style in ("secure", None, "unrecognized"):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as d:
                self.state(d, pods=[self.attachment_pod("patient", style)],
                           node_looks=self.node_looks("True", "Unknown"))
                life = self.counsel(d, looks=3, clock_step=1, thresholds={"secure": 1})
                self.assertEqual(life.code, 0, life.err)
                self.assertEqual(life.err, "")
                st = self.state(d)
                self.assertEqual(st["evicted"], ["patient"])
                event, = st["events"]
                self.assertEqual((event["type"], event["reason"], event["message"]),
                                 ("Normal", "Separated", "secure: n1 out of touch for 1s, moving on"))

    def test_avoidant_reunion_adds_one_carried_scar(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[self.attachment_pod("distant", "avoidant")],
                       relationships={"shop/deployment-web.n1": self.failing("n1", scars=3)},
                       node_looks=self.node_looks("True", "False", "Unknown", "True"))
            life = self.counsel(d, looks=7, clock_step=1, thresholds={"avoidant": 1})
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.err, "")
            st = self.state(d)
            self.assertNotIn("evicted", st)
            rel = st["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertEqual(rel["scars"], 4)
            self.assertEqual([h["what"] for h in rel["history"]],
                             ["distant kept its distance: n1 went silent for 2s"])

    def test_separation_never_evicts_bare_pods(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[self.attachment_pod("solo", "anxious", owner=None)],
                       node_looks=self.node_looks("False"))
            life = self.counsel(d, looks=2, thresholds={"anxious": 0})
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.err, "")
            self.assertNotIn("eviction_attempts", self.state(d))

    def test_refused_separation_retries_but_terminating_pod_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[self.attachment_pod("worried", "anxious")],
                       node_looks=self.node_looks("False"), refuse_evictions=1, keep_terminating=True)
            life = self.counsel(d, looks=3, thresholds={"anxious": 0})
            self.assertEqual(life.code, 0, life.err)
            self.assertIn("disruption budget refused", life.err)
            st = self.state(d)
            self.assertEqual(st["eviction_attempts"], ["worried", "worried"])
            self.assertEqual(st["evicted"], ["worried"])
            self.assertEqual(len(st["events"]), 1)

    def test_a_relationship_is_kept_and_remembered_across_restarts(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[counselled_pod("web-5d9f-a", "n1")])
            life = self.counsel(d, looks=7)
            self.assertEqual(life.code, 0, life.err)
            rel = self.state(d)["relationships"]["shop/deployment-web.n1"]
            self.assertEqual(rel["spec"], {"partner": {"kind": "Deployment", "name": "web"}, "node": "n1"})
            self.assertEqual(rel["status"]["health"], "stable")
            # Written when it began and every sixth look after.
            self.assertGreater(rel["status"]["positive"], 6.5)
            # A new counsel, the same story: what it knew is in the API.
            self.state(d, pods=[counselled_pod("web-5d9f-a", "n1", restarts=2, oom=True)])
            life = self.counsel(d)
            rel = self.state(d)["relationships"]["shop/deployment-web.n1"]
            self.assertEqual(rel["status"]["scars"], 2)
            self.assertEqual(rel["status"]["contempt"], 2)
            self.assertIn("contempt: web-5d9f-a was killed for memory",
                          [h["what"] for h in rel["status"]["history"]])
            self.assertEqual(rel["status"]["health"], "at risk")
            self.assertIn("shop/deployment-web.n1 is at risk", " ".join(life.lines))
            life = self.counsel(d)
            self.assertEqual(self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]["scars"], 2)

    def probing_pod(self):
        p = counselled_pod("web-5d9f-a", "n1")
        p["metadata"]["uid"] = "pod-web"
        p["status"]["startTime"] = "2020-01-01T00:00:00Z"
        p["spec"]["containers"][0].update(livenessProbe={}, readinessProbe={"periodSeconds": 5})
        return p

    def probe_event(self, reason, message, count=1, uid="event-1", pod_uid="pod-web"):
        return {"metadata": {"uid": uid}, "reason": reason, "message": message, "count": count,
                "involvedObject": {"kind": "Pod", "namespace": "shop", "name": "web-5d9f-a",
                                   "uid": pod_uid}}

    def test_probe_bids_turn_towards(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[self.probing_pod()])
            life = self.counsel(d, interval=100)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("counsel:", life.err)
            st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertEqual((st["bids"], st["towards"], st["turning"], st["health"]),
                             (30, 30, 100, "stable"))
            self.assertEqual(self.state(d)["event_polls"], {"Unhealthy": 1, "Killing": 1})

    def test_first_look_baselines_existing_events_then_counts_only_growth(self):
        for reason, message, answer in [("Unhealthy", "Liveness probe failed", "away"),
                                         ("Killing", "Container failed liveness probe", "against")]:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as d:
                e = self.probe_event(reason, message, 50)
                self.state(d, pods=[self.probing_pod()], probe_events=[e])
                life = self.counsel(d)
                self.assertEqual(life.code, 0, life.err)
                self.assertNotIn("counsel:", life.err)
                st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
                self.assertEqual((st["away"], st["against"], st["history"]), (0, 0, []))

                # Restart against the same Relationship: establish 50, then count only 3.
                self.state(d, event_polls={}, probe_event_looks=[[e], [{**e, "count": 53}]])
                life = self.counsel(d, looks=2, clock_step=100)
                self.assertEqual(life.code, 0, life.err)
                self.assertNotIn("counsel:", life.err)
                st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
                self.assertEqual(st[answer], 3)
                self.assertEqual(len(st["history"]), 1)

                # Another restart must preserve the faded total without adding 53 again.
                self.state(d, event_polls={}, probe_event_looks=[[{**e, "count": 53}]])
                life = self.counsel(d)
                self.assertEqual(life.code, 0, life.err)
                self.assertNotIn("counsel:", life.err)
                st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
                self.assertEqual(st[answer], 2.97)
                self.assertEqual(len(st["history"]), 1)

    def test_probe_failures_grow_and_are_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.probe_event("Unhealthy", "Readiness probe failed: refused", 2)
            grown = {**e, "count": 42}
            # A second look sees a large increment; later looks see the same count.
            self.state(d, pods=[self.probing_pod()], probe_event_looks=[[e], [grown]])
            life = self.counsel(d, looks=7, interval=0)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("counsel:", life.err)
            st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertAlmostEqual(st["away"], 38.04, places=2)
            self.assertEqual(len(st["history"]), 1)
            self.assertEqual(self.state(d)["event_polls"], {"Unhealthy": 7, "Killing": 7})

    def test_growing_unhealthy_count_bounds_health(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.probe_event("Unhealthy", "Liveness probe failed: refused", 25)
            self.state(d, pods=[self.probing_pod()], probe_event_looks=[[e], [{**e, "count": 100}]])
            life = self.counsel(d, looks=2, clock_step=100)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("counsel:", life.err)
            st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertEqual((st["bids"], st["away"], st["towards"], st["turning"], st["health"]),
                             (30, 75, 0, 0, "failing"))
            self.assertIn("turned away from 75 bids", st["history"][-1]["what"])

    def test_turning_thresholds_and_minimum_sample(self):
        for interval, failures, turning, health in [(100, 4, 86, "stable"),
                                                    (100, 5, 83, "at risk"),
                                                    (100, 20, 33, "at risk"),
                                                    (100, 21, 30, "failing"),
                                                    (10, 3, 0, "stable")]:
            with self.subTest(turning=turning), tempfile.TemporaryDirectory() as d:
                self.state(d, pods=[self.probing_pod()], probe_event_looks=[[], [
                    self.probe_event("Unhealthy", "Liveness probe failed", failures)]])
                life = self.counsel(d, looks=2, clock_step=interval)
                self.assertEqual(life.code, 0, life.err)
                self.assertNotIn("counsel:", life.err)
                st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
                self.assertEqual((st["turning"], st["health"]), (turning, health))

    def test_event_counts_are_pruned_and_container_loops_keep_totals(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.probing_pod()
            p["spec"]["containers"] *= 12
            e = self.probe_event("Unhealthy", "Readiness probe failed", 2)
            self.state(d, pods=[p], probe_event_looks=[[e], [], [e]])
            life = self.counsel(d, looks=3, interval=100, clock_step=100)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("counsel:", life.err)
            st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertEqual(st["bids"], 1069.24)
            self.assertEqual(st["away"], 2)
            self.assertEqual(len(st["history"]), 1)

    def test_killing_is_against_and_told_without_contempt(self):
        with tempfile.TemporaryDirectory() as d:
            events = [self.probe_event("Killing", "Container web failed liveness probe, will be restarted"),
                      self.probe_event("Killing", "Stopping container web", 100, "unrelated"),
                      self.probe_event("Unhealthy", "Startup probe failed", 100, "startup"),
                      self.probe_event("Unhealthy", "Liveness probe failed", 100, "old", "old-pod")]
            self.state(d, pods=[self.probing_pod()], probe_event_looks=[[], events])
            life = self.counsel(d, looks=2, clock_step=100)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("counsel:", life.err)
            st = self.state(d)["relationships"]["shop/deployment-web.n1"]["status"]
            self.assertEqual((st["against"], st["away"], st["towards"], st["contempt"], st["scars"]),
                             (1, 0, 29, 0, 0))
            self.assertIn("turned against 1 bids: killed for a failed liveness probe", st["history"][0]["what"])

    @staticmethod
    def roomy(name, seats=None):
        node = fake_node(name, seats=seats)
        return node

    def failing(self, node, scars=5):
        return {"apiVersion": "amae.io/v1", "kind": "Relationship",
                "metadata": {"namespace": "shop", "name": f"deployment-web.{node}", "resourceVersion": "1"},
                "spec": {"partner": {"kind": "Deployment", "name": "web"}, "node": node},
                "status": {"positive": 0, "criticism": 10, "scars": scars, "health": "failing"}}

    def test_a_failing_relationship_ends_in_divorce(self):
        with tempfile.TemporaryDirectory() as d:
            # Another workload counselled in the same look must not make
            # counsel forget this one.
            self.state(d, nodes=[self.roomy("n1"), self.roomy("n2")],
                       pods=[counselled_pod("web-5d9f-a", "n1"),
                             counselled_pod("api-77a-b", "n1", owner=("ReplicaSet", "api-77a"), hash_="77a")],
                       relationships={"shop/deployment-web.n1": self.failing("n1")})
            life = self.counsel(d, divorce=True)
            self.assertEqual(life.code, 0, life.err)
            st = self.state(d)
            self.assertEqual(st["evicted"], ["web-5d9f-a"])
            self.assertIn("shop/web-5d9f-a parts from n1: their relationship is failing (5 scars)", life.lines)
            (event,) = st["events"]
            self.assertEqual((event["reason"], event["source"]["component"]), ("Divorced", "counsel"))

    def test_no_divorce_to_a_node_it_has_failed_with_before(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, nodes=[self.roomy("n1"), self.roomy("n2")],
                       pods=[counselled_pod("web-5d9f-a", "n1")],
                       relationships={"shop/deployment-web.n1": self.failing("n1"),
                                      "shop/deployment-web.n2": self.failing("n2")})
            life = self.counsel(d, divorce=True)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("evicted", self.state(d))

    def test_no_divorce_without_somewhere_better_or_without_an_owner(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, nodes=[self.roomy("n1")],
                       pods=[counselled_pod("web-5d9f-a", "n1"), counselled_pod("solo", "n1", owner=None)],
                       relationships={"shop/deployment-web.n1": self.failing("n1"),
                                      "shop/pod-solo.n1": {**self.failing("n1"), "metadata": {
                                          "namespace": "shop", "name": "pod-solo.n1", "resourceVersion": "1"},
                                          "spec": {"partner": {"kind": "Pod", "name": "solo"}, "node": "n1"}}})
            life = self.counsel(d, divorce=True)
            self.assertEqual(life.code, 0, life.err)
            self.assertNotIn("evicted", self.state(d))

    def test_an_unstable_pair_parts(self):
        """The pod likes n2 better and n2 has a seat: both would rather be
        together, so the pod parts from n1. Without a seat it stays."""
        with tempfile.TemporaryDirectory() as d:
            self.state(d, nodes=[self.roomy("n1"), self.roomy("n2", seats=0)],
                       pods=[counselled_pod("web-5d9f-a", "n1", likes="n2 n1")])
            life = self.counsel(d, divorce=True)
            self.assertNotIn("evicted", self.state(d))
            self.state(d, nodes=[self.roomy("n1"), self.roomy("n2", seats=1)])
            life = self.counsel(d, divorce=True)
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(self.state(d)["evicted"], ["web-5d9f-a"])
            self.assertIn("shop/web-5d9f-a parts from n1: it would rather live on n2, and n2 has a seat for it",
                          life.lines)

    def test_gottman_ratio(self):
        with tempfile.TemporaryDirectory() as d:
            self.state(d, pods=[counselled_pod("web-5d9f-a", "n1", ready=False),
                                counselled_pod("solo", "n1", owner=None, phase="Failed", reason="OutOfcpu")])
            life = self.counsel(d, looks=2)
            self.assertEqual(life.code, 0, life.err)
            rels = self.state(d)["relationships"]
            self.assertEqual(rels["shop/deployment-web.n1"]["status"]["health"], "failing")
            self.assertGreater(rels["shop/deployment-web.n1"]["status"]["stonewalling"], 1.9)
            solo = rels["shop/pod-solo.n1"]["status"]
            self.assertEqual((solo["defensiveness"] > 0.9, solo["scars"]), (True, 1))


def imagined_node(name, leaving=False):
    return {"metadata": {"name": name, "annotations": {"amaenetes.io/leaving": "true"} if leaving else {}},
            "spec": {}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}


def imagined_pod(name, node, owner=True):
    meta = {"name": name, "namespace": "a"}
    if owner:
        meta["ownerReferences"] = [{"kind": "ReplicaSet", "name": "x"}]
    return {"metadata": meta, "spec": {"nodeName": node},
            "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]}}


class LiveParting(unittest.TestCase):
    """parting looking after a cluster itself, through a kubectl that only imagines one."""

    def test_drains_a_leaving_node_through_kubectl(self):
        with open(os.path.join(ROOT, "kube", "parting.amae")) as f:
            source = f.read()
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write(FAKE_KUBECTL)
            os.chmod(fake, 0o755)
            state = os.path.join(d, "state.json")
            with open(state, "w") as f:
                json.dump({"nodes": [imagined_node("w1"), imagined_node("w2", leaving=True)],
                           "pods": [imagined_pod("x", "w2"), imagined_pod("y", "w2"),
                                    imagined_pod("z", "w1")]}, f)
            life = run(source, flags=("--patience=0",),
                       env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined", "FAKE_STATE": state,
                            "PARTING_INTERVAL": "0.2", "PARTING_TICKS": "8"})
            with open(state + ".log") as f:
                done = f.read().splitlines()
            with open(state) as f:
                after = json.load(f)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(done[0], "cordon w2")
        self.assertEqual([x.split()[2] for x in done if x.startswith("create")],
                         ["/api/v1/namespaces/a/pods/x/eviction", "/api/v1/namespaces/a/pods/y/eviction"])
        self.assertEqual(done[-1], "annotate node w2 amaenetes.io/left=true --overwrite")
        self.assertIn("w2 has left; it let go of 2 pods", life.lines)
        self.assertEqual({p["spec"]["nodeName"] for p in after["pods"]}, {"w1"})


class Parting(unittest.TestCase):
    """The operator in kube/parting.amae, against a cluster that is only imagined."""

    def live(self, nodes, pods, ticks, slow=0, refuse=0, same_name=False):
        with open(os.path.join(ROOT, "kube", "parting.amae")) as f:
            program, _ = compile_source(f.read())
        d = tempfile.mkdtemp()
        life = subprocess.Popen([program], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, bufsize=1,
                                env=dict(os.environ, AMAE_HISTORY=os.path.join(d, "h.json")))
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
        self.assertEqual(history[2], ["annotate node w2 amaenetes.io/left=true"])
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
        self.assertEqual(history[2], ["annotate node w2 amaenetes.io/left=true"])

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
        self.assertIn(["annotate node w2 amaenetes.io/left=true"], history)

    def test_a_pod_that_comes_back_under_its_own_name(self):
        nodes = {"w1": ["ready", "schedulable", "staying"],
                 "w2": ["ready", "cordoned", "leaving"]}
        pods = {"a/db-0": ["w2", "ready", "a/StatefulSet/db"],
                "a/db-1": ["w2", "ready", "a/StatefulSet/db"]}
        history = self.live(nodes, pods, 6, same_name=True)
        self.assertEqual(history[0], ["evict a/db-0"])
        self.assertEqual(history[1], ["evict a/db-1"])
        self.assertEqual(history[2], ["annotate node w2 amaenetes.io/left=true"])

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
                if lang != "amae":
                    continue
                given, j = "", i + 1
                if blocks[j][0] == "input":
                    given, j = blocks[j][1], j + 1
                if blocks[j][0] != "output":
                    module = re.match(r"# (\S+?):", body).group(1)
                    with open(os.path.join(d, module), "w") as f:
                        f.write(body)
                    if re.search(r"^soul ", body, re.M):
                        # a whole program that needs a cluster to run: it must compile
                        subprocess.run([os.path.join(ROOT, "bin", "tc"), os.path.join(d, module),
                                        "-o", os.path.join(d, module + ".out")], check=True)
                    continue
                source = os.path.join(d, f"program{checked}.amae")
                with open(source, "w") as f:
                    f.write(body)
                program = os.path.join(d, f"program{checked}")
                subprocess.run([os.path.join(ROOT, "bin", "tc"), source, "-o", program], check=True)
                res = subprocess.run([program], input=given, capture_output=True, text=True, cwd=d,
                                     env=dict(os.environ, AMAE_HISTORY=os.path.join(d, f"h{checked}")))
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




MEDIATOR_FAKE_KUBECTL = r'''#!/usr/bin/env python3
"""Mutable cluster snapshots; None lets the previous patch survive a look."""
import json, os, sys
path = os.environ["FAKE_STATE"]
args = sys.argv[1:]
assert args[:2] == ["--context", "imagined"], args
args = args[2:]
ns = None
if args and args[0] == "-n":
    ns = args[1]
    args = args[2:]
with open(path) as f:
    state = json.load(f)
def save():
    with open(path + ".new", "w") as f:
        json.dump(state, f)
    os.replace(path + ".new", path)
if args[:2] == ["get", "relationships.amae.io"]:
    print(json.dumps({"items": list(state["relationships"].values())}))
elif args[0] == "get":
    assert args == ["get", "deployments.apps", "-A", "--show-managed-fields", "-o", "json"], args
    look = state.get("looks", 0)
    state["looks"] = look + 1
    snapshots = state["snapshots"]
    snapshot = snapshots[min(look, len(snapshots) - 1)]
    if snapshot is not None:
        state["objects"] = snapshot
    save()
    print(json.dumps({"items": state["objects"]}))
elif args[:2] == ["patch", "events"]:
    body = json.load(sys.stdin)
    state.setdefault("event_patches", []).append({"name": args[2], "body": body})
    event = next((e for e in state.get("events", []) if e["metadata"]["name"] == args[2]
                  and e["metadata"].get("namespace") == ns), None)
    if event is None:
        save()
        sys.exit('Error from server (NotFound): events "%s" not found' % args[2])
    event.update(body)
    save()
elif args[0] == "patch":
    body = json.load(sys.stdin)
    state.setdefault("attempts", []).append({"args": args, "body": body, "look": state["looks"]})
    if state.get("refuse", 0):
        state["refuse"] -= 1
        save()
        sys.exit("patch refused")
    state.setdefault("patches", []).append(state["attempts"][-1])
    assert "--type=merge" in args and "--patch-file=/dev/stdin" in args, args
    manager = next(a.split("=", 1)[1] for a in args if a.startswith("--field-manager="))
    obj = next(o for o in state["objects"] if o["metadata"]["name"] == args[2])
    def merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict):
                merge(dst.setdefault(k, {}), v)
            else:
                dst[k] = v
    merge(obj, body)
    def fields(src):
        return {"f:" + k: fields(v) if isinstance(v, dict) else {} for k, v in src.items()}
    obj["metadata"]["managedFields"] = [{"manager": manager, "fieldsV1": fields(body)}]
    save()
elif args[:2] == ["create", "--raw"] and args[2].endswith("/events"):
    state.setdefault("events", []).append(json.load(sys.stdin))
    save()
elif args[0] in ("create", "replace") and args[1] == "--raw":
    body = json.load(sys.stdin)
    assert body["kind"] == "Relationship", body
    key = body["metadata"]["namespace"] + "/" + body["metadata"]["name"]
    old = state["relationships"].get(key)
    if args[0] == "create":
        assert old is None, "AlreadyExists"
    else:
        assert old["metadata"]["resourceVersion"] == body["metadata"]["resourceVersion"], "Conflict"
    body["metadata"]["resourceVersion"] = str(int(old["metadata"]["resourceVersion"]) + 1 if old else 1)
    state["relationships"][key] = body
    state.setdefault("written", []).append(body)
    save()
else:
    sys.exit("fake kubectl cannot " + " ".join(args))
'''


class LiveMediator(unittest.TestCase):
    """Compile the actual mediator and observe its API requests over many looks."""

    def obj(self, manager="hpa", value=2, agreement=None, parted=None):
        annotations = {}
        if agreement is not None:
            annotations["amaenetes.io/agreement"] = agreement
        if parted is not None:
            annotations["amaenetes.io/parted"] = parted
        return {"apiVersion": "apps/v1", "kind": "Deployment",
                "metadata": {"namespace": "demo", "name": "web", "uid": "web-uid",
                             "annotations": annotations, "managedFields": [
                                 {"manager": manager, "fieldsV1": {"f:spec": {"f:replicas": {}}}}]},
                "spec": {"replicas": value}}

    def swaps(self, **kwargs):
        return [[self.obj(m, v, **kwargs)] for m, v in
                [("hpa", 2), ("gitops", 5), ("hpa", 2), ("gitops", 5)]]

    def mediate(self, snapshots, patience=6, refuse=0):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write(MEDIATOR_FAKE_KUBECTL)
            os.chmod(fake, 0o755)
            state_path = os.path.join(d, "state.json")
            with open(state_path, "w") as f:
                json.dump({"snapshots": snapshots, "objects": [], "relationships": {}, "refuse": refuse}, f)
            with open(os.path.join(ROOT, "kube", "mediator.amae")) as f:
                source = f.read()
            life = run(source, flags=("--patience=0",),
                       env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined", "FAKE_STATE": state_path,
                            "MEDIATOR_INTERVAL": "0.001", "MEDIATOR_RESOURCES": "deployments.apps",
                            "MEDIATOR_PATIENCE": str(patience), "MEDIATOR_LOOKS": str(len(snapshots))})
            self.assertEqual(life.code, 0, life.err)
            if refuse:
                self.assertIn("patch refused", life.err)
            else:
                self.assertEqual(life.err, "")
            with open(state_path) as f:
                return json.load(f)

    def reasons(self, state):
        return [e["reason"] for e in state.get("events", [])]

    def relationship(self, state):
        rel, = state["relationships"].values()
        return rel

    def test_three_swaps_open_quarrel(self):
        state = self.mediate(self.swaps())
        self.assertEqual(self.reasons(state), ["Conflict"])
        rel = self.relationship(state)
        self.assertEqual(rel["spec"]["kind"], "quarrel")
        self.assertEqual(set(rel["spec"]["between"]), {"hpa", "gitops"})
        self.assertEqual(rel["spec"]["over"], "deployments.apps demo/web spec.replicas")
        self.assertEqual(rel["status"]["resolution"], "open")
        self.assertEqual(rel["status"]["swaps"], 3)
        event, = state["events"]
        self.assertEqual(event["message"], "hpa and gitops keep overwriting spec.replicas")
        self.assertEqual((event["type"], event["source"]["component"]), ("Warning", "mediator"))
        self.assertEqual((event["involvedObject"]["kind"], event["involvedObject"]["apiVersion"]),
                         ("Deployment", "apps/v1"))

    def test_agreement_restores_chosen_value(self):
        state = self.mediate(self.swaps(agreement="spec.replicas=hpa") +
                             [None, [self.obj("gitops", 8, agreement="spec.replicas=hpa")]])
        self.assertEqual(self.reasons(state).count("Agreed"), 1)
        # Restored is told twice and aggregated: one Event, patched to count 2.
        self.assertEqual(self.reasons(state).count("Restored"), 1)
        restored = next(e for e in state["events"] if e["reason"] == "Restored")
        self.assertEqual(restored["count"], 2)
        self.assertEqual(self.relationship(state)["status"]["resolution"], "consent")
        self.assertEqual(self.relationship(state)["status"]["owner"], "hpa")
        for patch in state["patches"]:
            self.assertIn("--field-manager=hpa", patch["args"])
            self.assertEqual(patch["body"], {"spec": {"replicas": 2}})

    def test_yields_after_patience(self):
        state = self.mediate(self.swaps() + [None] * 6)
        self.assertIn("Yielded", self.reasons(state))
        self.assertEqual(state["patches"][0]["look"], 10)
        self.assertEqual(state["patches"][0]["body"], {"spec": {"replicas": 2}})
        self.assertEqual(self.relationship(state)["status"]["resolution"], "yielded")
        yielded = next(e for e in state["events"] if e["reason"] == "Yielded")
        self.assertEqual(yielded["message"], "gitops yields spec.replicas to hpa")

    def test_three_scars_part_and_stop_patching(self):
        state = self.mediate(self.swaps() + [None] * 2 + [[self.obj("gitops", 5)]] * 5, patience=2)
        self.assertEqual(self.reasons(state).count("Parted"), 1)
        self.assertEqual(len(state["patches"]), 3)
        self.assertEqual(self.relationship(state)["status"]["resolution"], "parted")
        self.assertEqual(self.relationship(state)["status"]["scars"], 3)
        self.assertIn("remain parted", self.relationship(state)["status"]["history"][-1]["what"])

    def test_restore_is_not_a_swap_or_scar(self):
        state = self.mediate(self.swaps() + [None] * 5, patience=2)
        self.assertEqual(len(state["patches"]), 1)
        self.assertEqual(self.relationship(state)["status"]["swaps"], 3)
        self.assertEqual(self.relationship(state)["status"]["scars"], 0)
        self.assertEqual(self.reasons(state).count("Conflict"), 1)

    def test_status_only_never_quarrels(self):
        snapshots = self.swaps() * 2
        for snapshot in snapshots:
            obj = snapshot[0]
            obj["metadata"]["managedFields"][0]["subresource"] = "status"
        state = self.mediate(snapshots)
        self.assertEqual(state["relationships"], {})
        self.assertEqual(self.reasons(state), [])

    def test_parting_annotation_then_agreement(self):
        snapshots = self.swaps(parted="hpa") + [None, [self.obj("gitops", 9, agreement="spec.replicas=hpa")]]
        state = self.mediate(snapshots)
        self.assertEqual(self.reasons(state).count("Parted"), 1)
        self.assertEqual(len(state["patches"]), 1)
        self.assertEqual(state["patches"][0]["look"], 6)
        self.assertEqual(self.relationship(state)["status"]["resolution"], "consent")

    def test_refused_patch_retries_next_look(self):
        state = self.mediate(self.swaps(agreement="spec.replicas=hpa") + [None], refuse=1)
        self.assertEqual(len(state["attempts"]), 2)
        self.assertEqual(len(state["patches"]), 1)
        self.assertEqual(self.reasons(state).count("Restored"), 1)

    def test_disappeared_object_is_forgotten(self):
        state = self.mediate(self.swaps()[:3] + [[]] + self.swaps()[:2])
        self.assertEqual(state["relationships"], {})

    def test_expired_swaps_do_not_quarrel(self):
        state = self.mediate(self.swaps()[:2] + [None] * 7 + self.swaps()[2:], patience=2)
        self.assertEqual(state["relationships"], {})

    def test_nested_leaves_and_literal_label_keys_survive_long_walks(self):
        snapshots = []
        for manager, value in [("hpa", "elder"), ("gitops", "late"), ("hpa", "elder"), ("gitops", "late")]:
            objects = []
            for n in range(3):
                obj = self.obj(manager)
                obj["metadata"]["name"] = "web-" + str(n)
                labels = {"example.io/key." + str(i): value for i in range(12)}
                obj["metadata"]["labels"] = labels
                obj["spec"] = {"template": {"spec": {"nodeSelector": {"zone": value}}}}
                obj["metadata"]["annotations"] = {
                    "amaenetes.io/agreement": "\n".join("metadata.labels." + k + "=hpa" for k in labels)}
                obj["metadata"]["managedFields"] = [{"manager": manager, "fieldsV1": {
                    "f:metadata": {"f:labels": {"f:" + k: {} for k in labels}},
                    "f:spec": {"f:template": {"f:spec": {"f:nodeSelector": {"f:zone": {}}}}}}}]
                objects.append(obj)
            snapshots.append(objects)
        state = self.mediate(snapshots)
        self.assertEqual(len(state["relationships"]), 39)
        self.assertEqual(len(state["patches"]), 36)
        for patch in state["patches"]:
            label, = patch["body"]["metadata"]["labels"].items()
            self.assertTrue(label[0].startswith("example.io/key."))
            self.assertEqual(label[1], "elder")
        # The three objects carry one uid in this fixture, so each telling
        # told alike three times lands on one Event patched to count 3:
        # 13 paths (12 label keys and the node selector) quarrel each once.
        conflicts = [e for e in state["events"] if e["reason"] == "Conflict"]
        self.assertEqual(self.reasons(state).count("Conflict"), 13)
        self.assertEqual({e["count"] for e in conflicts}, {3})
        # Every Event is told three times: two merge patches each.
        self.assertEqual(len(state["event_patches"]), 2 * len(state["events"]))

    def test_ignored_annotations_and_associative_lists(self):
        snapshots = self.swaps() * 2
        for snapshot in snapshots:
            obj = snapshot[0]
            val = str(obj["spec"]["replicas"])
            keys = ["amaenetes.io/anything", "kubectl.kubernetes.io/last-applied-configuration",
                    "deployment.kubernetes.io/revision"]
            obj["metadata"]["annotations"] = {k: val for k in keys}
            obj["spec"]["containers"] = [{"name": "web", "image": val}]
            obj["metadata"]["managedFields"][0]["fieldsV1"] = {
                "f:metadata": {"f:annotations": {"f:" + k: {} for k in keys}},
                "f:spec": {"f:containers": {'k:{"name":"web"}': {"f:image": {}}}},
                "f:status": {"f:replicas": {}}}
            obj["status"] = {"replicas": val}
        state = self.mediate(snapshots)
        self.assertEqual(state["relationships"], {})

    def test_owner_only_or_value_only_changes_are_not_swaps(self):
        for snapshots in ([[self.obj(m, 2)] for m in ["hpa", "gitops"] * 4],
                          [[self.obj("hpa", v)] for v in [2, 5] * 4]):
            state = self.mediate(snapshots)
            self.assertEqual(state["relationships"], {})

    def test_different_pairs_are_not_one_quarrel(self):
        snapshots = [[self.obj(m, i)] for i, m in enumerate(["hpa", "gitops", "operator", "hpa"])]
        state = self.mediate(snapshots)
        self.assertEqual(state["relationships"], {})

    def test_ambiguous_ownership_is_skipped(self):
        snapshots = self.swaps() * 2
        for snapshot in snapshots:
            snapshot[0]["metadata"]["managedFields"].append(
                {"manager": "shared", "fieldsV1": {"f:spec": {"f:replicas": {}}}})
        state = self.mediate(snapshots)
        self.assertEqual(state["relationships"], {})

    def test_mediator_owner_is_never_patched(self):
        snapshots = [[self.obj(m, v, agreement="spec.replicas=hpa")] for m, v in
                     [("hpa", 2), ("mediator", 5), ("hpa", 2), ("mediator", 5)]]
        state = self.mediate(snapshots)
        self.assertEqual(self.relationship(state)["status"]["resolution"], "consent")
        self.assertEqual(state.get("patches", []), [])

    def test_scheduler_keeps_node_relationships_beside_quarrels(self):
        quarrel = {"metadata": {"namespace": "ns", "name": "quarrel-test"},
                   "spec": {"kind": "quarrel", "between": ["hpa", "gitops"]},
                   "status": {"resolution": "parted", "scars": 3}}
        bond = {"metadata": {"namespace": "ns", "name": "pod-web.a"},
                "spec": {"partner": {"kind": "Pod", "name": "web"}, "node": "a"},
                "status": {"health": "failing", "scars": 3}}
        life, placed = place([fake_node("a"), fake_node("b")],
                             [fake_pod("web", likes="a b")], [quarrel, bond])
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(placed, {})
        self.assertIn("ns/web is refused by a: it has been failing with Pod/web: 3 scars", life.lines)

    def test_counsel_ignores_quarrel_relationships(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write(MEDIATOR_FAKE_KUBECTL)
            os.chmod(fake, 0o755)
            path = os.path.join(d, "state.json")
            with open(path, "w") as f:
                json.dump({"relationships": {"demo/quarrel": {
                    "metadata": {"namespace": "demo", "name": "quarrel"},
                    "spec": {"kind": "quarrel"}}}}, f)
            with open(os.path.join(ROOT, "kube", "counsel.amae")) as f:
                source = f.read().split("soul counsel\n")[0]
            source += 'soul check_\n    perform known_relationships into known\n    say json of known\nend\n'
            life = run(source, env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined", "FAKE_STATE": path})
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.lines, ["{}"])

    def test_restores_boolean_null_and_string_values_without_coercion(self):
        for elder, late in [(True, False), (None, ""), ("amae-json:true", "amae-json:null"),
                            ({"amae-json:": True, "value": "amae-json:false"}, {"value": None}), ("true", 'false\\"null'),
                            ({"enabled": True, "optional": None}, {"enabled": False, "optional": ""})]:
            snapshots = [[self.obj(m, v, agreement="spec.replicas=hpa")] for m, v in
                         [("hpa", elder), ("gitops", late), ("hpa", elder), ("gitops", late)]]
            state = self.mediate(snapshots)
            self.assertEqual(self.reasons(state).count("Conflict"), 1)
            restored = state["patches"][0]["body"]["spec"]["replicas"]
            self.assertEqual(restored, elder)
            self.assertIs(type(restored), type(elder))


    def large_objects(self, count=120):
        objects = []
        for i in range(count):
            obj = self.obj()
            obj["metadata"]["name"] = f"web-{i}"
            obj["metadata"]["labels"] = {f"example.io/label-{k}": str(k) for k in range(20)}
            obj["spec"].update({"paused": False, "optional": None,
                                "template": {"spec": {"nodeSelector": {"zone": "east"}}}})
            obj["data"] = {"payload": 'actual config: true false null \\\"\n' * 80}
            obj["metadata"]["managedFields"][0]["fieldsV1"].update({
                "f:data": {"f:payload": {}},
                "f:metadata": {"f:labels": {f"f:{k}": {} for k in obj["metadata"]["labels"]}},
                "f:spec": {"f:replicas": {}, "f:paused": {}, "f:optional": {},
                           "f:template": {"f:spec": {"f:nodeSelector": {"f:zone": {}}}}}})
            objects.append(obj)
        return objects

    def test_large_cluster_looks_finish_within_budget(self):
        # Time execution, not compilation. Check both a cold and a warm look:
        # a populated state table used to be copied once for every field.
        payload = json.dumps({"items": self.large_objects()})
        self.assertGreater(len(payload.encode()), 500_000)
        self.assertLess(len(payload.encode()), 600_000)
        with open(os.path.join(ROOT, "kube", "mediator.amae")) as f:
            source = f.read()
        source = source.replace('        perform mediator_once', '''        note "benchmark start" = now
        perform mediator_once
        note "benchmark elapsed" = now - note "benchmark start"
        let states_ = note "states"
        let names_ = keys of states_
        let count_ = 0
        let i_ = 1
        while i_ <= length of names_
            count_ = count_ + length of keys of states_[names_[i_]]
            recall states_ names_ count_
            i_ = i_ + 1
        end
        say json of {"elapsed": note "benchmark elapsed", "objects": length of names_, "fields": count_}''')
        program, error = compile_source(source)
        self.assertIsNone(error, error)
        with tempfile.TemporaryDirectory() as d:
            input_path = os.path.join(d, "input.json")
            with open(input_path, "w") as f:
                f.write(payload)
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write('''#!/bin/sh
case "$*" in
 *relationships.amae.io*) echo '{"items":[]}' ;;
 *) cat "$LARGE_INPUT" ;;
esac
''')
            os.chmod(fake, 0o755)
            started = time.perf_counter()
            result = subprocess.run([program, "--patience=0"], capture_output=True, text=True, timeout=12,
                                    env=dict(os.environ, KUBECTL=fake, KUBE_CONTEXT="imagined",
                                             LARGE_INPUT=input_path, AMAE_HISTORY=os.path.join(d, "history.json"),
                                             MEDIATOR_RESOURCES="deployments.apps", MEDIATOR_INTERVAL="0",
                                             MEDIATOR_LOOKS="2"))
            elapsed = time.perf_counter() - started
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            looks = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(looks), 2)
            for look in looks:
                self.assertEqual((look["objects"], look["fields"]), (120, 3000))
                self.assertLess(look["elapsed"], 5, look)
            self.assertLess(elapsed, 10)
            print(f"Mediator {len(payload.encode())} bytes: cold {looks[0]['elapsed']:.3f}s, "
                  f"warm {looks[1]['elapsed']:.3f}s; process {elapsed:.3f}s")

    def test_failed_list_is_not_hidden_by_jq(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write('''#!/bin/sh
echo '{"items":[]}'
case "$*" in
 *relationships.amae.io*) exit 0 ;;
 *) echo 'list refused' >&2; exit 23 ;;
esac
''')
            os.chmod(fake, 0o755)
            with open(os.path.join(ROOT, "kube", "mediator.amae")) as f:
                source = f.read()
            life = run(source, env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined",
                                    "MEDIATOR_RESOURCES": "deployments.apps", "MEDIATOR_LOOKS": "1"})
            self.assertEqual(life.code, 0, life.err)
            self.assertIn("list refused", life.err)


CRONJOB_FAKE_KUBECTL = r'''#!/usr/bin/env python3
import json, os, sys
p = os.environ['FAKE_STATE']
s = json.load(open(p))
a = sys.argv[1:]
assert a[:2] == ['--context', 'imagined'], a
a = a[2:]
s.setdefault('calls', []).append(a)
fail = s.get('fail_once')
if fail and ((fail == 'list' and a[:2] == ['get', 'jobs.batch']) or
             (fail == 'patch' and a[0] == 'patch') or
             (fail == 'delete' and a[0] == 'delete') or
             (fail == 'create' and a[0] == 'create' and '/jobs' in a[a.index('--raw') + 1])):
    s.pop('fail_once')
    json.dump(s, open(p, 'w'))
    print('injected failure', file=sys.stderr)
    sys.exit(1)
result = {}
if 'get' in a:
    resource = a[a.index('get') + 1]
    if resource == 'leases.coordination.k8s.io':
        result = s.get('lease')
    elif resource == 'cronjobs.batch.tutorial.kubebuilder.io':
        s['looks'] = s.get('looks', 0) + 1
        if s.get('clocks'):
            with open(os.environ['CRONJOB_NOW'], 'w') as f:
                f.write(str(s['clocks'][min(s['looks'] - 1, len(s['clocks']) - 1)]))
        result = {'items': s['cronjobs']}
    elif resource == 'jobs.batch':
        result = {'items': s['jobs']}
    else:
        raise AssertionError(a)
elif a[0] in ('create', 'replace'):
    body = json.load(sys.stdin)
    kind = body['kind']
    if kind == 'Lease':
        s['lease'] = body
    elif kind == 'Event':
        s.setdefault('events', []).append(body)
    elif kind == 'Job':
        s.setdefault('attempts', []).append(body)
        if s.get('already_exists') or any(j['metadata']['name'] == body['metadata']['name'] and
                j['metadata']['namespace'] == body['metadata']['namespace'] for j in s['jobs']):
            json.dump(s, open(p, 'w'))
            print('Error from server (AlreadyExists): jobs.batch already exists', file=sys.stderr)
            sys.exit(1)
        body['metadata']['uid'] = 'created-' + body['metadata']['name']
        s['jobs'].append(body)
        s.setdefault('creates', []).append(body)
        s.setdefault('actions', []).append('create:' + body['metadata']['name'])
    else:
        raise AssertionError(body)
elif a[0] == '-n' and a[2:4] == ['patch', 'events']:
    body = json.load(sys.stdin)
    name = a[4]
    s.setdefault('event_patches', []).append({'name': name, 'body': body})
    event = next((e for e in s.get('events', []) if e['metadata']['name'] == name and
                  e['metadata']['namespace'] == a[1]), None)
    if event is None:
        json.dump(s, open(p, 'w'))
        print('Error from server (NotFound): events "%s" not found' % name, file=sys.stderr)
        sys.exit(1)
    event.update(body)
    json.dump(s, open(p, 'w'))
elif a[0] == 'patch':
    assert '--subresource=status' in a, a
    body = json.load(sys.stdin)
    s.setdefault('patches', []).append(body)
    parent = next(c for c in s['cronjobs'] if c['metadata']['name'] == a[2] and
                  c['metadata']['namespace'] == a[a.index('-n') + 1])
    parent['status'] = {k: v for k, v in body['status'].items() if v is not None}
elif a[0] == 'delete':
    assert '--cascade=background' in a and '--wait=false' in a, a
    ns = a[a.index('-n') + 1]
    s.setdefault('deletes', []).append(a[2])
    s.setdefault('actions', []).append('delete:' + a[2])
    s['jobs'] = [j for j in s['jobs'] if (j['metadata']['namespace'], j['metadata']['name']) != (ns, a[2])]
else:
    raise AssertionError(a)
json.dump(s, open(p, 'w'))
print('' if result is None else json.dumps(result))
'''


class LiveCronJob(unittest.TestCase):
    """Run the real controller with a persistent API fake and a file clock."""

    @staticmethod
    def source():
        with open(os.path.join(ROOT, 'operators', 'cronjob.amae')) as f:
            return f.read()

    def parent(self, **spec):
        return {'apiVersion': 'batch.tutorial.kubebuilder.io/v1', 'kind': 'CronJob',
                'metadata': {'name': 'hello', 'namespace': 'demo', 'uid': 'parent-uid',
                             'creationTimestamp': '2024-01-01T00:00:00Z'},
                'spec': dict(schedule='* * * * *', jobTemplate={
                    'metadata': {'labels': {'app': 'hello'}, 'annotations': {'keep': 'true'}},
                    'spec': {'template': {'spec': {'restartPolicy': 'Never',
                        'hostNetwork': False, 'securityContext': None,
                        'containers': [{'name': 'hello', 'image': 'busybox',
                                        'command': ['echo', 'amae-json:true']}]}}}}, **spec)}

    def child(self, name='old', condition=None, scheduled=None, start=None):
        job = {'apiVersion': 'batch/v1', 'kind': 'Job',
               'metadata': {'name': name, 'namespace': 'demo', 'uid': 'uid-' + name,
                            'ownerReferences': [{'apiVersion': 'batch.tutorial.kubebuilder.io/v1',
                                'kind': 'CronJob', 'uid': 'parent-uid', 'name': 'hello', 'controller': True}]},
               'status': {}}
        if condition:
            job['status']['conditions'] = [{'type': condition, 'status': 'True'}]
        if scheduled:
            job['metadata']['annotations'] = {'batch.tutorial.kubebuilder.io/scheduled-at': scheduled}
        if start:
            job['status']['startTime'] = start
        return job

    def reconcile(self, parent=None, jobs=(), looks=1, clock=1704067260, expected_error='', **extra):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, 'kubectl')
            with open(fake, 'w') as f:
                f.write(CRONJOB_FAKE_KUBECTL)
            os.chmod(fake, 0o755)
            state = os.path.join(d, 'state.json')
            with open(state, 'w') as f:
                json.dump(dict(cronjobs=parent if isinstance(parent, list) else [parent or self.parent()], jobs=list(jobs), **extra), f)
            clock_file = os.path.join(d, 'clock')
            with open(clock_file, 'w') as f:
                f.write(str(clock))
            life = run(self.source(), flags=('--patience=0',), timeout=60,
                       env={'KUBECTL': fake, 'KUBE_CONTEXT': 'imagined', 'FAKE_STATE': state,
                            'CRONJOB_NOW': clock_file, 'CRONJOB_LOOKS': str(looks),
                            'CRONJOB_INTERVAL': '0.001'})
            self.assertEqual(life.code, 0, life.err)
            if expected_error:
                self.assertIn(expected_error, life.err)
            else:
                self.assertEqual(life.err, '')
            with open(state) as f:
                return json.load(f)

    def test_parser(self):
        cases = [
            ('*/15 * * * *', '2024-01-01T00:07:00Z', '2024-01-01T00:15:00Z'),
            ('5,20,50 9-17/2 * * *', '2024-01-01T09:51:00Z', '2024-01-01T11:05:00Z'),
            ('0 8 * JAN MON-FRI', '2024-01-05T08:00:00Z', '2024-01-08T08:00:00Z'),
            ('@hourly', '2024-01-01T12:30:00Z', '2024-01-01T13:00:00Z'),
            ('@daily', '2024-02-28T12:00:00Z', '2024-02-29T00:00:00Z'),
            ('@midnight', '2024-01-31T00:00:00Z', '2024-02-01T00:00:00Z'),
            ('@weekly', '2024-01-01T00:00:00Z', '2024-01-07T00:00:00Z'),
            ('@monthly', '2024-02-01T00:00:00Z', '2024-03-01T00:00:00Z'),
            ('@yearly', '2024-01-01T00:00:00Z', '2025-01-01T00:00:00Z'),
            ('@annually', '2024-11-01T00:00:00Z', '2025-01-01T00:00:00Z'),
            ('0 0 13 * fri', '2024-01-11T00:00:00Z', '2024-01-12T00:00:00Z'),
            ('0 0 13 * fri', '2024-01-12T00:00:00Z', '2024-01-13T00:00:00Z'),
            ('0 0 31 * *', '2024-04-01T00:00:00Z', '2024-05-31T00:00:00Z'),
            ('0 0 29 feb *', '2023-03-01T00:00:00Z', '2024-02-29T00:00:00Z'),
            ('0 0 29 feb *', '2096-02-29T00:00:00Z', '2104-02-29T00:00:00Z'),
            ('0 0 */2 * mon', '2024-01-02T00:00:00Z', '2024-01-15T00:00:00Z'),
        ]
        source = self.source().split('soul cronjob\n')[0] + '''soul check_cron
    hear world into text
    let cases = meaning of text
    let i = 1
    while i <= length of cases
        perform cron_parse with cases[i][1] into parsed
        perform seconds_of with cases[i][2] into at
        perform cron_next with parsed, at into next_
        perform stamp_of with next_ into stamp
        say stamp
        recall cases
        i = i + 1
    end
end
'''
        life = run(source, given=json.dumps(cases) + '\n', flags=('--patience=0',), timeout=60)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(life.lines, [c[2] for c in cases])

    def test_invalid_parser(self):
        cases = ['* * * *', '60 * * * *', '*/0 * * * *', '0 24 * * *',
                 '0 0 0 * *', '0 0 * 13 *', '0 0 * * 7', '0 0 * * mo',
                 '2-1 * * * *', '1,,2 * * * *', '*/-2 * * * *', '@every 1m']
        source = self.source().split('soul cronjob\n')[0] + '''soul check_cron
    hear world into text
    let cases = meaning of text
    let i = 1
    while i <= length of cases
        perform cron_parse with cases[i] into parsed
        say length of parsed
        recall cases
        i = i + 1
    end
end
'''
        life = run(source, given=json.dumps(cases) + '\n', timeout=30)
        self.assertEqual(life.code, 0, life.err)
        self.assertEqual(life.lines, ['0'] * len(cases))

    def test_due_and_second_look(self):
        s = self.reconcile(looks=3)
        job, = s['creates']
        self.assertEqual(job['metadata']['name'], 'hello-1704067260')
        self.assertEqual(job['metadata']['annotations'], {
            'keep': 'true', 'batch.tutorial.kubebuilder.io/scheduled-at': '2024-01-01T00:01:00Z'})
        self.assertEqual(job['metadata']['labels'], {'app': 'hello'})
        self.assertEqual(job['metadata']['ownerReferences'], [{
            'apiVersion': 'batch.tutorial.kubebuilder.io/v1', 'kind': 'CronJob',
            'name': 'hello', 'uid': 'parent-uid', 'controller': True, 'blockOwnerDeletion': True}])
        self.assertIs(job['spec']['template']['spec']['hostNetwork'], False)
        self.assertIsNone(job['spec']['template']['spec']['securityContext'])
        self.assertEqual(job['spec'], self.parent()['spec']['jobTemplate']['spec'])
        st = s['cronjobs'][0]['status']
        self.assertEqual(st['lastScheduleTime'], '2024-01-01T00:01:00Z')
        self.assertEqual(st['active'][0]['uid'], job['metadata']['uid'])
        self.assertEqual(len(s['patches']), 1)
        self.assertEqual(len(s['attempts']), 1)
        self.assertEqual([e['reason'] for e in s['events']], ['SuccessfulCreate'])
        self.assertEqual(sum('jobs.batch' in c and 'get' in c for c in s['calls']), 3)

    def test_history_and_status_while_suspended(self):
        jobs = [self.child('success-' + str(i), 'Complete', start=f'2024-01-01T00:0{i}:00Z')
                for i in [3, 1, 2]] + [self.child('failed-' + str(i), 'Failed',
                start=f'2024-01-01T00:0{i}:00Z') for i in [2, 1]]
        jobs += [self.child('active', scheduled='2024-01-01T00:01:00Z')]
        s = self.reconcile(self.parent(suspend=True, successfulJobsHistoryLimit=1,
                                      failedJobsHistoryLimit=0), jobs)
        self.assertEqual(s['deletes'], ['success-1', 'success-2', 'failed-1', 'failed-2'])
        self.assertEqual(s['cronjobs'][0]['status']['active'][0]['name'], 'active')
        self.assertEqual(s['cronjobs'][0]['status']['lastScheduleTime'], '2024-01-01T00:01:00Z')
        self.assertFalse(s.get('creates'))

    def test_deadline_and_too_many(self):
        s = self.reconcile(self.parent(startingDeadlineSeconds=10), clock=1704067290)
        self.assertFalse(s.get('creates'))
        s = self.reconcile(clock=1704073320)
        self.assertFalse(s.get('creates'))
        self.assertEqual(s['events'][0]['reason'], 'TooManyMissedTimes')
        s = self.reconcile(self.parent(startingDeadlineSeconds=60), clock=1704073320)
        self.assertEqual(len(s['creates']), 1)

    def test_concurrency(self):
        for policy in ['Forbid', 'Replace', 'Allow']:
            with self.subTest(policy=policy):
                s = self.reconcile(self.parent(concurrencyPolicy=policy), [self.child()])
                if policy == 'Forbid':
                    self.assertFalse(s.get('creates'))
                    self.assertEqual(s['events'][0]['reason'], 'JobAlreadyActive')
                elif policy == 'Replace':
                    self.assertEqual(s['actions'], ['delete:old', 'create:hello-1704067260'])
                else:
                    self.assertEqual(len(s['jobs']), 2)
                    self.assertFalse(s.get('deletes'))

    def test_already_exists(self):
        s = self.reconcile(already_exists=True)
        self.assertEqual(len(s['attempts']), 1)
        self.assertFalse(s.get('creates'))
        self.assertFalse(s.get('events'))

    def test_owner_uid_namespace_and_controller(self):
        jobs = [self.child(str(i)) for i in range(4)]
        jobs[0]['metadata']['ownerReferences'][0]['controller'] = False
        jobs[1]['metadata']['ownerReferences'][0]['uid'] = 'stale-uid'
        jobs[2]['metadata']['namespace'] = 'other'
        jobs[3]['metadata']['ownerReferences'][0]['apiVersion'] = 'batch/v1'
        s = self.reconcile(self.parent(concurrencyPolicy='Forbid'), jobs)
        self.assertEqual(len(s['creates']), 1)

    def test_offset_annotation_and_latest_finished(self):
        jobs = [self.child('done', 'Complete', '2024-01-01T01:01:00.123+01:00'),
                self.child('failed', 'Failed', '2024-01-01T00:00:00Z')]
        s = self.reconcile(jobs=jobs)
        self.assertFalse(s.get('creates'))
        self.assertEqual(s['cronjobs'][0]['status']['lastScheduleTime'], '2024-01-01T00:01:00Z')

    def test_other_leader(self):
        s = self.reconcile(lease={'apiVersion': 'coordination.k8s.io/v1', 'kind': 'Lease',
            'metadata': {'name': 'cronjob', 'namespace': 'amaenetes'}, 'spec': {
                'holderIdentity': 'another', 'leaseDurationSeconds': 30,
                'renewTime': '2099-01-01T00:00:00Z'}})
        self.assertFalse(s.get('looks'))
        self.assertFalse(s.get('creates'))

    def test_failed_mutations_retry_and_failed_list_never_creates(self):
        for operation in ['list', 'patch', 'delete', 'create']:
            with self.subTest(operation=operation):
                parent = self.parent(concurrencyPolicy='Replace')
                s = self.reconcile(parent, [self.child()], looks=2,
                                   fail_once=operation, expected_error='injected failure')
                self.assertEqual(len(s['creates']), 1)
                self.assertEqual(s['actions'], ['delete:old', 'create:hello-1704067260'])
                self.assertEqual(s['looks'], 2)

    def test_clock_file_advances_and_most_recent_missed_run(self):
        s = self.reconcile(looks=3, clocks=[1704067380, 1704067380, 1704067440])
        self.assertEqual([j['metadata']['name'] for j in s['creates']],
                         ['hello-1704067380', 'hello-1704067440'])
        self.assertEqual(len(s['attempts']), 2)

    def test_many_parents_and_large_template(self):
        parents = []
        jobs = []
        for i in range(12):
            parent = self.parent(concurrencyPolicy='Forbid')
            parent['metadata']['name'] = 'parent-' + str(i)
            parent['metadata']['uid'] = 'uid-' + str(i)
            parent['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['args'] = ['x' * 10000]
            parents.append(parent)
            if i % 2 == 0:
                job = self.child(str(i))
                job['metadata']['ownerReferences'][0]['uid'] = parent['metadata']['uid']
                jobs.append(job)
        s = self.reconcile(parents, jobs, looks=2)
        self.assertEqual(len(s['creates']), 6)
        self.assertEqual({j['metadata']['ownerReferences'][0]['uid'] for j in s['creates']},
                         {'uid-' + str(i) for i in range(1, 12, 2)})
        self.assertEqual(len(s['creates'][0]['spec']['template']['spec']['containers'][0]['args'][0]), 10000)

    def test_status_order_does_not_cause_patch(self):
        jobs = [self.child('a'), self.child('b')]
        parent = self.parent(suspend=True)
        parent['status'] = {'active': [{
            'apiVersion': 'batch/v1', 'kind': 'Job', 'namespace': 'demo',
            'name': j['metadata']['name'], 'uid': j['metadata']['uid']} for j in reversed(jobs)]}
        s = self.reconcile(parent, jobs)
        self.assertFalse(s.get('patches'))

    def test_invalid_and_impossible_schedule(self):
        for expression in ['*/0 * * * *', '0 0 31 feb *']:
            with self.subTest(expression=expression):
                parent = self.parent()
                parent['spec']['schedule'] = expression
                s = self.reconcile(parent)
                self.assertFalse(s.get('creates'))
                self.assertEqual(s['events'][0]['reason'], 'InvalidSchedule')


EVENTS_FAKE_KUBECTL = r'''#!/usr/bin/env python3
"""A kubectl that keeps Events, applying merge patches to them; fail_patch_at
makes the numbered patch answer NotFound, as an expired Event would."""
import json, os, sys
p = os.environ["FAKE_STATE"]
s = json.load(open(p))
a = sys.argv[1:]
assert a[:2] == ["--context", "imagined"], a
a = a[2:]
ns = ""
if a[0] == "-n":
    ns = a[1]
    a = a[2:]
if a[:2] == ["create", "--raw"] and a[2].endswith("/events"):
    body = json.load(sys.stdin)
    s.setdefault("events", []).append(body)
    json.dump(s, open(p, "w"))
    print(json.dumps(body))
elif a[:2] == ["patch", "events"]:
    body = json.load(sys.stdin)
    name = a[2]
    s.setdefault("patches", []).append({"name": name, "body": body})
    if s.get("fail_patch_at") == len(s["patches"]):
        json.dump(s, open(p, "w"))
        print('Error from server (NotFound): events "%s" not found' % name, file=sys.stderr)
        sys.exit(1)
    event = next((e for e in s.get("events", []) if e["metadata"]["name"] == name
                  and e["metadata"]["namespace"] == ns), None)
    if event is None:
        json.dump(s, open(p, "w"))
        print('Error from server (NotFound): events "%s" not found' % name, file=sys.stderr)
        sys.exit(1)
    event.update(body)
    json.dump(s, open(p, "w"))
else:
    sys.exit("fake kubectl cannot " + " ".join(a))
'''


class LiveEvents(unittest.TestCase):
    """tell_event through a kubectl that keeps Events: a telling just like an
    earlier one patches the Event first created, it does not create another."""

    SOURCE = '''written by "tests"
learn "kube.amae"
soul teller
    hear world into line
    let pod = meaning of line
    perform tell_event with pod, "Normal", "Scheduled", "assigned to a", "tester"
    perform tell_event with pod, "Normal", "Scheduled", "assigned to a", "tester"
    perform tell_event with pod, "Normal", "Scheduled", "assigned to b", "tester"
    perform tell_event with pod, "Normal", "Scheduled", "assigned to b", "tester"
    perform tell_event with pod, "Normal", "Scheduled", "assigned to b", "tester"
end
'''

    def tell(self, fail_patch_at=None):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "kubectl")
            with open(fake, "w") as f:
                f.write(EVENTS_FAKE_KUBECTL)
            os.chmod(fake, 0o755)
            state = os.path.join(d, "state.json")
            with open(state, "w") as f:
                json.dump({"fail_patch_at": fail_patch_at} if fail_patch_at else {}, f)
            pod = {"metadata": {"name": "web", "namespace": "ns", "uid": "uid-web"},
                   "spec": {}, "status": {}}
            life = run(self.SOURCE, given=json.dumps(pod) + "\n",
                       env={"KUBECTL": fake, "KUBE_CONTEXT": "imagined", "FAKE_STATE": state})
            self.assertEqual(life.code, 0, life.err)
            self.assertEqual(life.err, "")
            with open(state) as f:
                return json.load(f)

    def test_a_repeat_patches_the_event_first_created(self):
        state = self.tell()
        first, second = state["events"]
        # Same pod, type, reason and component: a new message is a new Event,
        # a repeated telling patches the one first created, count one more.
        self.assertEqual(len(state["events"]), 2)
        self.assertEqual(first["count"], 2)
        self.assertEqual(second["count"], 3)
        self.assertEqual(len(state["patches"]), 3)
        for patch, count, target in [(state["patches"][0], 2, first),
                                     (state["patches"][1], 2, second),
                                     (state["patches"][2], 3, second)]:
            self.assertEqual(patch["name"], target["metadata"]["name"])
            self.assertEqual(patch["body"]["count"], count)
            self.assertRegex(patch["body"]["lastTimestamp"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_a_patch_that_finds_nothing_creates_a_new_event(self):
        state = self.tell(fail_patch_at=2)
        first, second, third = state["events"]
        # The second telling of "assigned to b" found its Event gone: a new
        # one was created and remembered, and the third telling patched it.
        self.assertEqual(first["count"], 2)
        self.assertEqual(second["count"], 1)
        self.assertEqual(third["count"], 2)
        self.assertNotEqual(second["metadata"]["name"], third["metadata"]["name"])
        self.assertEqual(len(state["patches"]), 3)
        self.assertEqual(state["patches"][1]["name"], second["metadata"]["name"])
        self.assertEqual(state["patches"][1]["body"]["count"], 2)
        self.assertEqual(state["patches"][2]["name"], third["metadata"]["name"])
        self.assertEqual(state["patches"][2]["body"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
