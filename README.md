# Tainted

Tainted is an esoteric programming language in which computation happens
between souls rather than inside them. A program is a set of souls running side
by side. They reach each other only by meeting, they trust and fear, give their
hearts away, wound and forgive, and what they say to each other stays with them.

The language is Turing complete, and the proof is not built on memory, which
fades, but on trust: a counter machine runs on how much one soul trusts another.

```
soul alice
    meet bob
    give heart to bob
    confide bob "the thing I never told anyone"
    hear bob into answer
    say "alice heard: " + answer
end

soul bob
    meet alice
    hear alice into secret
    wound alice
    tell alice "I know"
end
```

## Running

```
python3 tainted.py examples/hello.tainted
python3 tainted.py --feelings examples/courtship.tainted   # print every relationship at the end
python3 -m unittest discover -s tests
```

Python 3.9 or newer, no dependencies.

Every run is recorded in `~/.tainted/history.json` (or the file named by
`TAINTED_HISTORY`) before it starts, so the same program never runs for the
first time twice.

## The language

A program is a list of souls, each written as `soul <name>` … `end`. Each
round, every soul that is still alive takes one step, in the order the souls are
written; the starting soul shifts with every past run of the program.

### Words a soul can say to itself

| Statement | Meaning |
|---|---|
| `let x = expr`, `x = expr` | remember a value |
| `say expr` | speak to the world (standard output) |
| `if expr` … `else` … `end` | |
| `while expr` … `end` | |
| `mark name`, `return to name` | name a moment and return to it later |
| `first time` … `end` | runs only on the very first run of the program |
| `wait` | let a step pass |
| `recall x y …` | think of these memories again so they do not fade further |
| `hear world into x` | read a line from standard input; at the end of input `x` becomes `0` |
| `goodbye` | end this soul |

### Words between two souls

| Statement | Meaning |
|---|---|
| `meet b` | rendezvous: both souls must be waiting for each other; there is no timeout |
| `tell b expr` | hand a value over; completes only when `b` is listening |
| `hear b into x`, `hear anyone into x` | listen |
| `confide b expr` | tell a secret; allowed only to someone you gave your heart to |
| `warm to b`, `cool to b` | trust `b` one step more or less |
| `promise b` | commitment grows |
| `give heart to b` | irreversible; `b` may now be confided in, and a wound from `b` no longer closes you |
| `wound b` | `b` loses all calculated trust in you, half the intimacy, and gains a scar |
| `forgive b` | open the door that a wound from `b` closed; the scar stays |
| `leave b` | irreversible; everything each of you heard becomes scars |

### Expressions

Numbers, strings, `+ - * / %`, comparisons, `and`, `or`, `not`, and what a soul
knows about its relationships: `trust b`, `intimacy b`, `passion b`,
`commitment b`, `afraid of b`, `bond with b`, `scars of b`, `scar n of b`, and
`runs`, the number of earlier runs of this program. Words have `length of x`
and `part i j of x`, the letters from `i` to `j`, counting from 1.

## How feelings work

**Meeting.** Nothing can be said to a soul you have never met. On the first
meeting passion becomes 3 if both souls arrived in the same round (first sight)
and 1 otherwise. Each later meeting adds 1; passion cools by 1 for every 50
steps without a meeting.

**Answered words.** Intimacy grows on both sides only when a message is
answered. Unanswered messages build pressure. When the pressure exceeds the
listener's intimacy by more than two, the listener becomes afraid: for several
steps nothing from the speaker reaches them, and their passion drops.

**Two kinds of trust.** Calculated trust (`warm to`, `cool to`) is earned and
counted, and a single wound resets it to zero and shuts the door until the
wounded soul forgives. The gift (`give heart to`) cannot be earned or taken
back: it hands over the heart together with the knife. A soul that has given
its heart can still be wounded and scarred, but it stays open, and only the gift
allows secrets to be confided.

