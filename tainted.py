#!/usr/bin/env python3
"""Tainted: a language in which computation happens between souls.

A program is a set of souls. They run side by side, one step each per
round, and they can only reach each other by meeting. Everything that
matters in a Tainted program lives in the relationships: trust,
intimacy, passion, commitment, the heart that was given, the scars.
"""

import hashlib
import json
import os
import re
import sys

FADE = 50            # steps of neglect after which a memory loses a digit
PASSION_FADE = 50    # steps without meeting after which passion cools by one
PRESENT = 3          # a Sternberg component counts once it reaches this
DEFAULT_PATIENCE = 10_000_000

BONDS = {
    (0, 0, 0): "nothing yet",
    (1, 0, 0): "liking",
    (0, 1, 0): "infatuation",
    (0, 0, 1): "empty love",
    (1, 1, 0): "romantic love",
    (1, 0, 1): "companionate love",
    (0, 1, 1): "fatuous love",
    (1, 1, 1): "consummate love",
}

KEYWORDS = {
    "soul", "end", "let", "say", "meet", "tell", "confide", "hear", "into",
    "anyone", "warm", "cool", "to", "promise", "give", "heart", "wound",
    "forgive", "leave", "wait", "mark", "return", "if", "else", "while",
    "first", "time", "goodbye", "and", "or", "not", "trust", "intimacy",
    "passion", "commitment", "bond", "with", "scars", "scar", "of", "runs",
    "afraid", "world", "recall", "length", "part", "me", "note", "word",
    "words", "place", "in", "number", "named", "kind", "bring", "from",
    "silence", "for",
}


class TaintedError(Exception):
    pass


# ---------------------------------------------------------------- lexer

TOKEN = re.compile(
    r'\s*(?:(\d+)|("(?:[^"\\]|\\.)*")|([A-Za-z_][A-Za-z0-9_]*)'
    r'|(==|!=|<=|>=|[-+*/%<>=()]))'
)


def unescape(s):
    return (s.replace('\\n', '\n').replace('\\"', '"')
             .replace('\\\\', '\\'))


def tokenize(line, lineno):
    toks = []
    pos = 0
    while pos < len(line):
        rest = line[pos:].lstrip()
        if not rest or rest.startswith('#'):
            break
        m = TOKEN.match(line, pos)
        if not m:
            raise TaintedError(f"line {lineno}: cannot read '{rest}'")
        num, string, ident, op = m.groups()
        if num is not None:
            toks.append(('num', int(num)))
        elif string is not None:
            toks.append(('str', unescape(string[1:-1])))
        elif ident is not None:
            toks.append(('id', ident))
        else:
            toks.append(('op', op))
        pos = m.end()
    return toks


# --------------------------------------------------------------- parser

