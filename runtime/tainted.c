/* The Tainted runtime. See tainted.h. */
#include "tainted.h"

#include <errno.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define FADE 50
#define PASSION_FADE 50
#define PRESENT 3
#define DEFAULT_PATIENCE 10000000LL
#define DEEPEST 10000

/* ------------------------------------------------------------ memory */

typedef struct Block { struct Block *next; size_t used, size; char data[]; } Block;
static Block *arena;
static void **doomed;
static size_t ndoomed, capdoomed;

static void *oom(void *p) {
    if (!p) { fputs("tainted: out of memory\n", stderr); exit(1); }
    return p;
}

static void *scratch(size_t n) {
    n = (n + 15) & ~(size_t)15;
    if (!arena || arena->used + n > arena->size) {
        size_t size = n > 65536 ? n : 65536;
        Block *b = oom(malloc(sizeof(Block) + size));
        b->next = arena; b->used = 0; b->size = size;
        arena = b;
    }
    void *p = arena->data + arena->used;
    arena->used += n;
    return p;
}

/* Values made during a step live until the step is over; anything kept
 * longer is copied to the heap, and the heap copy it replaces is freed only
 * when the step is over, so a value still in hand never disappears. */
static void step_over(void) {
    while (arena && arena->next) { Block *b = arena->next; arena->next = b->next; free(b); }
    if (arena) arena->used = 0;
    for (size_t i = 0; i < ndoomed; i++) free(doomed[i]);
    ndoomed = 0;
}

static void doom(const void *p) {
    if (!p) return;
    if (ndoomed == capdoomed) {
        capdoomed = capdoomed ? capdoomed * 2 : 64;
        doomed = oom(realloc(doomed, capdoomed * sizeof *doomed));
    }
    doomed[ndoomed++] = (void *)p;
}

static Value keep(Value v) {
    if (v.tag != T_STR) return v;
    char *p = oom(malloc((size_t)v.n + 1));
    memcpy(p, v.s, (size_t)v.n);
    p[v.n] = 0;
    v.s = p;
    return v;
}

static void drop(Value v) { if (v.tag == T_STR) doom(v.s); }

Value t_int(int64_t i) { Value v = {0}; v.tag = T_INT; v.i = i; return v; }
Value t_str(const char *s, int64_t n) { Value v = {0}; v.tag = T_STR; v.s = s; v.n = n; return v; }
Value t_cstr(const char *s) { return t_str(s, (int64_t)strlen(s)); }

static Value fresh(const char *s, int64_t n) {
    char *p = scratch((size_t)n + 1);
    memcpy(p, s, (size_t)n);
    p[n] = 0;
    return t_str(p, n);
}

static Value printf_value(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(NULL, 0, fmt, ap); va_end(ap);
    char *p = scratch((size_t)n + 1);
    va_start(ap, fmt); vsnprintf(p, (size_t)n + 1, fmt, ap); va_end(ap);
    return t_str(p, n);
}

/* A value as text, the way `say` shows it. */
static Value show(Value v) {
    if (v.tag == T_STR) return v;
    return printf_value("%lld", (long long)v.i);
}

static const char *cs(Value v) {      /* show, terminated, for messages */
    Value t = show(v);
    char *p = scratch((size_t)t.n + 1);
    memcpy(p, t.s, (size_t)t.n);
    p[t.n] = 0;
    return p;
}

static int same(Value a, Value b) {
    if (a.tag != b.tag) return 0;
    if (a.tag == T_INT) return a.i == b.i;
    return a.n == b.n && memcmp(a.s, b.s, (size_t)a.n) == 0;
}

/* Text is UTF-8; lengths and parts count characters, as people do. */
static int64_t chars(Value v) {
    int64_t n = 0;
    for (int64_t i = 0; i < v.n; i++) if (((unsigned char)v.s[i] & 0xC0) != 0x80) n++;
    return n;
}

static int64_t offset(Value v, int64_t k) {   /* byte offset of character k */
    int64_t seen = 0;
    for (int64_t i = 0; i < v.n; i++) {
        if (((unsigned char)v.s[i] & 0xC0) != 0x80) {
            if (seen == k) return i;
            seen++;
        }
    }
    return v.n;
}

/* ------------------------------------------------------------- tables */

typedef struct { char *key; int64_t klen; int val; } Entry;
typedef struct { Entry *e; size_t cap, n; } Table;

static uint64_t hash(const char *s, int64_t n) {
    uint64_t h = 1469598103934665603ULL;
    for (int64_t i = 0; i < n; i++) { h ^= (unsigned char)s[i]; h *= 1099511628211ULL; }
    return h;
}

static int table_get(const Table *t, const char *k, int64_t n) {
    if (!t->cap) return -1;
    for (size_t i = hash(k, n) & (t->cap - 1);; i = (i + 1) & (t->cap - 1)) {
        Entry *e = &t->e[i];
        if (!e->key) return -1;
        if (e->klen == n && memcmp(e->key, k, (size_t)n) == 0) return e->val;
    }
}

