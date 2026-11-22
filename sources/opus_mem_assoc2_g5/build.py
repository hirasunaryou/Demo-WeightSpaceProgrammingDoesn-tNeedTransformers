"""Turns the hand-written knowledge base in kb/ into the weights of the second-order association memory (arch.py).

Run `python build.py --vocab` once after editing kb/ to regenerate vocab.txt; build() reads vocab.txt and kb/.
See NOTES.md for the design.
"""
import glob
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np
import torch

TOKEN = re.compile(r"[a-z0-9']+")
HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "kb")
PRIME = 1000003
H = 1 << 22          # rows of the pair table (few rows used, so few false hits)
R = 16               # recalls per pair row (longer rows keep their strongest)

# ---------------------------------------------------------------- weights of the parts (chosen by reasoning, not fitted)
W_SYM_A = 1.0        # symmetric fact line: every concept <-> every other (first order), scaled 1/sqrt(m-1)
W_SYM_P = 0.3        # symmetric fact line: a pair recalls the rest of the line
W_SYN = 0.4          # near-synonym lines (facts_synonyms.txt) count less than topic lines
W_DIR_A = 1.5        # directed rule cue -> answer (first order), scaled 1/sqrt(#cues)
W_DIR_P = 2.0        # directed rule: a pair of cues recalls the answers
W_REV = 0.3          # a directed rule also supports its cues from its answers (first order only), at this fraction
W_REV_P = 0.0        # ... and through pairs (off: it made answers' many words into noisy cues)
W_EQ_P = 0.5         # 'term = definition': pair (term, definition word) recalls the other definition words
W_NEG = -0.7         # 'cues >! answers': evidence against
W_TAX = 1.0          # taxonomy parent <-> child, decays per level
TAX_DECAY = 0.5
TAX_PAIR = 0.4       # the words of a category name together recall its members only weakly
FAN_REF = 20.0       # first-order rows of hub concepts are scaled by 1/sqrt(1 + fan/FAN_REF)
FAN_IN_REF = 40.0    # ... and answer concepts supported by very many question concepts by 1/sqrt(1 + fan_in/FAN_IN_REF)
HOP2 = 0.5           # total mass of two-hop associations (q -> b -> c) relative to the direct ones
PAIR_UNIT = 1.0      # pair recalls add up sublinearly: v -> sqrt(v * PAIR_UNIT)
A_UNIT = 1.0         # first-order sums above this grow as sqrt (as PAIR_UNIT does for pairs)
OFFSET = 0.0         # a constant penalty on every first-order recall (off: no help on my questions)
RESTATE = 1.0        # "which is the independent variable?": each new option concept costs this (first order)
RESTATE_WORDS = ["independent", "dependent", "manipulated"]
MIX = 1.5            # weight of the first-order read q A against the pair read
IDF_COMMON = 0.8     # cap on the weight of general (non-science) words, kb/common.txt
# negation: (EXCEPT, q) and (NOT, q) take back q's first-order recall 2.5 times over and also what q recalls together
# with a phrase-mate ("simple" + "machine"). The parent let 'not' only cancel q's first-order recall, because 'not'
# is often part of a scenario ("the seeds did not sprout"); on invented "which is NOT" questions that model was right
# less often than a coin, so generation 4 treats 'not' like 'except' (see NOTES.md).
# "cannot / doesn't / didn't ..." (#cant) are mostly scenario words and stay pair-only.
G_EXCEPT = 2.5
G_NOT = 2.5          # generation 4: "not" negates as strongly as "except" (see NOTES.md)
P_EXCEPT = 1.0
P_NOT = 1.0
# word: (concept, strength against first-order recall, strength against what phrase-mate pairs recall)
NEG_WORDS = {"except": ("#except", G_EXCEPT, P_EXCEPT), "not": ("#not", G_NOT, P_NOT),
             "isn't": ("#not", G_NOT, P_NOT), "aren't": ("#not", G_NOT, P_NOT),
             "least": ("#not", G_NOT, P_NOT)}     # "which is least likely to ..." asks for the option least supported
NEG_KEEP_AGAINST = 4  # generation 5: slots of a negation row kept for the concept's evidence against
IDF_NEG = 4.5        # above every other concept, so a negation word is always among the J strongest
# direction words: one concept for "more/increase", one for "less/decrease". They carry no topic, so they get no
# first-order associations at all; they only act inside pairs (e.g. (float, water) recalls "less dense", and
# (altitude, #up) recalls "#down pressure").
DIRECTION = {"#up": "more increase increases increased increasing raise raises raised greater greatest high higher highest gain gains gained gaining".split(),
             "#down": ("less fewer decrease decreases decreased decreasing reduce reduces reduced reducing lessen lessens "
                       "low lower lowers lowered lowest lose loses losing").split(),
             # taking in vs giving off: photosynthesis takes in carbon dioxide and gives off oxygen
             "#in": ("absorb absorbs absorbed absorbing absorption inhale inhales inhaled inhaling intake "
                     "take takes taken taking took").split(),     # generation 4: "plants take in carbon dioxide"
             "#out": ("release releases released releasing emit emits emitted emitting emission exhale exhales exhaled "
                      "exhaling off").split(),
             # absence: "animals without a backbone"
             "#without": "without lack lacks lacking lacked no none absence absent".split(),
             # "eats only plants" (herbivore) vs "eats both plants and animals" (omnivore)
             "#only": "only solely".split(),
             "#both": "both".split(),
             # generation 4: "cannot / doesn't / never" in a question; acts only in pairs (no cancelling, unlike "not")
             "#cant": "cannot can't don't doesn't didn't won't wouldn't couldn't never".split()}
