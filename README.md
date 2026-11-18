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

A program is a list of souls, each written as `soul <name>` … `end`, and of
kinds of souls, written as `kind <name>` … `end`, from which new souls are
born while the program runs. Each round, every soul that is still alive takes one step, in the order the souls are
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
| `note key = expr` | write something down; notes never fade |
| `bring k named expr` | bring a new soul of kind `k` into the world |
| `wait for silence` | wait until nobody else has anything left to do |
| `hear world into x` | read a line from standard input; at the end of input `x` becomes `0` |
| `goodbye` | end this soul |

### Words between two souls

| Statement | Meaning |
|---|---|
| `meet b` | rendezvous: both souls must be waiting for each other; there is no timeout |
| `meet anyone as x` | meet whoever comes looking for you, and learn their name |
| `tell b expr` | hand a value over; completes only when `b` is listening |
| `hear b into x`, `hear anyone into x [from who]` | listen; `from` learns who spoke |
| `confide b expr` | tell a secret; allowed only to someone you gave your heart to |
| `warm to b`, `cool to b` | trust `b` one step more or less |
| `promise b` | commitment grows |
| `give heart to b` | irreversible; `b` may now be confided in, and a wound from `b` no longer closes you |
| `wound b` | `b` loses all calculated trust in you, half the intimacy, and gains a scar |
| `forgive b` | open the door that a wound from `b` closed; the scar stays |
| `leave b` | irreversible; everything each of you heard becomes scars |

Wherever a soul is named, `soul named expr` names it by a computed word:
`tell soul named who "yes"`.

### Expressions

Numbers, strings, `+ - * / %`, comparisons, `and`, `or`, `not`, and what a soul
knows about its relationships: `trust b`, `intimacy b`, `passion b`,
`commitment b`, `afraid of b`, `bond with b`, `scars of b`, `scar n of b`, and
`runs`, the number of earlier runs of this program. Words have `length of x`
and `part i j of x`, the letters from `i` to `j`, counting from 1. A line is
also a list of words: `words of x`, `word i of x`, `place of w in x` (0 when
`w` is not there) and `number of x`. A soul knows its own name as `me` and
reads its notes with `note key`.

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

`taintednetes.tainted` is a scheduler written in Tainted. It hears the cluster
from standard input, one line per pod or node:

```
pod web alpha beta gamma        the nodes web would live on, best first
node alpha 2 db cache web       how many pods alpha can take, and whom it prefers
```

and brings every pod and every node to life as a soul. A pod proposes to the
nodes it likes, in order. A node keeps the best pods that have asked so far,
says no to the rest and, when someone better comes while it is full, tells the
least wanted pod to go and wounds it in parting. A pod gives its heart to the
node that takes it, so the wound leaves a scar but does not close the pod to
the next node.

Nobody compares the cluster with a desired state. When every soul is waiting
and nobody has anything left to say, the cluster hears the silence, asks every
pod where it lives and lets everyone rest. That silence is a stable matching:
no pod and node would both rather be with each other than where they are. The
tests run random clusters with random capacities and compare the result with
the Gale–Shapley algorithm.

Waiting is what a soul does most in a scheduler, and a soul that waits forgets,
so everything that has to outlive a wait is written down in notes.

```
python3 tainted.py taintednetes.tainted < examples/cluster.txt
```

### On a real cluster

`kube/bridge.py` makes `taintednetes.tainted` the scheduler of a real
Kubernetes cluster. It reads pending pods with `schedulerName: taintednetes`
and the ready nodes through `kubectl`, describes them to the Tainted program
and binds every pod where the program says it lives. The bridge decides only
who may meet whom: a pod likes the nodes it fits on (free CPU and memory, node
selector, taints it tolerates), a node offers as many seats as it can hold of
the largest pod that wants it.

| Annotation | On | Meaning |
|---|---|---|
| `taintednetes.io/likes: "node-a node-b"` | pod | nodes it wants first |
| `taintednetes.io/likes: "ns/pod ns/pod"` | node | pods it wants first |
| `taintednetes.io/seats: "N"` | node | at most N pods of this scheduler |

Without annotations, pods prefer nodes with more free cores, and where the
nodes are equal every pod has its own lasting taste, so identical pods spread
out; nodes prefer pods with higher priority, then the ones waiting longest.

```
kubectl --context <ctx> create namespace demo
kubectl --context <ctx> -n demo apply -f kube/demo.yaml
python3 kube/bridge.py --context <ctx> --once     # or leave it running
```

On a kind cluster with three workers limited to two seats each, seven pods
compete for six places:

```
scarcity/db settles on taintednetes-worker
scarcity/web settles on taintednetes-worker
scarcity/crowd-6d4fb9dc84-gkc7j is sent away from taintednetes-worker
scarcity/crowd-6d4fb9dc84-gkc7j settles on taintednetes-worker3
scarcity/crowd-6d4fb9dc84-qm6qc is sent away from taintednetes-worker3
scarcity/crowd-6d4fb9dc84-qm6qc has nowhere to live
...
the cluster is at rest
```

The six who found a home are running; the seventh stays pending until a seat
opens.

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

### Classic programs

The usual programs, the way souls would write them, in `examples/classics/`.

| File | What it shows |
|---|---|
| `hello-world.tainted` | one soul, alone |
| `fizzbuzz.tainted`, `factorial.tainted`, `fibonacci.tainted`, `primes.tainted` | ordinary arithmetic and loops |
| `bottles.tainted` | 99 bottles of beer |
| `cat.tainted`, `reverse.tainted`, `wc.tainted` | reading the world line by line |
| `sort.tainted` | insertion sort over notes, because a list in memory would fade |
| `gcd.tainted` | Euclid as a conversation between two souls |
| `ping-pong.tainted` | answered messages grow into romantic love |
| `producer-consumer.tainted` | a producer that never waits for an answer frightens its consumer |
| `sleep-sort.tainted` | every number becomes a soul that waits as long as it is large |
| `philosophers.tainted` | dining philosophers: forks are souls, and the host listens for silence |

## License

Apache License 2.0, see [LICENSE](LICENSE).