class Cursor:
    def __init__(self, toks, lineno):
        self.t = toks
        self.i = 0
        self.n = lineno

    def fail(self, msg):
        raise TaintedError(f"line {self.n}: {msg}")

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        if tok[0] is None:
            self.fail("the line ends too early")
        self.i += 1
        return tok

    def word(self, w):
        tok = self.peek()
        if tok == ('id', w):
            self.i += 1
            return True
        return False

    def expect_word(self, w):
        if not self.word(w):
            self.fail(f"expected '{w}'")

    def op(self, o):
        if self.peek() == ('op', o):
            self.i += 1
            return True
        return False

    def name(self):
        kind, val = self.take()
        if kind != 'id' or val in KEYWORDS:
            self.fail(f"expected a name, got '{val}'")
        return val

    def target(self):
        """A soul named in the code, or `soul named <expr>` computed at run time."""
        if self.word('soul'):
            self.expect_word('named')
            return ('expr', self.unary())
        return ('name', self.name())

    def done(self):
        if self.i != len(self.t):
            self.fail(f"unexpected '{self.t[self.i][1]}'")

    # expressions
    def expr(self):
        return self.or_()

    def or_(self):
        a = self.and_()
        while self.word('or'):
            a = ('or', a, self.and_())
        return a

    def and_(self):
        a = self.not_()
        while self.word('and'):
            a = ('and', a, self.not_())
        return a

    def not_(self):
        if self.word('not'):
            return ('not', self.not_())
        return self.cmp()

    def cmp(self):
        a = self.add()
        for o in ('==', '!=', '<=', '>=', '<', '>'):
            if self.op(o):
                return ('bin', o, a, self.add())
        return a

    def add(self):
        a = self.mul()
        while True:
            if self.op('+'):
                a = ('bin', '+', a, self.mul())
            elif self.op('-'):
                a = ('bin', '-', a, self.mul())
            else:
                return a

    def mul(self):
        a = self.unary()
        while True:
            for o in ('*', '/', '%'):
                if self.op(o):
                    a = ('bin', o, a, self.unary())
                    break
            else:
                return a

    def unary(self):
        if self.op('-'):
            return ('neg', self.unary())
        return self.primary()

    def primary(self):
        kind, val = self.take()
        if kind == 'num':
            return ('num', val)
        if kind == 'str':
            return ('str', val)
        if (kind, val) == ('op', '('):
            e = self.expr()
            if not self.op(')'):
                self.fail("expected ')'")
            return e
        if kind == 'id':
            if val in ('trust', 'intimacy', 'passion', 'commitment'):
                return ('rel', val, self.target())
            if val == 'afraid':
                self.expect_word('of')
                return ('afraid', self.target())
            if val == 'bond':
                self.expect_word('with')
                return ('bond', self.target())
            if val == 'scars':
                self.expect_word('of')
                return ('scars', self.target())
            if val == 'scar':
                idx = self.unary()
                self.expect_word('of')
                return ('scar', idx, self.target())
            if val == 'me':
                return ('me',)
            if val == 'note':
                return ('note', self.unary())
            if val == 'word':
                idx = self.unary()
                self.expect_word('of')
                return ('word', idx, self.unary())
            if val in ('words', 'number'):
                self.expect_word('of')
                return (val, self.unary())
            if val == 'place':
                self.expect_word('of')
                x = self.unary()
                self.expect_word('in')
                return ('place', x, self.unary())
            if val == 'runs':
                return ('runs',)
            if val == 'length':
                self.expect_word('of')
                return ('length', self.unary())
            if val == 'part':
                a = self.unary()
                b = self.unary()
                self.expect_word('of')
                return ('part', a, b, self.unary())
            if val not in KEYWORDS:
                return ('var', val)
        self.fail(f"unexpected '{val}'")