OPPOSITES = [("#up", "#down"), ("#in", "#out")]
NEGATED = ("#without", "#not", "#cant")   # a rule cue: only pairs that include it recall the answer
# generation 4: negation inside fact lines. The parent dropped "not/cannot" from fact lines, so
# "sound cannot travel > vacuum" taught (sound, travel) -> vacuum. Now a negation on the cue side gates the rule
# (only pairs with a negation concept of the question recall the answers, no first-order recall), and a negation on
# the answer side turns the next content word into evidence against.
NEG_FACT = set("avoid not cannot can't don't doesn't didn't won't isn't aren't never wasn't weren't".split())
NEG_GATES = ("#not", "#cant")
# generation 5: on the cue side "avoid" is an ordinary cue word ("lab safety avoid > eating drinking"), because
# questions ask "which should the students avoid"; on the answer side it still negates the next word.
NEG_CUE_KEEP = {"avoid"}
IDF_DIR = 1.6
DIR_OPP = 0.7        # a pair's recall of one direction counts this much against the other direction
TIERS = True         # generation 4: directed-rule recalls fill a pair row before topic and chained ones
PHRASE_SHARE = True  # words of a multiword name share one answer weight
DEF_CHAIN = 0.5      # a rule whose answer is a defined term also recalls the definition, at this fraction
TAX_INST = 0.5       # rule cues that name a category also fire for its members, at this fraction
TAX_INST_MAX = 150   # ... for categories with at most this many members
# generation 5: adjective opposites, as generation 2's more/less: a recall of one argues against the other
# ("polar bear" recalls "thick fur", so the distractor "thin fur" should lose, not just tie on "fur").
ANT_OPP = 0.5
P_FAN_IN_REF = 1000.0   # generation 5: pair-row fan-in damping (about the 99th percentile of fan-in; 0 = off)
ANTONYMS = """thick thin; hot cold; warm cool; wet dry; fast slow; large small; big small; long short; strong weak;
hard soft; rough smooth; deep shallow; wide narrow; many few; tall short; dark bright; attract repel; absorb reflect;
conductor insulator; renewable nonrenewable; dominant recessive; living nonliving; inherited learned; physical chemical;
transparent opaque; natural artificial; oldest youngest; healthy sick; safe dangerous; float sink; expand contract;
melt freeze; evaporate condense"""     # not pairs that rules usually name together (day and night, push or pull)


def kb_lines(pattern):
    for path in sorted(glob.glob(os.path.join(KB, pattern))):
        with open(path) as f:
            for line in f:
                line = line.split("#", 1)[0].strip().lower()
                if line:
                    yield line


def words(text):
    return TOKEN.findall(text.lower())


# ---------------------------------------------------------------- morphology
VOWELS = set("aeiou")
PROTECT = {"habitat", "combat", "format", "thermostat", "lens", "news", "species", "series", "always", "gas",
           "lightning", "early", "physics", "mathematics", "genetics", "economics", "electronics", "diabetes",
           "rabies", "measles", "mumps", "glasses", "scissors", "pants", "clothes", "means", "molasses",
           "christmas", "texas", "kansas", "arkansas", "atlas", "canvas", "chaos", "bias", "pancreas",
           "cactus", "fungus", "nucleus", "virus", "octopus", "platypus", "hippopotamus", "walrus",
           "asparagus", "uterus", "esophagus", "stimulus", "hummus", "status", "census", "focus", "bonus",
           "bus", "us", "this", "his", "is", "was", "has", "its", "plus", "thus", "perhaps", "towards"}


def has_vowel(s):
    return any(c in VOWELS for c in s)


