import numpy as np
import re
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer

STOPWORDS = set('''a an and or the of for with to in on at by from as is are be all any
other others miscellaneous misc accessories products items goods stuff supplies
supply category categories types type sets set kits kit s
'''.split())


def _tokens(text):
    text = text.lower()
    toks = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]


def _last_segment(path):
    parts = [p.strip() for p in path.split('>') if p.strip()]
    return parts[-1] if parts else path


def _format_name(words, max_words=4):
    seen = set()
    out = []
    for w in words:
        w = (w or '').strip()
        if not w:
            continue
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(w.title())
        if len(out) >= max_words:
            break
    return ' | '.join(out) if out else 'Misc'


def _top_terms(strings, parent_terms=set(), n=8, exclude=set()):
    if not strings:
        return []
    docs = [_last_segment(s).lower() for s in strings]
    try:
        vec = TfidfVectorizer(stop_words=list(STOPWORDS), ngram_range=(1,2),
                              max_features=100, token_pattern=r"[a-z]+")
        m = vec.fit_transform(docs)
        scores = np.asarray(m.sum(axis=0)).flatten()
        feats = vec.get_feature_names_out()
        ranked = sorted(zip(feats, scores), key=lambda x: -x[1])
        out = []
        for term, sc in ranked:
            t_words = set(term.split())
            if term.lower() in exclude:
                continue
            if any(w in parent_terms for w in t_words):
                continue
            if len(term) < 2:
                continue
            out.append(term)
            if len(out) >= n:
                break
        return out
    except Exception:
        cnt = Counter()
        for d in docs:
            for t in _tokens(d):
                if t not in parent_terms:
                    cnt[t] += 1
        return [t for t, _ in cnt.most_common(n)]


def _centroid_terms(strings, embeddings, parent_terms=set(), n=4):
    if len(strings) == 0:
        return []
    if len(strings) == 1:
        return [t for t in _tokens(_last_segment(strings[0])) if t not in parent_terms][:n]
    c = embeddings.mean(axis=0)
    c = c / (np.linalg.norm(c) + 1e-9)
    sims = embeddings @ c
    idx = int(np.argmax(sims))
    return [t for t in _tokens(_last_segment(strings[idx])) if t not in parent_terms][:n]


def _name_words(name):
    return set(re.findall(r"[a-z]+", name.lower())) - {''}


def _overlap(a, b):
    sa = _name_words(a)
    sb = _name_words(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def name_all_levels(label_matrix, texts, embeddings):
    N, L = label_matrix.shape
    texts = np.array(texts, dtype=object)
    names = {}

    def items_under(prefix):
        mask = np.ones(N, dtype=bool)
        for i, v in enumerate(prefix):
            mask &= (label_matrix[:, i] == v)
        return np.where(mask)[0]

    def get_prefixes(level):
        uniq = set()
        for row in label_matrix:
            pref = tuple(row[:level+1])
            if 0 in pref:
                continue  # skip leaves
            uniq.add(pref)
        return sorted(uniq)

    for level in range(L):
        prefixes = get_prefixes(level)
        sibling_groups = defaultdict(list)
        for p in prefixes:
            sibling_groups[p[:-1]].append(p)
        for parent, sibs in sibling_groups.items():
            # Collect ancestor word terms (avoid reuse)
            anc_terms = set()
            for k in range(1, len(parent)+1):
                anc_terms |= _name_words(names.get(parent[:k], ''))
            chosen_names = []
            # Compute candidates per sibling
            sib_data = []
            for p in sibs:
                idxs = items_under(p)
                strs = list(texts[idxs])
                embs = embeddings[idxs]
                cand_terms = _top_terms(strs, parent_terms=anc_terms, n=10)
                cent_terms = _centroid_terms(strs, embs, parent_terms=anc_terms, n=4)
                sib_data.append((p, cand_terms, cent_terms, strs))
            for p, cand_terms, cent_terms, strs in sib_data:
                # Build pool of candidates: tfidf first, then centroid tokens
                pool = list(cand_terms)
                for t in cent_terms:
                    if t not in pool:
                        pool.append(t)
                if not pool:
                    cnt = Counter()
                    for s in strs:
                        for t in _tokens(_last_segment(s)):
                            if t not in anc_terms:
                                cnt[t] += 1
                    pool = [w for w, _ in cnt.most_common(8)] or ['Items']
                # Try to pick 1-3 terms that produce a unique name with <0.3 overlap to chosen
                # Try single best first, then enrich.
                best_name = None
                for size in (1, 2, 3):
                    found = False
                    for start in range(len(pool) - size + 1):
                        words = pool[start:start+size]
                        # Skip if any words are in ancestor
                        if any(any(w in anc_terms for w in t.split()) for t in words):
                            continue
                        name = _format_name(words, max_words=4)
                        if any(_overlap(name, ex) > 0.3 for ex in chosen_names):
                            continue
                        # parent-child distinct
                        parent_name = names.get(parent, '')
                        if parent_name and _overlap(name, parent_name) > 0.5:
                            continue
                        best_name = name
                        found = True
                        break
                    if found:
                        break
                if best_name is None:
                    # Force disambiguation: pick the first pool term whose words don't appear in chosen names; if none, use a numeric suffix that has zero word-overlap with chosen names
                    chosen_words = set()
                    for n in chosen_names:
                        chosen_words |= _name_words(n)
                    cand = None
                    for term in pool:
                        tw = set(term.lower().split())
                        if not (tw & chosen_words):
                            cand = term
                            break
                    if cand is None:
                        # Use a unique single-token suffix (not in any chosen or ancestor)
                        suffix = f"sub{len(chosen_names)+1}"
                        best_name = _format_name([suffix], max_words=4)
                    else:
                        best_name = _format_name([cand], max_words=4)
                        # If still overlapping, append unique suffix
                        if any(_overlap(best_name, ex) > 0.3 for ex in chosen_names):
                            best_name = _format_name([cand, f"sub{len(chosen_names)+1}"], max_words=4)
                names[p] = best_name
                chosen_names.append(best_name)
    return names
