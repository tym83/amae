/* The Tainted runtime. See tainted.h. */
#include "tainted.h"

#include <errno.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#define FADE 50
#define PASSION_FADE 50
#define PRESENT 3
#define DEFAULT_PATIENCE 10000000LL
#define DEEPEST 10000

/* ------------------------------------------------------------ memory */

typedef struct Block { struct Block *next; size_t used, size; char data[]; } Block;
static Block *arena;
static Value *doomed;
static size_t ndoomed, capdoomed;
static Obj **temps;
static size_t ntemps, captemps;

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

static Value keep(Value v);

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

/* Lists and maps. A map keeps its keys, which are words, in the order they
 * were first written. */
struct Obj {
    int kind;
    Value *v;
    char **keys;
    int64_t *klen;
    size_t n, cap;
    Table index;
};

static void free_value(Value v);

static void free_obj(Obj *o) {
    for (size_t i = 0; i < o->n; i++) {
        free_value(o->v[i]);
        if (o->keys) free(o->keys[i]);
    }
    free(o->v);
    free(o->keys);
    free(o->klen);
    for (size_t i = 0; i < o->index.cap; i++) free(o->index.e[i].key);
    free(o->index.e);
    free(o);
}

static void free_value(Value v) {
    if (v.tag == T_STR) free((void *)v.s);
    else if (v.tag == T_LIST || v.tag == T_MAP) free_obj(v.o);
}

/* Values made during a step live until the step is over; anything kept
 * longer is copied to the heap, and the heap copy it replaces is freed only
 * when the step is over, so a value still in hand never disappears. */
static void step_over(void) {
    while (arena && arena->next) { Block *b = arena->next; arena->next = b->next; free(b); }
    if (arena) arena->used = 0;
    for (size_t i = 0; i < ndoomed; i++) free_value(doomed[i]);
    ndoomed = 0;
    for (size_t i = 0; i < ntemps; i++) free_obj(temps[i]);
    ntemps = 0;
}

static void drop(Value v) {
    if (v.tag != T_STR && v.tag != T_LIST && v.tag != T_MAP) return;
    if (ndoomed == capdoomed) {
        capdoomed = capdoomed ? capdoomed * 2 : 64;
        doomed = oom(realloc(doomed, capdoomed * sizeof *doomed));
    }
    doomed[ndoomed++] = v;
}

static Obj *new_obj(int kind, int temporary) {
    Obj *o = oom(calloc(1, sizeof(Obj)));
    o->kind = kind;
    if (temporary) {
        if (ntemps == captemps) {
            captemps = captemps ? captemps * 2 : 64;
            temps = oom(realloc(temps, captemps * sizeof *temps));
        }
        temps[ntemps++] = o;
    }
    return o;
}

static void grow(Obj *o) {
    if (o->n < o->cap) return;
    o->cap = o->cap ? o->cap * 2 : 4;
    o->v = oom(realloc(o->v, o->cap * sizeof(Value)));
    if (o->kind == T_MAP) {
        o->keys = oom(realloc(o->keys, o->cap * sizeof(char *)));
        o->klen = oom(realloc(o->klen, o->cap * sizeof(int64_t)));
    }
}

/* A copy that belongs to whoever keeps it: strings, lists and maps are
 * copied all the way down. */
static Value keep(Value v) {
    if (v.tag == T_STR) {
        char *p = oom(malloc((size_t)v.n + 1));
        memcpy(p, v.s, (size_t)v.n);
        p[v.n] = 0;
        v.s = p;
        return v;
    }
    if (v.tag == T_LIST || v.tag == T_MAP) {
        Obj *o = new_obj(v.tag, 0), *from = v.o;
        o->cap = from->n;
        o->n = from->n;
        if (o->n) {
            o->v = oom(malloc(o->n * sizeof(Value)));
            if (v.tag == T_MAP) {
                o->keys = oom(malloc(o->n * sizeof(char *)));
                o->klen = oom(malloc(o->n * sizeof(int64_t)));
            }
        }
        for (size_t i = 0; i < o->n; i++) {
            o->v[i] = keep(from->v[i]);
            if (v.tag == T_MAP) {
                o->keys[i] = oom(malloc((size_t)from->klen[i] + 1));
                memcpy(o->keys[i], from->keys[i], (size_t)from->klen[i] + 1);
                o->klen[i] = from->klen[i];
                table_put(&o->index, o->keys[i], o->klen[i], (int)i);
            }
        }
        v.o = o;
    }
    return v;
}

Value t_int(int64_t i) { Value v = {0}; v.tag = T_INT; v.i = i; return v; }
Value t_dec(double d) { Value v = {0}; v.tag = T_DEC; v.d = d; return v; }
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

/* Growing text, for show and json. */
typedef struct { char *p; size_t n, cap; } Text;

static void text_add(Text *t, const char *s, size_t n) {
    if (t->n + n + 1 > t->cap) {
        t->cap = (t->n + n + 1) * 2;
        t->p = oom(realloc(t->p, t->cap));
    }
    memcpy(t->p + t->n, s, n);
    t->n += n;
    t->p[t->n] = 0;
}

static void text_c(Text *t, const char *s) { text_add(t, s, strlen(s)); }

static Value text_value(Text *t) {
    Value v = fresh(t->p ? t->p : "", (int64_t)t->n);
    free(t->p);
    return v;
}

/* The shortest decimal that reads back as the same number, with a point. */
static void decimal_text(double d, char out[40]) {
    if (d != d) { strcpy(out, "nan"); return; }
    if (d == 1.0 / 0.0) { strcpy(out, "inf"); return; }
    if (d == -1.0 / 0.0) { strcpy(out, "-inf"); return; }
    for (int p = 1; p <= 17; p++) {
        snprintf(out, 40, "%.*g", p, d);
        if (strtod(out, NULL) == d) break;
    }
    if (!strchr(out, '.') && !strchr(out, 'e') && !strchr(out, 'n')) strcat(out, ".0");
}

static void json_text(Text *t, Value v, int quoted);

static void json_string(Text *t, const char *s, int64_t n) {
    text_c(t, "\"");
    for (int64_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c == '"') text_c(t, "\\\"");
        else if (c == '\\') text_c(t, "\\\\");
        else if (c == '\n') text_c(t, "\\n");
        else if (c == '\r') text_c(t, "\\r");
        else if (c == '\t') text_c(t, "\\t");
        else if (c < 0x20) { char u[8]; snprintf(u, sizeof u, "\\u%04x", c); text_c(t, u); }
        else text_add(t, (const char *)&c, 1);
    }
    text_c(t, "\"");
}

/* Strings inside lists and maps are shown quoted, as JSON writes them. */
static void json_text(Text *t, Value v, int quoted) {
    char buf[40];
    switch (v.tag) {
    case T_INT: snprintf(buf, sizeof buf, "%lld", (long long)v.i); text_c(t, buf); break;
    case T_DEC: decimal_text(v.d, buf); text_c(t, buf); break;
    case T_STR:
        if (quoted) json_string(t, v.s, v.n); else text_add(t, v.s, (size_t)v.n);
        break;
    case T_LIST:
        text_c(t, "[");
        for (size_t i = 0; i < v.o->n; i++) { if (i) text_c(t, ", "); json_text(t, v.o->v[i], 1); }
        text_c(t, "]");
        break;
    case T_MAP:
        text_c(t, "{");
        for (size_t i = 0; i < v.o->n; i++) {
            if (i) text_c(t, ", ");
            json_string(t, v.o->keys[i], v.o->klen[i]);
            text_c(t, ": ");
            json_text(t, v.o->v[i], 1);
        }
        text_c(t, "}");
        break;
    }
}

/* A value as text, the way `say` shows it. */
static Value show(Value v) {
    if (v.tag == T_STR) return v;
    if (v.tag == T_INT) return printf_value("%lld", (long long)v.i);
    Text t = {0};
    json_text(&t, v, 0);
    return text_value(&t);
}

static const char *cs(Value v) {      /* show, terminated, for messages */
    Value t = show(v);
    char *p = scratch((size_t)t.n + 1);
    memcpy(p, t.s, (size_t)t.n);
    p[t.n] = 0;
    return p;
}

static int numeric(Value v) { return v.tag == T_INT || v.tag == T_DEC; }
static double as_double(Value v) { return v.tag == T_INT ? (double)v.i : v.d; }