def raw_stem(w):
    w = w.replace("'", "")
    if len(w) <= 2 or w.isdigit() or w in PROTECT:
        return w
    suffixed = False
    if w.endswith("ies") and len(w) > 4:
        w, suffixed = w[:-3] + "y", True
    elif w.endswith("s") and len(w) > 3 and not w.endswith(("ss", "us", "is")):
        w, suffixed = w[:-1], True
    if w in PROTECT:
        return w
    if w.endswith("ing") and len(w) - 3 >= 2 and has_vowel(w[:-3]):
        w, suffixed = w[:-3], True
    elif w.endswith("ied") and len(w) > 4:
        w, suffixed = w[:-3] + "y", True
    elif w.endswith("ed") and not w.endswith("eed") and len(w) - 2 >= 2 and has_vowel(w[:-2]):
        w, suffixed = w[:-2], True
    elif w.endswith("ly") and len(w) >= 6 and not w.endswith("lly"):
        w = w[:-2]
    elif w.endswith("lly") and len(w) >= 7:
        w = w[:-2]
    if w.endswith("ification") and len(w) > 11:
        w = w[:-9] + "ify"
    elif w.endswith("ication") and len(w) - 7 >= 3:
        w = w[:-7] + "ic"
    elif w.endswith("ation") and len(w) - 5 >= 3:
        w = w[:-5]
    elif w.endswith(("ction", "ption", "ution")) and len(w) - 3 >= 4:
        w = w[:-3]
    elif w.endswith("ate") and len(w) - 3 >= 3 and w[-4] not in VOWELS:
        w = w[:-3]
    elif suffixed and w.endswith("at") and len(w) - 2 >= 3 and w[-3] not in VOWELS and w not in PROTECT:
        w = w[:-2]
    if w.endswith("e") and len(w) >= 3:
        w = w[:-1]
    if len(w) >= 3 and w[-1] == w[-2] and w[-1] not in "aeiousy":
        w = w[:-1]
    return w


class Morph:
    def __init__(self):
        self.stop = set()
        for line in kb_lines("stop.txt"):
            self.stop.update(words(line))
        self.same = {}
        for line in kb_lines("same.txt"):
            ws = line.split()
            if not ws:
                continue
            if ws[0].startswith("!"):          # a concept of its own, kept apart from the stem
                ws[0] = ws[0][1:]
                key = ws[0] + "#"
            else:
                key = self.same.get(ws[0], raw_stem(ws[0]))
            for x in ws:
                self.same[x] = key
        for key, ws in DIRECTION.items():
            for x in ws:
                self.same[x] = key
                self.stop.discard(x)
        self.stop -= set(NEG_WORDS)
        # adjectives: comparatives and superlatives map to the base
        for line in kb_lines("adj.txt"):
            for a in words(line):
                key = self.same.get(a, raw_stem(a))
                self.same.setdefault(a, key)
                for f in comparatives(a):
                    self.same.setdefault(f, key)

    def stem(self, w):
        w = w.replace("'", "") if w not in self.same else w
        if w in self.same:
            return self.same[w]
        return raw_stem(w)

    def concept_words(self, text):
        """Stems of the content words of a text (stop words dropped)."""
        out = []
        for w in words(text):
            if w in self.stop or w.replace("'", "") in self.stop:
                continue
            s = self.stem(w)
            if s and s not in out:
                out.append(s)
        return out


def comparatives(a):
    out = []
    if a.endswith("y") and len(a) > 2:
        out += [a[:-1] + "ier", a[:-1] + "iest"]
    elif a.endswith("e"):
        out += [a + "r", a + "st"]
    else:
        out += [a + "er", a + "est"]
        if len(a) >= 3 and a[-1] not in "aeiouwy" and a[-2] in VOWELS and a[-3] not in VOWELS:
            out += [a + a[-1] + "er", a + a[-1] + "est"]
    return out


def inflections(w):
    """Candidate inflected forms of a written word (kept only if they stem back to the same concept)."""
    out = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing", w + "ly", w + "'s", w + "s'"}
    if w.endswith("e"):
        out |= {w[:-1] + "ing", w[:-1] + "ation", w[:-1] + "ion"}
    if w.endswith("y"):
        out |= {w[:-1] + "ies", w[:-1] + "ied"}
    if w.endswith("ate"):
        out |= {w[:-1] + "ion", w[:-3] + "ation"}
    if len(w) >= 3 and w[-1] not in "aeiouwxy" and w[-2] in VOWELS and w[-3] not in VOWELS:
        out |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    if w.endswith("ify"):
        out |= {w[:-1] + "ication"}
    if w.endswith(("ct", "pt", "ut")):
        out |= {w + "ion", w + "ions"}
    if w.endswith("s") and not w.endswith("ss"):
        out |= {w[:-1]}
    return out


# ---------------------------------------------------------------- knowledge base parsing
def parse_facts(m):
    """Fact lines from kb/facts_*.txt as (kind, left stems, right stems).
    'a b > x y' directed, 'a b = x y' both directions, 'a b c' symmetric."""
    facts = []
    for path in sorted(glob.glob(os.path.join(KB, "facts_*.txt"))):
        for line in kb_lines(os.path.basename(path)):
            parse_line(m, line, facts, "syn" if "synonyms" in path else "sym")
    return facts


def split_neg(m, text):
    """(text without negations and negated words, negated words, whether the text had a negation)."""
    pos, neg, had, pending = [], [], False, False
    for w in words(text):
        if w in NEG_FACT:
            had, pending = True, True
            continue
        if pending and w not in m.stop and m.stem(w) not in DIRECTION:
            neg.append(w)
            pending = False
            continue
        pos.append(w)
    return " ".join(pos), " ".join(neg), had


