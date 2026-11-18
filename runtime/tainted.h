/* The Tainted runtime: what every compiled Tainted program links against.
 *
 * The compiler turns every soul, kind and ritual into a unit: a table of
 * instructions that other souls can look at (to see whether this soul is
 * waiting to meet them, or to tell them something) and a step function that
 * carries out one instruction. Expressions become C functions. The runtime
 * owns everything that happens between souls: rounds, meetings, words,
 * feelings, memory and the world.
 */
#ifndef TAINTED_H
#define TAINTED_H

#include <stdint.h>

typedef struct World World;
typedef struct Soul Soul;

enum { T_INT = 0, T_STR = 1, T_DEC = 2, T_LIST = 3, T_MAP = 4 };

typedef struct Obj Obj;

typedef struct Value {
    int64_t i;          /* the number, for T_INT */
    double d;           /* the number, for T_DEC */
    const char *s;      /* the bytes, for T_STR; not necessarily terminated */
    int64_t n;          /* the length in bytes, for T_STR */
    Obj *o;             /* the items, for T_LIST and T_MAP */
    int tag;
} Value;

typedef Value (*Expr)(World *, Soul *);
typedef int (*Step)(World *, Soul *);

enum {
    OP_LET, OP_SAY, OP_MEET, OP_TELL, OP_CONFIDE, OP_HEAR, OP_WARM, OP_COOL,
    OP_PROMISE, OP_GIVE, OP_WOUND, OP_FORGIVE, OP_LEAVE, OP_WAIT, OP_SILENCE,
    OP_RECALL, OP_GOODBYE, OP_NOTE, OP_BRING, OP_PERFORM, OP_GIVEBACK,
    OP_JZ, OP_JMP, OP_FIRST, OP_CRY,
    OP_SET, OP_PUT, OP_REMOVE, OP_ASK, OP_LISTEN, OP_READ, OP_WRITE, OP_APPEND,
    OP_SLEEP, OP_ENDURE, OP_ENDURED,
    OP_SEND, OP_RECEIVE, OP_THANK, OP_HOPE, OP_ADMIT, OP_APOLOGIZE, OP_TAKE_BACK,
    OP_CONSENT, OP_WITHDRAW, OP_TOGETHER, OP_TOGETHER_END, OP_GUARD
};

enum { TO_NAMED = 0, TO_ANYONE = 1, TO_WORLD = 2 };

typedef struct Ins {
    int op;
    int line;
    int mode;           /* meet and hear: TO_NAMED, TO_ANYONE or TO_WORLD */
    Expr target;        /* the soul it is about, when named */
    int var;            /* the variable it fills: hear, meet anyone, let, perform into */
    int var2;           /* hear anyone ... from */
    Expr a, b;          /* the values it needs */
    int jump;           /* jz, jmp and first; where endure goes when it hurts */
    int until;          /* endure: where the enduring ends */
    int tender;         /* tell ... tenderly */
    int unit;           /* the ritual performed or the kind brought, -1 if none */
    const char *name;   /* its name, for errors */
    int nargs;
    const Expr *args;   /* perform with */
    int nvars;
    const int *vars;    /* recall */
} Ins;

enum { D_SOUL = 0, D_KIND = 1, D_RITUAL = 2 };

typedef struct Unit {
    int decl;
    const char *name;
    int nins;
    const Ins *ins;
    int nslots;
    const char *const *slots;
    int nparams;
    const int *params;
    Step step;
    const char *file;   /* the file it was learned from, or 0 for the program itself */
    int style;          /* how a soul of this unit loves: S_ flags */
} Unit;

enum { S_ANXIOUS = 1, S_AVOIDANT = 2, S_SECURE = 4, S_EROS = 8, S_LUDUS = 16, S_STORGE = 32,
       S_PRAGMA = 64, S_MANIA = 128, S_AGAPE = 256 };

typedef struct Program {
    int nunits;
    const Unit *units;
    const char *source;
    int deterministic;  /* no chemistry: the program said so */
} Program;

int tainted_main(const Program *program, int argc, char **argv);

