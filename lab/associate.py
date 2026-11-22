"""Pure-stdlib, inspectable teaching analogue of the published WSP memory.

NOT the authors' compiled weights, token/concept mapping or forward() function.
Uses published row syntax and selected published constants to illustrate:
human-readable fact -> first-order links + hashed pair slots -> answer scores.
It cannot reproduce the paper's ARC accuracy. No inference claim is made.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
import math

from .data import facts, parse_line, source_url, tokens

H = 1 << 22
PRIME = 1000003
TOP_CONCEPTS = 16
MIX = 1.5
W_DIR_A = 1.5
W_DIR_P = 2.0
W_SYM_A = 1.0
W_SYM_P = 0.3
W_NEG = -0.7
MAX_CONTRIBUTIONS = 65


@dataclass(frozen=True)
class Link:
    target: int
    strength: float
    rule_id: str
    branch: str


def pair_address(a, b):
    lo,hi = sorted((int(a),int(b)))
    return (lo * PRIME + hi) % H


class EducationalMemory:
    def __init__(self, rules, base_memory=None):
        self.rules=tuple(rules)
        vocabulary=set()
        docfreq=Counter()
        for row in self.rules:
            term=set(tokens(row.left)+tokens(row.right))
            vocabulary.update(term)
            docfreq.update(term)
        if base_memory is not None:
            # The counterfactual must change only the NEW rule, not renumber
            # every concept in the pre-existing associative memory. An added
            # word is assigned an ID after all pre-existing vocabulary.
            old=set(base_memory.vocab)
            self.vocab=base_memory.vocab+tuple(sorted(vocabulary-old))
        else:
            self.vocab=tuple(sorted(vocabulary))
        self.ids={w:i+1 for i,w in enumerate(self.vocab)}
        n=max(1,len(self.rules))
        self.idf={w:(
            base_memory.idf[w] if base_memory is not None and w in base_memory.idf
            else math.log(1+(n-docfreq[w]+.5)/(docfreq[w]+.5))
        ) for w in self.vocab}
        self.A=defaultdict(list)
        self.P=defaultdict(list)
        self.counts=Counter()
        for row in self.rules:
            self._compile_row(row)

    def _compile_row(self, row):
        cue=set(tokens(row.left))
        out=set(tokens(row.right))
        if not cue or not out:
            return
        if row.kind=="definition":
            directions=[(cue,out,1.0),(out,cue,0.75)]
        elif row.kind=="topic":
            # Topic rows are loosely symmetric; illustrative only.
            everything=list(cue)
            directions=[(set([word]),set(everything)-{word},0.3)
                        for word in everything[:18]]
        else:
            directions=[(cue,out,W_NEG if row.kind=="against" else 1.0)]
        for cues,targets,sign in directions:
            known=[self.ids[w] for w in sorted(cues) if w in self.ids][:18]
            values=[self.ids[w] for w in sorted(targets) if w in self.ids][:22]
            if not known or not values:
                continue
            base1=(W_SYM_A if row.kind in ("definition","topic") else W_DIR_A)*sign
            base2=(W_SYM_P if row.kind in ("definition","topic") else W_DIR_P)*sign
            den1=max(1.0,math.sqrt(len(known)))
            for x in known:
                for y in values:
                    self.A[x].append(Link(y,base1/den1,row.id,"first"))
                    self.counts["first"]+=1
            pairs=list(combinations(known,2))
            den2=max(1.0,math.sqrt(len(pairs)))
            for a,b in pairs[:170]:
                slot=pair_address(a,b)
                for y in values:
                    self.P[slot].append(Link(y,base2/den2,row.id,"pair"))
                    self.counts["pairs"]+=1

    def public_metadata(self):
        return {
            "words":len(self.vocab),"rows":len(self.rules),
            "first_links":self.counts["first"],"pair_links":self.counts["pairs"],
            "materialized_pair_slots":len(self.P),
            "possible_pair_slots":H,"hash_prime":PRIME,
            "pair_slots_per_row_in_original":16,
            "top_question_concepts_in_original":TOP_CONCEPTS,
            "original_source_constants":{"W_DIR_A":W_DIR_A,"W_DIR_P":W_DIR_P,
                                         "W_NEG":W_NEG,"MIX":MIX},
            "label":"Educational analogue; original build.py/arch.py are not run.",
        }

    def score(self, question, options, disabled=()):
        removed=set(disabled)
        words=[x for x in set(tokens(question)) if x in self.ids]
        ranked=sorted(words,key=lambda w:(-self.idf[w],w))[:TOP_CONCEPTS]
        present={self.ids[w] for w in ranked}
        accumulated=defaultdict(float)
        contributions=[]
        first_hits=0
        pair_hits=0
        for word in ranked:
            word_id=self.ids[word]
            strength=self.idf[word]*MIX
            for edge in self.A.get(word_id,()):
                if edge.rule_id in removed or edge.target in present:
                    continue
                delta=strength*edge.strength
                accumulated[edge.target]+=delta
                contributions.append((edge.target,edge.rule_id,delta,"first",word))
                first_hits+=1
        pairs=[]
        for left,right in combinations(ranked,2):
            a,b=self.ids[left],self.ids[right]
            address=pair_address(a,b)
            hits=0
            factor=self.idf[left]*self.idf[right]
            for edge in self.P.get(address,()):
                if edge.rule_id in removed or edge.target in present:
                    continue
                delta=factor*edge.strength
                accumulated[edge.target]+=delta
                contributions.append((edge.target,edge.rule_id,delta,"pair",left+" + "+right))
                pair_hits+=1
                hits+=1
            pairs.append({"left":left,"right":right,"address":address,"materialized":hits>0,
                          "contributions":hits})
        inverse={self.ids[word]:word for word in self.vocab}
        scores=[]
        for option in options:
            words=set(tokens(option))
            selected=[self.ids[w] for w in words if w in self.ids and self.ids[w] not in present]
            score=sum(accumulated.get(t,0.0)*self.idf[inverse[t]] for t in selected)
            by_rule=Counter()
            by_branch=defaultdict(lambda:{"first":0.0,"pair":0.0,"terms":set()})
            for target,source,delta,branch,cue in contributions:
                if target not in selected:
                    continue
                weighted=delta*self.idf[inverse[target]]
                by_rule[source]+=weighted
                by_branch[source][branch]+=weighted
                by_branch[source]["terms"].add(inverse[target])
            ranked_rows=sorted(by_rule,key=lambda rid:abs(by_rule[rid]),reverse=True)
            evidence=[]
            for rid in ranked_rows[:MAX_CONTRIBUTIONS]:
                row=next((r for r in self.rules if r.id==rid),None)
                if not row:
                    continue
                evidence.append({
                    "id":rid, "text":row.text, "path":row.path, "line":row.line,
                    "kind":row.kind,"url":source_url(row.path,row.line),
                    "effect":round(by_rule[rid],4),
                    "first":round(by_branch[rid]["first"],4),
                    "pair":round(by_branch[rid]["pair"],4),
                    "matched_concepts":sorted(by_branch[rid]["terms"])[:10],
                })
            scores.append({"option":option,"score":round(score,4),
                           "unknown_words":sorted(w for w in words if w not in self.ids),
                           "evidence":evidence[:12]})
        values=[item["score"] for item in scores]
        unique=sorted(values,reverse=True)
        winning=values.index(unique[0]) if unique and unique[0]>0 and (
            len(unique)<2 or unique[0]>unique[1]+1e-8) else None
        return {
            "scores":scores,"choice":winning,
            "question_concepts":[{"word":w,"concept":self.ids[w],"idf":round(self.idf[w],3)}
                                 for w in ranked],
            "pair_addresses":pairs[:70],
            "first_order_activations":first_hits,
            "second_order_activations":pair_hits,
            "memory_read_terms": [
                {"concept":inverse[idx],"value":round(val,4)}
                for idx,val in sorted(accumulated.items(),
                                      key=lambda pair:abs(pair[1]),reverse=True)[:24]
            ],
            "unresolved":winning is None,
        }


@lru_cache(maxsize=1)
def released_subset_memory():
    return EducationalMemory(facts())


def validate(question, choices, disabled, custom):
    if not isinstance(question,str) or not 0 < len(question.strip()) <= 500:
        raise ValueError("質問は1〜500文字で入力してください")
    if not isinstance(choices,list) or len(choices)!=4 or any(
        not isinstance(x,str) or not 0<len(x.strip())<=180 for x in choices
    ):
        raise ValueError("選択肢は4件、各180文字以内で入力してください")
    if not isinstance(disabled,list) or len(disabled)>50 or any(
        not isinstance(x,str) or len(x)>160 for x in disabled
    ):
        raise ValueError("無効化するルールの指定が不正です")
    if not isinstance(custom,str) or len(custom)>300:
        raise ValueError("追加ルールは300文字以内で入力してください")
    return question.strip(),[x.strip() for x in choices],disabled,custom.strip()


def evaluate(question, choices, disabled=None, custom=""):
    q,o,disabled,custom=validate(question,choices,disabled or [],custom)
    memory=released_subset_memory()
    baseline=memory.score(q,o)
    if custom:
        extra=parse_line(custom,"local/demo_added_rule.txt",1)
        if not extra:
            raise ValueError("追加ルールの書式が不正です。例: gravity pulls > down")
        # The custom rule is never written to original data or GitHub.
        updated=EducationalMemory(list(memory.rules)+[extra],base_memory=memory)
        changed=updated.score(q,o,disabled)
    else:
        updated=memory
        changed=memory.score(q,o,disabled)
    return {
        "baseline":baseline,"edited":changed,
        "changes":[round(a["score"]-b["score"],4)
                   for a,b in zip(changed["scores"],baseline["scores"])],
        "mode":"educational_analogue",
        "original_model_executed":False,
        "original_facts_used":True,
        "disabled_count":len(disabled),"custom_rule":custom,
        "weights":updated.public_metadata(),
        "limitations":[
            "Source fact lines are verbatim. Word->concept mapping is a tiny simplified vocabulary.",
            "IDF, link compilation, hashing and scores are educational approximations, not original PyTorch weights.",
            "Original reported ARC test accuracy is NOT measured by this UI.",
            "Existing concept IDs and IDF are frozen during a custom-row ablation to avoid unrelated score drift.",
            "Changing one rule in this app does not edit original released model weights.",
        ],
    }