**What we are.** `bond with b` names the relationship by Sternberg's triangle:
intimacy, passion and commitment, each counting once it reaches 3. The result is
one of *nothing yet*, *liking*, *infatuation*, *empty love*, *romantic love*,
*companionate love*, *fatuous love* and *consummate love*, and it changes as
the relationship changes.

**Fading memory.** A value that nobody looks at loses one digit, or one
character from the end, for every 50 steps of neglect. Looking at it again saves
the faded version. Waiting counts as time, so memories fade while a soul waits.

**Scars.** Scars never fade and can only be read. When a soul leaves, the other
one keeps waiting, and the program ends with a list of those still waiting.

**Exit codes.** 0 when every soul finished, 1 on an error, 2 when the remaining
souls wait for each other forever, 4 when patience (`--patience=N` rounds) runs
out.

## Turing completeness

`tools/minsky.py` compiles any Minsky counter machine into Tainted. Each counter
becomes a soul, its value is the machine's trust in it, `warm to` increments,
`cool to` decrements and `trust c == 0` tests for zero. Minsky showed that two
counters are enough to simulate any Turing machine. The test suite compiles
random two-counter machines and checks every result against a reference
simulator.

```
python3 tools/minsky.py examples/multiply.minsky > examples/multiply.tainted
python3 tainted.py examples/multiply.tainted     # c = 42
```

## The compiler written in Tainted

`compiler.tainted` hears a Tainted program from standard input and lowers
`if`, `while`, `first time`, `mark` and `return` into Tainted assembly, a flat
list of statements, labels and jumps that `tainted.py` runs directly when the
file ends in `.tas`. `tainted.py --compile` is the reference compiler in Python.

```
python3 tainted.py --compile compiler.tainted > c1.tas    # stage 0, Python
python3 tainted.py c1.tas < compiler.tainted > c2.tas     # the compiler compiles itself
python3 tainted.py c2.tas < compiler.tainted > c3.tas     # and once more
```

The code reaches a fixed point at the second generation. The first line of the
output never does: in it the compiler says how many times it has run before,
so running the same compiler on the same program never gives the same file
twice.

The compiler's memory fades like anyone's. Reading a long line takes more than
fifty steps, and a compiler that does not keep recalling its stack of open
blocks and its block counter loses digits from them and emits wrong labels.
The test suite checks this too: remove the `recall` lines and the bootstrap
breaks.

## Taintednetes

`tools/taintednetes.py` turns a cluster into a Tainted program in which every
pod and every node is a soul. A pod proposes to the nodes it likes, best first.
A node keeps the best pod that has asked so far, says no to the others and,
when someone better comes, tells its current pod to go and wounds it in
parting. A pod gives its heart to the node that takes it, so the wound leaves a
scar but does not close the pod to the next node.

Nobody compares the cluster with a desired state. The cluster settles when
every soul is waiting for someone and nobody has anything left to say, and
that silence is a stable matching: no pod and node would both rather be with
each other than where they are. The tests run random clusters and compare the
result with the Gale–Shapley algorithm.

```
python3 tools/taintednetes.py examples/cluster.taintednetes
python3 tools/taintednetes.py --emit examples/cluster.taintednetes   # print the program
```

```
web settles on alpha
cache settles on beta
db settles on alpha
web is sent away from alpha
web settles on beta
cache is sent away from beta
cache settles on gamma

web lives on beta; sent away 1 time(s)
db lives on alpha; sent away 0 time(s)
cache lives on gamma; sent away 1 time(s)
```

## Examples

| File | What happens |
|---|---|
| `hello.tainted` | a first meeting |
| `courtship.tainted` | answered words and promises grow into consummate love |
| `rush.tainted` | three unanswered messages frighten bob |
| `heart-and-knife.tainted` | trust as a gift survives a wound |
| `calculation.tainted` | trust as a calculation does not |
| `breakup.tainted` | leaving, scars, and the one who keeps waiting |
| `first-time.tainted` | run it twice |
| `penelope.tainted` | memory fades while she waits |
| `multiply.tainted` | 6 × 7 computed on trust alone |

## License

Apache License 2.0, see [LICENSE](LICENSE).