static void table_put(Table *t, const char *k, int64_t n, int val) {
    if ((t->n + 1) * 2 > t->cap) {
        Table bigger = {0};
        bigger.cap = t->cap ? t->cap * 2 : 16;
        bigger.e = oom(calloc(bigger.cap, sizeof(Entry)));
        for (size_t i = 0; i < t->cap; i++)
            if (t->e[i].key) {
                size_t j = hash(t->e[i].key, t->e[i].klen) & (bigger.cap - 1);
                while (bigger.e[j].key) j = (j + 1) & (bigger.cap - 1);
                bigger.e[j] = t->e[i];
                bigger.n++;
            }
        free(t->e);
        *t = bigger;
    }
    for (size_t i = hash(k, n) & (t->cap - 1);; i = (i + 1) & (t->cap - 1)) {
        Entry *e = &t->e[i];
        if (!e->key) {
            e->key = oom(malloc((size_t)n + 1));
            memcpy(e->key, k, (size_t)n);
            e->key[n] = 0;
            e->klen = n; e->val = val; t->n++;
            return;
        }
        if (e->klen == n && memcmp(e->key, k, (size_t)n) == 0) { e->val = val; return; }
    }
}

typedef struct { Value *v; size_t n, cap; } List;

static void list_push(List *l, Value v) {
    if (l->n == l->cap) {
        l->cap = l->cap ? l->cap * 2 : 4;
        l->v = oom(realloc(l->v, l->cap * sizeof(Value)));
    }
    l->v[l->n++] = keep(v);
}

/* -------------------------------------------------------------- souls */

typedef struct { Value v; int64_t touched; int set; } Slot;

typedef struct {
    int unit, pc;
    Slot *mem;
    int into;
    int64_t began;
} Frame;

typedef struct { int who; int64_t left; } Fear;

struct Soul {
    int id;
    char *name;
    int64_t nlen;
    int unit, pc;
    Slot *mem;
    Table notes;
    Value *notev;
    size_t nnotes, capnotes;
    Frame *frames;
    size_t nframes, capframes;
    int64_t step, arrived;
    int done;
    Fear *fears;
    size_t nfears, capfears;
};

typedef struct {
    int a, b;
    int met, gift, closed, left, abandoned;
    int64_t trust, intimacy, passion, commitment, pressure, last_meet, faded;
    List heard, scars;
} Rel;

struct World {
    const Program *p;
    Soul **order;
    size_t nsouls, capsouls;
    Table names;
    Rel **rels;         /* each on its own, so a pointer to one outlives new ones */
    size_t nrels, caprels;
    Table relindex;
    int64_t runs, round, patience;
    int ending;
    char *error;
    jmp_buf *trap;
};

int t_pc(const Soul *s) { return s->pc; }

static const Unit *unit_of(World *w, Soul *s) { return &w->p->units[s->unit]; }

static const Ins *current(World *w, Soul *s) {
    const Unit *u = unit_of(w, s);
    return s->pc < u->nins ? &u->ins[s->pc] : NULL;
}

_Noreturn void t_fail(World *w, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(NULL, 0, fmt, ap); va_end(ap);
    free(w->error);
    w->error = oom(malloc((size_t)n + 1));
    va_start(ap, fmt); vsnprintf(w->error, (size_t)n + 1, fmt, ap); va_end(ap);
    longjmp(*w->trap, 1);
}

static Slot *new_mem(const Unit *u) {
    return oom(calloc(u->nslots ? (size_t)u->nslots : 1, sizeof(Slot)));
}

static Soul *new_soul(World *w, const char *name, int64_t n, int unit) {
    Soul *s = oom(calloc(1, sizeof(Soul)));
    s->name = oom(malloc((size_t)n + 1));
    memcpy(s->name, name, (size_t)n);
    s->name[n] = 0;
    s->nlen = n;
    s->unit = unit;
    s->mem = new_mem(&w->p->units[unit]);
    if (w->nsouls == w->capsouls) {
        w->capsouls = w->capsouls ? w->capsouls * 2 : 8;
        w->order = oom(realloc(w->order, w->capsouls * sizeof(Soul *)));
    }
    s->id = (int)w->nsouls;
    w->order[w->nsouls++] = s;
    table_put(&w->names, s->name, n, s->id);
    return s;
}

static Soul *find(World *w, Value name) {
    int id = table_get(&w->names, name.s, name.n);
    return id < 0 ? NULL : w->order[id];
}

static Value name_of(Soul *s) { return t_str(s->name, s->nlen); }

/* ------------------------------------------------------ relationships */

static void cool_down(Rel *r, Soul *owner) {
    if (r->met && !r->left && owner->step > r->last_meet) {
        int64_t due = (owner->step - r->last_meet) / PASSION_FADE;
        if (due > r->faded) {
            r->passion -= due - r->faded;
            if (r->passion < 0) r->passion = 0;
            r->faded = due;
        }
    }
}

static Rel *rel(World *w, Soul *a, Soul *b) {
    char key[16];
    memcpy(key, &a->id, sizeof(int));
    memcpy(key + sizeof(int), &b->id, sizeof(int));
    int i = table_get(&w->relindex, key, 2 * sizeof(int));
    if (i < 0) {
        if (w->nrels == w->caprels) {
            w->caprels = w->caprels ? w->caprels * 2 : 16;
            w->rels = oom(realloc(w->rels, w->caprels * sizeof(Rel *)));
        }
        i = (int)w->nrels++;
        w->rels[i] = oom(calloc(1, sizeof(Rel)));
        w->rels[i]->a = a->id;
        w->rels[i]->b = b->id;
        table_put(&w->relindex, key, 2 * sizeof(int), i);
    }
    Rel *r = w->rels[i];
    cool_down(r, a);
    return r;
}

static const char *bond_name(Rel *r) {
    static const char *names[8] = {
        "nothing yet", "empty love", "infatuation", "fatuous love",
        "liking", "companionate love", "romantic love", "consummate love"};
    int k = (r->intimacy >= PRESENT) * 4 + (r->passion >= PRESENT) * 2 + (r->commitment >= PRESENT);
    return names[k];
}

