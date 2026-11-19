#!/usr/bin/env python3
"""Record what every program does, compiled by the Tainted compiler.

Each case in tests/golden/<name>/ holds the program (prog.tainted), what the
world says to it (input, if anything) and, for its first and second run,
what it printed, what it lamented and how it ended (out0, err0, code0, out1,
err1, code1). The compiled programs are checked against these.
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "golden")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import minsky  # noqa: E402

INLINE = {
    "rule-ritual-arity": "written by \"tests\"\nritual r a\nend\nsoul s\n perform r with 1, 2\nend\n",
    "rule-tell-a-stranger": "written by \"tests\"\nsoul a\n tell b 1\nend\nsoul b\n hear a into x\nend\n",
    "rule-confide-needs-heart": "written by \"tests\"\nsoul a\n meet b\n knowingly confide b 1\nend\nsoul b\n meet a\n hear a into x\nend\n",
    "rule-leaving-is-final": "written by \"tests\"\nsoul a\n meet b\n knowingly leave b\n meet b\nend\nsoul b\n meet a\nend\n",
    "rule-forgiveness": ("written by \"tests\"\nsoul a\n meet b\n knowingly wound b\n hear b into x\n say x\nend\n"
                         "soul b\n meet a\n forgive a\n tell a \"still here\"\n say scars of a\nend\n"),
    "long-endure": ("written by \"tests\"\nsoul s\n let n = 0\n endure\n"
                    + "".join("  n = n + 1\n" for _ in range(60))
                    + "  endure\n   cry \"inner\"\n  when it hurts as again\n   say \"held \" + again\n  end\n"
                    + "  say n\n when it hurts as pain\n  say pain\n end\nend\n"),
    "rule-no-timeout": "written by \"tests\"\nsoul a\n meet b\nend\nsoul b\n goodbye\nend\n",
    "rule-passion-cools": ("written by \"tests\"\nsoul a\n meet b\n let i = 0\n while i < 60\n  i = i + 1\n end\n"
                           " say passion b\nend\nsoul b\n meet a\nend\n"),
    "rule-recursion": ("written by \"tests\"\nritual f n\n if n <= 1\n give back 1\n end\n"
                       " perform f with n - 1 into m\n give back n * m\nend\n"
                       "soul s\n perform f with 12 into x\n say x\nend\n"),
    "rule-memory-held": ("written by \"tests\"\nritual long\n let i = 0\n while i < 200\n i = i + 1\n end\nend\n"
                         "soul s\n let year = 1999\n perform long\n say year\nend\n"),
    "rule-overflow": "written by \"tests\"\nsoul s\n let x = 9223372036854775807\n say x\n say x + 1\nend\n",
    "rule-division": "written by \"tests\"\nsoul s\n say 7 / -2\n say 7 % -2\n say -7 / 2\n say -7 % 2\n say 1 / 0\nend\n",
    "rule-types": "written by \"tests\"\nsoul s\n say \"a\" < \"b\"\n say 1 == \"1\"\n say \"x\" - 1\nend\n",
    "rule-text": ("written by \"tests\"\nsoul s\n let t = \"  one two  three \"\n say words of t\n say word 2 of t\n"
                  " say \"[\" + word 9 of t + \"]\"\n say place of \"three\" in t\n say length of \"héllo\"\n"
                  " say part 2 4 of \"héllo\"\n say number of \" -1_000 \"\n say number of \"x\"\nend\n"),
    "rule-unknown-variable": "written by \"tests\"\nsoul s\n say ghost\nend\n",
    "rule-unknown-soul": "written by \"tests\"\nsoul s\n meet nobody\nend\n",
    "rule-themself": "written by \"tests\"\nsoul s\n meet s\nend\n",
    "rule-names-are-words": "written by \"tests\"\nsoul s\n meet soul named 5\nend\n",
    "rule-giveback-outside": "written by \"tests\"\nsoul s\n give back 1\nend\n",
    "rule-unknown-ritual": "written by \"tests\"\nsoul s\n perform nothing\nend\n",
    "rule-unknown-kind": "written by \"tests\"\nsoul s\n bring ghost named \"g\"\nend\n",
    "rule-bring-twice": "written by \"tests\"\nkind k\nend\nsoul s\n bring k named \"a\"\n bring k named \"a\"\nend\n",
    "rule-scar-number": "written by \"tests\"\nsoul a\n meet b\n say scar 1 of b\nend\nsoul b\n meet a\nend\n",
    "rule-note-missing": "written by \"tests\"\nsoul s\n note 1 = \"one\"\n say note \"1\"\n say note 2\nend\n",
    "rule-fear": ("written by \"tests\"\nsoul a\n meet b\n tell b 1\n tell b 2\n tell b 3\n tell b 4\nend\n"
                  "soul b\n meet a\n hear a into x\n hear a into y\n hear a into z\n say afraid of a\n"
                  " hear a into q\n say q\n say afraid of a\nend\n"),
    "rule-strangers": ("written by \"tests\"\nkind k\n meet anyone as who\n tell soul named who me\nend\n"
                       "soul s\n bring k named \"k1\"\n meet soul named \"k1\"\n"
                       " hear anyone into x from y\n say x + \" \" + y\nend\n"),
    "rule-silence": ("written by \"tests\"\nsoul a\n wait for silence\n say \"a\"\nend\nsoul b\n wait\n wait\n"
                     " wait for silence\n say \"b\"\nend\n"),
    "rule-patience": "written by \"tests\"\nsoul s\n mark top\n return to top\nend\n",
    "rule-short-circuit": ("written by \"tests\"\nsoul s\n let j = 0\n say j >= 1 and note j > 1\n say j == 0 or note j > 1\n"
                           " say 1 and 2\n say 0 or \"\"\nend\n"),
    "rule-escapes": "written by \"tests\"\nsoul s\n say \"a\\\\nb\"\n say \"q\\\"q\"\n say \"x\\ny\"\n say \"t\\tz\"\nend\n",
    "rule-cry": "written by \"tests\"\nsoul s\n cry \"it hurts\"\n say \"still\"\n goodbye with 3\n say \"never\"\nend\n",
    "rule-bad-ending": "written by \"tests\"\nsoul s\n goodbye with \"soon\"\nend\n",
    "values-lists-maps": ("written by \"tests\"\nsoul s\n let xs = [3, 1, 2]\n put 10 into xs\n xs[2] = 5\n say xs\n"
                          " let m = {\"a\": 1, \"b\": [2, 3]}\n m[\"c\"] = 2.5\n remove \"a\" from m\n"
                          " say m\n say keys of m\n say json of m\n say m[\"b\"][2] * 1.5\n"
                          " say meaning of \"[1, {\\\"x\\\": null}]\"\nend\n"),
    "values-fade": ("written by \"tests\"\nsoul s\n let xs = [1, 2, 3, 4]\n let d = 3.14159\n let i = 0\n"
                    " while i < 40\n i = i + 1\n end\n say xs\n say d\nend\n"),
    "values-endure": ("written by \"tests\"\nritual risky n\n if n == 0\n say {}[\"x\"]\n end\n perform risky with n - 1\nend\n"
                      "soul s\n endure\n perform risky with 2\n say \"no\"\n when it hurts as pain\n"
                      " say pain\n end\n endure\n say 1 / 0\n when it hurts as pain\n say pain\n end\n"
                      " say [1][3]\nend\n"),
    "syntax-list": "written by \"tests\"\nsoul s\n say [1, 2\nend\n",
    "styles-anxious-avoidant": ("written by \"tests\"\nsoul a is anxious\n meet b\n hear b into x\n say x\nend\n"
                                "soul b is avoidant and storge\n meet a\n let i = 0\n while i < 10\n"
                                "  i = i + 1\n end\n tell a \"late\"\nend\n"),
    "syntax-style": "written by \"tests\"\nsoul a is shy\nend\n",
    "syntax-knowingly": "written by \"tests\"\nsoul a\n meet b\n wound b\nend\nsoul b\n meet a\nend\n",
    "syntax-dialogue": "written by \"tests\"\nsoul a\n meet b\n tell b 1\nend\nsoul b\n meet a\n tell a 2\nend\n",
    "syntax-unanswered": "written by \"tests\"\nsoul a\n meet b\n tell b 1\n tell b 2\nend\nsoul b\n meet a\n hear a into x\nend\n",
    "syntax-two-hearts": ("written by \"tests\"\nsoul a\n meet b\n meet c\n give heart to b\n give heart to c\nend\n"
                          "soul b\n meet a\nend\nsoul c\n meet a\nend\n"),
    "rule-heart-moves": ("written by \"tests\"\nsoul a\n meet b\n meet c\n give heart to b\n take back heart from b\n"
                         " give heart to c\n give heart to soul named \"b\"\n say scars of c\nend\n"
                         "soul b\n meet a\nend\nsoul c\n meet a\n wait\n wait\n wait\n say scar 1 of a\nend\n"),
    "consent-needed": ("written by \"tests\"\nsoul a\n meet b\n consent to b\n together with b\n say \"never\"\n end\nend\n"
                       "soul b\n meet a\n together with a\n say \"never\"\n end\nend\n"),
    "syntax-map": "written by \"tests\"\nsoul s\n say {\"a\" 1}\nend\n",
    "syntax-endure": "written by \"tests\"\nsoul s\n endure\n say 1\n end\nend\n",
    "syntax-learn": "written by \"tests\"\nlearn missing\nsoul s\nend\n",
    # compile errors
    "syntax-outside": "say 1\n",
    "syntax-no-end": "written by \"tests\"\nsoul s\n say 1\n",
    "syntax-twice": "written by \"tests\"\nsoul s\nend\nsoul s\nend\n",
    "syntax-keyword-name": "written by \"tests\"\nsoul s\n let word = 1\nend\n",
    "syntax-no-moment": "written by \"tests\"\nsoul s\n return to nowhere\nend\n",
    "syntax-moment-twice": "written by \"tests\"\nsoul s\n mark m\n mark m\nend\n",
    "syntax-big-number": "written by \"tests\"\nsoul s\n say 99999999999999999999\nend\n",
    "syntax-while-else": "written by \"tests\"\nsoul s\n while 1\n else\n end\nend\n",
    "syntax-unread": "written by \"tests\"\nsoul s\n say $\nend\n",
    "syntax-not-a-deed": "written by \"tests\"\nsoul s\n dance\nend\n",
    "syntax-early-end": "written by \"tests\"\nsoul s\n say 1 +\nend\n",
}

# Cases where the program reads the world.
INPUTS = {
    "classics-cat": "hello\nworld\n",
    "classics-reverse": "stressed\nlevel\n",
    "classics-wc": "the quick brown fox\njumps over\nthe lazy dog\n",
    "classics-sort": "5\n3\n10\n1\n42\n7\n7\n0\n",
}

PATIENCE = {"rule-patience": 1000}


def run(prog, given, history, patience=None, cwd=None):
    """Compile the program and run it; a program that does not compile says
    what the compiler said, every time."""
    binary = prog[:-len(".tainted")]
    if not os.path.exists(binary):
        with open(prog) as f:
            res = subprocess.run([os.path.join(ROOT, "build", "tc-core")], stdin=f,
                                 capture_output=True, text=True,
                                 env=dict(os.environ, TAINTED_HISTORY=history + ".compiler",
                                          TAINTED_MEMORY=history + ".memory",
                                          TAINTED_LIB=os.path.join(ROOT, "lib")))
        if res.returncode:
            return "", res.stderr, str(res.returncode)
        with open(binary + ".c", "w") as f:
            f.write(res.stdout)
        subprocess.run(["cc", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-D_DEFAULT_SOURCE", "-O1", "-w",
                        "-I" + os.path.join(ROOT, "runtime"), binary + ".c",
                        os.path.join(ROOT, "runtime", "tainted.c"), "-o", binary, "-lm"], check=True)
    args = [binary, "--feelings"]
    if patience:
        args.append(f"--patience={patience}")
    res = subprocess.run(args, input=given, capture_output=True, text=True, cwd=cwd,
                         env=dict(os.environ, TAINTED_HISTORY=history))
    return res.stdout, res.stderr, str(res.returncode)


def add(name, source, given="", patience=None):
    d = os.path.join(GOLDEN, name)
    os.makedirs(d)
    prog = os.path.join(d, "prog.tainted")
    with open(prog, "w") as f:
        f.write(source)
    if given:
        with open(os.path.join(d, "input"), "w") as f:
            f.write(given)
    if patience:
        with open(os.path.join(d, "patience"), "w") as f:
            f.write(str(patience))
    with tempfile.TemporaryDirectory() as t:
        history = os.path.join(t, "history.json")
        shutil.copy(prog, os.path.join(t, "prog.tainted"))
        for k in range(2):
            out, err, code = run(os.path.join(t, "prog.tainted"), given, history, patience, cwd=t)
            for part, text in (("out", out), ("err", err), ("code", code)):
                with open(os.path.join(d, f"{part}{k}"), "w") as f:
                    f.write(text)


def snapshot():
    """A cluster as kubectl tells it: nodes, then pods, one JSON line each."""
    def node(name, labels=None, taint=False, extra=None, seats=None):
        notes = {"taintednetes.io/seats": str(seats)} if seats is not None else {}
        return {"metadata": {"name": name, "labels": labels or {}, "annotations": notes},
                "spec": {"taints": [{"key": "role", "effect": "NoSchedule"}] if taint else []},
                "status": {"allocatable": {"cpu": "2", "memory": "4Gi", "pods": "110", **(extra or {})},
                           "conditions": [{"type": "Ready", "status": "True"}]}}

    def pod(name, node=None, requests=None, likes=None, spec=None):
        c = {"resources": {"requests": requests or {"cpu": "500m", "memory": "64Mi"}}}
        body = {"schedulerName": "taintednetes", "nodeName": node, "containers": [c], **(spec or {})}
        return {"metadata": {"name": name, "namespace": "shop",
                             "creationTimestamp": "2026-11-18T10:00:00Z",
                             "annotations": {"taintednetes.io/likes": likes} if likes else {}},
                "spec": body, "status": {"phase": "Running" if node else "Pending"}}
    zone = {"affinity": {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {
        "nodeSelectorTerms": [{"matchExpressions": [{"key": "zone", "operator": "In", "values": ["west"]}]}]}}}}
    nodes = [node("east", labels={"zone": "east"}), node("west", labels={"zone": "west"}, seats=3),
             node("lab", extra={"nvidia.com/gpu": "1"}), node("control", taint=True)]
    pods = [pod("db-0", node="east", requests={"cpu": "1500m"}), pod("web", likes="east west"),
            pod("api", spec=zone), pod("train", requests={"cpu": "1", "nvidia.com/gpu": "1"}),
            pod("tune", requests={"cpu": "1", "nvidia.com/gpu": "1"}),
            pod("big", requests={"cpu": "3"}),
            pod("urgent", requests={"cpu": "1"}, spec={"priority": 100, "nodeSelector": {"zone": "east"}})]
    return json.dumps({"items": nodes}) + "\n" + json.dumps({"items": pods}) + "\n"


def cluster(rng):
    pods = [f"p{i}" for i in range(rng.randint(3, 30))]
    nodes = [f"n{i}" for i in range(rng.randint(2, 6))]
    lines = [f"pod {p} " + " ".join(rng.sample(nodes, rng.randint(1, len(nodes)))) for p in pods]
    lines += [f"node {n} {rng.randint(0, 4)} " + " ".join(rng.sample(pods, rng.randint(1, len(pods))))
              for n in nodes]
    return "\n".join(lines) + "\n"


def ticks(nodes, pods_by_tick):
    out = []
    for t, pods in enumerate(pods_by_tick, 1):
        out.append(f"tick {t}")
        out += [f"node {n}" for n in nodes]
        out += [f"pod {p}" for p in pods]
        out.append("end")
    return "\n".join(out) + "\n"


def main():
    if os.path.exists(GOLDEN):
        shutil.rmtree(GOLDEN)
    os.makedirs(GOLDEN)
    for folder, prefix in (("examples", "examples-"), ("examples/classics", "classics-"),
                           ("examples/feelings", "feelings-"), ("examples/consent", "consent-"),
                           ("examples/styles", "styles-")):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".tainted"):
                key = prefix + name[:-len(".tainted")]
                with open(os.path.join(ROOT, folder, name)) as f:
                    add(key, f.read(), INPUTS.get(key, ""))
    for key, src in INLINE.items():
        add(key, src, patience=PATIENCE.get(key))
    with open(os.path.join(ROOT, "docs", "tutorial.md")) as f:
        blocks = re.findall(r"```(\w*)\n(.*?)```", f.read(), re.S)
    chapter = 0
    for i, (lang, body) in enumerate(blocks):
        if lang == "tainted":
            chapter += 1
            given = blocks[i + 1][1] if blocks[i + 1][0] == "input" else ""
            follows = blocks[i + 2][0] if given else blocks[i + 1][0]
            if follows != "output" or 'learn "' in body:
                continue        # a file to learn from, or a program that learns
            add(f"tutorial-{chapter:02d}", body, given)
    with open(os.path.join(ROOT, "taintednetes.tainted")) as f:
        scheduler = f.read()
    with open(os.path.join(ROOT, "examples", "cluster.txt")) as f:
        add("taintednetes-example", scheduler, f.read())
    rng = random.Random(2026)
    for k in range(6):
        add(f"taintednetes-random-{k}", scheduler, cluster(rng))
    add("taintednetes-snapshot", scheduler, snapshot())
    with open(os.path.join(ROOT, "kube", "parting.tainted")) as f:
        parting = f.read()
    nodes = ["w1 ready schedulable staying", "w2 ready schedulable leaving"]
    add("parting-drain", parting, ticks(nodes, [
        ["a/x w2 ready a/RS/x", "a/y w2 ready a/RS/x"],
        ["a/y w2 ready a/RS/x", "a/n1 w1 ready a/RS/x"],
        ["a/n1 w1 ready a/RS/x", "a/n2 w1 waiting a/RS/x"],
        ["a/n1 w1 ready a/RS/x", "a/n2 w1 ready a/RS/x"]]))
    add("parting-bare-pod", parting, ticks(["w2 ready cordoned leaving"],
                                           [["a/bare w2 ready none"]] * 3))
    add("parting-refused", parting, ticks(["w1 ready schedulable staying",
                                            "w2 ready cordoned leaving"],
                                           [["a/x w2 ready a/RS/x"]] * 8))
    mrng = random.Random(1978)
    made = 0
    while made < 12:
        size = mrng.randint(2, 6)
        labels = [f"s{i}" for i in range(size)] + ["stop"]
        prog = {}
        for i in range(size):
            if mrng.random() < 0.5:
                prog[f"s{i}"] = ("inc", mrng.choice("xy"), mrng.choice(labels))
            else:
                prog[f"s{i}"] = ("dec", mrng.choice("xy"), mrng.choice(labels), mrng.choice(labels))
        prog["stop"] = ("halt",)
        machine = (["x", "y"], {"x": mrng.randint(0, 5), "y": mrng.randint(0, 5)}, prog, "s0")
        if minsky.simulate(*machine, limit=2000) is None:
            continue
        add(f"minsky-{made:02d}", minsky.compile_machine(*machine))
        made += 1
    print(len(os.listdir(GOLDEN)), "cases")


if __name__ == "__main__":
    main()
