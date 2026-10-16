/* vxcore: the postings kernels of the memory structure (L-PUB-160..).  Plain C11, no dependencies, exact integer arithmetic only.
 *
 * A Tier keeps, for every unit id, the sorted sids of the sentences that hold the unit and, in parallel, the index of the unit's FIRST occurrence in that sentence's unit
 * list.  The three answers are the integers of verantyx.line3.space.TierSpace:
 *   n(u)         = |postings(u)|
 *   n_pair(u,v)  = |postings(u) & postings(v)|
 *   p_pair(u,v)  = #{ sid in postings(u) & postings(v) : first(u, sid) < first(v, sid) }
 * `limit` makes every answer the answer of the corpus of the first `limit` sentences, so one Tier is shared by the corpora of a growing chain (each reads only its own prefix).
 * Nothing here allocates on a query; a failed allocation returns an error code and leaves the Tier as it was.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define VX_ABI 1

typedef struct { int64_t *sid; int32_t *first; int64_t n, cap; } VxPost;
typedef struct { VxPost *p; int64_t nunits, cap; int64_t nsent; } VxTier;

int vx_abi(void) { return VX_ABI; }

VxTier *vx_tier_new(void) { return (VxTier *)calloc(1, sizeof(VxTier)); }

void vx_tier_free(VxTier *t) {
    if (!t) return;
    for (int64_t i = 0; i < t->nunits; i++) { free(t->p[i].sid); free(t->p[i].first); }
    free(t->p);
    free(t);
}

int64_t vx_tier_nsent(const VxTier *t) { return t ? t->nsent : -1; }

static int post_push(VxPost *p, int64_t sid, int32_t first) {
    if (p->n == p->cap) {
        int64_t nc = p->cap ? p->cap * 2 : 4;
        int64_t *s = (int64_t *)realloc(p->sid, (size_t)nc * sizeof(int64_t));
        if (!s) return -1;
        p->sid = s;
        int32_t *f = (int32_t *)realloc(p->first, (size_t)nc * sizeof(int32_t));
        if (!f) return -1;
        p->first = f;
        p->cap = nc;
    }
    p->sid[p->n] = sid;
    p->first[p->n] = first;
    p->n++;
    return 0;
}

static int grow_units(VxTier *t, int64_t need) {
    if (need <= t->cap) return 0;
    int64_t nc = t->cap ? t->cap : 64;
    while (nc < need) nc *= 2;
    VxPost *np = (VxPost *)realloc(t->p, (size_t)nc * sizeof(VxPost));
    if (!np) return -1;
    memset(np + t->cap, 0, (size_t)(nc - t->cap) * sizeof(VxPost));
    t->p = np;
    t->cap = nc;
    return 0;
}

/* Append sentence `sid` (must equal nsent).  uids[0..k) are the DISTINCT unit ids of the sentence, first[i] the index of uids[i]'s first occurrence in the sentence's unit list. */
int vx_tier_append(VxTier *t, int64_t sid, const int32_t *uids, const int32_t *first, int32_t k) {
    if (!t || sid != t->nsent || k < 0) return -2;
    int32_t top = -1;
    for (int32_t i = 0; i < k; i++) { if (uids[i] < 0) return -3; if (uids[i] > top) top = uids[i]; }
    if (top >= 0) {
        if (grow_units(t, (int64_t)top + 1) != 0) return -1;
        if ((int64_t)top + 1 > t->nunits) t->nunits = (int64_t)top + 1;
    }
    for (int32_t i = 0; i < k; i++) {
        if (post_push(&t->p[uids[i]], sid, first[i]) != 0) return -1;    /* an earlier push of this call stays: the caller discards the Tier on -1 */
    }
    t->nsent = sid + 1;
    return 0;
}

