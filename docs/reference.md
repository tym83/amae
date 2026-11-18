# Tainted reference

This is the complete description of Tainted as its compiler builds it. The
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
- [Before souls meet](#before-souls-meet)
- [Ways of loving](#ways-of-loving)
- [Consent](#consent)
- [Boundaries](#boundaries)
- [Letters and grief](#letters-and-grief)
- [Enduring](#enduring)
- [Learning](#learning)
- [How a program ends](#how-a-program-ends)
- [The command line](#the-command-line)
- [The compiler](#the-compiler)
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
- A number is a run of decimal digits; with a point and more digits,
  `3.25`, it is a decimal. A minus sign is the unary operator.
- A string is written in double quotes. Inside it `\n` is a new line, `\"` a
  quote and `\\` a backslash, read once from left to right; a backslash before
  anything else stays a backslash.
- A number written in the program must fit in 64 bits.
- A name starts with a letter or `_` and goes on with letters, digits and `_`.
  Names are case-sensitive.
- Operators: `+ - * / % == != < <= > >= = ( ) , [ ] { } :`.

### Reserved words

These cannot be used as names of variables, parameters, souls, kinds,
rituals or moments:

```
afraid and anyone as back bond bring commitment confide cool end else
first for forgive from give goodbye hear heart if in intimacy into kind
knowingly leave length let mark me meet named not note number of or part passion
perform place promise recall return ritual runs say scar scars silence
soul tell time to trust wait warm while with word words world wound cry
ask telling listen read write append file seconds endure when hurts learn
keys json meaning whole fate now put remove lines send receive letters thank
hope hoping resentment toward apologize tenderly take distance jealous ashamed
before longing admit consent withdraw together apart guard crossings
is anxious avoidant secure eros ludus storge pragma mania agape knowingly deterministic chemistry attachment phase
```

Common words such as `word`, `words`, `first`, `back` and `kind` are among
them; a program that wants a variable with such a meaning has to call it
something else.

## Values

| Value | Written | Notes |
|---|---|---|
| a whole number | `42`, `-7` | 64 bits, from −2⁶³ to 2⁶³ − 1; a result that does not fit is an error |
| a decimal | `3.25`, `1 / 4.0` | a 64-bit floating-point number |
| a string | `"hello"` | UTF-8; lengths and parts count characters |
| a list | `[1, "two", [3]]` | items counted from 1 |
| a map | `{"name": "ana", "age": 30}` | keys are words, kept in the order they were first written |

There are no booleans: a comparison gives `1` or `0`, and a condition is false
when it is `0`, `0.0`, the empty string, an empty list or an empty map. A key
of a map, like the key of a [note](#notes), is turned into a word: `m[1]` and
`m["1"]` are the same.

What a soul keeps is its own. Storing a value in a variable or a note, telling
it, giving it to a ritual or keeping it as a scar makes a copy all the way
down, so a list can only be changed through the variable that holds it.

## Expressions

From the loosest binding to the tightest:

| Level | Operators | Notes |
|---|---|---|
| 1 | `a or b` | `1` if either is true, else `0`; `b` is looked at only if `a` is false |
| 2 | `a and b` | `1` if both are true, else `0`; `b` is looked at only if `a` is true |
| 3 | `not a` | `1` if `a` is false, else `0` |
| 4 | `== != < <= > >=` | one comparison per level; `a < b < c` is an error |
| 5 | `+ -` | left to right |
| 6 | `* / %` | left to right |
| 7 | `-a` | numbers only |
| 8 | everything below, a name, a literal, `( … )` | |

`+` joins two values into a string if either of them is a string, joins two
lists into one, and adds numbers otherwise: `"pod " + 3` is `"pod 3"`,
`[1] + [2]` is `[1, 2]`. A whole number and a decimal together make a decimal;
`/` between two whole numbers still rounds down, `/` with a decimal divides
exactly. `==` and `!=` compare any two values
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
| `distance from S` | how far apart they have grown ([Distance](#distance-and-attention)) |
| `longing for S` | `1` while they are far apart (distance 2 or more) and passion is left |
| `resentment toward S` | `1` while this soul resents a wound `S` gave it |
| `ashamed before S` | `1` after wounding `S`, who had given this soul its heart, until it apologizes |
| `jealous of S` | `1` once `S`, who has this soul's heart, confided in someone else |
| `hoping for S` | `1` while this soul hopes for `S` |
| `letters from S` | how many letters from `S` have arrived and are not yet read |
| `consent from S` | `1` while `S` consents to this soul |
| `crossings with S` | how many times a boundary between them was crossed |
| `chemistry with S` | what their first meeting brought that nobody could work out: −1, 0 or 1 ([Chemistry](#chemistry)) |
| `attachment to S` | how much long closeness has bound this soul to `S` ([Attachment](#attachment)) |
| `phase with S` | `"strangers"`, `"acquaintance"`, `"lust"`, `"attraction"` or `"attachment"` ([Attachment](#attachment)) |
| `note k of S` | the note `k` of another soul, if it lets this one in ([Boundaries](#boundaries)) |

All of them describe how this soul sees `S`; relationships are not symmetric.
A soul that has never met `S` sees nothing: zeros, `nothing yet`, no scars.

### Text

| Expression | Value |
|---|---|
| `length of s` | the number of characters in `s`, or of items in a list or a map |
| `part a b of s` | characters `a` to `b` of `s`, counted from 1, both included |
| `words of s` | the number of words in `s`, split on spaces |
| `word n of s` | the n-th word of `s`, or `""` if there is none |
| `place of x in s` | the position of the word `x` among the words of `s`, of an item equal to `x` in a list, or of the key `x` in a map; `0` if there is none |
| `number of s` | the number written in `s`, whole or decimal; an error if `s` is not a number |
| `lines of s` | the lines of `s`, as a list, without their endings |

### Lists, maps and JSON

| Expression | Value |
|---|---|
| `[a, b, …]` | a list |
| `{k: v, …}` | a map |
| `x[i]` | the i-th item of a list, the value under the key `i` of a map, or the i-th character of a string; an error if there is none |
| `keys of m` | the keys of a map, as a list |
| `json of v` | `v` written as JSON |
| `meaning of s` | the JSON in `s` read back: objects become maps, arrays lists; `true` is `1`, `false` `0` and `null` the empty string |
| `whole of x` | the whole part of a number, rounded down |

### Environment and time

| Expression | Value |
|---|---|
| `world e` | the environment variable named `e`, or `""` |
| `now` | the time, in seconds since 1970, as a decimal |
| `fate n` | a whole number from 0 to `n − 1`, as chance decides; `TAINTED_FATE` fixes the chance for a run |

The operand after `of` and `in`, and the indexes of `word`, `part` and
`scar`, are unary: a literal, a name, another of these expressions or
something in parentheses. `word i + 1 of s` is an error; write
`word (i + 1) of s`. The same holds for `note`: `note ("likes " + name)`.

## Statements

| Statement | Effect | Waits? |
|---|---|---|
| `let x = e` or `x = e` | stores `e` in the variable `x` | no |
| `say e` | prints `e` and a new line to standard output | no |
| `cry e` | prints `e` and a new line to standard error | no |
| `meet S` | [meets](#meeting) `S` | until `S` meets back |
| `meet anyone as x` | meets whoever is looking for this soul; their name goes to `x` | until someone does |
| `tell S e` | [tells](#speaking-and-hearing) `S` the value of `e` | until `S` hears |
| `tell S e tenderly` | the same, gently: it puts no pressure on `S` and brings `S` closer | until `S` hears |
| `knowingly confide S e` | tells `S` a secret; only to a soul this one gave its heart to | until `S` hears |
| `hear S into x` | hears from `S` into `x` | until `S` tells |
| `hear anyone into x` | hears from whoever speaks to this soul first | until someone does |
| `hear anyone into x from y` | the same, and the speaker's name goes to `y` | until someone does |
| `hear world into x` | reads a line from [the world](#the-world) into `x` | while the world is slow |
| `warm to S` | trust in `S` grows by one | no |
| `cool to S` | trust in `S` falls by one, not below zero | no |
| `promise S` | commitment to `S` grows by one | no |
| `give heart to S` | gives `S` this soul's heart, and takes it from whoever had it ([Fidelity](#fidelity)) | no |
| `knowingly wound S` | wounds `S` ([Wounds](#wounds)) | no |
| `forgive S` | opens this soul to `S` again after a wound | no |
| `apologize to S for scar n` | apologizes for the wound that is `S`'s scar `n` ([Apologies](#apologies)) | no |
| `admit resentment toward S` | names this soul's resentment, which lets it go | no |
| `thank S` | gratitude: commitment to `S` grows, and `S` feels closer | no |
| `hope for S` | this soul hopes: its passion for `S` no longer cools | no |
| `take back heart from S` | takes back the heart given to `S` | no |
| `consent to S` | consents to doing things together with `S` | no |
| `withdraw consent from S` | withdraws it, even in the middle of something done together | no |
| `together with S` … `apart` … `end` | does something together with `S` ([Consent](#consent)) | until both consent and come |
| `guard k` | puts the note `k` behind this soul's boundary | no |
| `send S e` | sends `S` a letter, which arrives in its own time ([Letters](#letters-and-grief)) | no |
| `receive from S into x` | reads a letter from `S` | until one has arrived |
| `receive anyone into x from y` | reads the first letter that has arrived, and who wrote it | until one has arrived |
| `knowingly leave S` | leaves `S` for good ([Leaving](#leaving)) | no |
| `note k = e` | writes `e` down under the key `k` ([Notes](#notes)) | no |
| `recall a b …` | reads the variables, which keeps them from fading | no |
| `bring K named e` | brings a new soul of kind `K`, named `e`, to life | no |
| `perform R with a, b into x` | performs the ritual `R` ([Rituals](#rituals)) | while it lasts |
| `give back e` | ends the current ritual with the value `e` | no |
| `wait` | does nothing for one step | one step |
| `wait for silence` | waits until nobody else can do anything ([Silence](#silence)) | yes |
| `x[i] = e` | changes an item of a list or a map, however deep: `grid[2][1] = 9` | no |
| `put e into x` | adds `e` to the end of the list in `x` (or `x[i]…`) | no |
| `remove k from x` | takes item `k` out of a list, or key `k` out of a map | no |
| `ask world c into x` | runs the command `c` and waits for what it prints ([The world](#the-world)) | until it ends |
| `ask world c telling t into x` | the same, with `t` as the command's input | until it ends |
| `listen to world c` | starts the command `c`; every line it prints comes to `hear world` | no |
| `read file f into x` | the whole file `f` | no |
| `write e to file f` | writes `e` into the file `f`, replacing what was there | no |
| `append e to file f` | adds `e` to the end of the file `f` | no |
| `wait e seconds` | sleeps for `e` seconds while the others live | while it sleeps |
| `endure` … `when it hurts as p` … `end` | lives through mistakes ([Enduring](#enduring)) | no |
| `goodbye` | ends this soul's life | — |
| `goodbye with e` | ends this soul's life; the program ends with the exit code `e` ([How a program ends](#how-a-program-ends)) | — |
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
| passion | 0 | +3 at first sight, +1 for a later meeting while it is below 6, −1 for fright, cools while apart |
| attachment | 0 | +1 for every 150 steps spent close, without resentment |
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

### Attachment

Passion needs meetings and cools without them; a later meeting feeds it only
until it reaches 6, because being in love does not grow without end. What
grows with time is attachment: every 150 steps two souls spend close, in
touch at least every 50 steps and with no resentment between them, bind them
by one more. Attachment is what holds when passion has cooled:

- a soul attached by `a` is frightened only by more than `intimacy + 2 + a`
  unanswered words;
- intimacy, which fades without attention, does not fade below attachment;
- a wound does not close a soul attached by 3 or more, as if it had given its
  heart.

`phase with S` follows Helen Fisher's three stages: `lust` while passion is
there alone, `attraction` when intimacy has come too, and `attachment` once
attachment has reached 3. A long love moves through Sternberg's names the same
way: infatuation at first sight, romantic love as intimacy grows, consummate
love with commitment, and, when passion has cooled and intimacy, commitment
and attachment remain, companionate love: calm, and strong.

### Chemistry

Two souls that did everything right may still not fall in love. At their first
meeting a pair gets a chemistry of −1, 0 or 1, added to the passion of both;
it comes from who they are and from the lives the program has already lived,
so nobody can declare it or work it out from the code. A program's first life
has none: the first time, nothing stands in the way.

Infrastructure wants the same life every run. A program that starts with the
line `deterministic`, or runs with `--deterministic` or `TAINTED_DETERMINISTIC`
set, has no chemistry; Taintednetes and the operators are such programs.

### Passion cools

For every 50 of its own steps since the last meeting, a soul's passion for
another cools by one, down to zero. Meeting again starts the count again.
Passion for a soul one has left does not change any more.

### Distance and attention

Two souls drift apart while nothing passes between them. For every 50 of its
own steps without a word, a letter or a meeting, a soul's distance from the
other grows by one; words from far away take that many rounds on their way
before they can be heard, and a letter arrives that many rounds after it was
sent. Words in flight are time passing, not a deadlock. Each meeting halves the
distance, so closeness comes back gradually.

Intimacy needs attention: it falls by one for every 100 steps without contact,
or every 50 while there is resentment. Trust does not fade; it is what the
language computes with.

### Feelings

Feelings happen in a relationship and change it.

| Feeling | Comes | Does | Goes |
|---|---|---|---|
| resentment | with a wound | answers no longer bring the two closer, and intimacy fades twice as fast | when it is admitted, or the wound apologized for |
| shame | after wounding someone who gave this soul their heart | `ashamed before` | with an apology |
| jealousy | when the one who has this soul's heart confides in another | passion grows by one, intimacy falls by one | stays |
| longing | while far apart with passion left | `longing for` | when they are close again |
| gratitude | `thank S` | commitment grows, and `S` feels closer | stays |
| hope | `hope for S` | passion for `S` no longer cools; a lament says that it still hopes | stays |
| tenderness | `tell S e tenderly` | the word puts no pressure on `S` and brings `S` closer | — |

### Apologies

An apology names the wound it is for: `apologize to S for scar n`, where `n`
is the number of the scar `"wounded by <this soul>"` among `S`'s scars from this
soul. An apology without `for` does not compile, and one for a scar that is not
a wound this soul gave is an error. `S`'s resentment goes, this soul's shame
goes, `S`'s trust grows by one, and `S` keeps one more scar:
`"<this soul> apologized for: wounded by <this soul>"`. The wound stays.

### Wounds

`knowingly wound S` changes how `S` sees this soul: `S`'s trust drops to zero, its
intimacy is halved (rounded down), it keeps the scar
`"wounded by <name>"` and it resents the wound. If `S` had not given its heart to this soul, `S` is
also closed: it will not hear this soul and will not meet it until it
forgives. If it had, it stays open: the heart given is what lets a
relationship survive a wound.

### Leaving

`knowingly leave S` is final for both. This soul's commitment to `S` becomes zero;
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
- a string loses its last character: after 50 steps `"hello"` is `"hell"`;
- a decimal loses its last digit after the point first, then its whole digits;
- a list loses its last item, a map its last key.

The faded value is what the soul remembers from then on, and reading it
touches it again. `recall a b` reads the variables only to keep them fresh.
A loop that runs long touches its counter every turn and is safe; a variable
the loop does not use fades while it runs.

Parameters of a ritual are fresh when the ritual starts, and the variables of
the soul that performs it are held while the ritual lasts.

### Remembering rewrites

A memory cannot be read without being rewritten. When a soul reads a variable
that has faded, what was lost is filled in from the end of what the soul heard
last, if that was the same kind of thing: a number's lost digits from the last
digits of the number it heard, a string's lost letters from the end of the
string it heard. A soul that remembered the year 1999 and last heard 47 recalls
1997; one that heard nothing, or heard words, recalls 1990.

### Notes

`note k = e` writes `e` down under the key `k`, turned into a string: `note 1`
and `note "1"` are the same note. Notes never fade, they belong to the soul,
and rituals performed by the soul share them. Reading a note never written is
an error. Notes are how a Tainted program keeps tables: `note ("likes " + name)`.

## Runs

Tainted remembers how many times every program has run. Before a program
starts, it looks up the SHA-256 of the source it was compiled from in
`~/.tainted/history.json` (or the file named by `TAINTED_HISTORY`), takes the
count it finds as `runs` and writes back one more. Changing the program by a
single character makes it a new program that has never run.

`runs` is `0` the first time, `first time` blocks run only then, and the
order of souls in a round turns by one with every run, so a program with
several souls never lives the same life twice in a row.

## The world

`hear world into x` reads one line, without its line ending, from what the
world says: standard input, and every command the program listens to. At the
end of all of them it gives the number `0`, so a loop `while line != 0` reads
to the end. The world is not a soul: it cannot be met, told or wounded.

`listen to world c` starts the command `c` with `/bin/sh`; each line it prints
is one more thing the world says. A soul waiting for the world is not stuck:
if nobody else can move, the whole world waits for the next line instead of
ending. So does a soul that sleeps with `wait n seconds`.

`ask world c into x` runs `c` with `/bin/sh` and waits for it to end; `x`
gets everything it printed, without the last line ending. With `telling t`,
the command reads `t` as its input. A command that ends with an exit code
other than 0 is an error, which the soul can [endure](#enduring); the error
says what the command printed on standard error.

`read file`, `write … to file` and `append … to file` read and write whole
files; paths are relative to where the program runs.

### Silence

`wait for silence` waits until no soul can do anything: everyone else is
waiting for someone, and nobody can be met, told or heard. Then every soul
waiting for silence moves on, together, in the same round. A soul that waits
for silence while the world still has something to say waits for the world
first.

This is how a Tainted program knows that a computation spread over many souls
has settled: the scheduler in `taintednetes.tainted` waits for silence and then
asks every pod where it lives.

## Before souls meet

The compiler looks at what souls will do to each other before they ever
meet, and refuses three things.

### What cannot be undone

A confession, a wound and a leaving cannot be undone, so they are only done
knowingly: `knowingly confide S e`, `knowingly wound S`, `knowingly leave S`.
Without the word the program does not compile. Forgiving is possible after
them; the scar stays.

### Dialogues

When two souls name each other in their code, the compiler reads what each
of them does with the other, in order: meetings, words said and heard, things
done together. The two must fit: a meeting answers a meeting, words told
answer words heard, `together` answers `together`. Two souls that both wait to
hear, or both speak first, or one of whom says something the other never
listens to, cannot get along, and the program does not compile:

```
tainted: line 3: a and b cannot get along: here a tells b, but at line 7 b tells a
```

Only what is certain is compared: a soul whose partners the code cannot tell
(one that performs rituals, meets or hears strangers, or marks moments) is
not, and neither is anything inside `if`, `while` or another block. After a
wound, a leaving or a `goodbye`, the rest is the souls' story, and the
compiler stops comparing.

### Fidelity

A heart is given to one at a time. A soul whose code gives its heart to two
different souls by name, and never takes it back with `take back heart from`,
does not compile. When it happens at run time anyway, through a computed name,
the heart moves: the one who had it loses it and keeps the scar
`"<giver> gave their heart to <new>"`, and the giver keeps `"gave my heart to
<new>"`. Both know.

## Ways of loving

```
soul ana is anxious and agape
kind pod is avoidant
```

A soul or a kind may say how it loves; the souls of a kind love the way the
kind does. Attachment styles are ways of waiting, the styles of John Alan Lee
are ways of feeling.

| Style | What changes |
|---|---|
| `secure` | nothing: the rules as written |
| `anxious` | every fourth step it spends asking whether the other is still there, and the asking presses on them |
| `avoidant` | it comes to a meeting and hears words only after it has waited two rounds, even when it was ready |
| `eros` | passion at first sight is 5, not 3, and cools twice as fast |
| `ludus` | its promises bring no commitment, and leaving leaves it no scars |
| `storge` | trust grows by one for every second `warm to`; `cool to` takes nothing, and a wound only halves its trust |
| `pragma` | it gives its heart only where it trusts at least 3; trying otherwise is an error |
| `mania` | it asks like an anxious soul, and is jealous of every word the one who has its heart says to another, twice as much |
| `agape` | a wound does not close it, and it holds no resentment |

An unknown style does not compile.

## Consent

```
together with ben
    …               done together
apart
    …               if it stopped halfway
end
```

What two souls do together they do only with the consent of both. A soul
gives it with `consent to S` and takes it back with `withdraw consent from S`.
`together with S` waits until `S` is at `together with` this soul and both
consent; then both go in. Whatever happens inside, each soul goes on with its
own steps; at the `end` of the block each waits for the other, and both go on
only when both have come, so what is done together is done by both or by
neither.

Consent can be withdrawn at any moment, by either soul, even in the middle. If
it is, or if one of them leaves or is gone, both stop wherever they are, let
go of the rituals they were in, and go to `apart`. A block without `apart`
simply ends.

## Boundaries

A soul reads another soul's note with `note k of S`, if `S` lets it in: a note
in the open needs `S`'s calculated trust (`S` has warmed to this soul at least
once); a note `S` keeps behind its boundary with `guard k` opens only to a soul
`S` gave its heart to, and every crossing is seen by both: `crossings with S`
grows on both sides. Without that, reading is an error that names the
boundary.

## Letters and grief

`send S e` writes `S` a letter and goes on at once; it does not wait for `S`. The
letter arrives after as many rounds as the two are far apart, and waits until
`S` reads it with `receive from` or `receive anyone`. Letters are kept even after
the one who wrote them is gone: they cannot be stopped, only read. Whatever a
soul has not read of the letters from souls that are gone, it keeps as scars
when it ends.

## Enduring

```
endure
    …
when it hurts as pain
    …
end
```

A mistake ends the program, unless the soul that makes it is inside an
`endure`. Then the soul goes on after `when it hurts as pain`, with the reason
in `pain`, a string such as `"there is no item 5 in a list of 1"`. Whatever went
wrong inside, however deep in rituals, the soul comes back to the ritual where
it endured, and the rituals it was in are let go, their memories with them.
A mistake made while a soul hears another (in the value the speaker computes)
is the listener's to endure.

## Learning

```
learn "kube.tainted"
```

At the top of a program, outside any soul, `learn` brings in the kinds and
rituals of another file, as if they were written there. The file is looked
for next to the program (`TAINTED_DIR`, set by `bin/tc`), then in the library
(`TAINTED_LIB`, `lib/` by default). A file learned twice is learned once. A
mistake in a learned file names it: `line 7 of kube.tainted, s: …`. The
learned files are part of the program's source, and so of the history of its
runs.

## How a program ends

| Exit code | When |
|---|---|
| 0 | every soul reached its end or said `goodbye` |
| `e` | every soul reached its end, and the last to say `goodbye with e` said this number, from 0 to 255 |
| 1 | an error: a mistake in the program or something a soul cannot do |
| 2 | everyone left is waiting for someone and nobody can move |
| 4 | the world ran out of patience ([Constants](#constants)) |
| 64 | the program was called wrongly |

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
make                                build the compiler, build/tc-core, from the seed
bin/tc program.tainted              compile a program to ./program
bin/tc program.tainted -o path      compile it to path
bin/tc program.tainted -c           print the C the compiler makes of it
./program                           run it; the world is its standard input
./program --feelings                run it, then print every relationship
./program --patience=N              give up after N rounds
./program --deterministic           no chemistry, the same life every run
```

`--feelings` prints, on standard error, one line per soul and soul it met:

```
alice -> bob: romantic love; trust 3, intimacy 4, passion 3, commitment 0, scars 0, heart given
```

A program that does not compile ends the compiler with exit code 1 and the
reason: `tainted: line 4: expected 'of'`.

## The compiler

`compiler.tainted` is the compiler. It is a Tainted program: it hears a program
from the world, line by line, and says a C program that, built together with
`runtime/tainted.c`, lives the same life. `bin/tc` runs the compiler and the C
compiler one after the other.

- Every soul, kind and ritual becomes a unit: a table of its instructions and
  a step function. Other souls look at the table (whether this one waits to
  meet them, to tell them something, to hear them); the step function carries
  out the instruction in front of the soul.
- Every expression becomes a C function of its own, evaluated from left to
  right; `and` and `or` look at their right side only when they need to.
- The runtime owns everything between souls: rounds, meetings, words, fear,
  relationships, memory and its fading, rituals, the world and the history of
  runs. Its rules are the ones in this reference.
- The source of the program is kept inside the program it compiles to, so the
  program counts its own runs.

The compiler compiles itself. `boot/tc.c` is the seed: the C that the
compiler says of its own source. `make` builds the compiler from the seed;
`make bootstrap` lets it compile itself twice more and checks that the
generations say the same program; `make seed` replaces the seed after a change
to the compiler. A new rule of the language is first taught to the compiler in
the words the previous generation already understands.

The compiler forgets like any soul. It writes down in notes everything that has
to outlive a few steps; where a loop runs long, it recalls what it will need
afterwards. A compiler that does not recall the name of the function it is
writing loses letters from it and builds C that does not compile; the test
suite checks this.

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

- A ritual call is a statement, not an expression.
- Strings cannot hold the character 0.