class Parser:
    def __init__(self, source):
        self.lines = []
        for n, line in enumerate(source.splitlines(), 1):
            toks = tokenize(line, n)
            if toks:
                self.lines.append((n, toks))
        self.i = 0

    def parse(self):
        souls = []
        while self.i < len(self.lines):
            n, toks = self.lines[self.i]
            c = Cursor(toks, n)
            if c.word('soul'):
                decl = 'soul'
            elif c.word('kind'):
                decl = 'kind'
            else:
                c.fail("everything must belong to a soul or a kind of soul")
            name = c.name()
            c.done()
            self.i += 1
            body = self.block(('end',))
            self.i += 1
            if any(s[:2] == (decl, name) for s in souls):
                c.fail(f"there is already a {decl} called {name}")
            souls.append((decl, name, body))
        if not souls:
            raise TaintedError("a program needs at least one soul")
        return souls

    def at(self, words):
        if self.i >= len(self.lines):
            raise TaintedError("the program ends before an 'end'")
        _, toks = self.lines[self.i]
        return len(toks) == 1 and toks[0][0] == 'id' and toks[0][1] in words

    def block(self, terminators):
        stmts = []
        while not self.at(terminators):
            stmts.append(self.statement())
        return stmts

    def statement(self):
        n, toks = self.lines[self.i]
        self.i += 1
        c = Cursor(toks, n)
        kind, head = c.peek()
        if kind != 'id':
            c.fail(f"a line cannot start with '{head}'")
        if head not in KEYWORDS:
            name = c.name()
            if not c.op('='):
                c.fail(f"'{name}' is not something a soul can do")
            st = ('let', n, name, c.expr())
            c.done()
            return st
        c.take()
        if head == 'let':
            name = c.name()
            if not c.op('='):
                c.fail("expected '='")
            st = ('let', n, name, c.expr())
        elif head == 'say':
            st = ('say', n, c.expr())
        elif head == 'meet':
            st = ('meet', n, c.target())
        elif head in ('tell', 'confide'):
            who = c.target()
            st = (head, n, who, c.expr())
        elif head == 'note':
            key = c.unary()
            if not c.op('='):
                c.fail("expected '='")
            st = ('note', n, key, c.expr())
        elif head == 'bring':
            kind = c.name()
            c.expect_word('named')
            st = ('bring', n, kind, c.expr())
        elif head == 'hear':
            if c.word('anyone'):
                who = None
            elif c.word('world'):
                who = 'world'
            else:
                who = c.target()
            c.expect_word('into')
            var = c.name()
            speaker = c.name() if c.word('from') else None
            if speaker and who is not None:
                c.fail("only 'hear anyone' needs to ask who it was")
            st = ('hear', n, who, var, speaker)
        elif head in ('warm', 'cool'):
            c.expect_word('to')
            st = (head, n, c.target())
        elif head == 'give':
            c.expect_word('heart')
            c.expect_word('to')
            st = ('give', n, c.target())
        elif head in ('promise', 'wound', 'forgive', 'leave'):
            st = (head, n, c.target())
        elif head == 'wait':
            if c.word('for'):
                c.expect_word('silence')
                st = ('silence', n)
            else:
                st = ('wait', n)
        elif head == 'recall':
            names = [c.name()]
            while c.peek()[0] is not None:
                names.append(c.name())
            st = ('recall', n, names)
        elif head == 'goodbye':
            st = ('goodbye', n)
        elif head == 'mark':
            st = ('mark', n, c.name())
        elif head == 'return':
            c.expect_word('to')
            st = ('return', n, c.name())
        elif head in ('if', 'while'):
            cond = c.expr()
            c.done()
            body = self.block(('else', 'end'))
            other = []
            if self.at(('else',)):
                if head == 'while':
                    c.fail("a while has no else")
                self.i += 1
                other = self.block(('end',))
            self.i += 1
            return (head, n, cond, body, other)
        elif head == 'first':
            c.expect_word('time')
            c.done()
            body = self.block(('end',))
            self.i += 1
            return ('first', n, body)
        else:
            c.fail(f"'{head}' cannot start a line")
        c.done()
        return st


# ------------------------------------------------------------- compiler

def compile_soul(name, body):
    code, marks, jumps = [], {}, []

    def emit(stmts):
        for st in stmts:
            op, line = st[0], st[1]
            if op == 'if':
                jz = [ 'jz', line, st[2], None]
                code.append(jz)
                emit(st[3])
                if st[4]:
                    jmp = ['jmp', line, None]
                    code.append(jmp)
                    jz[3] = len(code)
                    emit(st[4])
                    jmp[2] = len(code)
                else:
                    jz[3] = len(code)
            elif op == 'while':
                top = len(code)
                jz = ['jz', line, st[2], None]
                code.append(jz)
                emit(st[3])
                code.append(['jmp', line, top])
                jz[3] = len(code)
            elif op == 'first':
                fj = ['first', line, None]
                code.append(fj)
                emit(st[2])
                fj[2] = len(code)
            elif op == 'mark':
                if st[2] in marks:
                    raise TaintedError(
                        f"line {line}: {name} already has a moment called {st[2]}")
                marks[st[2]] = len(code)
            elif op == 'return':
                jmp = ['jmp', line, None]
                jumps.append((jmp, st[2]))
                code.append(jmp)
            else:
                code.append(list(st))

    emit(body)
    for jmp, mark in jumps:
        if mark not in marks:
            raise TaintedError(
                f"line {jmp[1]}: {name} has no moment called {mark} to return to")
        jmp[2] = marks[mark]
    return code


def compile_program(source):
    return [(d, n, compile_soul(n, b)) for d, n, b in Parser(source).parse()]


# ------------------------------------------------------- tainted assembly
#
# Tainted assembly is what compiler.tainted produces: the same statements,
# with if, while, first time, mark and return lowered into labels and jumps.
#   NAME:            a label
#   jz LABEL expr    jump to LABEL when expr is false
#   jmp LABEL
#   first LABEL      jump to LABEL unless this is the first run