static int64_t *fear_of(Soul *s, int who) {
    for (size_t i = 0; i < s->nfears; i++) if (s->fears[i].who == who) return &s->fears[i].left;
    return NULL;
}

static void frighten(Soul *s, int who, int64_t steps) {
    int64_t *f = fear_of(s, who);
    if (f) { *f = steps; return; }
    if (s->nfears == s->capfears) {
        s->capfears = s->capfears ? s->capfears * 2 : 4;
        s->fears = oom(realloc(s->fears, s->capfears * sizeof(Fear)));
    }
    s->fears[s->nfears].who = who;
    s->fears[s->nfears].left = steps;
    s->nfears++;
}

/* --------------------------------------------------------------- memory */

static Value fade(Value v, int64_t periods) {
    if (v.tag == T_INT) {
        if (periods >= 19) return t_int(0);
        int64_t lost = 1;
        for (int64_t k = 0; k < periods; k++) lost *= 10;
        int64_t a = v.i < 0 ? -v.i : v.i;
        return t_int((v.i < 0 ? -1 : 1) * (a / lost * lost));
    }
    int64_t keepn = chars(v) - periods;
    if (keepn < 0) keepn = 0;
    return fresh(v.s, offset(v, keepn));
}

static void store(Slot *slot, Value v, int64_t now) {
    if (slot->set) drop(slot->v);
    slot->v = keep(v);
    slot->touched = now;
    slot->set = 1;
}

Value t_var(World *w, Soul *s, int slot) {
    Slot *m = &s->mem[slot];
    if (!m->set) t_fail(w, "%s does not remember any %s", s->name, unit_of(w, s)->slots[slot]);
    int64_t periods = (s->step - m->touched) / FADE;
    if (periods) {
        Value faded = fade(m->v, periods);
        store(m, faded, s->step);
    } else {
        m->touched = s->step;
    }
    return m->v;
}

/* ---------------------------------------------------------- expressions */

int t_truthy(Value v) { return v.tag == T_INT ? v.i != 0 : v.n != 0; }

Value t_neg(World *w, Value v) {
    if (v.tag != T_INT) t_fail(w, "only numbers can be negated");
    if (v.i == INT64_MIN) t_fail(w, "the number grew too large to hold");
    return t_int(-v.i);
}

Value t_not(Value v) { return t_int(!t_truthy(v)); }
Value t_and(Value a, Value b) { return t_int(t_truthy(a) && t_truthy(b)); }
Value t_or(Value a, Value b) { return t_int(t_truthy(a) || t_truthy(b)); }

static int compare(Value a, Value b) {
    if (a.tag == T_INT) return (a.i > b.i) - (a.i < b.i);
    int64_t n = a.n < b.n ? a.n : b.n;
    int c = memcmp(a.s, b.s, (size_t)n);
    if (c) return c < 0 ? -1 : 1;
    return (a.n > b.n) - (a.n < b.n);
}

Value t_bin(World *w, int op, Value a, Value b) {
    if (op == B_ADD && (a.tag == T_STR || b.tag == T_STR)) {
        Value x = show(a), y = show(b);
        char *p = scratch((size_t)(x.n + y.n) + 1);
        memcpy(p, x.s, (size_t)x.n);
        memcpy(p + x.n, y.s, (size_t)y.n);
        p[x.n + y.n] = 0;
        return t_str(p, x.n + y.n);
    }
    if (op == B_EQ) return t_int(same(a, b));
    if (op == B_NE) return t_int(!same(a, b));
    if (a.tag != b.tag) t_fail(w, "cannot compare or combine '%s' and '%s'", cs(a), cs(b));
    switch (op) {
    case B_LT: return t_int(compare(a, b) < 0);
    case B_GT: return t_int(compare(a, b) > 0);
    case B_LE: return t_int(compare(a, b) <= 0);
    case B_GE: return t_int(compare(a, b) >= 0);
    }
    static const char *ops[] = {"+", "-", "*", "/", "%"};
    if (a.tag != T_INT) t_fail(w, "'%s' works only on numbers", ops[op]);
    int64_t r;
    switch (op) {
    case B_ADD:
        if (__builtin_add_overflow(a.i, b.i, &r)) t_fail(w, "the number grew too large to hold");
        return t_int(r);
    case B_SUB:
        if (__builtin_sub_overflow(a.i, b.i, &r)) t_fail(w, "the number grew too large to hold");
        return t_int(r);
    case B_MUL:
        if (__builtin_mul_overflow(a.i, b.i, &r)) t_fail(w, "the number grew too large to hold");
        return t_int(r);
    }
    if (b.i == 0) t_fail(w, "a number cannot be divided by nothing");
    if (a.i == INT64_MIN && b.i == -1) {
        if (op == B_DIV) t_fail(w, "the number grew too large to hold");
        return t_int(0);
    }
    int64_t q = a.i / b.i, m = a.i % b.i;
    if (m != 0 && ((m < 0) != (b.i < 0))) { q -= 1; m += b.i; }
    return t_int(op == B_DIV ? q : m);
}

Value t_me(World *w, Soul *s) { (void)w; return name_of(s); }
Value t_runs(World *w) { return t_int(w->runs); }

static Soul *resolve(World *w, Soul *s, Value who) {
    if (who.tag != T_STR) t_fail(w, "%s looks for a soul named %s, but names are words", s->name, cs(who));
    Soul *b = find(w, who);
    if (!b) t_fail(w, "%s looks for %s, but there is no such soul", s->name, cs(who));
    if (b == s) t_fail(w, "%s cannot do this with themself", s->name);
    return b;
}