/* What compiled code calls. */
int t_pc(const Soul *s);
_Noreturn void t_fail(World *w, const char *fmt, ...);
Value t_int(int64_t i);
Value t_str(const char *s, int64_t n);
Value t_cstr(const char *s);
int t_truthy(Value v);
Value t_var(World *w, Soul *s, int slot);
Value t_neg(World *w, Value v);
Value t_not(Value v);
Value t_and(Value a, Value b);
Value t_or(Value a, Value b);
Value t_bin(World *w, int op, Value a, Value b);
Value t_me(World *w, Soul *s);
Value t_runs(World *w);
Value t_rel(World *w, Soul *s, int what, Value who);
Value t_afraid(World *w, Soul *s, Value who);
Value t_bond(World *w, Soul *s, Value who);
Value t_scars(World *w, Soul *s, Value who);
Value t_scar(World *w, Soul *s, Value idx, Value who);
Value t_note_get(World *w, Soul *s, Value key);
Value t_word(World *w, Value idx, Value text);
Value t_words(World *w, Value text);
Value t_place(World *w, Value x, Value text);
Value t_number(World *w, Value text);
Value t_length(World *w, Value text);
Value t_part(World *w, Value a, Value b, Value text);
Value t_dec(double d);
Value t_list_new(World *w);
void t_list_push(World *w, Value list, Value v);
Value t_map_new(World *w);
void t_map_put(World *w, Value map, Value key, Value v);
Value t_index(World *w, Value x, Value i);
Value t_keys(World *w, Value m);
Value t_json(World *w, Value v);
Value t_meaning(World *w, Value text);
Value t_whole(World *w, Value v);
Value t_env(World *w, Value name);
Value t_now(World *w);
Value t_fate(World *w, Value n);
Value t_lines(World *w, Value text);
Value t_feeling(World *w, Soul *s, int what, Value who);
enum { F_DISTANCE, F_RESENTMENT, F_HOPING, F_JEALOUS, F_ASHAMED, F_LONGING, F_LETTERS,
       F_CONSENT, F_CROSSINGS, F_CHEMISTRY, F_ATTACHMENT, F_PHASE };
Value t_note_of(World *w, Soul *s, Value key, Value who);

enum { B_ADD, B_SUB, B_MUL, B_DIV, B_MOD, B_EQ, B_NE, B_LT, B_LE, B_GT, B_GE };
enum { R_TRUST, R_INTIMACY, R_PASSION, R_COMMITMENT };

/* Instructions. Each returns 1 if the soul did something, 0 if it waits. */
int t_let(World *w, Soul *s, int slot, Value v);
int t_say(World *w, Soul *s, Value v);
int t_cry(World *w, Soul *s, Value v);
int t_goodbye_with(World *w, Soul *s, Value code);
int t_note(World *w, Soul *s, Value key, Value v);
int t_jz(World *w, Soul *s, Value cond, int to);
int t_jmp(World *w, Soul *s, int to);
int t_first(World *w, Soul *s, int to);
int t_wait(World *w, Soul *s);
int t_goodbye(World *w, Soul *s);
int t_silence(World *w, Soul *s);
int t_recall(World *w, Soul *s, const Ins *ins);
int t_bring(World *w, Soul *s, const Ins *ins);
int t_perform(World *w, Soul *s, const Ins *ins);
int t_giveback(World *w, Soul *s, Value v);
int t_meet(World *w, Soul *s, const Ins *ins);
int t_tell(World *w, Soul *s, const Ins *ins);
int t_hear(World *w, Soul *s, const Ins *ins);
int t_feel(World *w, Soul *s, const Ins *ins);
/* path: the variable, then the indexes inside it */
int t_set(World *w, Soul *s, int slot, int n, const Value *path, Value v);
int t_put(World *w, Soul *s, int slot, int n, const Value *path, Value v);
int t_remove(World *w, Soul *s, int slot, int n, const Value *path, Value key);
int t_ask(World *w, Soul *s, int slot, Value command, int telling, Value input);
int t_listen(World *w, Soul *s, Value command);
int t_read(World *w, Soul *s, int slot, Value file);
int t_write(World *w, Soul *s, Value v, Value file, int append);
int t_sleep(World *w, Soul *s, Value seconds);
int t_endure(World *w, Soul *s, const Ins *ins);
int t_endured(World *w, Soul *s, int to);
int t_send(World *w, Soul *s, const Ins *ins);
int t_receive(World *w, Soul *s, const Ins *ins);
int t_apologize(World *w, Soul *s, const Ins *ins, Value scar);
int t_together(World *w, Soul *s, const Ins *ins);
int t_together_end(World *w, Soul *s, const Ins *ins);
int t_guard(World *w, Soul *s, Value key);

#endif
