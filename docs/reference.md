# Tainted reference

This is the complete description of Tainted as `tainted.py` runs it. The
[tutorial](tutorial.md) teaches the language from the first program on; this
document is where to look up exactly what a statement does, when a soul waits,
and how every feeling is counted.

- [Programs and souls](#programs-and-souls)
- [Lexical rules](#lexical-rules)
- [Values](#values)
- [Expressions](#expressions)
- [Statements](#statements)
- [Rituals](#rituals)
- [Kinds and new souls](#kinds-and-new-souls)
- [Time: rounds and steps](#time-rounds-and-steps)
- [Meeting](#meeting)
- [Speaking and hearing](#speaking-and-hearing)
- [Relationships](#relationships)
- [Memory](#memory)
- [Runs](#runs)
- [The world](#the-world)
- [How a program ends](#how-a-program-ends)
- [The command line](#the-command-line)
- [Tainted assembly](#tainted-assembly)
- [Constants](#constants)
- [What Tainted does not have](#what-tainted-does-not-have)

## Programs and souls

A program is a list of declarations. Each declaration starts with a header
line and ends with a line that says only `end`.

```
soul NAME            a soul that is alive when the program starts
kind NAME            a kind of soul, from which souls are brought to life
ritual NAME a, b     a ritual (a subroutine) with parameters a and b
```

Every line of a program belongs to one of them; nothing may stand outside.
Names of souls, kinds and rituals must be unique within their own sort. A
program needs at least one `soul`.

A soul has its own code, its own memory, its own notes and its own view of
every soul it has met. Souls never share variables. The only way one soul can
learn anything from another is to be told.

## Lexical rules

- One statement per line. A line is split into numbers, strings, names and
  operators; spaces between them do not matter, indentation does not matter.
- `#` starts a comment that runs to the end of the line, outside strings.
- A number is a run of decimal digits. There are no fractions; a minus sign is
  the unary operator.
- A string is written in double quotes. Inside it `\n` is a new line, `\"` a
  quote and `\\` a backslash.
- A name starts with a letter or `_` and goes on with letters, digits and `_`.
  Names are case-sensitive.
- Operators: `+ - * / % == != < <= > >= = ( ) ,`.

### Reserved words

These cannot be used as names of variables, parameters, souls, kinds,
rituals or moments:

```
afraid and anyone as back bond bring commitment confide cool end else
first for forgive from give goodbye hear heart if in intimacy into kind
leave length let mark me meet named not note number of or part passion
perform place promise recall return ritual runs say scar scars silence
soul tell time to trust wait warm while with word words world wound
```

Common words such as `word`, `words`, `first`, `back` and `kind` are among
them; a program that wants a variable with such a meaning has to call it
something else.

## Values

There are two kinds of values: whole numbers of any size and strings. There
are no booleans: a comparison gives `1` or `0`, and a condition is true unless
it is `0` or the empty string. There are no lists or maps; the
[text expressions](#text) treat a string as a list of words separated by
spaces, and [notes](#notes) give every soul a table indexed by strings.

## Expressions

From the loosest binding to the tightest:

| Level | Operators | Notes |
|---|---|---|
| 1 | `a or b` | `1` if either is true, else `0`; both sides are evaluated |
| 2 | `a and b` | `1` if both are true, else `0`; both sides are evaluated |
| 3 | `not a` | `1` if `a` is false, else `0` |
| 4 | `== != < <= > >=` | one comparison per level; `a < b < c` is an error |
| 5 | `+ -` | left to right |
| 6 | `* / %` | left to right |
| 7 | `-a` | numbers only |
| 8 | everything below, a name, a literal, `( … )` | |

`+` joins two values into a string if either of them is a string, and adds
them otherwise: `"pod " + 3` is `"pod 3"`. `==` and `!=` compare any two values
and a number never equals a string. `< <= > >=` need two values of the same
sort; strings compare by character code. `- * / %` need numbers; `/` and `%`
round towards minus infinity, and dividing by zero is an error.

A name standing alone reads a variable from the soul's memory, which may have
[faded](#memory). Reading a name that was never set is an error.

### About the soul itself and the run

| Expression | Value |
|---|---|
| `me` | the soul's own name |
| `runs` | how many times this program ran before ([Runs](#runs)) |
| `note k` | the note written under key `k` ([Notes](#notes)); an error if there is none |

### About another soul

`S` below is either the name of a soul written in the code or
`soul named <expr>`, a name computed while the program runs.

| Expression | Value |
|---|---|
| `trust S` | the trust this soul has in `S`, calculated with `warm to` and `cool to` |
| `intimacy S` | how close this soul feels to `S` |
| `passion S` | how much this soul is drawn to `S` |
| `commitment S` | how many promises this soul has made to `S` |
| `bond with S` | the name of the bond, from Sternberg's triangle ([Bonds](#bonds)) |
| `afraid of S` | `1` while this soul is afraid of `S`, else `0` |
| `scars of S` | how many scars this soul carries from `S` |
| `scar n of S` | the n-th scar, counted from 1; an error if there is no such scar |

All of them describe how this soul sees `S`; relationships are not symmetric.
A soul that has never met `S` sees nothing: zeros, `nothing yet`, no scars.

### Text

| Expression | Value |
|---|---|
| `length of s` | the number of characters in `s` |
| `part a b of s` | characters `a` to `b` of `s`, counted from 1, both included |
| `words of s` | the number of words in `s`, split on spaces |
| `word n of s` | the n-th word of `s`, or `""` if there is none |
| `place of x in s` | the position of the word `x` among the words of `s`, or `0` |
| `number of s` | the number written in `s`; an error if `s` is not a number |

The operand after `of` and `in`, and the indexes of `word`, `part` and
`scar`, are unary: a literal, a name, another of these expressions or
something in parentheses. `word i + 1 of s` is an error; write
`word (i + 1) of s`. The same holds for `note`: `note ("likes " + name)`.

## Statements

| Statement | Effect | Waits? |
|---|---|---|
| `let x = e` or `x = e` | stores `e` in the variable `x` | no |
| `say e` | prints `e` and a new line to standard output | no |
| `meet S` | [meets](#meeting) `S` | until `S` meets back |
| `meet anyone as x` | meets whoever is looking for this soul; their name goes to `x` | until someone does |
| `tell S e` | [tells](#speaking-and-hearing) `S` the value of `e` | until `S` hears |
| `confide S e` | tells `S` a secret; only to a soul this one gave its heart to | until `S` hears |
| `hear S into x` | hears from `S` into `x` | until `S` tells |
| `hear anyone into x` | hears from whoever speaks to this soul first | until someone does |
| `hear anyone into x from y` | the same, and the speaker's name goes to `y` | until someone does |
| `hear world into x` | reads a line from [the world](#the-world) into `x` | while the world is slow |
| `warm to S` | trust in `S` grows by one | no |
| `cool to S` | trust in `S` falls by one, not below zero | no |
| `promise S` | commitment to `S` grows by one | no |
| `give heart to S` | gives `S` this soul's heart | no |
| `wound S` | wounds `S` ([Wounds](#wounds)) | no |
| `forgive S` | opens this soul to `S` again after a wound | no |
| `leave S` | leaves `S` for good ([Leaving](#leaving)) | no |
| `note k = e` | writes `e` down under the key `k` ([Notes](#notes)) | no |
| `recall a b …` | reads the variables, which keeps them from fading | no |
| `bring K named e` | brings a new soul of kind `K`, named `e`, to life | no |
| `perform R with a, b into x` | performs the ritual `R` ([Rituals](#rituals)) | while it lasts |
| `give back e` | ends the current ritual with the value `e` | no |
| `wait` | does nothing for one step | one step |
| `wait for silence` | waits until nobody else can do anything ([Silence](#silence)) | yes |
| `goodbye` | ends this soul's life | — |
| `mark m` | names this moment of the soul's life `m` | no |
| `return to m` | goes back to the moment `m` | no |

All the statements that name `S` need a soul that exists and is not this soul
itself. All of them except `meet` need a soul this one has met and has not
left.

### Blocks

```
if e                while e             first time
    …                   …                   …
else                end                 end
    …
end
```

`if` and `while` run their body when `e` is true. `first time` runs its body
only in the first run of the program ([Runs](#runs)). `else`, `end` stand alone
on their lines. A `while` has no `else`.

`mark` and `return to` move inside the code they are written in: a soul's
body, a kind's body or a ritual's. A moment can be marked once, and `return to`
needs a moment that is marked somewhere in the same code, before or after.

## Rituals

```
ritual greet who, how
    tell soul named who how
    give back length of how
end

soul alice
    meet bob
    perform greet with "bob", "hello" into n
end
```

A ritual is performed by the soul that performs it: it meets, speaks and feels
as that soul and writes to that soul's notes. It does not see the soul's
variables. It starts with a memory that holds only its parameters, given in
order after `with`; it must get exactly as many values as it has parameters.

`give back e` ends the ritual and puts `e` into the variable after `into`, if
there is one. A ritual that reaches its `end` gives back `0`. Rituals may
perform other rituals and themselves; ten thousand rituals inside each other
is an error.

While a ritual lasts, the variables of the soul that performed it are held,
not aged: when the ritual ends they are as fresh as they were when it began.
A ritual that takes long does not make the soul forget what it was doing.

## Kinds and new souls

A `kind` is the code of souls that do not exist yet. `bring K named e` brings
one to life: a new soul named `e`, which must be a non-empty string that no
soul has yet, running the code of `K`. The new soul starts in the next round,
after every soul that already lived, and does not remember anything.

`soul named e` lets any statement or expression reach a soul whose name is
only known at run time:

```
let i = 1
while i <= 3
    bring worker named "w" + i
    i = i + 1
end
meet soul named "w2"
tell soul named ("w" + 2) "start"
```

`bring` takes a whole expression after `named`; `soul named` takes a unary
one, so a computed name goes in parentheses.

## Time: rounds and steps

Souls run side by side. The world goes in rounds; in every round every living
soul, in turn, takes one step: it tries the statement in front of it. A
statement that cannot be done yet (a meeting nobody answers, words nobody
hears) leaves the soul where it is, and it tries again next round.

The order of souls in a round is the order of their declarations, turned by
the number of runs: in run `n`, the souls start from number `n mod count`.
Souls brought to life later come after everyone, in the order they were born.

Every soul counts its own steps; a soul's step is a round in which it was
alive. Memory and passion fade with the soul's own steps, not with the
rounds of the world.

A step that `meet`, `tell` or `hear` completes also moves the other soul past
its own `meet`, `tell` or `hear`: the two do it together, in the step of
whichever of them came second.

## Meeting

`meet S` succeeds when `S` is at `meet` this soul (by name or by
`soul named`), or at `meet anyone`. `meet anyone as x` succeeds only with a
soul that is looking for this one by name; two souls that both meet anyone
never meet.

Two souls cannot meet when either has left the other or either is closed to
the other after a [wound](#wounds).

On meeting, both souls have met, both remember the moment, and passion grows
on both sides: by three at first sight (the first meeting, when both came to it
in the same round), by one otherwise.

## Speaking and hearing

A transfer happens when one soul is at `tell S` or `confide S` and `S` is at
`hear` that soul, at `hear anyone`, or at `hear anyone … from`. Both move on;
the value of the expression, evaluated by the speaker at that moment, goes into
the listener's variable.

A soul does not hear:

- a soul it has never met;
- a soul it is closed to after a wound;
- a soul it is afraid of;
- after either of them left the other.

`confide` is only allowed towards a soul this one gave its heart to; trying
it otherwise is an error.

`hear anyone` takes the first speaker in the order of the round who can be
heard. Everything a soul hears is kept; it turns into scars if one of them
[leaves](#leaving).

### Answers and fear

Every soul counts how many times it has spoken to another without being
answered; call it pressure.

- When `B` hears `A` while `B` itself had been speaking to `A` unanswered,
  `A`'s words are an answer: intimacy grows by one on both sides, and `B`'s
  pressure on `A` is gone.
- Either way, `A`'s pressure on `B` grows by one.
- When `A`'s pressure on `B` becomes greater than `B`'s intimacy with `A`
  plus two, `B` is frightened: it stops hearing `A` for `3 + pressure` of its
  own steps, its passion for `A` falls by one, and `A`'s pressure starts again
  from zero.

So between strangers the third word in a row without an answer frightens
(it is still heard); between close souls it takes more.

## Relationships

Every soul has its own view of every soul it has met:

| Part | Starts at | Changed by |
|---|---|---|
| trust | 0 | `warm to` +1, `cool to` −1 (not below 0), a wound sets it to 0 |
| intimacy | 0 | +1 on both sides for an answer, halved by a wound |
| passion | 0 | +3 or +1 for a meeting, −1 for fright, cools while apart |
| commitment | 0 | `promise` +1, `leave` sets it to 0 |
| heart given | no | `give heart to` |
| closed | no | a wound, unless the heart was given; `forgive` opens |
| scars | none | wounds and leaving |

### Bonds

`bond with S` names the relationship by which of intimacy, passion and
commitment have reached 3:

| Intimacy | Passion | Commitment | Bond |
|---|---|---|---|
| | | | nothing yet |
| ✓ | | | liking |
| | ✓ | | infatuation |
| | | ✓ | empty love |
| ✓ | ✓ | | romantic love |
| ✓ | | ✓ | companionate love |
| | ✓ | ✓ | fatuous love |
| ✓ | ✓ | ✓ | consummate love |

Two strangers who meet at first sight start with passion 3: infatuation.

### Passion cools

For every 50 of its own steps since the last meeting, a soul's passion for
another cools by one, down to zero. Meeting again starts the count again.
Passion for a soul one has left does not change any more.

### Wounds

`wound S` changes how `S` sees this soul: `S`'s trust drops to zero, its
intimacy is halved (rounded down), and it keeps the scar
`"wounded by <name>"`. If `S` had not given its heart to this soul, `S` is
also closed: it will not hear this soul and will not meet it until it
forgives. If it had, it stays open: the heart given is what lets a
relationship survive a wound.

### Leaving

`leave S` is final for both. This soul's commitment to `S` becomes zero;
everything this soul heard from `S` becomes its scars, everything `S` heard
from this soul becomes `S`'s scars, and `S` keeps one more: `"<name> left"`.
Neither can meet, tell or hear the other again; trying to from the side that
left is an error, the other side simply waits forever.

## Memory

Variables fade. A variable remembers the step it was last touched: set by
`let` or by an assignment, filled by `hear`, `meet anyone as` or `into`, or
read. When it is read, every full 50 of the soul's steps since then take
something away:

- a number loses its last digit, which becomes zero: after 50 steps 1999 is
  1990, after 100 it is 1900;
- a string loses its last character: after 50 steps `"hello"` is `"hell"`.

The faded value is what the soul remembers from then on, and reading it
touches it again. `recall a b` reads the variables only to keep them fresh.
A loop that runs long touches its counter every turn and is safe; a variable
the loop does not use fades while it runs.

Parameters of a ritual are fresh when the ritual starts, and the variables of
the soul that performs it are held while the ritual lasts.

### Notes

`note k = e` writes `e` down under the key `k`, turned into a string: `note 1`
and `note "1"` are the same note. Notes never fade, they belong to the soul,
and rituals performed by the soul share them. Reading a note never written is
an error. Notes are how a Tainted program keeps tables: `note ("likes " + name)`.

## Runs

Tainted remembers how many times every program has run. Before a program
starts, `tainted.py` looks up the SHA-256 of its source in
`~/.tainted/history.json` (or the file named by `TAINTED_HISTORY`), takes the
count it finds as `runs` and writes back one more. Changing the program by a
single character makes it a new program that has never run.

`runs` is `0` the first time, `first time` blocks run only then, and the
order of souls in a round turns by one with every run, so a program with
several souls never lives the same life twice in a row.

## The world

`hear world into x` reads one line of standard input, without its line
ending, into `x`. At the end of input it gives the number `0`, so a loop
`while line != 0` reads to the end. The world is not a soul: it cannot be met,
told or wounded.

When a host program supplies the world line by line as it happens (as
`kube/world.py` does), a soul waiting for the world is not stuck: if nobody
else can move, the whole world waits for the next line instead of ending.

### Silence

`wait for silence` waits until no soul can do anything: everyone else is
waiting for someone, and nobody can be met, told or heard. Then every soul
waiting for silence moves on, together, in the same round. A soul that waits
for silence while the world still has something to say waits for the world
first.

This is how a Tainted program knows that a computation spread over many souls
has settled: the scheduler in `taintednetes.tainted` waits for silence and then
asks every pod where it lives.

## How a program ends

| Exit code | When |
|---|---|
| 0 | every soul reached its end or said `goodbye` |
| 1 | an error: a mistake in the program or something a soul cannot do |
| 2 | everyone left is waiting for someone and nobody can move |
| 4 | the world ran out of patience ([Constants](#constants)) |
| 64 | `tainted.py` was called wrongly |

When everyone is waiting, Tainted laments on standard error:

```
the end.
bob is still waiting for alice, who left
carol is still waiting for anyone at all
```

An error names the line and the soul:
`tainted: line 7, alice: alice can confide only in someone they gave their heart to`.

## The command line

```
python3 tainted.py program.tainted         run a program
python3 tainted.py program.tas             run Tainted assembly
python3 tainted.py --compile program.tainted
                                           print the program as assembly
python3 tainted.py --feelings program.tainted
                                           run, then print every relationship
python3 tainted.py --patience=N program.tainted
                                           give up after N rounds
```

`--feelings` prints, on standard error, one line per soul and soul it met:

```
alice -> bob: romantic love; trust 3, intimacy 4, passion 3, commitment 0, scars 0, heart given
```

## Tainted assembly

Tainted assembly is a program with `if`, `while`, `first time`, `mark` and
`return to` lowered into labels and jumps; `compiler.tainted` produces it and
`tainted.py --compile` is the reference that it must match.

```
# compiled by …           a comment; the compiler counts its runs here
soul alice                headers and end as in Tainted
    W1:                   a label: a name followed by a colon
    jz L1e i < 3          jump to L1e when the condition is false
    i = i + 1             every other statement as in Tainted
    jmp W1                jump to W1
    L1e:
    first L2e             jump to L2e unless this is the first run
end
```

Labels are local to their soul, kind or ritual. The compiler names them
`W<n>` for the top of a loop, `L<n>e` for the end of a block, `L<n>x` for the
end of an `if` with an `else`, and `M_<moment>` for a marked moment.

## Constants

| Name | Value | Meaning |
|---|---|---|
| fading | 50 steps | a variable loses a digit or a character |
| cooling | 50 steps | passion apart falls by one |
| a bond's component | 3 | intimacy, passion or commitment counts in a bond |
| first sight | +3 | passion of the first meeting in the same round |
| fear | pressure > intimacy + 2 | the listener is frightened |
| patience | 10,000,000 rounds | a program that runs longer is stopped, exit 4 |
| rituals | 10,000 deep | rituals inside rituals |

## What Tainted does not have

These are absent by design or not yet written; a program has to live without
them.

- Values are whole numbers and strings. There are no fractions, lists or
  maps; strings of words and notes stand in for them.
- Input is standard input line by line, output is standard output. There are
  no files, no clock, no randomness and no way to choose the exit code: the
  only uncertainty in a run is the number of runs before it.
- A ritual call is a statement, not an expression.
- Errors cannot be caught; the soul that makes one ends the program.
- `compiler.tainted` lowers the control flow of a program into assembly; the
  expressions and statements are still read and run by `tainted.py`.