static Value target(World *w, Soul *s, const Ins *ins) {
    Value who = ins->target(w, s);
    if (who.tag != T_STR) t_fail(w, "%s looks for a soul named %s, but names are words", s->name, cs(who));
    return who;
}

static Rel *known(World *w, Soul *s, Soul *b) {
    Rel *r = rel(w, s, b);
    if (!r->met) t_fail(w, "%s has never met %s", s->name, b->name);
    if (r->left) t_fail(w, "%s left %s; there is nothing more to do", s->name, b->name);
    return r;
}

Value t_rel(World *w, Soul *s, int what, Value who) {
    Rel *r = rel(w, s, resolve(w, s, who));
    switch (what) {
    case R_TRUST: return t_int(r->trust);
    case R_INTIMACY: return t_int(r->intimacy);
    case R_PASSION: return t_int(r->passion);
    default: return t_int(r->commitment);
    }
}

Value t_afraid(World *w, Soul *s, Value who) {
    Soul *b = resolve(w, s, who);
    int64_t *f = fear_of(s, b->id);
    return t_int(f && *f > 0);
}

Value t_bond(World *w, Soul *s, Value who) {
    return t_cstr(bond_name(rel(w, s, resolve(w, s, who))));
}

Value t_scars(World *w, Soul *s, Value who) {
    return t_int((int64_t)rel(w, s, resolve(w, s, who))->scars.n);
}

Value t_scar(World *w, Soul *s, Value idx, Value who) {
    Soul *b = resolve(w, s, who);
    List *scars = &rel(w, s, b)->scars;
    if (idx.tag != T_INT || idx.i < 1 || idx.i > (int64_t)scars->n)
        t_fail(w, "%s has no scar number %s from %s", s->name, cs(idx), b->name);
    return scars->v[idx.i - 1];
}

Value t_note_get(World *w, Soul *s, Value key) {
    Value k = show(key);
    int i = table_get(&s->notes, k.s, k.n);
    if (i < 0) t_fail(w, "%s never wrote down %s", s->name, cs(k));
    return s->notev[i];
}