TAKE_WORDS = ("take", "takes", "taken", "taking", "took")
TAKE_DURATION = re.compile(r"\b(?:%s)\b(?!\s+(?:in|up)\b)" % "|".join(TAKE_WORDS))


def parse_line(m, line, facts, plain):
    # generation 5: "take" is #in ("plants take in carbon dioxide") only when "in"/"up" follows it. Duration lines
    # ("earth rotation takes 24 hours") taught (#in, earth) -> rotate, axis, which then fired for every question
    # with "takes" ("Earth takes 365 days to ..." picked "rotate").
    line = TAKE_DURATION.sub(" ", line)
    if NEG_FACT & set(words(line)):
        parse_neg_line(m, line, facts, plain)
        return
    if True:
        if ">!" in line:                    # negative rule: the cues argue against these answers
            l, r = line.split(">!", 1)
            facts.append(("neg", m.concept_words(l), m.concept_words(r)))
        elif ">" in line:
            l, r = line.split(">", 1)
            facts.append(("dir", m.concept_words(l), m.concept_words(r)))
        elif "=" in line:
            l, r = line.split("=", 1)
            L, Rr = m.concept_words(l), m.concept_words(r)
            if {"#up", "#down"} <= set(L + Rr):      # "how high or low": no direction meant
                L, Rr = [x for x in L if x not in DIRECTION], [x for x in Rr if x not in DIRECTION]
            facts.append(("def", L, Rr))
            facts.append(("def", Rr, L))
            facts.append(("eq", L, Rr))
        else:   # topic clusters carry no direction
            facts.append((plain, [x for x in m.concept_words(line) if x not in DIRECTION], []))


def parse_neg_line(m, line, facts, plain):
    """A fact line with a negation word (see NEG_FACT)."""
    for sep in (">!", ">", "="):
        if sep in line:
            l, r = line.split(sep, 1)
            break
    else:
        pos, neg, _ = split_neg(m, line)
        facts.append((plain, [x for x in m.concept_words(pos) if x not in DIRECTION], []))
        return
    lw = set(words(l)) - NEG_CUE_KEEP
    L = m.concept_words(" ".join(w for w in words(l) if w not in NEG_FACT or w in NEG_CUE_KEEP))
    rpos, rneg, _ = split_neg(m, r)
    Rp, Rn = m.concept_words(rpos), m.concept_words(rneg)
    if NEG_FACT & lw:              # "sound cannot travel > vacuum": only (negation, cue) pairs recall the answer
        if sep == ">!":
            Rp, Rn = Rn, Rp
        for g in NEG_GATES:
            if Rp:
                facts.append(("dir", L + [g], Rp))
            if Rn:
                facts.append(("neg", L + [g], Rn))
        return
    if sep == ">!":
        Rp, Rn = Rn, Rp
    if sep == "=":
        facts.append(("def", L, Rp))
        facts.append(("def", Rp, L))
        facts.append(("eq", L, Rp))
    elif Rp:
        facts.append(("dir", L, Rp))
    if Rn:
        facts.append(("neg", L, Rn))


def parse_tax(m):
    """kb/tax_*.txt lines 'parent: child child ...' (multiword names joined with _ are split into words)."""
    edges = defaultdict(set)
    for line in kb_lines("tax*.txt"):
        if ":" not in line:
            continue
        p, cs = line.split(":", 1)
        P = tuple(m.concept_words(p.replace("_", " ")))
        for c in cs.split(","):
            C = tuple(m.concept_words(c.replace("_", " ")))
            if P and C and P != C:
                edges[P].add(C)
    return edges


def all_written_words():
    ws = set()
    for pat in ("facts_*.txt", "tax*.txt", "same.txt", "adj.txt"):
        for line in kb_lines(pat):
            ws.update(words(line.replace("_", " ")))
    return ws


def bases(w):
    """Guesses at the base form of a written (possibly inflected) word."""
    out = {w}
    if w.endswith("ies"):
        out.add(w[:-3] + "y")
    if w.endswith("es"):
        out.add(w[:-2])
    if w.endswith("s"):
        out.add(w[:-1])
    if w.endswith("ed"):
        out |= {w[:-2], w[:-1]}
        if len(w) > 4 and w[-3] == w[-4]:
            out.add(w[:-3])
    if w.endswith("ing"):
        out |= {w[:-3], w[:-3] + "e"}
        if len(w) > 5 and w[-4] == w[-5]:
            out.add(w[:-4])
    if w.endswith("ied"):
        out.add(w[:-3] + "y")
    return {b for b in out if len(b) >= 2}


def make_vocab():
    m = Morph()
    base = all_written_words()
    vocab = set()
    for w in base:
        if w in m.stop:
            continue
        s = m.stem(w)
        for b in bases(w):
            for f in inflections(b):
                if f not in m.stop and m.stem(f) == s:
                    vocab.add(f)
    for w, s in m.same.items():
        if w not in m.stop:
            vocab.add(w)
    vocab |= set(NEG_WORDS)
    vocab = sorted(v for v in vocab if TOKEN.fullmatch(v))
    with open(os.path.join(HERE, "vocab.txt"), "w") as f:
        f.write("\n".join(vocab) + "\n")
    return vocab