static int same(Value a, Value b) {
    if (numeric(a) && numeric(b)) {
        if (a.tag == T_INT && b.tag == T_INT) return a.i == b.i;
        return as_double(a) == as_double(b);
    }
    if (a.tag != b.tag) return 0;
    if (a.tag == T_STR) return a.n == b.n && memcmp(a.s, b.s, (size_t)a.n) == 0;
    if (a.o->n != b.o->n) return 0;
    for (size_t i = 0; i < a.o->n; i++) {
        if (a.tag == T_MAP && (a.o->klen[i] != b.o->klen[i] ||
                               memcmp(a.o->keys[i], b.o->keys[i], (size_t)a.o->klen[i])))
            return 0;
        if (!same(a.o->v[i], b.o->v[i])) return 0;
    }
    return 1;
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
    int sleeping;
    double wake;
    Value last_heard;   /* what the soul heard last, which rewrites what it forgets */
    int heard_any;
    struct Letter *letters;
    size_t nletters, capletters;
    int style;          /* S_ flags: how this soul loves */
    int64_t warmth_owed;   /* storge: half a warmth not yet given */
    int partner;        /* the soul it is together with, or -1 */
    int tg_unit, tg_depth, tg_start, tg_end, tg_apart, tg_arrived;
    Table guarded;      /* notes behind this soul's boundary */
    struct Handler *handlers;   /* the enduring this soul is inside of */
    size_t nhandlers, caphandlers;
};

typedef struct Handler { int unit, depth, start, end, to, slot; } Handler;

/* A letter is on its way until the round it arrives in; it is kept until it
 * is read, even after its writer is gone. */
typedef struct Letter { int from; int64_t arrives; Value v; int read; } Letter;

/* Where the world's lines come from: standard input, and every process the
 * program listens to. */
typedef struct { int fd; char *buf; size_t n, cap; int closed; } Source;

typedef struct {
    int a, b;
    int met, gift, closed, left, abandoned;
    int64_t trust, intimacy, passion, commitment, pressure, last_meet, faded;
    int64_t distance, contact, apart_counted, attention_counted;
    int resentment, shame, hope, jealous;
    int consent;
    int64_t crossings, chemistry;
    int64_t love, close;   /* the love built so far, and the closeness not yet counted into it */
    int kindled;           /* passion has once been full: building can begin */
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
    Source *src;
    size_t nsrc, capsrc;
    int in_transit;     /* words or letters are on their way: time passes, nobody is stuck */
    int mania;          /* someone here loves like mania */
    int deterministic;  /* no chemistry */
};

int t_pc(const Soul *s) { return s->pc; }

static void grieve(World *w, Soul *s);
static void heard(Soul *s, Value v);

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
    s->partner = -1;
    s->style = w->p->units[unit].style;
    if (s->style & S_MANIA) w->mania = 1;
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

/* Distance grows by one for every FADE steps without a word or a meeting;
 * intimacy, which needs attention, falls by one for every 2 * FADE such
 * steps, or every FADE while there is resentment. */
static void settle(Rel *r, Soul *owner) {
    if (!r->met || r->left || owner->step <= r->contact) return;
    int64_t apart = owner->step - r->contact;
    int64_t due = apart / FADE;
    if (due > r->apart_counted) { r->distance += due - r->apart_counted; r->apart_counted = due; }
    int64_t every = r->resentment ? FADE : 2 * FADE;
    int64_t lost = apart / every;
    if (lost > r->attention_counted) {
        int64_t floor_ = r->intimacy < r->love ? r->intimacy : r->love;
        r->intimacy -= lost - r->attention_counted;
        if (r->intimacy < floor_) r->intimacy = floor_;   /* love holds what attention cannot */
        r->attention_counted = lost;
    }
}

#define BUILDING (3 * FADE)

/* Love is built. Passion is only the spark: until it has once been full,
 * nothing is built. After that, every BUILDING steps the two spend in touch,
 * with no resentment between them, add to it, and the more love there is the
 * more each such stretch adds: it grows stronger with time. */
static void in_touch(Rel *r, Soul *owner) {
    settle(r, owner);
    int64_t gap = owner->step - r->contact;
    if (r->met && r->kindled && gap < FADE && !r->resentment) {
        r->close += gap;
        while (r->close >= BUILDING) { r->close -= BUILDING; r->love += 1 + r->love / 5; }
    }
    r->contact = owner->step;
    r->apart_counted = 0;
    r->attention_counted = 0;
}