static int space(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f'; }

/* The n-th word (from 1); returns 0 if there is none. */
static int nth_word(Value text, int64_t n, int64_t *start, int64_t *len) {
    int64_t i = 0, k = 0;
    while (i < text.n) {
        while (i < text.n && space(text.s[i])) i++;
        if (i >= text.n) break;
        int64_t b = i;
        while (i < text.n && !space(text.s[i])) i++;
        if (++k == n) { *start = b; *len = i - b; return 1; }
    }
    return 0;
}

static int64_t count_words(Value text) {
    int64_t i = 0, k = 0;
    while (i < text.n) {
        while (i < text.n && space(text.s[i])) i++;
        if (i >= text.n) break;
        k++;
        while (i < text.n && !space(text.s[i])) i++;
    }
    return k;
}

static void needs_word(World *w, const char *what, Value text) {
    if (text.tag != T_STR) t_fail(w, "'%s' needs a word, not %s", what, cs(text));
}

Value t_word(World *w, Value idx, Value text) {
    needs_word(w, "word", text);
    int64_t b, n;
    if (idx.tag == T_INT && idx.i >= 1 && nth_word(text, idx.i, &b, &n)) return t_str(text.s + b, n);
    return t_str("", 0);
}

Value t_words(World *w, Value text) {
    needs_word(w, "words", text);
    return t_int(count_words(text));
}

Value t_place(World *w, Value x, Value text) {
    needs_word(w, "place", text);
    Value want = show(x);
    int64_t b, n;
    for (int64_t k = 1; nth_word(text, k, &b, &n); k++)
        if (n == want.n && memcmp(text.s + b, want.s, (size_t)n) == 0) return t_int(k);
    return t_int(0);
}

Value t_number(World *w, Value text) {
    needs_word(w, "number", text);
    int64_t i = 0, j = text.n;
    while (i < j && space(text.s[i])) i++;
    while (j > i && space(text.s[j - 1])) j--;
    int neg = 0;
    int64_t k = i;
    if (k < j && (text.s[k] == '+' || text.s[k] == '-')) { neg = text.s[k] == '-'; k++; }
    if (k >= j) t_fail(w, "'%s' is not a number", cs(text));
    int64_t r = 0;
    int prev_digit = 0;
    for (; k < j; k++) {
        char c = text.s[k];
        if (c == '_' && prev_digit && k + 1 < j && text.s[k + 1] >= '0' && text.s[k + 1] <= '9') {
            prev_digit = 0;
            continue;
        }
        if (c < '0' || c > '9') t_fail(w, "'%s' is not a number", cs(text));
        if (__builtin_mul_overflow(r, 10, &r) || __builtin_add_overflow(r, c - '0', &r))
            t_fail(w, "the number grew too large to hold");
        prev_digit = 1;
    }
    return t_int(neg ? -r : r);
}

Value t_length(World *w, Value text) {
    if (text.tag != T_STR) t_fail(w, "only words have a length");
    return t_int(chars(text));
}

Value t_part(World *w, Value a, Value b, Value text) {
    if (a.tag != T_INT || b.tag != T_INT || text.tag != T_STR)
        t_fail(w, "part takes two numbers and a word");
    int64_t from = (a.i > 1 ? a.i : 1) - 1, to = b.i > 0 ? b.i : 0;
    int64_t len = chars(text);
    if (to > len) to = len;
    if (from >= to) return t_str("", 0);
    int64_t x = offset(text, from), y = offset(text, to);
    return t_str(text.s + x, y - x);
}

/* ---------------------------------------------------------- instructions */

static void advance(Soul *s) { s->pc++; }

int t_let(World *w, Soul *s, int slot, Value v) {
    (void)w;
    store(&s->mem[slot], v, s->step);
    advance(s);
    return 1;
}

int t_say(World *w, Soul *s, Value v) {
    (void)w;
    Value t = show(v);
    fwrite(t.s, 1, (size_t)t.n, stdout);
    fputc('\n', stdout);
    advance(s);
    return 1;
}

int t_cry(World *w, Soul *s, Value v) {
    (void)w;
    Value t = show(v);
    fflush(stdout);
    fwrite(t.s, 1, (size_t)t.n, stderr);
    fputc('\n', stderr);
    advance(s);
    return 1;
}

int t_goodbye_with(World *w, Soul *s, Value code) {
    if (code.tag != T_INT || code.i < 0 || code.i > 255)
        t_fail(w, "a program can only end with a number from 0 to 255, not %s", cs(code));
    w->ending = (int)code.i;
    s->done = 1;
    return 1;
}

int t_note(World *w, Soul *s, Value key, Value v) {
    (void)w;
    Value k = show(key);
    int i = table_get(&s->notes, k.s, k.n);
    if (i < 0) {
        if (s->nnotes == s->capnotes) {
            s->capnotes = s->capnotes ? s->capnotes * 2 : 8;
            s->notev = oom(realloc(s->notev, s->capnotes * sizeof(Value)));
        }
        i = (int)s->nnotes++;
        table_put(&s->notes, k.s, k.n, i);
    } else {
        drop(s->notev[i]);
    }
    s->notev[i] = keep(v);
    advance(s);
    return 1;
}

int t_jz(World *w, Soul *s, Value cond, int to) {
    (void)w;
    if (t_truthy(cond)) advance(s); else s->pc = to;
    return 1;
}

int t_jmp(World *w, Soul *s, int to) { (void)w; s->pc = to; return 1; }

int t_first(World *w, Soul *s, int to) {
    if (w->runs) s->pc = to; else advance(s);
    return 1;
}

int t_wait(World *w, Soul *s) { (void)w; advance(s); return 1; }
int t_goodbye(World *w, Soul *s) { (void)w; s->done = 1; return 1; }
int t_silence(World *w, Soul *s) { (void)w; (void)s; return 0; }

int t_recall(World *w, Soul *s, const Ins *ins) {
    for (int i = 0; i < ins->nvars; i++) (void)t_var(w, s, ins->vars[i]);
    advance(s);
    return 1;
}

int t_bring(World *w, Soul *s, const Ins *ins) {
    if (ins->unit < 0) t_fail(w, "there is no kind of soul called %s", ins->name);
    Value name = ins->a(w, s);
    if (name.tag != T_STR || name.n == 0) t_fail(w, "a soul needs a name, not %s", cs(name));
    if (find(w, name)) t_fail(w, "there is already a soul called %s", cs(name));
    Soul *child = new_soul(w, name.s, name.n, ins->unit);
    child->arrived = w->round;
    advance(s);
    return 1;
}

int t_perform(World *w, Soul *s, const Ins *ins) {
    if (ins->unit < 0) t_fail(w, "%s knows no ritual called %s", s->name, ins->name);
    const Unit *r = &w->p->units[ins->unit];
    if (ins->nargs != r->nparams)
        t_fail(w, "the ritual %s takes %d things, not %d", ins->name, r->nparams, ins->nargs);
    Value *values = scratch(sizeof(Value) * (size_t)(ins->nargs ? ins->nargs : 1));
    for (int i = 0; i < ins->nargs; i++) values[i] = ins->args[i](w, s);
    if (s->nframes > DEEPEST) t_fail(w, "%s is lost in rituals inside rituals", s->name);
    if (s->nframes == s->capframes) {
        s->capframes = s->capframes ? s->capframes * 2 : 8;
        s->frames = oom(realloc(s->frames, s->capframes * sizeof(Frame)));
    }
    Frame *f = &s->frames[s->nframes++];
    f->unit = s->unit; f->pc = s->pc + 1; f->mem = s->mem; f->into = ins->var; f->began = s->step;
    s->unit = ins->unit;
    s->pc = 0;
    s->mem = new_mem(r);
    for (int i = 0; i < r->nparams; i++) store(&s->mem[r->params[i]], values[i], s->step);
    return 1;
}

static void finish_ritual(World *w, Soul *s, Value value) {
    Frame f = s->frames[--s->nframes];
    const Unit *u = unit_of(w, s);
    for (int i = 0; i < u->nslots; i++) if (s->mem[i].set) drop(s->mem[i].v);
    Value v = keep(value);      /* the value may live in the memory being let go */
    doom(s->mem);
    int64_t held = s->step - f.began;
    s->unit = f.unit;
    s->pc = f.pc;
    s->mem = f.mem;
    const Unit *back = unit_of(w, s);
    for (int i = 0; i < back->nslots; i++) if (s->mem[i].set) s->mem[i].touched += held;
    if (f.into >= 0) store(&s->mem[f.into], v, s->step);
    drop(v);
}

int t_giveback(World *w, Soul *s, Value v) {
    if (!s->nframes) t_fail(w, "%s has nothing to give back outside a ritual", s->name);
    finish_ritual(w, s, v);
    return 1;
}

static int wants_to_meet(World *w, Soul *b, Soul *a, int strangers) {
    const Ins *bi = current(w, b);
    if (!bi || bi->op != OP_MEET) return 0;
    if (bi->mode == TO_ANYONE) return strangers;
    Value who = target(w, b, bi);
    return same(who, name_of(a));
}

static int try_meet(World *w, Soul *a, Soul *b) {
    Rel *ra = rel(w, a, b), *rb = rel(w, b, a);
    if (ra->left || rb->left || ra->closed || rb->closed) return 0;
    int64_t warmth = (!ra->met && a->arrived == b->arrived) ? 3 : 1;
    Soul *pair[2][2] = {{a, b}, {b, a}};
    for (int k = 0; k < 2; k++) {
        const Ins *ins = current(w, pair[k][0]);
        if (ins->mode == TO_ANYONE) store(&pair[k][0]->mem[ins->var], name_of(pair[k][1]), pair[k][0]->step);
    }
    Rel *rs[2] = {ra, rb};
    for (int k = 0; k < 2; k++) {
        rs[k]->met = 1;
        rs[k]->passion += warmth;
        rs[k]->last_meet = pair[k][0]->step;
        rs[k]->faded = 0;
        advance(pair[k][0]);
    }
    return 1;
}

int t_meet(World *w, Soul *s, const Ins *ins) {
    if (ins->mode == TO_ANYONE) {
        for (size_t i = 0; i < w->nsouls; i++) {
            Soul *b = w->order[i];
            if (b != s && !b->done && wants_to_meet(w, b, s, 0) && try_meet(w, s, b)) return 1;
        }
        return 0;
    }
    Soul *b = resolve(w, s, target(w, s, ins));
    if (rel(w, s, b)->left) t_fail(w, "%s left %s; there is nothing more to do", s->name, b->name);
    return wants_to_meet(w, b, s, 1) && try_meet(w, s, b);
}

static int try_transfer(World *w, Soul *snd, Soul *rcv) {
    const Ins *si = current(w, snd), *ri = current(w, rcv);
    if (!si || (si->op != OP_TELL && si->op != OP_CONFIDE)) return 0;
    if (!same(target(w, snd, si), name_of(rcv))) return 0;
    if (!ri || ri->op != OP_HEAR || ri->mode == TO_WORLD) return 0;
    if (ri->mode == TO_NAMED && !same(target(w, rcv, ri), name_of(snd))) return 0;
    Rel *rs = rel(w, snd, rcv), *rr = rel(w, rcv, snd);
    if (!rr->met || rr->closed || rr->left || rs->left) return 0;
    int64_t *f = fear_of(rcv, snd->id);
    if (f && *f > 0) return 0;
    if (si->op == OP_CONFIDE && !rs->gift)
        t_fail(w, "%s can confide only in someone they gave their heart to", snd->name);
    Value value = si->a(w, snd);
    store(&rcv->mem[ri->var], value, rcv->step);
    if (ri->var2 >= 0) store(&rcv->mem[ri->var2], name_of(snd), rcv->step);
    list_push(&rr->heard, value);
    if (rr->pressure > 0) { rs->intimacy++; rr->intimacy++; }
    rr->pressure = 0;
    rs->pressure++;
    if (rs->pressure > rr->intimacy + 2) {
        frighten(rcv, snd->id, 3 + rs->pressure);
        if (rr->passion > 0) rr->passion--;
        rs->pressure = 0;
    }
    advance(snd);
    advance(rcv);
    return 1;
}

int t_tell(World *w, Soul *s, const Ins *ins) {
    Soul *b = resolve(w, s, target(w, s, ins));
    Rel *r = known(w, s, b);
    if (ins->op == OP_CONFIDE && !r->gift)
        t_fail(w, "%s can confide only in someone they gave their heart to", s->name);
    return try_transfer(w, s, b);
}

int t_hear(World *w, Soul *s, const Ins *ins) {
    if (ins->mode == TO_WORLD) {
        char *line = NULL;
        size_t cap = 0;
        ssize_t n = getline(&line, &cap, stdin);
        if (n < 0) {
            store(&s->mem[ins->var], t_int(0), s->step);
        } else {
            while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) n--;
            store(&s->mem[ins->var], t_str(line, n), s->step);
        }
        free(line);
        advance(s);
        return 1;
    }
    if (ins->mode == TO_NAMED) {
        Soul *b = resolve(w, s, target(w, s, ins));
        known(w, s, b);
        return try_transfer(w, b, s);
    }
    for (size_t i = 0; i < w->nsouls; i++) {
        Soul *b = w->order[i];
        if (b != s && try_transfer(w, b, s)) return 1;
    }
    return 0;
}