/* A copy of the first `nsent` sentences. */
VxTier *vx_tier_clone(const VxTier *t, int64_t nsent) {
    if (!t || nsent < 0 || nsent > t->nsent) return NULL;
    VxTier *c = vx_tier_new();
    if (!c) return NULL;
    if (grow_units(c, t->nunits > 0 ? t->nunits : 1) != 0) { vx_tier_free(c); return NULL; }
    c->nunits = t->nunits;
    for (int64_t u = 0; u < t->nunits; u++) {
        const VxPost *s = &t->p[u];
        int64_t m = 0;
        while (m < s->n && s->sid[m] < nsent) m++;
        if (m == 0) continue;
        VxPost *d = &c->p[u];
        d->sid = (int64_t *)malloc((size_t)m * sizeof(int64_t));
        d->first = (int32_t *)malloc((size_t)m * sizeof(int32_t));
        if (!d->sid || !d->first) { vx_tier_free(c); return NULL; }
        memcpy(d->sid, s->sid, (size_t)m * sizeof(int64_t));
        memcpy(d->first, s->first, (size_t)m * sizeof(int32_t));
        d->n = d->cap = m;
    }
    c->nsent = nsent;
    return c;
}

/* number of entries of p with sid < limit */
static int64_t upto(const VxPost *p, int64_t limit) {
    int64_t lo = 0, hi = p->n;
    while (lo < hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (p->sid[mid] < limit) lo = mid + 1; else hi = mid;
    }
    return lo;
}

static const VxPost *post_of(const VxTier *t, int32_t u) {
    return (t && u >= 0 && (int64_t)u < t->nunits) ? &t->p[u] : NULL;
}

int64_t vx_n(const VxTier *t, int32_t u, int64_t limit) {
    const VxPost *p = post_of(t, u);
    return p ? upto(p, limit) : 0;
}

/* Walk the common sids of a and b below limit; calls fn on (index in a, index in b).  Merge, or binary-search the longer list when the lists differ a lot. */
typedef void (*vx_visit)(const VxPost *a, int64_t i, const VxPost *b, int64_t j, void *ctx);

static void walk(const VxPost *a, int64_t na, const VxPost *b, int64_t nb, vx_visit fn, void *ctx) {
    if (na * 16 < nb) {
        int64_t lo = 0;
        for (int64_t i = 0; i < na; i++) {
            int64_t hi = nb, l = lo;
            while (l < hi) { int64_t m = l + (hi - l) / 2; if (b->sid[m] < a->sid[i]) l = m + 1; else hi = m; }
            lo = l;
            if (lo < nb && b->sid[lo] == a->sid[i]) fn(a, i, b, lo, ctx);
        }
    } else if (nb * 16 < na) {
        int64_t lo = 0;
        for (int64_t j = 0; j < nb; j++) {
            int64_t hi = na, l = lo;
            while (l < hi) { int64_t m = l + (hi - l) / 2; if (a->sid[m] < b->sid[j]) l = m + 1; else hi = m; }
            lo = l;
            if (lo < na && a->sid[lo] == b->sid[j]) fn(a, lo, b, j, ctx);
        }
    } else {
        int64_t i = 0, j = 0;
        while (i < na && j < nb) {
            if (a->sid[i] < b->sid[j]) i++;
            else if (a->sid[i] > b->sid[j]) j++;
            else { fn(a, i, b, j, ctx); i++; j++; }
        }
    }
}

static void count_n(const VxPost *a, int64_t i, const VxPost *b, int64_t j, void *ctx) { (void)a; (void)i; (void)b; (void)j; (*(int64_t *)ctx)++; }
static void count_p(const VxPost *a, int64_t i, const VxPost *b, int64_t j, void *ctx) { if (a->first[i] < b->first[j]) (*(int64_t *)ctx)++; }

int64_t vx_n_pair(const VxTier *t, int32_t u, int32_t v, int64_t limit) {
    const VxPost *a = post_of(t, u), *b = post_of(t, v);
    if (!a || !b) return 0;
    int64_t c = 0;
    walk(a, upto(a, limit), b, upto(b, limit), count_n, &c);
    return c;
}

/* sentences where u's first occurrence precedes v's */
int64_t vx_p_pair(const VxTier *t, int32_t u, int32_t v, int64_t limit) {
    const VxPost *a = post_of(t, u), *b = post_of(t, v);
    if (!a || !b) return 0;
    int64_t c = 0;
    walk(a, upto(a, limit), b, upto(b, limit), count_p, &c);
    return c;
}