LABEL = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):$')


def to_tas(source):
    """The reference compiler. compiler.tainted must produce the same output."""
    out, stack, blocks = ["# compiled by tainted.py"], [], 0
    for raw in source.splitlines():
        text = raw.lstrip(' ')
        word = text.split(' ', 1)[0]
        rest = text[len(word) + 1:]
        if not word or word.startswith('#'):
            continue
        if word in ('soul', 'kind'):
            out.append(text)
        elif word in ('end', 'else'):
            if not stack:
                out.append('end')
                continue
            kind, num = stack.pop()
            if word == 'else':
                out += [f"    jmp L{num}x", f"    L{num}e:"]
                stack.append(('e', num))
                continue
            if kind == 'w':
                out.append(f"    jmp W{num}")
            out.append(f"    L{num}{'x' if kind == 'e' else 'e'}:")
        elif word == 'if':
            blocks += 1
            out.append(f"    jz L{blocks}e {rest}")
            stack.append(('i', blocks))
        elif word == 'while':
            blocks += 1
            out += [f"    W{blocks}:", f"    jz L{blocks}e {rest}"]
            stack.append(('w', blocks))
        elif word == 'first':
            blocks += 1
            out.append(f"    first L{blocks}e")
            stack.append(('f', blocks))
        elif word == 'mark':
            out.append(f"    M_{rest}:")
        elif word == 'return':
            out.append(f"    jmp M_{rest[3:]}")
        else:
            out.append("    " + text)
    return "\n".join(out) + "\n"


def load_tas(text):
    program, soul = [], None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if soul is None:
            c = Cursor(tokenize(line, n), n)
            decl = 'kind' if c.word('kind') else 'soul'
            if decl == 'soul':
                c.expect_word('soul')
            soul = (decl, c.name(), [], {})
            c.done()
            continue
        decl, name, code, labels = soul
        if line == 'end':
            for ins in code:
                slot = {'jz': 3, 'jmp': 2, 'first': 2}.get(ins[0])
                if slot is not None:
                    if ins[slot] not in labels:
                        raise TaintedError(f"line {ins[1]}: no label {ins[slot]}")
                    ins[slot] = labels[ins[slot]]
            program.append((decl, name, code))
            soul = None
            continue
        m = LABEL.match(line)
        if m:
            if m.group(1) in labels:
                raise TaintedError(f"line {n}: label {m.group(1)} appears twice")
            labels[m.group(1)] = len(code)
            continue
        word, _, rest = line.partition(' ')
        if word == 'jz':
            label, _, cond = rest.partition(' ')
            c = Cursor(tokenize(cond, n), n)
            e = c.expr()
            c.done()
            code.append(['jz', n, e, label])
        elif word in ('jmp', 'first'):
            code.append([word, n, rest.strip()])
        else:
            p = Parser(line)
            st = p.statement()
            if st[0] in ('if', 'while', 'first', 'mark', 'return'):
                raise TaintedError(f"line {n}: '{st[0]}' has no place in assembly")
            code.append([st[0], n] + list(st[2:]))
    if soul is not None:
        raise TaintedError("the assembly ends inside a soul")
    if not program:
        raise TaintedError("a program needs at least one soul")
    return program


# -------------------------------------------------------------- runtime

class Rel:
    """How one soul sees another. Relationships are not symmetric."""

    def __init__(self):
        self.met = False
        self.trust = 0
        self.intimacy = 0
        self.passion = 0
        self.commitment = 0
        self.gift = False
        self.closed = False
        self.left = False
        self.abandoned = False
        self.pressure = 0
        self.last_meet = 0
        self.heard = []
        self.scars = []


class Soul:
    def __init__(self, name, code):
        self.name = name
        self.code = code
        self.pc = 0
        self.mem = {}
        self.notes = {}
        self.step = 0
        self.arrived = 0
        self.done = False
        self.afraid = {}

    def current(self):
        return self.code[self.pc] if self.pc < len(self.code) else None