int t_feel(World *w, Soul *s, const Ins *ins) {
    Value who = target(w, s, ins);
    Soul *b = resolve(w, s, who);
    Rel *mine = known(w, s, b);
    switch (ins->op) {
    case OP_WARM: mine->trust++; break;
    case OP_COOL: if (mine->trust > 0) mine->trust--; break;
    case OP_PROMISE: mine->commitment++; break;
    case OP_GIVE: mine->gift = 1; break;
    case OP_FORGIVE: mine->closed = 0; break;
    case OP_WOUND: {
        Rel *them = rel(w, b, s);
        them->trust = 0;
        them->intimacy /= 2;
        list_push(&them->scars, printf_value("wounded by %s", s->name));
        if (!them->gift) them->closed = 1;
        break;
    }
    case OP_LEAVE: {
        Rel *them = rel(w, b, s);
        mine->left = 1;
        mine->commitment = 0;
        for (size_t i = 0; i < mine->heard.n; i++) list_push(&mine->scars, mine->heard.v[i]);
        for (size_t i = 0; i < them->heard.n; i++) list_push(&them->scars, them->heard.v[i]);
        list_push(&them->scars, printf_value("%s left", s->name));
        them->abandoned = 1;
        break;
    }
    }
    advance(s);
    return 1;
}

