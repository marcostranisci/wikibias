"""Jensen-Shannon divergence of event distributions between author groups,
with permutation tests.

Data: data/expanded_events.parquet (s = author, p = event, o = object,
post_colonial = 1 transnational / 0 Western, P21 = gender).

Groups (two axes):
  tw = transnational women   tm = transnational men
  ww = Western women         wm = Western men
Comparisons: all 6 pairs of the four groups, plus the two axes alone
(women vs men, transnational vs Western).

Each group is a frequency distribution over events (one count per row).
JSD uses log base 2 (0 = identical, 1 = disjoint).

Significance: authors are the unit, because one author's rows are not
independent. Group labels are shuffled across the authors of the two groups
(sizes kept) N_PERM times; p = share of shuffles with JSD >= observed
(+1 smoothing, so the smallest possible p is 1 / (N_PERM + 1)).

Effect size: null_mean is the JSD expected from sampling noise alone (the
mean over shuffles). Raw JSD is inflated for small groups, so excess =
jsd - null_mean is the number to compare across pairs. (A bootstrap CI is
not reported: resampling authors with replacement inflates JSD, so its
intervals are biased upwards.)

Per event: contribution to the JSD (non-negative, they sum to the JSD) and
the group it is more frequent in. Events occurring at least MIN_COUNT times
in the two groups combined get a permutation p-value (is the contribution
larger than chance?) with Benjamini-Hochberg FDR correction.

Excluded: non-binary authors (too few for the 2x2 split) and authors whose
gender or post_colonial label differs across their rows.

Outputs (folder data/jsd_significance/):
  overall.csv          one row per comparison
  events_<A>_<B>.csv   per-event contributions for each comparison
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parent
EVENTS = ROOT / 'data' / 'expanded_events.parquet'
OUT_DIR = ROOT / 'data' / 'jsd_significance'
N_PERM = 10000
MIN_COUNT = 20
BATCH = 50
SEED = 42

GROUP_NAMES = {'tw': 'transnational women', 'tm': 'transnational men',
               'ww': 'Western women', 'wm': 'Western men',
               'women': 'women', 'men': 'men',
               'transnational': 'transnational', 'western': 'Western'}
COMPARISONS = [('tw', 'tm'), ('tw', 'ww'), ('tw', 'wm'), ('tm', 'ww'), ('tm', 'wm'),
               ('ww', 'wm'), ('women', 'men'), ('transnational', 'western')]


def load():
    # Converted from expanded_events.csv with keep_default_na=False, so events
    # such as 'NA' or 'null' are words, not missing values.
    d = pd.read_parquet(EVENTS)
    d = d.dropna(subset=['p'])
    labels = d.groupby('s').agg(pc=('post_colonial', 'nunique'), g=('P21', 'nunique'))
    conflicting = labels[(labels.pc > 1) | (labels.g > 1)].index
    d = d[~d['s'].isin(conflicting) & d['P21'].isin(['female', 'male'])]

    authors = d.drop_duplicates('s').set_index('s')[['post_colonial', 'P21']]
    a_idx = {s: i for i, s in enumerate(authors.index)}
    events = pd.Index(sorted(d['p'].astype(str).unique()))
    e_idx = {e: i for i, e in enumerate(events)}
    rows = d['s'].map(a_idx).to_numpy()
    cols = d['p'].astype(str).map(e_idx).to_numpy()
    X = sparse.csr_matrix((np.ones(len(d)), (rows, cols)),
                          shape=(len(authors), len(events)))

    t = authors['post_colonial'].to_numpy() == 1
    w = authors['P21'].to_numpy() == 'female'
    masks = {'tw': t & w, 'tm': t & ~w, 'ww': ~t & w, 'wm': ~t & ~w,
             'women': w, 'men': ~w, 'transnational': t, 'western': ~t}
    print(f'{len(d)} rows, {len(authors)} authors, {len(events)} events '
          f'(dropped {len(conflicting)} authors with conflicting labels)')
    return X, events, masks


def jsd_parts(a, b):
    """Per-event JSD contributions (base 2) for count matrices of shape (k, events)."""
    p = a / a.sum(axis=-1, keepdims=True)
    q = b / b.sum(axis=-1, keepdims=True)
    m = (p + q) / 2
    with np.errstate(divide='ignore', invalid='ignore'):
        kp = np.where(p > 0, p * np.log2(p / m), 0.0)
        kq = np.where(q > 0, q * np.log2(q / m), 0.0)
    return 0.5 * kp + 0.5 * kq


def bh(p):
    """Benjamini-Hochberg adjusted p-values."""
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adj, 1)
    return out


def compare(X, events, mask_a, mask_b, rng):
    Xa, Xb = X[mask_a], X[mask_b]
    ca = np.asarray(Xa.sum(0)).ravel()
    cb = np.asarray(Xb.sum(0)).ravel()
    parts = jsd_parts(ca[None], cb[None])[0]
    observed = parts.sum()

    # Shuffle which authors belong to A, keeping group sizes.
    Xab = sparse.vstack([Xa, Xb]).tocsr()
    total = ca + cb
    na, n = Xa.shape[0], Xab.shape[0]
    null = np.empty(N_PERM)
    exceed = np.zeros(len(events))
    for start in range(0, N_PERM, BATCH):
        k = min(BATCH, N_PERM - start)
        sel = np.zeros((k, n))
        for i in range(k):
            sel[i, rng.choice(n, na, replace=False)] = 1
        pa = (sparse.csr_matrix(sel) @ Xab).toarray()
        pparts = jsd_parts(pa, total[None] - pa)
        null[start:start + k] = pparts.sum(1)
        exceed += (pparts >= parts[None]).sum(0)
    p_value = (np.sum(null >= observed) + 1) / (N_PERM + 1)

    per_event = pd.DataFrame({
        'event': events,
        'count_a': ca.astype(int), 'count_b': cb.astype(int),
        'freq_a': ca / ca.sum(), 'freq_b': cb / cb.sum(),
        'contribution': parts,
        'p_value': (exceed + 1) / (N_PERM + 1),
    })
    per_event = per_event[(per_event.count_a + per_event.count_b) > 0]
    per_event['more_frequent_in'] = np.where(per_event.freq_a > per_event.freq_b, 'a', 'b')
    tested = (per_event.count_a + per_event.count_b) >= MIN_COUNT
    per_event.loc[~tested, 'p_value'] = np.nan
    per_event['p_fdr'] = np.nan
    per_event.loc[tested, 'p_fdr'] = bh(per_event.loc[tested, 'p_value'].to_numpy())
    per_event = per_event.sort_values('contribution', ascending=False)

    significant = per_event.p_fdr < 0.05
    summary = {'authors_a': int(mask_a.sum()), 'authors_b': int(mask_b.sum()),
               'rows_a': int(ca.sum()), 'rows_b': int(cb.sum()),
               'jsd': observed, 'null_mean': null.mean(),
               'null_95th': np.percentile(null, 95),
               'excess': observed - null.mean(), 'p_value': p_value,
               'events_tested': int(tested.sum()),
               'events_fdr_0.05': int(significant.sum()),
               'jsd_share_significant': per_event.loc[significant, 'contribution'].sum() / observed}
    return summary, per_event


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    X, events, masks = load()
    rng = np.random.default_rng(SEED)
    rows = []
    for a, b in COMPARISONS:
        summary, per_event = compare(X, events, masks[a], masks[b], rng)
        per_event['more_frequent_in'] = per_event['more_frequent_in'].map({'a': a, 'b': b})
        per_event = per_event.rename(columns={'count_a': f'count_{a}', 'count_b': f'count_{b}',
                                              'freq_a': f'freq_{a}', 'freq_b': f'freq_{b}'})
        per_event.to_csv(f'{OUT_DIR}/events_{a}_{b}.csv', index=False)
        rows.append({'comparison': f'{a} vs {b}',
                     'groups': f'{GROUP_NAMES[a]} vs {GROUP_NAMES[b]}', **summary})
        print(f'{a} vs {b}: JSD={summary["jsd"]:.4f} p={summary["p_value"]:.5f}', flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(f'{OUT_DIR}/overall.csv', index=False)
    with pd.option_context('display.width', 250, 'display.float_format', '{:.4f}'.format):
        print(res.drop(columns=['groups']).to_string(index=False))


if __name__ == '__main__':
    main()