static void cool_down(Rel *r, Soul *owner) {
    settle(r, owner);
    /* built love brings the fire back: passion is kept at a quarter of it, up
     * to full */
    int64_t warmth = r->love / 4 < 2 * PRESENT ? r->love / 4 : 2 * PRESENT;
    if (r->passion < warmth && !r->left) r->passion = warmth;
    if (r->hope) { r->last_meet = owner->step; r->faded = 0; return; }
    if (r->met && !r->left && owner->step > r->last_meet) {
        int64_t due = (owner->step - r->last_meet) / (owner->style & S_EROS ? PASSION_FADE / 2 : PASSION_FADE);
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

static Rel *rel_if(World *w, Soul *a, Soul *b) {
    char key[16];
    memcpy(key, &a->id, sizeof(int));
    memcpy(key + sizeof(int), &b->id, sizeof(int));
    int i = table_get(&w->relindex, key, 2 * sizeof(int));
    if (i < 0) return NULL;
    cool_down(w->rels[i], a);
    return w->rels[i];
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

/* What a memory keeps after `periods` times fifty steps untouched: a number
 * loses its last digits, a decimal the last digits after its point first, a
 * word its last letters, a list its last items and a map its last keys. */
static Value fade(Value v, int64_t periods) {
    if (v.tag == T_INT) {
        if (periods >= 19) return t_int(0);
        int64_t lost = 1;
        for (int64_t k = 0; k < periods; k++) lost *= 10;
        int64_t a = v.i < 0 ? -v.i : v.i;
        return t_int((v.i < 0 ? -1 : 1) * (a / lost * lost));
    }
    if (v.tag == T_DEC) {
        char buf[40];
        decimal_text(v.d, buf);
        char *point = strchr(buf, '.');
        if (!point || strchr(buf, 'e')) return v;
        int64_t places = (int64_t)strlen(point + 1);
        if (periods < places) {
            point[1 + places - periods] = 0;
            return t_dec(strtod(buf, NULL));
        }
        double whole = v.d < 0 ? -(double)(int64_t)(-v.d) : (double)(int64_t)v.d;
        int64_t rest = periods - places;
        double lost = 1;
        for (int64_t k = 0; k < rest && k < 300; k++) lost *= 10;
        return t_dec(whole < 0 ? -((double)(int64_t)(-whole / lost)) * lost
                               : ((double)(int64_t)(whole / lost)) * lost);
    }
    if (v.tag == T_LIST || v.tag == T_MAP) {
        Obj *o = new_obj(v.tag, 1);
        size_t n = v.o->n > (size_t)periods ? v.o->n - (size_t)periods : 0;
        for (size_t i = 0; i < n; i++) {
            if (v.tag == T_LIST) t_list_push(NULL, (Value){.tag = T_LIST, .o = o}, v.o->v[i]);
            else t_map_put(NULL, (Value){.tag = T_MAP, .o = o},
                           t_str(v.o->keys[i], v.o->klen[i]), v.o->v[i]);
        }
        Value faded = {0};
        faded.tag = v.tag;
        faded.o = o;
        return faded;
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
        /* Remembering rewrites: what was lost is filled in from the end of what
         * the soul heard last, when it heard the same kind of thing. */
        if (s->heard_any && faded.tag == T_INT && s->last_heard.tag == T_INT && periods < 19) {
            int64_t lost = 1;
            for (int64_t k = 0; k < periods; k++) lost *= 10;
            int64_t tail = s->last_heard.i < 0 ? -(s->last_heard.i % lost) : s->last_heard.i % lost;
            faded.i += faded.i < 0 ? -tail : tail;
        } else if (s->heard_any && faded.tag == T_STR && m->v.tag == T_STR && s->last_heard.tag == T_STR) {
            int64_t missing = chars(m->v) - chars(faded);
            int64_t have = chars(s->last_heard);
            if (missing > have) missing = have;
            Value tail = t_str(s->last_heard.s + offset(s->last_heard, have - missing),
                               s->last_heard.n - offset(s->last_heard, have - missing));
            faded = t_bin(w, B_ADD, faded, tail);
        }
        store(m, faded, s->step);
    } else {
        m->touched = s->step;
    }
    return m->v;
}

/* ---------------------------------------------------------- expressions */

int t_truthy(Value v) {
    switch (v.tag) {
    case T_INT: return v.i != 0;
    case T_DEC: return v.d != 0;
    case T_STR: return v.n != 0;
    default: return v.o->n != 0;
    }
}

Value t_neg(World *w, Value v) {
    if (v.tag == T_DEC) return t_dec(-v.d);
    if (v.tag != T_INT) t_fail(w, "only numbers can be negated");
    if (v.i == INT64_MIN) t_fail(w, "the number grew too large to hold");
    return t_int(-v.i);
}

Value t_not(Value v) { return t_int(!t_truthy(v)); }
Value t_and(Value a, Value b) { return t_int(t_truthy(a) && t_truthy(b)); }
Value t_or(Value a, Value b) { return t_int(t_truthy(a) || t_truthy(b)); }

static int compare(Value a, Value b) {
    if (a.tag == T_INT && b.tag == T_INT) return (a.i > b.i) - (a.i < b.i);
    if (numeric(a)) { double x = as_double(a), y = as_double(b); return (x > y) - (x < y); }
    int64_t n = a.n < b.n ? a.n : b.n;
    int c = memcmp(a.s, b.s, (size_t)n);
    if (c) return c < 0 ? -1 : 1;
    return (a.n > b.n) - (a.n < b.n);
}

static Value concat(Value a, Value b) {
    Obj *o = new_obj(T_LIST, 1);
    Value l = {0};
    l.tag = T_LIST;
    l.o = o;
    for (size_t i = 0; i < a.o->n; i++) t_list_push(NULL, l, a.o->v[i]);
    for (size_t i = 0; i < b.o->n; i++) t_list_push(NULL, l, b.o->v[i]);
    return l;
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
    if (op == B_ADD && a.tag == T_LIST && b.tag == T_LIST) return concat(a, b);
    int both_numbers = numeric(a) && numeric(b);
    if (a.tag != b.tag && !both_numbers)
        t_fail(w, "cannot compare or combine '%s' and '%s'", cs(a), cs(b));
    if (op >= B_LT) {
        if (a.tag == T_LIST || a.tag == T_MAP)
            t_fail(w, "cannot compare or combine '%s' and '%s'", cs(a), cs(b));
        int c = compare(a, b);
        switch (op) {
        case B_LT: return t_int(c < 0);
        case B_GT: return t_int(c > 0);
        case B_LE: return t_int(c <= 0);
        default: return t_int(c >= 0);
        }
    }
    static const char *ops[] = {"+", "-", "*", "/", "%"};
    if (!both_numbers) t_fail(w, "'%s' works only on numbers", ops[op]);
    if (a.tag == T_DEC || b.tag == T_DEC) {
        double x = as_double(a), y = as_double(b);
        switch (op) {
        case B_ADD: return t_dec(x + y);
        case B_SUB: return t_dec(x - y);
        case B_MUL: return t_dec(x * y);
        }
        if (y == 0) t_fail(w, "a number cannot be divided by nothing");
        if (op == B_DIV) return t_dec(x / y);
        double m = fmod(x, y);
        if (m != 0 && ((m < 0) != (y < 0))) m += y;
        return t_dec(m);
    }
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

static int key_at(Obj *o, Value key) {
    Value k = show(key);
    return table_get(&o->index, k.s, k.n);
}

Value t_place(World *w, Value x, Value text) {
    if (text.tag == T_LIST) {
        for (size_t i = 0; i < text.o->n; i++) if (same(text.o->v[i], x)) return t_int((int64_t)i + 1);
        return t_int(0);
    }
    if (text.tag == T_MAP) return t_int(key_at(text.o, x) + 1);
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
    int64_t dot = -1;
    for (int64_t q = k; q < j; q++) if (text.s[q] == '.' || text.s[q] == 'e' || text.s[q] == 'E') dot = q;
    if (dot >= 0) {
        char buf[128];
        int64_t len = j - i < 127 ? j - i : 127;
        memcpy(buf, text.s + i, (size_t)len);
        buf[len] = 0;
        char *end;
        double d = strtod(buf, &end);
        if (*end || !(text.s[k] >= '0' && text.s[k] <= '9')) t_fail(w, "'%s' is not a number", cs(text));
        return t_dec(d);
    }
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
    if (text.tag == T_LIST || text.tag == T_MAP) return t_int((int64_t)text.o->n);
    if (text.tag != T_STR) t_fail(w, "only words, lists and maps have a length");
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

/* ------------------------------------------------------- lists and maps */

Value t_list_new(World *w) {
    (void)w;
    Value v = {0};
    v.tag = T_LIST;
    v.o = new_obj(T_LIST, 1);
    return v;
}

void t_list_push(World *w, Value list, Value v) {
    (void)w;
    grow(list.o);
    list.o->v[list.o->n++] = keep(v);
}

Value t_map_new(World *w) {
    (void)w;
    Value v = {0};
    v.tag = T_MAP;
    v.o = new_obj(T_MAP, 1);
    return v;
}

void t_map_put(World *w, Value map, Value key, Value v) {
    (void)w;
    Obj *o = map.o;
    Value k = show(key);
    int i = table_get(&o->index, k.s, k.n);
    if (i >= 0) { drop(o->v[i]); o->v[i] = keep(v); return; }
    grow(o);
    o->keys[o->n] = oom(malloc((size_t)k.n + 1));
    memcpy(o->keys[o->n], k.s, (size_t)k.n);
    o->keys[o->n][k.n] = 0;
    o->klen[o->n] = k.n;
    o->v[o->n] = keep(v);
    table_put(&o->index, o->keys[o->n], k.n, (int)o->n);
    o->n++;
}

static Value *item(World *w, Value x, Value i) {
    if (x.tag == T_LIST) {
        if (i.tag != T_INT || i.i < 1 || i.i > (int64_t)x.o->n)
            t_fail(w, "there is no item %s in a list of %zu", cs(i), x.o->n);
        return &x.o->v[i.i - 1];
    }
    if (x.tag == T_MAP) {
        int k = key_at(x.o, i);
        if (k < 0) t_fail(w, "there is nothing under %s", cs(i));
        return &x.o->v[k];
    }
    t_fail(w, "only lists and maps have items, not %s", cs(x));
}

Value t_index(World *w, Value x, Value i) {
    if (x.tag == T_STR) {
        if (i.tag != T_INT || i.i < 1 || i.i > chars(x))
            t_fail(w, "there is no letter %s in a word of %lld", cs(i), (long long)chars(x));
        int64_t a = offset(x, i.i - 1), b = offset(x, i.i);
        return t_str(x.s + a, b - a);
    }
    return *item(w, x, i);
}

Value t_keys(World *w, Value m) {
    if (m.tag != T_MAP) t_fail(w, "only maps have keys, not %s", cs(m));
    Value l = t_list_new(w);
    for (size_t i = 0; i < m.o->n; i++) t_list_push(w, l, t_str(m.o->keys[i], m.o->klen[i]));
    return l;
}

Value t_json(World *w, Value v) {
    (void)w;
    Text t = {0};
    json_text(&t, v, 1);
    return text_value(&t);
}

typedef struct { World *w; const char *s; int64_t n, i; Value text; } Reader;

_Noreturn static void not_json(Reader *r) {
    t_fail(r->w, "this is not json: %s", cs(r->text));
}

static void skip_space(Reader *r) { while (r->i < r->n && space(r->s[r->i])) r->i++; }

static Value read_json(Reader *r, int depth);

static Value read_json_string(Reader *r) {
    Text t = {0};
    r->i++;
    while (r->i < r->n && r->s[r->i] != '"') {
        char c = r->s[r->i++];
        if (c != '\\') { text_add(&t, &c, 1); continue; }
        if (r->i >= r->n) not_json(r);
        char e = r->s[r->i++];
        switch (e) {
        case 'n': text_c(&t, "\n"); break;
        case 't': text_c(&t, "\t"); break;
        case 'r': text_c(&t, "\r"); break;
        case 'b': text_c(&t, "\b"); break;
        case 'f': text_c(&t, "\f"); break;
        case 'u': {
            if (r->i + 4 > r->n) not_json(r);
            char hex[5] = {0};
            memcpy(hex, r->s + r->i, 4);
            r->i += 4;
            unsigned cp = (unsigned)strtoul(hex, NULL, 16);
            if (cp >= 0xD800 && cp < 0xDC00 && r->i + 6 <= r->n && r->s[r->i] == '\\' && r->s[r->i + 1] == 'u') {
                memcpy(hex, r->s + r->i + 2, 4);
                unsigned lo = (unsigned)strtoul(hex, NULL, 16);
                r->i += 6;
                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
            }
            char u[4];
            int k = 0;
            if (cp < 0x80) u[k++] = (char)cp;
            else if (cp < 0x800) { u[k++] = (char)(0xC0 | cp >> 6); u[k++] = (char)(0x80 | (cp & 0x3F)); }
            else if (cp < 0x10000) {
                u[k++] = (char)(0xE0 | cp >> 12); u[k++] = (char)(0x80 | ((cp >> 6) & 0x3F));
                u[k++] = (char)(0x80 | (cp & 0x3F));
            } else {
                u[k++] = (char)(0xF0 | cp >> 18); u[k++] = (char)(0x80 | ((cp >> 12) & 0x3F));
                u[k++] = (char)(0x80 | ((cp >> 6) & 0x3F)); u[k++] = (char)(0x80 | (cp & 0x3F));
            }
            text_add(&t, u, (size_t)k);
            break;
        }
        default: text_add(&t, &e, 1);
        }
    }
    if (r->i >= r->n) not_json(r);
    r->i++;
    return text_value(&t);
}

static Value read_json(Reader *r, int depth) {
    if (depth > 1000) not_json(r);
    skip_space(r);
    if (r->i >= r->n) not_json(r);
    char c = r->s[r->i];
    if (c == '{') {
        Value m = t_map_new(r->w);
        r->i++;
        skip_space(r);
        if (r->i < r->n && r->s[r->i] == '}') { r->i++; return m; }
        for (;;) {
            skip_space(r);
            if (r->i >= r->n || r->s[r->i] != '"') not_json(r);
            Value k = read_json_string(r);
            skip_space(r);
            if (r->i >= r->n || r->s[r->i] != ':') not_json(r);
            r->i++;
            Value v = read_json(r, depth + 1);
            t_map_put(r->w, m, k, v);
            skip_space(r);
            if (r->i < r->n && r->s[r->i] == ',') { r->i++; continue; }
            if (r->i < r->n && r->s[r->i] == '}') { r->i++; return m; }
            not_json(r);
        }
    }
    if (c == '[') {
        Value l = t_list_new(r->w);
        r->i++;
        skip_space(r);
        if (r->i < r->n && r->s[r->i] == ']') { r->i++; return l; }
        for (;;) {
            t_list_push(r->w, l, read_json(r, depth + 1));
            skip_space(r);
            if (r->i < r->n && r->s[r->i] == ',') { r->i++; continue; }
            if (r->i < r->n && r->s[r->i] == ']') { r->i++; return l; }
            not_json(r);
        }
    }
    if (c == '"') return read_json_string(r);
    if (r->n - r->i >= 4 && memcmp(r->s + r->i, "true", 4) == 0) { r->i += 4; return t_int(1); }
    if (r->n - r->i >= 5 && memcmp(r->s + r->i, "false", 5) == 0) { r->i += 5; return t_int(0); }
    if (r->n - r->i >= 4 && memcmp(r->s + r->i, "null", 4) == 0) { r->i += 4; return t_str("", 0); }
    int64_t b = r->i;
    int decimal = 0;
    if (r->i < r->n && (r->s[r->i] == '-' || r->s[r->i] == '+')) r->i++;
    while (r->i < r->n && strchr("0123456789.eE+-", r->s[r->i])) {
        if (strchr(".eE", r->s[r->i])) decimal = 1;
        r->i++;
    }
    if (r->i == b) not_json(r);
    char buf[64];
    int64_t len = r->i - b < 63 ? r->i - b : 63;
    memcpy(buf, r->s + b, (size_t)len);
    buf[len] = 0;
    char *end;
    if (!decimal) {
        errno = 0;
        long long v = strtoll(buf, &end, 10);
        if (!*end && errno == 0) return t_int(v);
    }
    double d = strtod(buf, &end);
    if (*end) not_json(r);
    return t_dec(d);
}

Value t_meaning(World *w, Value text) {
    needs_word(w, "meaning", text);
    Reader r = {w, text.s, text.n, 0, text};
    Value v = read_json(&r, 0);
    skip_space(&r);
    if (r.i != r.n) not_json(&r);
    return v;
}

Value t_whole(World *w, Value v) {
    if (v.tag == T_INT) return v;
    if (v.tag != T_DEC) t_fail(w, "only numbers have a whole part, not %s", cs(v));
    double f = floor(v.d);
    if (!(f >= -9223372036854775808.0 && f < 9223372036854775808.0))
        t_fail(w, "the number grew too large to hold");
    return t_int((int64_t)f);
}

Value t_env(World *w, Value name) {
    needs_word(w, "world", name);
    char *n = (char *)cs(name);
    const char *v = getenv(n);
    return v ? fresh(v, (int64_t)strlen(v)) : t_str("", 0);
}

static double clock_now(void) {
    const char *fixed = getenv("TAINTED_CLOCK");     /* a world whose time is set, for tests */
    if (fixed && *fixed) return strtod(fixed, NULL);
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double)tv.tv_sec + tv.tv_usec / 1e6;
}

Value t_now(World *w) { (void)w; return t_dec(floor(clock_now() * 1000) / 1000); }

Value t_feeling(World *w, Soul *s, int what, Value who) {
    Soul *b = resolve(w, s, who);
    Rel *r = rel(w, s, b);
    switch (what) {
    case F_DISTANCE: return t_int(r->distance);
    case F_RESENTMENT: return t_int(r->resentment);
    case F_HOPING: return t_int(r->hope);
    case F_JEALOUS: return t_int(r->jealous);
    case F_ASHAMED: return t_int(r->shame);
    case F_LONGING: return t_int(r->distance >= 2 && r->passion > 0);
    case F_CONSENT: return t_int(rel(w, b, s)->consent);
    case F_CROSSINGS: return t_int(r->crossings);
    case F_CHEMISTRY: return t_int(r->chemistry);
    case F_LOVE: return t_int(r->love);
    case F_PHASE:
        /* Helen Fisher's lust, attraction and attachment, and the love that
         * is built on them */
        if (!r->met) return t_cstr("strangers");
        if (r->love >= 10) return t_cstr("love");
        if (r->love >= PRESENT) return t_cstr("attachment");
        if (r->passion >= PRESENT && r->intimacy >= PRESENT) return t_cstr("attraction");
        if (r->passion >= PRESENT) return t_cstr("lust");
        return t_cstr("acquaintance");
    default: {
        int64_t n = 0;
        for (size_t i = 0; i < s->nletters; i++)
            if (!s->letters[i].read && s->letters[i].from == b->id && s->letters[i].arrives <= w->round) n++;
        return t_int(n);
    }
    }
}

static void sha256(const unsigned char *data, size_t len, char out[65]);

Value t_lineage(World *w) { return t_cstr(w->p->lineage ? w->p->lineage : ""); }
Value t_source(World *w) { return t_cstr(w->p->source); }

Value t_hash(World *w, Value text) {
    Value t = show(text);
    char *out = scratch(65);
    sha256((const unsigned char *)t.s, (size_t)t.n, out);
    (void)w;
    return t_str(out, 64);
}

Value t_lines(World *w, Value text) {
    needs_word(w, "lines", text);
    Value l = t_list_new(w);
    int64_t start = 0;
    for (int64_t i = 0; i <= text.n; i++) {
        if (i == text.n || text.s[i] == '\n') {
            if (i == text.n && start == text.n) break;
            int64_t end = i;
            if (end > start && text.s[end - 1] == '\r') end--;
            t_list_push(w, l, t_str(text.s + start, end - start));
            start = i + 1;
        }
    }
    return l;
}

static uint64_t fate_state;

Value t_fate(World *w, Value n) {
    if (n.tag != T_INT || n.i < 1) t_fail(w, "fate needs a number of choices, not %s", cs(n));
    if (!fate_state) {
        const char *seed = getenv("TAINTED_FATE");
        fate_state = seed ? strtoull(seed, NULL, 10) * 2654435761ULL + 1
                          : ((uint64_t)clock_now() * 1000003ULL) ^ ((uint64_t)getpid() << 21) ^ 0x9E3779B97F4A7C15ULL;
    }
    fate_state ^= fate_state << 13;
    fate_state ^= fate_state >> 7;
    fate_state ^= fate_state << 17;
    return t_int((int64_t)(fate_state % (uint64_t)n.i));
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
    grieve(w, s);
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
int t_goodbye(World *w, Soul *s) { grieve(w, s); s->done = 1; return 1; }
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
    free(s->mem);
    while (s->nhandlers && s->handlers[s->nhandlers - 1].depth > (int)s->nframes) s->nhandlers--;
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
    if ((a->style & S_AVOIDANT && w->round - a->arrived < 2) || (b->style & S_AVOIDANT && w->round - b->arrived < 2)) {
        w->in_transit = 1;      /* an avoidant soul comes, but late */
        return 0;
    }
    int first_sight = !ra->met && a->arrived == b->arrived;
    /* Chemistry: what nobody can declare or work out from the code. It comes
     * from the souls and from the lives the program has already lived; the
     * first life has none. */
    int64_t chemistry = 0;
    if (!ra->met && !w->deterministic && w->runs > 0) {
        const char *x = a->name, *y = b->name;
        if (strcmp(x, y) > 0) { const char *t = x; x = y; y = t; }
        uint64_t h = hash(x, (int64_t)strlen(x)) * 31 + hash(y, (int64_t)strlen(y)) + (uint64_t)w->runs * 2654435761ULL;
        chemistry = (int64_t)(h % 3) - 1;
    }
    Soul *pair[2][2] = {{a, b}, {b, a}};
    for (int k = 0; k < 2; k++) {
        const Ins *ins = current(w, pair[k][0]);
        if (ins->mode == TO_ANYONE) store(&pair[k][0]->mem[ins->var], name_of(pair[k][1]), pair[k][0]->step);
    }
    Rel *rs[2] = {ra, rb};
    for (int k = 0; k < 2; k++) {
        settle(rs[k], pair[k][0]);
        rs[k]->distance /= 2;
        rs[k]->met = 1;
        /* first sight kindles; later meetings feed passion only until it is
         * full: being in love does not grow without end */
        if (first_sight) rs[k]->passion += pair[k][0]->style & S_EROS ? 5 : 3;
        else if (rs[k]->passion < 2 * PRESENT) rs[k]->passion++;
        if (chemistry) { rs[k]->chemistry += chemistry; rs[k]->passion += chemistry; }
        if (rs[k]->passion < 0) rs[k]->passion = 0;
        if (rs[k]->passion >= PRESENT) rs[k]->kindled = 1;
        rs[k]->last_meet = pair[k][0]->step;
        rs[k]->faded = 0;
        in_touch(rs[k], pair[k][0]);
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

/* ---------------------------------------------------------------- world */

static void add_source(World *w, int fd) {
    if (w->nsrc == w->capsrc) {
        w->capsrc = w->capsrc ? w->capsrc * 2 : 4;
        w->src = oom(realloc(w->src, w->capsrc * sizeof(Source)));
    }
    memset(&w->src[w->nsrc], 0, sizeof(Source));
    w->src[w->nsrc++].fd = fd;
}

static int take_line(Source *src, Value *line, int partial) {
    char *nl = src->n ? memchr(src->buf, '\n', src->n) : NULL;
    size_t len;
    if (nl) len = (size_t)(nl - src->buf);
    else if (partial && src->n) len = src->n;
    else return 0;
    size_t used = nl ? len + 1 : len;
    size_t keepn = len;
    while (keepn > 0 && (src->buf[keepn - 1] == '\r' || src->buf[keepn - 1] == '\n')) keepn--;
    *line = fresh(src->buf, (int64_t)keepn);
    memmove(src->buf, src->buf + used, src->n - used);
    src->n -= used;
    return 1;
}

static void listen_once(Source *src) {
    struct pollfd p = {src->fd, POLLIN, 0};
    if (poll(&p, 1, 0) <= 0) return;
    if (src->cap - src->n < 65536) {
        src->cap = src->n + 65536 * 2;
        src->buf = oom(realloc(src->buf, src->cap));
    }
    ssize_t got = read(src->fd, src->buf + src->n, 65536);
    if (got <= 0) { src->closed = 1; if (src->fd > 2) close(src->fd); }
    else src->n += (size_t)got;
}

/* 1 and a line, 0 if the world has nothing to say yet, -1 once it has
 * fallen silent for good. */
static int world_line(World *w, Value *line) {
    for (size_t i = 0; i < w->nsrc; i++) if (take_line(&w->src[i], line, 0)) return 1;
    for (size_t i = 0; i < w->nsrc; i++) if (!w->src[i].closed) listen_once(&w->src[i]);
    for (size_t i = 0; i < w->nsrc; i++) if (take_line(&w->src[i], line, 0)) return 1;
    int open = 0;
    for (size_t i = 0; i < w->nsrc; i++) {
        if (w->src[i].closed && take_line(&w->src[i], line, 1)) return 1;
        if (!w->src[i].closed) open = 1;
    }
    return open ? 0 : -1;
}

/* Wait until a source has something to say or the earliest sleeper wakes. */
static void await_world(World *w, double timeout) {
    struct pollfd *p = scratch(sizeof(struct pollfd) * (w->nsrc ? w->nsrc : 1));
    int n = 0;
    for (size_t i = 0; i < w->nsrc; i++)
        if (!w->src[i].closed) { p[n].fd = w->src[i].fd; p[n].events = POLLIN; p[n].revents = 0; n++; }
    int ms = timeout < 0 ? -1 : (int)(timeout * 1000) + 1;
    if (n) poll(p, (nfds_t)n, ms);
    else if (ms > 0) usleep((useconds_t)ms * 1000);
}

static char *temp_path(const char *what) {
    const char *dir = getenv("TMPDIR");
    if (!dir || !*dir) dir = "/tmp";
    size_t n = strlen(dir) + 40;
    char *p = oom(malloc(n));
    snprintf(p, n, "%s/tainted-%s-XXXXXX", dir, what);
    int fd = mkstemp(p);
    if (fd < 0) { free(p); return NULL; }
    close(fd);
    return p;
}

int t_ask(World *w, Soul *s, int slot, Value command, int telling, Value input) {
    needs_word(w, "ask", command);
    char *in = NULL, *err = temp_path("err");
    if (!err) t_fail(w, "the world has no room to answer: %s", strerror(errno));
    if (telling) {
        in = temp_path("in");
        if (!in) t_fail(w, "the world has no room to listen: %s", strerror(errno));
        FILE *f = fopen(in, "w");
        Value t = show(input);
        if (f) { fwrite(t.s, 1, (size_t)t.n, f); fclose(f); }
    }
    const char *cmd = cs(command);
    size_t n = strlen(cmd) + strlen(err) + (in ? strlen(in) : 12) + 32;
    char *full = scratch(n);
    snprintf(full, n, "{ %s\n} <%s 2>%s", cmd, in ? in : "/dev/null", err);
    fflush(stdout);
    FILE *p = popen(full, "r");
    if (!p) { unlink(err); free(err); if (in) { unlink(in); free(in); } t_fail(w, "the world cannot be asked: %s", strerror(errno)); }
    Text out = {0};
    char buf[65536];
    size_t got;
    while ((got = fread(buf, 1, sizeof buf, p)) > 0) text_add(&out, buf, got);
    int status = pclose(p);
    if (in) { unlink(in); free(in); }
    if (status != 0) {
        char said[512] = {0};
        FILE *e = fopen(err, "r");
        if (e) { size_t k = fread(said, 1, sizeof said - 1, e); said[k] = 0; fclose(e); }
        unlink(err); free(err);
        free(out.p);
        size_t k = strlen(said);
        while (k && (said[k - 1] == '\n' || said[k - 1] == '\r')) said[--k] = 0;
        int code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
        t_fail(w, "the world said no to %s (%d): %s", cmd, code, said);
    }
    unlink(err); free(err);
    Value v = text_value(&out);
    if (v.n && v.s[v.n - 1] == '\n') v.n--;
    store(&s->mem[slot], v, s->step);
    advance(s);
    return 1;
}

int t_listen(World *w, Soul *s, Value command) {
    needs_word(w, "listen", command);
    int fds[2];
    if (pipe(fds) < 0) t_fail(w, "the world cannot be listened to: %s", strerror(errno));
    fflush(stdout);
    pid_t pid = fork();
    if (pid < 0) t_fail(w, "the world cannot be listened to: %s", strerror(errno));
    if (pid == 0) {
        close(fds[0]);
        dup2(fds[1], 1);
        close(fds[1]);
        int null = open("/dev/null", O_RDONLY);
        if (null >= 0) { dup2(null, 0); close(null); }
        execl("/bin/sh", "sh", "-c", cs(command), (char *)NULL);
        _exit(127);
    }
    close(fds[1]);
    add_source(w, fds[0]);
    advance(s);
    return 1;
}

int t_read(World *w, Soul *s, int slot, Value file) {
    needs_word(w, "read", file);
    FILE *f = fopen(cs(file), "rb");
    if (!f) t_fail(w, "there is no reading %s: %s", cs(file), strerror(errno));
    Text t = {0};
    char buf[65536];
    size_t got;
    while ((got = fread(buf, 1, sizeof buf, f)) > 0) text_add(&t, buf, got);
    fclose(f);
    store(&s->mem[slot], text_value(&t), s->step);
    advance(s);
    return 1;
}

int t_write(World *w, Soul *s, Value v, Value file, int append) {
    needs_word(w, append ? "append" : "write", file);
    FILE *f = fopen(cs(file), append ? "ab" : "wb");
    if (!f) t_fail(w, "there is no writing %s: %s", cs(file), strerror(errno));
    Value t = show(v);
    fwrite(t.s, 1, (size_t)t.n, f);
    fclose(f);
    advance(s);
    return 1;
}

int t_sleep(World *w, Soul *s, Value seconds) {
    if (!numeric(seconds)) t_fail(w, "a soul can wait a number of seconds, not %s", cs(seconds));
    if (!s->sleeping) { s->sleeping = 1; s->wake = clock_now() + as_double(seconds); }
    if (clock_now() < s->wake) return 0;
    s->sleeping = 0;
    advance(s);
    return 1;
}

int t_send(World *w, Soul *s, const Ins *ins) {
    Soul *b = resolve(w, s, target(w, s, ins));
    Rel *r = known(w, s, b);
    Value v = ins->a(w, s);
    if (b->nletters == b->capletters) {
        b->capletters = b->capletters ? b->capletters * 2 : 8;
        b->letters = oom(realloc(b->letters, b->capletters * sizeof(Letter)));
    }
    Letter *l = &b->letters[b->nletters++];
    l->from = s->id;
    l->arrives = w->round + r->distance;
    l->v = keep(v);
    l->read = 0;
    in_touch(r, s);
    advance(s);
    return 1;
}

int t_receive(World *w, Soul *s, const Ins *ins) {
    Soul *from = NULL;
    if (ins->mode == TO_NAMED) {
        from = resolve(w, s, target(w, s, ins));
        known(w, s, from);
    }
    for (size_t i = 0; i < s->nletters; i++) {
        Letter *l = &s->letters[i];
        if (l->read || (from && l->from != from->id)) continue;
        if (l->arrives > w->round) { w->in_transit = 1; continue; }
        Soul *writer = w->order[l->from];
        Rel *r = rel(w, s, writer);
        if (r->closed) continue;
        l->read = 1;
        store(&s->mem[ins->var], l->v, s->step);
        if (ins->var2 >= 0) store(&s->mem[ins->var2], name_of(writer), s->step);
        list_push(&r->heard, l->v);
        heard(s, l->v);
        in_touch(r, s);
        advance(s);
        return 1;
    }
    return 0;
}

/* Letters from souls that are gone cannot be stopped, only read: whatever a
 * soul has not read of them when it ends stays with it as scars. */
static void grieve(World *w, Soul *s) {
    for (size_t i = 0; i < s->nletters; i++) {
        Letter *l = &s->letters[i];
        if (l->read || !w->order[l->from]->done) continue;
        l->read = 1;
        list_push(&rel(w, s, w->order[l->from])->scars, l->v);
    }
}

int t_apologize(World *w, Soul *s, const Ins *ins, Value scar) {
    Soul *b = resolve(w, s, target(w, s, ins));
    Rel *mine = known(w, s, b);
    Rel *them = rel(w, b, s);
    Value wound = printf_value("wounded by %s", s->name);
    if (scar.tag != T_INT || scar.i < 1 || scar.i > (int64_t)them->scars.n || !same(them->scars.v[scar.i - 1], wound))
        t_fail(w, "%s's scar %s is not a wound %s gave", b->name, cs(scar), s->name);
    them->resentment = 0;
    mine->shame = 0;
    them->trust++;
    if (them->love) them->love++;     /* what love lives through, it is built of */
    if (mine->love) mine->love++;
    list_push(&them->scars, printf_value("%s apologized for: wounded by %s", s->name, s->name));
    advance(s);
    return 1;
}

/* -------------------------------------------------- together, boundaries */

static void pull_up(World *w, Soul *s, int depth) {
    while ((int)s->nframes > depth) {
        Frame f = s->frames[--s->nframes];
        const Unit *u = unit_of(w, s);
        for (int i = 0; i < u->nslots; i++) if (s->mem[i].set) drop(s->mem[i].v);
        free(s->mem);
        int64_t held = s->step - f.began;
        s->unit = f.unit;
        s->mem = f.mem;
        const Unit *back = unit_of(w, s);
        for (int i = 0; i < back->nslots; i++) if (s->mem[i].set) s->mem[i].touched += held;
    }
}

static void begin_together(Soul *s, Soul *p, const Ins *ins) {
    s->partner = p->id;
    s->tg_unit = s->unit;
    s->tg_depth = (int)s->nframes;
    s->tg_start = s->pc + 1;
    s->tg_end = ins->until;
    s->tg_apart = ins->jump;
    s->tg_arrived = 0;
    s->pc++;
}

int t_together(World *w, Soul *s, const Ins *ins) {
    Soul *b = resolve(w, s, target(w, s, ins));
    Rel *mine = known(w, s, b), *theirs = rel(w, b, s);
    if (!mine->consent || !theirs->consent || theirs->left) return 0;
    const Ins *bi = current(w, b);
    if (!bi || bi->op != OP_TOGETHER || b->partner >= 0) return 0;
    if (!same(target(w, b, bi), name_of(s))) return 0;
    begin_together(s, b, ins);
    begin_together(b, s, bi);
    in_touch(mine, s);
    in_touch(theirs, b);
    return 1;
}

int t_together_end(World *w, Soul *s, const Ins *ins) {
    Soul *p = w->order[s->partner];
    s->tg_arrived = 1;
    const Ins *pi = current(w, p);
    if (!p->tg_arrived || p->partner != s->id || !pi || pi->op != OP_TOGETHER_END) return 0;
    s->pc = ins->jump;
    p->pc = pi->jump;
    s->partner = p->partner = -1;
    return 1;
}

/* A soul together with another goes apart as soon as either withdraws its
 * consent, leaves, or is gone; both go to their `apart`, wherever they were,
 * and the rituals they were in are let go. */
static int still_together(World *w, Soul *s) {
    if (s->partner < 0) return 1;
    Soul *p = w->order[s->partner];
    Rel *mine = rel(w, s, p), *theirs = rel(w, p, s);
    int unit = s->unit, pc = s->pc;
    if (s->tg_depth < (int)s->nframes) { unit = s->frames[s->tg_depth].unit; pc = s->frames[s->tg_depth].pc - 1; }
    if (s->tg_depth > (int)s->nframes || unit != s->tg_unit || pc < s->tg_start || pc > s->tg_end) {
        s->partner = -1;        /* it left the block some other way */
        return 1;
    }
    if (mine->consent && theirs->consent && !mine->left && !theirs->left && !p->done && p->partner == s->id)
        return 1;
    pull_up(w, s, s->tg_depth);
    s->pc = s->tg_apart;
    s->partner = -1;
    return 0;
}

int t_guard(World *w, Soul *s, Value key) {
    (void)w;
    Value k = show(key);
    table_put(&s->guarded, k.s, k.n, 1);
    advance(s);
    return 1;
}

Value t_note_of(World *w, Soul *s, Value key, Value who) {
    Soul *b = resolve(w, s, who);
    Rel *mine = known(w, s, b), *theirs = rel(w, b, s);
    Value k = show(key);
    if (table_get(&b->guarded, k.s, k.n) >= 0) {
        if (!theirs->gift) t_fail(w, "%s keeps %s behind a boundary %s may not cross", b->name, cs(k), s->name);
        mine->crossings++;
        theirs->crossings++;
    } else if (theirs->trust < 1) {
        t_fail(w, "%s does not trust %s with %s", b->name, s->name, cs(k));
    }
    int i = table_get(&b->notes, k.s, k.n);
    if (i < 0) t_fail(w, "%s never wrote down %s", b->name, cs(k));
    return b->notev[i];
}

int t_endure(World *w, Soul *s, const Ins *ins) {
    (void)w;
    if (s->nhandlers == s->caphandlers) {
        s->caphandlers = s->caphandlers ? s->caphandlers * 2 : 4;
        s->handlers = oom(realloc(s->handlers, s->caphandlers * sizeof(Handler)));
    }
    Handler *h = &s->handlers[s->nhandlers++];
    h->unit = s->unit;
    h->depth = (int)s->nframes;
    h->start = s->pc + 1;
    h->end = ins->until;
    h->to = ins->jump;
    h->slot = ins->var;
    advance(s);
    return 1;
}

int t_endured(World *w, Soul *s, int to) {
    (void)w;
    if (s->nhandlers) {
        Handler *h = &s->handlers[s->nhandlers - 1];
        if (h->unit == s->unit && h->depth == (int)s->nframes) s->nhandlers--;
    }
    s->pc = to;
    return 1;
}

/* -------------------------------------------------- lists and maps, deeds */

static Value *place_in(World *w, Soul *s, int slot, int n, const Value *path) {
    (void)t_var(w, s, slot);
    Value *v = &s->mem[slot].v;
    for (int i = 0; i < n; i++) v = item(w, *v, path[i]);
    return v;
}

int t_set(World *w, Soul *s, int slot, int n, const Value *path, Value v) {
    Value *box = place_in(w, s, slot, n - 1, path);
    Value i = path[n - 1];
    if (box->tag == T_MAP) {
        t_map_put(w, *box, i, v);
    } else if (box->tag == T_LIST) {
        if (i.tag != T_INT || i.i < 1 || i.i > (int64_t)box->o->n)
            t_fail(w, "there is no item %s in a list of %zu", cs(i), box->o->n);
        Value kept = keep(v);
        drop(box->o->v[i.i - 1]);
        box->o->v[i.i - 1] = kept;
    } else {
        t_fail(w, "only lists and maps have items, not %s", cs(*box));
    }
    advance(s);
    return 1;
}

int t_put(World *w, Soul *s, int slot, int n, const Value *path, Value v) {
    Value *box = place_in(w, s, slot, n, path);
    if (box->tag != T_LIST) t_fail(w, "only a list can be put into, not %s", cs(*box));
    t_list_push(w, *box, v);
    advance(s);
    return 1;
}

int t_remove(World *w, Soul *s, int slot, int n, const Value *path, Value key) {
    Value *box = place_in(w, s, slot, n, path);
    Obj *o;
    size_t at;
    if (box->tag == T_LIST) {
        o = box->o;
        if (key.tag != T_INT || key.i < 1 || key.i > (int64_t)o->n)
            t_fail(w, "there is no item %s in a list of %zu", cs(key), o->n);
        at = (size_t)key.i - 1;
    } else if (box->tag == T_MAP) {
        o = box->o;
        int k = key_at(o, key);
        if (k < 0) t_fail(w, "there is nothing under %s", cs(key));
        at = (size_t)k;
    } else {
        t_fail(w, "only lists and maps have items, not %s", cs(*box));
    }
    drop(o->v[at]);
    memmove(&o->v[at], &o->v[at + 1], (o->n - at - 1) * sizeof(Value));
    if (o->kind == T_MAP) {
        free(o->keys[at]);
        memmove(&o->keys[at], &o->keys[at + 1], (o->n - at - 1) * sizeof(char *));
        memmove(&o->klen[at], &o->klen[at + 1], (o->n - at - 1) * sizeof(int64_t));
    }
    o->n--;
    if (o->kind == T_MAP) {
        for (size_t i = 0; i < o->index.cap; i++) free(o->index.e[i].key);
        free(o->index.e);
        memset(&o->index, 0, sizeof o->index);
        for (size_t i = 0; i < o->n; i++) table_put(&o->index, o->keys[i], o->klen[i], (int)i);
    }
    advance(s);
    return 1;
}

static void heard(Soul *s, Value v) {
    if (s->heard_any) drop(s->last_heard);
    s->last_heard = keep(v);
    s->heard_any = 1;
}

/* Whoever gave their heart to someone who confides in another is jealous. */
static void jealousy(World *w, Soul *snd, Soul *rcv, int only_mania) {
    for (size_t i = 0; i < w->nsouls; i++) {
        Soul *a = w->order[i];
        if (a == snd || a == rcv) continue;
        if (only_mania && !(a->style & S_MANIA)) continue;
        Rel *r = rel_if(w, a, snd);
        if (!r || !r->gift || r->left) continue;
        r->jealous = 1;
        r->passion += a->style & S_MANIA ? 2 : 1;
        if (r->intimacy > 0) r->intimacy--;
    }
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
    if (rr->love < 6 && w->round - snd->arrived < rs->distance) { w->in_transit = 1; return 0; }  /* still on their way */
    if (rcv->style & S_AVOIDANT && w->round - rcv->arrived < 2) { w->in_transit = 1; return 0; }
    if (si->op == OP_CONFIDE && !rs->gift)
        t_fail(w, "%s can confide only in someone they gave their heart to", snd->name);
    Value value = si->a(w, snd);
    store(&rcv->mem[ri->var], value, rcv->step);
    if (ri->var2 >= 0) store(&rcv->mem[ri->var2], name_of(snd), rcv->step);
    list_push(&rr->heard, value);
    heard(rcv, value);
    in_touch(rs, snd);
    in_touch(rr, rcv);
    if (rr->pressure > 0 && !rr->resentment) { rs->intimacy++; rr->intimacy++; }
    rr->pressure = 0;
    if (si->tender) { if (!rr->resentment) rr->intimacy++; }
    else rs->pressure++;
    if (si->op == OP_CONFIDE) jealousy(w, snd, rcv, 0);
    else if (w->mania) jealousy(w, snd, rcv, 1);
    if (rs->pressure > rr->intimacy + 2 + rr->love) {
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
        Value line;
        int got = world_line(w, &line);
        if (got == 0) return 0;     /* the world is slow, not silent */
        store(&s->mem[ins->var], got > 0 ? line : t_int(0), s->step);
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
    case OP_WARM:
        if (s->style & S_STORGE) { if (++s->warmth_owed % 2 == 0) mine->trust++; }
        else mine->trust++;
        break;
    case OP_COOL: if (mine->trust > 0 && !(s->style & S_STORGE)) mine->trust--; break;
    case OP_PROMISE: if (!(s->style & S_LUDUS)) mine->commitment++; break;
    case OP_GIVE:
        if (s->style & S_PRAGMA && mine->trust < 3)
            t_fail(w, "%s gives its heart only where it trusts, and trusts %s only %lld", s->name, b->name,
                   (long long)mine->trust);
        /* a heart is given to one at a time: whoever had it loses it, and both know */
        for (size_t i = 0; i < w->nsouls; i++) {
            Soul *c = w->order[i];
            if (c == b || c == s) continue;
            Rel *before = rel_if(w, s, c);
            if (!before || !before->gift) continue;
            before->gift = 0;
            list_push(&before->scars, printf_value("gave my heart to %s", b->name));
            list_push(&rel(w, c, s)->scars, printf_value("%s gave their heart to %s", s->name, b->name));
        }
        mine->gift = 1;
        break;
    case OP_FORGIVE: mine->closed = 0; break;
    case OP_TAKE_BACK: mine->gift = 0; break;
    case OP_CONSENT: mine->consent = 1; break;
    case OP_WITHDRAW: mine->consent = 0; break;
    case OP_HOPE: mine->hope = 1; break;
    case OP_ADMIT: mine->resentment = 0; break;
    case OP_THANK: {
        mine->commitment++;
        Rel *them = rel(w, b, s);
        if (them->met && !them->resentment) them->intimacy++;
        break;
    }
    case OP_WOUND: {
        Rel *them = rel(w, b, s);
        them->trust = b->style & S_STORGE ? them->trust / 2 : 0;
        them->intimacy /= 2;
        list_push(&them->scars, printf_value("wounded by %s", s->name));
        if (!them->gift && !(b->style & S_AGAPE) && them->love < 3) them->closed = 1;
        them->resentment = !(b->style & S_AGAPE) && them->love < 6;
        if (them->gift) mine->shame = 1;
        break;
    }
    case OP_LEAVE: {
        Rel *them = rel(w, b, s);
        mine->left = 1;
        mine->commitment = 0;
        if (!(s->style & S_LUDUS))
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
        grieve(w, s);
        s->done = 1;
        return 1;
    }
    if (!still_together(w, s)) return 1;
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
        if (ins && ins->op == OP_TOGETHER_END && s->partner >= 0) {
            fprintf(stderr, "%s is still waiting for %s to finish what they do together\n",
                    s->name, w->order[s->partner]->name);
            continue;
        }
        if (ins && (ins->op == OP_MEET || ins->op == OP_TELL || ins->op == OP_CONFIDE || ins->op == OP_HEAR
                    || ins->op == OP_TOGETHER || ins->op == OP_RECEIVE)
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
        else if (rel(w, s, b)->hope) fprintf(stderr, "%s is still waiting for %s, and still hopes\n", s->name, b->name);
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

/* A soul that is inside `endure` when something goes wrong goes on where its
 * enduring says, with the pain in hand; the rituals it was in are let go. */
static int endure_pain(World *w, Soul *s) {
    while (s->nhandlers) {
        Handler h = s->handlers[--s->nhandlers];
        if (h.depth > (int)s->nframes) continue;
        int unit = s->unit, pc = s->pc;
        if (h.depth < (int)s->nframes) { unit = s->frames[h.depth].unit; pc = s->frames[h.depth].pc - 1; }
        if (unit != h.unit || pc < h.start || pc >= h.end) continue;
        while ((int)s->nframes > h.depth) {
            Frame f = s->frames[--s->nframes];
            const Unit *u = unit_of(w, s);
            for (int i = 0; i < u->nslots; i++) if (s->mem[i].set) drop(s->mem[i].v);
            free(s->mem);
            int64_t held = s->step - f.began;
            s->unit = f.unit;
            s->mem = f.mem;
            const Unit *back = unit_of(w, s);
            for (int i = 0; i < back->nslots; i++) if (s->mem[i].set) s->mem[i].touched += held;
        }
        s->pc = h.to;
        store(&s->mem[h.slot], t_cstr(w->error), s->step);
        return 1;
    }
    return 0;
}

/* One step of one soul: 1 if it did something, 0 if it waits, -1 if it made
 * a mistake nobody endures (the error is then in w->error). */
static int attempt(World *w, Soul *s) {
    jmp_buf trap;
    jmp_buf *outer = w->trap;
    w->trap = &trap;
    if (setjmp(trap)) {
        w->trap = outer;
        if (endure_pain(w, s)) return 1;
        const Ins *ins = current(w, s);
        char *inner = w->error;
        size_t n = strlen(inner) + strlen(s->name) + 64;
        w->error = oom(malloc(n));
        const char *file = unit_of(w, s)->file;
        n += file ? strlen(file) : 0;
        w->error = oom(realloc(w->error, n));
        if (ins && file) snprintf(w->error, n, "line %d of %s, %s: %s", ins->line, file, s->name, inner);
        else if (ins) snprintf(w->error, n, "line %d, %s: %s", ins->line, s->name, inner);
        else snprintf(w->error, n, "%s: %s", s->name, inner);
        free(inner);
        return -1;
    }
    int r = step_soul(w, s);
    w->trap = outer;
    return r;
}

/* Is anyone waiting for the world or for time? Then nobody is stuck: the
 * world is only slow. Returns how long to wait, or -2 if no one waits. */
static double waiting_for_world(World *w, Soul **alive, size_t n) {
    double soonest = -1;
    int world = 0, sleepers = 0;
    for (size_t k = 0; k < n; k++) {
        const Ins *ins = current(w, alive[k]);
        if (!ins) continue;
        if (ins->op == OP_HEAR && ins->mode == TO_WORLD) world = 1;
        if (ins->op == OP_SLEEP && alive[k]->sleeping) {
            double left = alive[k]->wake - clock_now();
            if (left < 0) left = 0;
            if (!sleepers || left < soonest) soonest = left;
            sleepers = 1;
        }
    }
    if (world) {
        int open = 0;
        for (size_t i = 0; i < w->nsrc; i++) if (!w->src[i].closed) open = 1;
        if (open) return sleepers ? soonest : -1;
    }
    return sleepers ? soonest : -2;
}

/* Returns the exit code; on an error, leaves it in w->error and returns -1. */
static int live(World *w) {
    jmp_buf trap;
    w->trap = &trap;
    for (;;) {
        size_t nalive = 0;
        Soul **alive = scratch(sizeof(Soul *) * (w->nsouls ? w->nsouls : 1));
        for (size_t i = 0; i < w->nsouls; i++) if (!w->order[i]->done) alive[nalive++] = w->order[i];
        if (!nalive) return w->ending;
        Soul **list = oom(malloc(sizeof(Soul *) * nalive));
        memcpy(list, alive, sizeof(Soul *) * nalive);
        step_over();
        w->round++;
        if (w->patience > 0 && w->round > w->patience) {
            fprintf(stderr, "patience ran out after %lld steps\n", (long long)w->patience);
            free(list);
            return 4;
        }
        int moved = 0;
        w->in_transit = 0;
        for (size_t k = 0; k < nalive; k++) {
            Soul *s = list[k];
            s->step++;
            int pc = s->pc;
            if (s->style & (S_ANXIOUS | S_MANIA) && s->step % 4 == 0) {
                /* it spends this step asking whether the other is still there */
                const Ins *ins = current(w, s);
                if (ins && ins->mode == TO_NAMED && ins->target &&
                    (ins->op == OP_MEET || ins->op == OP_HEAR || ins->op == OP_TELL || ins->op == OP_TOGETHER)) {
                    jmp_buf quiet, *outer = w->trap;
                    w->trap = &quiet;
                    if (setjmp(quiet) == 0) {
                        Value who = target(w, s, ins);
                        Soul *b = find(w, who);
                        if (b && b != s) { Rel *r = rel_if(w, s, b); if (r && r->met) r->pressure++; }
                    }
                    w->trap = outer;
                }
                w->in_transit = 1;
                step_over();
                continue;
            }
            int r = attempt(w, s);
            if (r < 0) { free(list); step_over(); return -1; }
            if (r) moved = 1;
            if (s->pc != pc) s->arrived = w->round;
            for (size_t f = 0; f < s->nfears;) {
                s->fears[f].left--;
                moved = 1;
                if (s->fears[f].left <= 0) s->fears[f] = s->fears[--s->nfears];
                else f++;
            }
            step_over();
        }
        if (!moved && w->in_transit) { free(list); continue; }
        if (!moved) {
            double wait = waiting_for_world(w, list, nalive);
            if (wait > -2) {
                await_world(w, wait);
                free(list);
                continue;
            }
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
    int deterministic = p->deterministic || (getenv("TAINTED_DETERMINISTIC") && *getenv("TAINTED_DETERMINISTIC"));
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--patience=", 11) == 0) patience = atoll(argv[i] + 11);
        else if (strcmp(argv[i], "--feelings") == 0) show_feelings = 1;
        else if (strcmp(argv[i], "--deterministic") == 0) deterministic = 1;
        else if (strcmp(argv[i], "--lineage") == 0) {
            fputs(p->lineage && *p->lineage ? p->lineage : "made by no compiler that remembers\n", stdout);
            return 0;
        }
        else if (strncmp(argv[i], "--", 2) == 0) { fprintf(stderr, "unknown flag %s\n", argv[i]); return 64; }
        else { fprintf(stderr, "usage: %s [--feelings] [--patience=N]\n", argv[0]); return 64; }
    }
    World *w = oom(calloc(1, sizeof(World)));
    w->p = p;
    add_source(w, 0);
    w->patience = patience;
    w->deterministic = deterministic;
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