/* ----------------------------------------------------------------- life */

static int step_soul(World *w, Soul *s) {
    if (!current(w, s)) {
        if (s->nframes) { finish_ritual(w, s, t_int(0)); return 1; }
        s->done = 1;
        return 1;
    }
    return unit_of(w, s)->step(w, s);
}

static void lament(World *w) {
    fputs("the end.\n", stderr);
    for (size_t i = 0; i < w->nsouls; i++) {
        Soul *s = w->order[i];
        if (s->done) continue;
        const Ins *ins = current(w, s);
        Value who = {0};
        int has = 0;
        if (ins && (ins->op == OP_MEET || ins->op == OP_TELL || ins->op == OP_CONFIDE || ins->op == OP_HEAR)
            && ins->mode == TO_NAMED) {
            jmp_buf trap, *outer = w->trap;
            w->trap = &trap;
            if (setjmp(trap) == 0) { who = target(w, s, ins); has = 1; }
            else { who = t_cstr("someone they no longer remember"); has = 1; }
            w->trap = outer;
        }
        if (!has) { fprintf(stderr, "%s is still waiting for anyone at all\n", s->name); continue; }
        Soul *b = find(w, who);
        if (!b) { fprintf(stderr, "%s is still waiting for %s\n", s->name, cs(who)); continue; }
        if (rel(w, b, s)->left) fprintf(stderr, "%s is still waiting for %s, who left\n", s->name, b->name);
        else if (b->done) fprintf(stderr, "%s is still waiting for %s, who is gone\n", s->name, b->name);
        else fprintf(stderr, "%s is still waiting for %s\n", s->name, b->name);
    }
}

static void feelings(World *w) {
    for (size_t i = 0; i < w->nrels; i++) {
        Rel *r = w->rels[i];
        if (!r->met) continue;
        Soul *a = w->order[r->a], *b = w->order[r->b];
        cool_down(r, a);
        fprintf(stderr, "%s -> %s: %s; trust %lld, intimacy %lld, passion %lld, commitment %lld, scars %zu",
                a->name, b->name, bond_name(r), (long long)r->trust, (long long)r->intimacy,
                (long long)r->passion, (long long)r->commitment, r->scars.n);
        const char *sep = ", ";
        if (r->gift) { fprintf(stderr, "%sheart given", sep); }
        if (r->closed) { fprintf(stderr, "%sclosed", sep); }
        if (r->left) { fprintf(stderr, "%sleft", sep); }
        if (r->abandoned) { fprintf(stderr, "%sabandoned", sep); }
        fputc('\n', stderr);
    }
}

/* Returns the exit code; on an error, leaves it in w->error and returns -1. */
static int live(World *w) {
    jmp_buf trap;
    w->trap = &trap;
    Soul *volatile who = NULL;
    if (setjmp(trap)) {
        Soul *s = who;
        const Ins *ins = current(w, s);
        char *inner = w->error;
        size_t n = strlen(inner) + strlen(s->name) + 64;
        w->error = oom(malloc(n));
        if (ins) snprintf(w->error, n, "line %d, %s: %s", ins->line, s->name, inner);
        else snprintf(w->error, n, "%s: %s", s->name, inner);
        free(inner);
        step_over();
        return -1;
    }
    for (;;) {
        size_t nalive = 0;
        Soul **alive = scratch(sizeof(Soul *) * (w->nsouls ? w->nsouls : 1));
        for (size_t i = 0; i < w->nsouls; i++) if (!w->order[i]->done) alive[nalive++] = w->order[i];
        if (!nalive) return w->ending;
        Soul **list = oom(malloc(sizeof(Soul *) * nalive));
        memcpy(list, alive, sizeof(Soul *) * nalive);
        step_over();
        w->round++;
        if (w->round > w->patience) {
            fprintf(stderr, "patience ran out after %lld steps\n", (long long)w->patience);
            free(list);
            return 4;
        }
        int moved = 0;
        for (size_t k = 0; k < nalive; k++) {
            Soul *s = list[k];
            who = s;
            s->step++;
            int pc = s->pc;
            if (step_soul(w, s)) moved = 1;
            if (s->pc != pc) s->arrived = w->round;
            for (size_t f = 0; f < s->nfears;) {
                s->fears[f].left--;
                moved = 1;
                if (s->fears[f].left <= 0) s->fears[f] = s->fears[--s->nfears];
                else f++;
            }
            step_over();
        }
        if (!moved) {
            int any = 0;
            for (size_t k = 0; k < nalive; k++) {
                const Ins *ins = current(w, list[k]);
                if (ins && ins->op == OP_SILENCE) { list[k]->pc++; list[k]->arrived = w->round; any = 1; }
            }
            if (!any) { free(list); lament(w); return 2; }
        }
        free(list);
    }
}

/* -------------------------------------------------------------- history */