# ---------------------------------------------------------------- build
def build_tables():
    m = Morph()
    vocab = [line.strip() for line in open(os.path.join(HERE, "vocab.txt"))]
    facts = parse_facts(m)
    tax = parse_tax(m)

    # concepts: every stem of the vocabulary that is not a stop word
    cid = {}
    word_c = np.zeros(len(vocab) + 2, dtype=np.int64)
    for i, w in enumerate(vocab):
        if w in m.stop:
            continue
        s = NEG_WORDS[w][0] if w in NEG_WORDS else m.stem(w)
        if s not in cid:
            cid[s] = len(cid) + 1
        word_c[i + 2] = cid[s]
    C = max(len(cid) + 1, 16)

    def ids(stems):
        return [cid[s] for s in stems if s in cid]
    inv_cid = {v: k for k, v in cid.items()}

    # document frequency over fact lines and taxonomy lines -> idf
    df = np.zeros(C)
    docs = 0
    for kind, L, Rr in facts:
        for c in set(ids(L) + ids(Rr)):
            df[c] += 1
        docs += 1
    for P, cs in tax.items():
        for c in set(ids(P) + [x for ch in cs for x in ids(ch)]):
            df[c] += 1
        docs += 1
    idf = np.log((docs + 1) / (df + 1)).astype(np.float32)
    idf = np.clip(idf, 1.0, None) / math.log(docs + 1) * 4.0   # roughly 0.5 .. 4
    idf[0] = 0.0
    for line in kb_lines("common.txt"):
        for wd in words(line):
            c = cid.get(m.stem(wd))
            if c and wd not in m.stop:
                idf[c] = min(idf[c], IDF_COMMON)

    A = defaultdict(float)
    P = defaultdict(lambda: defaultdict(float))
    # generation 4: weaker, second-tier pair recalls (topic lines, definition chaining, term + definition word).
    # A pair row holds only R recalls; the parent kept the R strongest, so chained definition words of a common
    # answer pushed a rule's own answers out of the row ("sound travels fastest": steel lost to "definite shape").
    # Now a row first keeps the recalls that some directed rule gives, then fills up with second-tier ones.
    P2 = defaultdict(lambda: defaultdict(float))

    # multiword names (taxonomy entries, defined terms): as answers, their words share one weight, so that an
    # option like "wheel and axle" or "carbon dioxide" does not count twice
    phrases = set()
    for par, chs in tax.items():
        for t in [par] + list(chs):
            if 2 <= len(t) <= 3:
                phrases.add(tuple(t))
    for kind, L, Rr in facts:
        if kind == "eq" and 2 <= len(L) <= 3:
            phrases.add(tuple(L))

    def answer_weights(stems):
        """{concept id: weight} for the answer words of a rule; words of one multiword name share a weight."""
        wt = [1.0] * len(stems)
        i = 0
        while i < len(stems):
            for k in (3, 2):
                if PHRASE_SHARE and i + k <= len(stems) and tuple(stems[i:i + k]) in phrases:
                    for j in range(i, i + k):
                        wt[j] = 1.0 / math.sqrt(k)
                    i += k - 1
                    break
            i += 1
        out = {}
        for st, x in zip(stems, wt):
            if st in cid:
                out[cid[st]] = max(out.get(cid[st], 0.0), x)
        return out

    def add_dir(L, Rr, wa, wp, phrase=False, tier2=False):
        gated = any(g in L for g in NEG_GATES)
        L = ids(L)
        aw = {c: 1.0 for c in ids(Rr)} if phrase else answer_weights(Rr)
        Rw = [(r, x) for r, x in aw.items() if r not in L]
        if not L or not Rw:
            return
        # a rule with many answers supports each less; the words of one named thing share one weight
        n_eff = sum(x for _, x in Rw)
        spread = 1.0 / len(Rw) if phrase else min(1.0, math.sqrt(2.0 / max(n_eff, 1.0)))
        wa, wp = wa * spread, wp * spread
        sa = wa / math.sqrt(len(L))
        for a in L:
            if gated:
                break
            for b, x in Rw:
                A[(a, b)] += sa * x
        if len(L) >= 2:
            sp = wp * 2.0 / len(L)
            gates = {cid[g] for g in NEGATED if g in cid} & set(L)
            for i in range(len(L)):
                for j in range(i + 1, len(L)):
                    if gates and not gates & {L[i], L[j]}:
                        continue     # "without X": X alone is no evidence for the answer
                    if L[i] in gates and L[j] in gates:
                        continue
                    lo, hi = min(L[i], L[j]), max(L[i], L[j])
                    row = (P2 if tier2 else P)[(lo, hi)]
                    for b, x in Rw:
                        row[b] += sp * x

    # an answer that is a defined term also brings its definition words (options often paraphrase the term)
    if DEF_CHAIN > 0:
        defs = defaultdict(list)
        for kind, L, Rr in facts:
            if kind == "eq":
                key = tuple(sorted(set(ids(L))))
                if 1 <= len(key) <= 3:
                    defs[key].extend(c for c in ids(Rr) if c not in key and c not in defs[key])
        by_word = defaultdict(list)
        for key in defs:
            by_word[key[0]].append(key)
        for kind, L, Rr in list(facts):
            if kind != "dir":
                continue
            Ri = set(ids(Rr))
            Li = set(ids(L))
            for r in list(Ri):
                for key in by_word.get(r, ()):
                    if set(key) <= Ri and not (set(key) & Li) and 2 * len(key) >= len(Ri):
                        extra = [c for c in defs[key] if c not in Ri and c not in Li][:8]
                        if extra:
                            facts.append(("chain", L, [inv_cid[c] for c in extra]))
    for kind, L, Rr in facts:
        if kind == "def":
            add_dir(L, Rr, W_DIR_A, W_DIR_P)
        elif kind == "dir":
            add_dir(L, Rr, W_DIR_A, W_DIR_P)
            if not any(g in L for g in NEG_GATES):
                add_dir(Rr, L, W_REV * W_DIR_A, W_REV_P * W_DIR_P)
        elif kind == "eq":
            # the term together with one word of its definition recalls the rest of the definition
            Li, Ri = ids(L), [r for r in ids(Rr) if r not in ids(L)]
            if Li and len(Ri) >= 2:
                sp = W_EQ_P * min(1.0, math.sqrt(2.0 / (len(Ri) - 1))) / len(Li)
                for a in Li:
                    for r in Ri:
                        lo, hi = min(a, r), max(a, r)
                        row = P2[(lo, hi)]
                        for b in Ri:
                            if b != r:
                                row[b] += sp
        elif kind == "neg":
            add_dir(L, Rr, W_NEG * W_DIR_A, W_NEG * W_DIR_P)
        elif kind == "chain":
            add_dir(L, Rr, DEF_CHAIN * W_DIR_A, DEF_CHAIN * W_DIR_P, tier2=True)
        else:
            S = ids(L)
            if len(S) < 2:
                continue
            sw = answer_weights(L)
            k = W_SYN if kind == "syn" else 1.0
            sa = k * W_SYM_A / math.sqrt(len(S) - 1)
            for a in S:
                for b in S:
                    if a != b:
                        A[(a, b)] += sa * sw.get(b, 1.0)
            if len(S) >= 3:
                sp = k * W_SYM_P * 2.0 / len(S)
                for i in range(len(S)):
                    for j in range(i + 1, len(S)):
                        lo, hi = min(S[i], S[j]), max(S[i], S[j])
                        row = P2[(lo, hi)]
                        for b in S:
                            if b != S[i] and b != S[j]:
                                row[b] += sp * sw.get(b, 1.0)

    # taxonomy: closure with decay; parent <-> descendant, and (parent words) pairs recall the child
    def descend(p):
        """Descendants of p with their shallowest depth (breadth first, in a fixed order)."""
        seen, frontier, depth = {p}, [p], 0
        while frontier:
            nxt = []
            for q in frontier:
                for ch in sorted(tax.get(q, ())):
                    if ch not in seen:
                        seen.add(ch)
                        nxt.append(ch)
                        yield ch, depth
            frontier, depth = nxt, depth + 1

    for p in sorted(tax):
        down = min(1.0, 3.0 / math.sqrt(len(tax[p])))     # a parent with many children supports each less
        for ch, depth in descend(p):
            w = W_TAX * (TAX_DECAY ** depth)
            add_dir(list(p), list(ch), w * down, w * down * TAX_PAIR, phrase=True)
            add_dir(list(ch), list(p), w, w, phrase=True)

    # direction concepts act only in pairs
    dirc = {cid[k] for k in DIRECTION if k in cid}
    for key in [k for k in A if k[0] in dirc or k[1] in dirc]:
        del A[key]
    for c in dirc:
        idf[c] = IDF_DIR
    # a rule about a category also holds for its members: the pair (member, other cue) recalls the rule's answers
    if TAX_INST > 0:
        members = {}
        for p in sorted(tax):
            if len(p) == 1 and p[0] in cid:
                ms = []
                for ch, depth in descend(p):
                    cs = [c for c in ids(list(ch)) if c != cid[p[0]]]
                    if cs:
                        ms.append((cs, TAX_DECAY ** depth))
                if len(ms) <= TAX_INST_MAX:
                    members[cid[p[0]]] = ms
        for kind, L, Rr in facts:
            if kind not in ("dir", "def"):
                continue
            Li = ids(L)
            Ri = [r for r in ids(Rr) if r not in Li]
            if len(Li) < 2 or not Ri:
                continue
            sp = TAX_INST * W_DIR_P * min(1.0, math.sqrt(2.0 / len(Ri))) * 2.0 / len(Li)
            gates = {cid[g] for g in NEGATED if g in cid} & set(Li)
            for a in Li:
                for cs, dec in members.get(a, ()):
                    for c in cs:
                        for b in Li:
                            if b == a or b == c or (gates and b not in gates):
                                continue
                            row = P[(min(b, c), max(b, c))]
                            for r in Ri:
                                if r != c:
                                    row[r] += sp * dec / len(cs)
    # many facts linking the same two concepts add up sublinearly (as in the pair table): being mentioned
    # together often shows relatedness, but should not outweigh one specific rule
    if A_UNIT > 0:
        for key in A:
            v = A[key]
            A[key] = math.copysign(math.sqrt(abs(v) * A_UNIT), v) if abs(v) > A_UNIT else v
    # a question concept that supports many answers (a hub) gives each of them less
    fan, fan_in = defaultdict(int), defaultdict(int)
    for (a, b) in A:
        fan[a] += 1
        fan_in[b] += 1
    for key in A:
        A[key] /= math.sqrt(1.0 + fan[key[0]] / FAN_REF) * math.sqrt(1.0 + fan_in[key[1]] / FAN_IN_REF)
    # adjective opposites (first order): what supports one of a pair argues against the other
    ant = []
    for part in ANTONYMS.replace("\n", " ").split(";"):
        x, y = part.split()
        cx, cy = cid.get(m.stem(x)), cid.get(m.stem(y))
        if cx and cy and cx != cy:
            ant.append((cx, cy))
    if ANT_OPP > 0 and ant:
        rows = defaultdict(dict)
        for (a, b), v in A.items():
            rows[a][b] = v
        for a, row in rows.items():
            for cx, cy in ant:
                u, d = row.get(cx, 0.0), row.get(cy, 0.0)
                if u > 0 or d > 0:
                    A[(a, cx)] = u - ANT_OPP * max(d, 0.0)
                    A[(a, cy)] = d - ANT_OPP * max(u, 0.0)
    # tiers: a pair keeps its directed-rule recalls first (see P2)
    if TIERS:
        for key in set(P) | set(P2):
            r1, r2 = P.get(key, {}), P2.get(key, {})
            tot = defaultdict(float)
            for b, v in r1.items():
                tot[b] += v
            for b, v in r2.items():
                tot[b] += v
            order = sorted(tot.items(), key=lambda kv: (kv[0] not in r1 or abs(r1[kv[0]]) < 1e-9, -abs(kv[1])))[:R]
            P[key] = defaultdict(float, order)
    else:
        for key, r2 in P2.items():
            for b, v in r2.items():
                P[key][b] += v
    P2.clear()
    # many rules recalling the same answer through the same pair add up sublinearly
    for row in P.values():
        for b in row:
            v = row[b]
            row[b] = math.copysign(math.sqrt(abs(v) * PAIR_UNIT), v)
    # generation 5: a concept that very many pair rows recall (heat, water, sun, light, motion) says little in any one
    # of them; the first-order table already damps such answers (FAN_IN_REF), the pair table did not
    if P_FAN_IN_REF > 0:
        pfan = defaultdict(int)
        for row in P.values():
            for b, v in row.items():
                if v > 0:
                    pfan[b] += 1
        for row in P.values():
            for b in row:
                if pfan[b] > 0:
                    row[b] /= math.sqrt(1.0 + pfan[b] / P_FAN_IN_REF)
    # a pair that recalls "more" argues against "less", and the other way round
    for ka, kb in OPPOSITES:
        up, down = cid.get(ka), cid.get(kb)
        if not (up and down and DIR_OPP > 0):
            continue
        for row in P.values():
            u, d = row.get(up, 0.0), row.get(down, 0.0)
            if u or d:
                row[up], row[down] = u - DIR_OPP * d, d - DIR_OPP * u
    if ANT_OPP > 0 and ant:
        for row in P.values():
            for cx, cy in ant:
                u, d = row.get(cx, 0.0), row.get(cy, 0.0)
                if u > 0 or d > 0:
                    row[cx], row[cy] = u - ANT_OPP * max(d, 0.0), d - ANT_OPP * max(u, 0.0)
    # negation: the pair (NOT, q) recalls q's first-order answers with negative weight, so that
    # 'which is NOT ...' / '... EXCEPT' turns the question's evidence around
    first = defaultdict(lambda: defaultdict(float))
    for (a, b), v in A.items():
        first[a][b] += MIX * v
    # words that together name one thing (a category such as "simple machine" or "fossil fuel", a defined term,
    # or the two cues of a short rule): in "which is NOT a simple machine" their pair recalls the members, so
    # (NOT, simple) must also take back what (simple, machine) recalls
    mates = set()
    def add_mates(ws):
        ws = [c for c in dict.fromkeys(ws) if c]
        if 2 <= len(ws) <= 3:
            for i in range(len(ws)):
                for j in range(i + 1, len(ws)):
                    mates.add((min(ws[i], ws[j]), max(ws[i], ws[j])))
    for par, chs in tax.items():
        for t in [par] + list(chs):
            add_mates(ids(list(t)))
    for kind, L, Rr in facts:
        if kind == "eq":
            add_mates(ids(L))
    partner = defaultdict(lambda: defaultdict(float))     # strongest recall of q through one phrase-mate
    for (lo, hi), row in list(P.items()):
        if (lo, hi) not in mates:
            continue
        for a, x in ((lo, hi), (hi, lo)):
            for b, v in row.items():
                if v > 0:
                    partner[a][b] = max(partner[a][b], v * idf[x])
    for key, gamma, pgamma in sorted(set(NEG_WORDS.values())):
        n = cid.get(key)
        if not n:
            continue
        idf[n] = IDF_NEG
        for a in set(first) | set(partner):
            tot = defaultdict(float)
            for b, v in first[a].items():
                tot[b] += gamma * v
            for b, v in partner[a].items():
                tot[b] += gamma * pgamma * v
            items = sorted(tot.items(), key=lambda kv: -abs(kv[1]))[:R]
            if NEG_KEEP_AGAINST > 0:
                # generation 5: keep a's strongest evidence against (renewable >! coal) in the row: under NOT it is
                # exactly what the question asks for, but it was pushed out by the larger positive recalls
                big = max((abs(v) for v in tot.values()), default=0.0)
                against = sorted((kv for kv in tot.items() if kv[1] < -0.3 * big), key=lambda kv: kv[1])[:NEG_KEEP_AGAINST]
                keep = [kv for kv in items if kv not in against][:R - len(against)]
                items = keep + against
            lo, hi = min(n, a), max(n, a)
            row = P[(lo, hi)]
            for b, v in items:
                row[b] += -v / IDF_NEG
    return vocab, word_c, C, idf, A, P, cid