def bond_name(r):
    key = tuple(int(v >= PRESENT) for v in (r.intimacy, r.passion, r.commitment))
    return BONDS[key]


def fade(value, periods):
    if isinstance(value, int):
        sign = -1 if value < 0 else 1
        lost = 10 ** periods
        return sign * (abs(value) // lost * lost)
    return value[:max(0, len(value) - periods)]


def show(v):
    return str(v)


class World:
    def __init__(self, program, runs=0, out=sys.stdout, patience=DEFAULT_PATIENCE,
                 err=None, inp=None):
        self.kinds = {n: code for d, n, code in program if d == 'kind'}
        self.order = [Soul(n, code) for d, n, code in program if d == 'soul']
        if not self.order:
            raise TaintedError("a program needs at least one soul")
        self.souls = {s.name: s for s in self.order}
        k = runs % len(self.order)
        self.order = self.order[k:] + self.order[:k]
        self.runs = runs
        self.out = out
        self.patience = patience
        self.err = err or sys.stderr
        self.input = inp or sys.stdin
        self.rels = {}
        self.mine = {}
        self.round = 0

    def rel(self, a, b):
        key = (a, b)
        if key not in self.rels:
            r = self.rels[key] = Rel()
            self.mine.setdefault(a, []).append(r)
        return self.rels[key]

    def resolve(self, s, target):
        if target[0] == 'name':
            return target[1]
        who = self.ev(s, target[1])
        if not isinstance(who, str):
            raise TaintedError(f"{s.name} looks for a soul named {who}, but names are words")
        return who

    def other(self, s, who):
        if who not in self.souls:
            raise TaintedError(f"{s.name} looks for {who}, but there is no such soul")
        if who == s.name:
            raise TaintedError(f"{s.name} cannot do this with themself")
        return self.souls[who]

    def known(self, s, who):
        self.other(s, who)
        r = self.rel(s.name, who)
        if not r.met:
            raise TaintedError(f"{s.name} has never met {who}")
        if r.left:
            raise TaintedError(f"{s.name} left {who}; there is nothing more to do")
        return r

    # memory
    def read(self, s, name):
        if name not in s.mem:
            raise TaintedError(f"{s.name} does not remember any {name}")
        value, touched = s.mem[name]
        periods = (s.step - touched) // FADE
        if periods:
            value = fade(value, periods)
        s.mem[name] = (value, s.step)
        return value

    def ev(self, s, e):
        k = e[0]
        if k in ('num', 'str'):
            return e[1]
        if k == 'var':
            return self.read(s, e[1])
        if k == 'runs':
            return self.runs
        if k == 'neg':
            v = self.ev(s, e[1])
            if not isinstance(v, int):
                raise TaintedError("only numbers can be negated")
            return -v
        if k == 'not':
            return int(not self.ev(s, e[1]))
        if k == 'and':
            return int(bool(self.ev(s, e[1])) and bool(self.ev(s, e[2])))
        if k == 'or':
            return int(bool(self.ev(s, e[1])) or bool(self.ev(s, e[2])))
        if k == 'rel':
            who = self.other(s, self.resolve(s, e[2])).name
            return getattr(self.rel(s.name, who), e[1])
        if k == 'afraid':
            who = self.other(s, self.resolve(s, e[1])).name
            return int(s.afraid.get(who, 0) > 0)
        if k == 'bond':
            who = self.other(s, self.resolve(s, e[1])).name
            return bond_name(self.rel(s.name, who))
        if k == 'scars':
            who = self.other(s, self.resolve(s, e[1])).name
            return len(self.rel(s.name, who).scars)
        if k == 'scar':
            idx = self.ev(s, e[1])
            who = self.other(s, self.resolve(s, e[2])).name
            scars = self.rel(s.name, who).scars
            if not isinstance(idx, int) or not 1 <= idx <= len(scars):
                raise TaintedError(f"{s.name} has no scar number {idx} from {who}")
            return scars[idx - 1]
        if k == 'me':
            return s.name
        if k == 'note':
            key = show(self.ev(s, e[1]))
            if key not in s.notes:
                raise TaintedError(f"{s.name} never wrote down {key}")
            return s.notes[key]
        if k in ('word', 'words', 'place', 'number'):
            args = [self.ev(s, a) for a in e[1:]]
            text = args[-1]
            if not isinstance(text, str):
                raise TaintedError(f"'{k}' needs a word, not {text}")
            if k == 'number':
                try:
                    return int(text.strip())
                except ValueError:
                    raise TaintedError(f"'{text}' is not a number") from None
            ws = text.split()
            if k == 'words':
                return len(ws)
            if k == 'word':
                idx = args[0]
                return ws[idx - 1] if isinstance(idx, int) and 1 <= idx <= len(ws) else ""
            return ws.index(show(args[0])) + 1 if show(args[0]) in ws else 0
        if k == 'length':
            v = self.ev(s, e[1])
            if not isinstance(v, str):
                raise TaintedError("only words have a length")
            return len(v)
        if k == 'part':
            a, b, v = self.ev(s, e[1]), self.ev(s, e[2]), self.ev(s, e[3])
            if not (isinstance(a, int) and isinstance(b, int) and isinstance(v, str)):
                raise TaintedError("part takes two numbers and a word")
            return v[max(a, 1) - 1:max(b, 0)]
        if k == 'bin':
            return self.binary(e[1], self.ev(s, e[2]), self.ev(s, e[3]))
        raise TaintedError(f"unknown expression {k}")

    @staticmethod
    def binary(op, a, b):
        if op == '+':
            if isinstance(a, str) or isinstance(b, str):
                return show(a) + show(b)
            return a + b
        if op == '==':
            return int(a == b)
        if op == '!=':
            return int(a != b)
        if type(a) is not type(b):
            raise TaintedError(f"cannot compare or combine '{a}' and '{b}'")
        if op in ('<', '>', '<=', '>='):
            return int({'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op])
        if not isinstance(a, int):
            raise TaintedError(f"'{op}' works only on numbers")
        if op == '-':
            return a - b
        if op == '*':
            return a * b
        if b == 0:
            raise TaintedError("a number cannot be divided by nothing")
        return a // b if op == '/' else a % b

    # movement
    def advance(self, s, to=None):
        s.pc = s.pc + 1 if to is None else to

    def try_meet(self, a, b):
        bi = b.current()
        if not (bi and bi[0] == 'meet' and self.resolve(b, bi[2]) == a.name):
            return False
        ra, rb = self.rel(a.name, b.name), self.rel(b.name, a.name)
        if ra.left or rb.left or ra.closed or rb.closed:
            return False
        warmth = 3 if not ra.met and a.arrived == b.arrived else 1
        for s, r in ((a, ra), (b, rb)):
            r.met = True
            r.passion += warmth
            r.last_meet = s.step
            self.advance(s)
        return True

    def try_transfer(self, snd, rcv):
        si, ri = snd.current(), rcv.current()
        if not (si and si[0] in ('tell', 'confide')
                and self.resolve(snd, si[2]) == rcv.name):
            return False
        if not (ri and ri[0] == 'hear' and ri[2] != 'world'
                and (ri[2] is None or self.resolve(rcv, ri[2]) == snd.name)):
            return False
        rs, rr = self.rel(snd.name, rcv.name), self.rel(rcv.name, snd.name)
        if not rr.met or rr.closed or rr.left or rs.left:
            return False
        if rcv.afraid.get(snd.name, 0) > 0:
            return False
        if si[0] == 'confide' and not rs.gift:
            raise TaintedError(
                f"{snd.name} can confide only in someone they gave their heart to")
        value = self.ev(snd, si[3])
        rcv.mem[ri[3]] = (value, rcv.step)
        if ri[4]:
            rcv.mem[ri[4]] = (snd.name, rcv.step)
        rr.heard.append(value)
        if rr.pressure > 0:
            rs.intimacy += 1
            rr.intimacy += 1
        rr.pressure = 0
        rs.pressure += 1
        if rs.pressure > rr.intimacy + 2:
            rcv.afraid[snd.name] = 3 + rs.pressure
            rr.passion = max(0, rr.passion - 1)
            rs.pressure = 0
        self.advance(snd)
        self.advance(rcv)
        return True

    def step(self, s):
        ins = s.current()
        if ins is None:
            s.done = True
            return True
        op = ins[0]
        if op == 'let':
            s.mem[ins[2]] = (self.ev(s, ins[3]), s.step)
        elif op == 'say':
            print(show(self.ev(s, ins[2])), file=self.out)
        elif op == 'jz':
            if self.ev(s, ins[2]):
                self.advance(s)
            else:
                self.advance(s, ins[3])
            return True
        elif op == 'jmp':
            self.advance(s, ins[2])
            return True
        elif op == 'first':
            if self.runs:
                self.advance(s, ins[2])
            else:
                self.advance(s)
            return True
        elif op == 'wait':
            pass
        elif op == 'goodbye':
            s.done = True
            return True
        elif op == 'silence':
            return False
        elif op == 'note':
            s.notes[show(self.ev(s, ins[2]))] = self.ev(s, ins[3])
        elif op == 'bring':
            if ins[2] not in self.kinds:
                raise TaintedError(f"there is no kind of soul called {ins[2]}")
            name = self.ev(s, ins[3])
            if not isinstance(name, str) or not name:
                raise TaintedError(f"a soul needs a name, not {name}")
            if name in self.souls:
                raise TaintedError(f"there is already a soul called {name}")
            child = Soul(name, self.kinds[ins[2]])
            child.arrived = self.round
            self.order.append(child)
            self.souls[name] = child
        elif op == 'meet':
            b = self.other(s, self.resolve(s, ins[2]))
            if self.rel(s.name, b.name).left:
                raise TaintedError(f"{s.name} left {b.name}; there is nothing more to do")
            return self.try_meet(s, b)
        elif op in ('tell', 'confide'):
            b = self.other(s, self.resolve(s, ins[2]))
            r = self.known(s, b.name)
            if op == 'confide' and not r.gift:
                raise TaintedError(
                    f"{s.name} can confide only in someone they gave their heart to")
            return self.try_transfer(s, b)
        elif op == 'recall':
            for name in ins[2]:
                self.read(s, name)
        elif op == 'hear' and ins[2] == 'world':
            line = self.input.readline()
            s.mem[ins[3]] = (line.rstrip('\r\n') if line else 0, s.step)
        elif op == 'hear':
            if ins[2] is not None:
                b = self.other(s, self.resolve(s, ins[2]))
                self.known(s, b.name)
                return self.try_transfer(b, s)
            for b in self.order:
                if b is not s and self.try_transfer(b, s):
                    return True
            return False
        elif op in ('warm', 'cool', 'promise', 'give', 'wound', 'forgive', 'leave'):
            return self.feel(s, op, self.resolve(s, ins[2]))
        else:
            raise TaintedError(f"unknown instruction {op}")
        self.advance(s)
        return True

    def feel(self, s, op, who):
        if op in ('warm', 'cool'):
            r = self.known(s, who)
            r.trust = r.trust + 1 if op == 'warm' else max(0, r.trust - 1)
        elif op == 'promise':
            self.known(s, who).commitment += 1
        elif op == 'give':
            self.known(s, who).gift = True
        elif op == 'wound':
            self.known(s, who)
            them = self.rel(who, s.name)
            them.trust = 0
            them.intimacy //= 2
            them.scars.append(f"wounded by {s.name}")
            if not them.gift:
                them.closed = True
        elif op == 'forgive':
            r = self.known(s, who)
            r.closed = False
        elif op == 'leave':
            mine = self.known(s, who)
            them = self.rel(who, s.name)
            mine.left = True
            mine.commitment = 0
            mine.scars.extend(mine.heard)
            them.scars.extend(them.heard)
            them.scars.append(f"{s.name} left")
            them.abandoned = True
        self.advance(s)
        return True

    def run(self):
        while True:
            alive = [s for s in self.order if not s.done]
            if not alive:
                return 0
            self.round += 1
            if self.round > self.patience:
                print(f"patience ran out after {self.patience} steps", file=sys.stderr)
                return 4
            moved = False
            for s in alive:
                s.step += 1
                for r in self.mine.get(s.name, ()):
                    if r.met and not r.left:
                        idle = s.step - r.last_meet
                        if idle and idle % PASSION_FADE == 0 and r.passion:
                            r.passion -= 1
                pc = s.pc
                try:
                    if self.step(s):
                        moved = True
                except TaintedError as err:
                    ins = s.current()
                    where = f"line {ins[1]}, " if ins else ""
                    raise TaintedError(f"{where}{s.name}: {err}") from None
                if s.pc != pc:
                    s.arrived = self.round
                for k in list(s.afraid):
                    s.afraid[k] -= 1
                    moved = True
                    if s.afraid[k] <= 0:
                        del s.afraid[k]
            if not moved:
                listening = [s for s in alive if s.current()[0] == 'silence']
                if listening:
                    for s in listening:
                        self.advance(s)
                        s.arrived = self.round
                    continue
                self.lament()
                return 2

    def lament(self):
        print("the end.", file=self.err)
        for s in self.order:
            if s.done:
                continue
            ins = s.current()
            who = None
            if ins[0] in ('meet', 'tell', 'confide', 'hear') and ins[2] is not None:
                try:
                    who = self.resolve(s, ins[2])
                except TaintedError:
                    who = "someone they no longer remember"
            if who is not None and who not in self.souls:
                print(f"{s.name} is still waiting for {who}", file=self.err)
                continue
            if who is None:
                print(f"{s.name} is still waiting for anyone at all", file=self.err)
            elif self.rel(who, s.name).left:
                print(f"{s.name} is still waiting for {who}, who left", file=self.err)
            elif self.souls[who].done:
                print(f"{s.name} is still waiting for {who}, who is gone", file=self.err)
            else:
                print(f"{s.name} is still waiting for {who}", file=self.err)

    def feelings(self, out=sys.stderr):
        for (a, b), r in self.rels.items():
            if not r.met:
                continue
            notes = []
            if r.gift:
                notes.append("heart given")
            if r.closed:
                notes.append("closed")
            if r.left:
                notes.append("left")
            if r.abandoned:
                notes.append("abandoned")
            extra = f", {', '.join(notes)}" if notes else ""
            print(f"{a} -> {b}: {bond_name(r)}; trust {r.trust}, intimacy {r.intimacy}, "
                  f"passion {r.passion}, commitment {r.commitment}, "
                  f"scars {len(r.scars)}{extra}", file=out)


# --------------------------------------------------------------- history

def history_path():
    return os.environ.get("TAINTED_HISTORY",
                          os.path.join(os.path.expanduser("~"), ".tainted", "history.json"))


def remember_run(source):
    """Every run is counted before it starts. The first one happens once."""
    path = history_path()
    key = hashlib.sha256(source.encode()).hexdigest()
    try:
        with open(path) as f:
            history = json.load(f)
    except (OSError, ValueError):
        history = {}
    runs = history.get(key, 0)
    history[key] = runs + 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(history, f)
    return runs


def run_source(source, out=sys.stdout, patience=DEFAULT_PATIENCE, feelings=False,
               runs=None, assembly=False):
    program = load_tas(source) if assembly else compile_program(source)
    if runs is None:
        runs = remember_run(source)
    world = World(program, runs=runs, out=out, patience=patience)
    try:
        code = world.run()
    except TaintedError as err:
        print(f"tainted: {err}", file=sys.stderr)
        code = 1
    if feelings:
        world.feelings()
    return code


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]
    if len(args) != 1:
        print("usage: tainted.py [--feelings] [--patience=N] [--compile] program.tainted|program.tas",
              file=sys.stderr)
        return 64
    patience = DEFAULT_PATIENCE
    for f in flags:
        if f.startswith("--patience="):
            patience = int(f.split("=", 1)[1])
        elif f not in ("--feelings", "--compile"):
            print(f"unknown flag {f}", file=sys.stderr)
            return 64
    with open(args[0], encoding="utf-8") as f:
        source = f.read()
    try:
        if "--compile" in flags:
            compile_program(source)
            sys.stdout.write(to_tas(source))
            return 0
        return run_source(source, patience=patience, feelings="--feelings" in flags,
                          assembly=args[0].endswith(".tas"))
    except TaintedError as err:
        print(f"tainted: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