static void sha256(const unsigned char *data, size_t len, char out[65]) {
    static const uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
    uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    size_t total = ((len + 9 + 63) / 64) * 64;
    unsigned char *msg = oom(calloc(total, 1));
    memcpy(msg, data, len);
    msg[len] = 0x80;
    uint64_t bits = (uint64_t)len * 8;
    for (int i = 0; i < 8; i++) msg[total - 1 - i] = (unsigned char)(bits >> (8 * i));
#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
    for (size_t off = 0; off < total; off += 64) {
        uint32_t m[64];
        for (int i = 0; i < 16; i++)
            m[i] = (uint32_t)msg[off + 4 * i] << 24 | (uint32_t)msg[off + 4 * i + 1] << 16 |
                   (uint32_t)msg[off + 4 * i + 2] << 8 | msg[off + 4 * i + 3];
        for (int i = 16; i < 64; i++) {
            uint32_t s0 = ROR(m[i - 15], 7) ^ ROR(m[i - 15], 18) ^ (m[i - 15] >> 3);
            uint32_t s1 = ROR(m[i - 2], 17) ^ ROR(m[i - 2], 19) ^ (m[i - 2] >> 10);
            m[i] = m[i - 16] + s0 + m[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; i++) {
            uint32_t S1 = ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t t1 = hh + S1 + ch + k[i] + m[i];
            uint32_t S0 = ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22);
            uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t t2 = S0 + mj;
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }
#undef ROR
    free(msg);
    for (int i = 0; i < 8; i++) snprintf(out + 8 * i, 9, "%08x", h[i]);
}

static char *history_path(void) {
    const char *env = getenv("TAINTED_HISTORY");
    if (env) return strdup(env);
    const char *home = getenv("HOME");
    if (!home) home = ".";
    size_t n = strlen(home) + 32;
    char *p = oom(malloc(n));
    snprintf(p, n, "%s/.tainted/history.json", home);
    return p;
}

static void make_parents(const char *path) {
    char *p = strdup(path);
    for (char *c = p + 1; *c; c++)
        if (*c == '/') { *c = 0; mkdir(p, 0755); *c = '/'; }
    free(p);
}

/* history.json is an object of source hashes to how many times they ran. */
static int64_t remember_run(const char *source) {
    char key[65];
    sha256((const unsigned char *)source, strlen(source), key);
    char *path = history_path();
    char **keys = NULL;
    long long *counts = NULL;
    size_t n = 0;
    FILE *f = fopen(path, "r");
    if (f) {
        int c;
        while ((c = fgetc(f)) != EOF) {
            if (c != '"') continue;
            char buf[256];
            size_t k = 0;
            while ((c = fgetc(f)) != EOF && c != '"') if (k < sizeof buf - 1) buf[k++] = (char)c;
            buf[k] = 0;
            while ((c = fgetc(f)) != EOF && c != ':') {}
            long long v = 0;
            if (fscanf(f, " %lld", &v) != 1) break;
            keys = oom(realloc(keys, (n + 1) * sizeof *keys));
            counts = oom(realloc(counts, (n + 1) * sizeof *counts));
            keys[n] = strdup(buf);
            counts[n] = v;
            n++;
        }
        fclose(f);
    }
    int64_t runs = 0;
    size_t i;
    for (i = 0; i < n; i++) if (strcmp(keys[i], key) == 0) break;
    if (i < n) { runs = counts[i]; counts[i]++; }
    else {
        keys = oom(realloc(keys, (n + 1) * sizeof *keys));
        counts = oom(realloc(counts, (n + 1) * sizeof *counts));
        keys[n] = strdup(key);
        counts[n] = 1;
        n++;
    }
    make_parents(path);
    f = fopen(path, "w");
    if (f) {
        fputc('{', f);
        for (size_t j = 0; j < n; j++) fprintf(f, "%s\"%s\": %lld", j ? ", " : "", keys[j], counts[j]);
        fputc('}', f);
        fclose(f);
    }
    for (size_t j = 0; j < n; j++) free(keys[j]);
    free(keys);
    free(counts);
    free(path);
    return runs;
}

/* ----------------------------------------------------------------- main */

int tainted_main(const Program *p, int argc, char **argv) {
    static char out_buffer[1 << 16];
    setvbuf(stdout, out_buffer, _IOLBF, sizeof out_buffer);
    int64_t patience = DEFAULT_PATIENCE;
    int show_feelings = 0;
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--patience=", 11) == 0) patience = atoll(argv[i] + 11);
        else if (strcmp(argv[i], "--feelings") == 0) show_feelings = 1;
        else if (strncmp(argv[i], "--", 2) == 0) { fprintf(stderr, "unknown flag %s\n", argv[i]); return 64; }
        else { fprintf(stderr, "usage: %s [--feelings] [--patience=N]\n", argv[0]); return 64; }
    }
    World *w = oom(calloc(1, sizeof(World)));
    w->p = p;
    w->patience = patience;
    for (int u = 0; u < p->nunits; u++)
        if (p->units[u].decl == D_SOUL) new_soul(w, p->units[u].name, (int64_t)strlen(p->units[u].name), u);
    w->runs = remember_run(p->source);
    size_t k = (size_t)(w->runs % (int64_t)w->nsouls);
    if (k) {
        Soul **turned = oom(malloc(w->nsouls * sizeof(Soul *)));
        for (size_t i = 0; i < w->nsouls; i++) turned[i] = w->order[(i + k) % w->nsouls];
        memcpy(w->order, turned, w->nsouls * sizeof(Soul *));
        free(turned);
        for (size_t i = 0; i < w->nsouls; i++) {
            w->order[i]->id = (int)i;
            table_put(&w->names, w->order[i]->name, w->order[i]->nlen, (int)i);
        }
    }
    int code = live(w);
    if (code < 0) { fprintf(stderr, "tainted: %s\n", w->error); code = 1; }
    if (show_feelings) feelings(w);
    fflush(stdout);
    return code;
}