def build():
    import gc
    global CID, MORPH
    vocab, word_c, C, idf, A, P, cid = build_tables()
    CID, MORPH = cid, Morph()
    del vocab
    if A:
        keys = np.array(list(A.keys()), dtype=np.int64)
        vals = np.array(list(A.values()), dtype=np.float32)
        del A
        At = torch.sparse_coo_tensor(torch.from_numpy(keys.T), torch.from_numpy(vals), (C, C)).coalesce()
        At = At.to_dense() if C <= 12000 else At
        if HOP2 > 0 and not At.is_sparse:
            # two-hop association: question concept -> b -> c (the second hop either way round)
            two = At @ (0.5 * (At + At.T))
            two.fill_diagonal_(0.0)
            scale = HOP2 * At.abs().sum() / max(float(two.abs().sum()), 1e-9)
            At.add_(two, alpha=float(scale))
            del two
        if RESTATE > 0 and not At.is_sparse:
            # "which is the independent (dependent) variable?": the answer names the factor the question already
            # describes as changed (measured), so every new concept an option brings counts against it
            for wd in RESTATE_WORDS:
                c = CID.get(MORPH.stem(wd))
                if c:
                    At[c, 1:] -= RESTATE
        if OFFSET > 0 and not At.is_sparse:
            # every option concept that the question does not support reads slightly negative, so an option that
            # only adds unrelated words falls below one that adds nothing new
            At.sub_(OFFSET)
    else:
        At = torch.zeros(C, C)

    # fold the pair rows into the hashed table: rows of pairs that share a slot are added, then each slot keeps
    # its R strongest recalls
    merged = defaultdict(lambda: defaultdict(float))
    for (lo, hi), row in P.items():
        tgt = merged[(lo * PRIME + hi) % H]
        for b, v in row.items():
            tgt[b] += v
    del P
    gc.collect()
    n = sum(min(len(r), R) for r in merged.values())
    hs = np.empty(n, np.int64); ks = np.empty(n, np.int64); bs = np.empty(n, np.int64); vs = np.empty(n, np.float32)
    t = 0
    for h, row in merged.items():
        items = sorted(row.items(), key=lambda kv: -abs(kv[1]))[:R]
        for k, (b, v) in enumerate(items):
            hs[t], ks[t], bs[t], vs[t] = h, k, b, v
            t += 1
    del merged
    gc.collect()
    row_ids = torch.zeros((H, R), dtype=torch.int64)
    row_w = torch.zeros((H, R), dtype=torch.float32)
    hs, ks = torch.from_numpy(hs), torch.from_numpy(ks)
    row_ids[hs, ks] = torch.from_numpy(bs)
    row_w[hs, ks] = torch.from_numpy(vs)
    return {
        "concept": torch.from_numpy(word_c),
        "idf": torch.from_numpy(idf.astype(np.float32)),
        "A": At,
        "row_ids": row_ids,
        "row_w": row_w,
        "mix": torch.tensor(MIX, dtype=torch.float32),
    }


if __name__ == "__main__":
    if "--vocab" in sys.argv:
        v = make_vocab()
        print(len(v), "words")
