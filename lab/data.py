"""Read only verbatim WSP paper artifacts (MIT, pinned commit).

The app does NOT execute the released build.py or arch.py and never calls
its educational scorer 'the original model'. Original result.json values
are always reported as published results, not recomputed measurements.
"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
from dataclasses import asdict, dataclass
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "sources" / "opus_mem_assoc2_g5"
PIN = "c3324efa7e8aeec9ff7b7303094799b67a20793b"
ORIGIN = "https://github.com/effl-lab/Weight-Space-Programming/blob/" + PIN
ORIGINAL_DIR = "models/opus/mem_assoc2_g5-arc_blind_K0_r0/"
FILES = (
    "facts_basic.txt", "facts_physics.txt", "facts_earth.txt",
    "facts_g2_miscon.txt", "facts_g5_reason.txt", "facts_g5_traps.txt",
    "facts_g3_direction.txt", "facts_life.txt", "facts_glossary.txt",
)
TOKEN = re.compile(r"#[a-z]+|[a-z0-9']+")
STOP = set("a an and are as at be by for from has have how i in into is it its "
           "of on or the their them these this to was were what when where which "
           "while who why with would could should can does do did not of".split())
KIND_LABEL = {
    "support": "手がかり → 支持する概念",
    "against": "手がかり → 反対の証拠",
    "definition": "用語 ↔ 定義",
    "topic": "同じ話題に属する概念",
}
PUBLISHED = {
    "test_questions": 3530,
    "chance_percent": 25.0,
    "writers": [
        {"name":"Claude Opus 5.5", "fixed":43.1,"transformer":36.1,"free_first":50.8,"free_last":54.4,"assoc_first":49.6,"assoc_last":52.4},
        {"name":"GPT-6.1 Sol", "fixed":35.0,"transformer":36.3,"free_first":44.6,"free_last":47.4,"assoc_first":41.2,"assoc_last":45.6},
        {"name":"GPT-6 Astra", "fixed":34.4,"transformer":32.6,"free_first":42.7,"free_last":46.2,"assoc_first":42.5,"assoc_last":47.4},
    ],
    "source": "Original authors' README: Results table, pinned at " + PIN,
}


def tokens(text):
    return [x for x in TOKEN.findall(str(text).lower()) if x not in STOP and len(x) > 1]


@dataclass(frozen=True)
class Fact:
    id: str
    path: str
    line: int
    text: str
    left: str
    right: str
    kind: str

    def public(self):
        data = asdict(self)
        data["url"] = source_url(self.path, self.line)
        return data


def source_url(path, line=1):
    if path.startswith("kb/"):
        return ORIGIN + "/" + ORIGINAL_DIR + path + "#L" + str(line)
    if path in ("arch.py", "build.py", "NOTES.md", "result.json"):
        return ORIGIN + "/" + ORIGINAL_DIR + path + "#L" + str(line)
    return ORIGIN


def parse_line(raw, path, line):
    content = raw.strip()
    if not content or content.startswith("#"):
        return None
    if ">!" in content:
        left,right = content.split(">!",1)
        kind = "against"
    elif ">" in content:
        left,right = content.split(">",1)
        kind = "support"
    elif "=" in content:
        left,right = content.split("=",1)
        kind = "definition"
    else:
        left = right = content
        kind = "topic"
    if not tokens(left) or not tokens(right):
        return None
    return Fact(path + ":" + str(line),path,line,content,left.strip(),right.strip(),kind)


@lru_cache(maxsize=1)
def facts():
    found = []
    for filename in FILES:
        path = "kb/" + filename
        data = (SNAPSHOT/path).read_text(encoding="utf-8")
        for line,raw in enumerate(data.splitlines(),1):
            row = parse_line(raw,path,line)
            if row:
                found.append(row)
    return tuple(found)


@lru_cache(maxsize=1)
def by_id():
    return {fact.id:fact for fact in facts()}


@lru_cache(maxsize=1)
def statistics():
    rows = facts()
    result = json.loads((SNAPSHOT/"result.json").read_text(encoding="utf-8"))
    return {
        "source_commit": PIN, "license": "MIT",
        "paper": "https://arxiv.org/abs/2611.22055",
        "original": "https://github.com/effl-lab/Weight-Space-Programming",
        "source_run": ORIGINAL_DIR.rstrip("/"),
        "types": dict(Counter(row.kind for row in rows)),
        "bundled_files": len(FILES),
        "bundled_fact_rows": len(rows),
        "selected_model":{
            "writer":result["writer"],"test_accuracy":result["test_accuracy"]*100,
            "weights":result.get("weights"),"nonzero":result.get("nonzero"),
            "source":"Original released result.json; not evaluated by this app",
        },
        "published": PUBLISHED,
        "caveat": "Bundled facts are a verbatim subset. The editable scorer is a separate, pedagogical approximation, NOT the original torch forward().",
    }


def lookup(query="", file="", kind="", limit=60):
    limit = max(1,min(120,int(limit)))
    phrase = str(query).strip().lower()
    if len(phrase) > 200:
        raise ValueError("検索語は200文字以内にしてください")
    items = []
    for item in facts():
        if file and item.path != file:
            continue
        if kind and item.kind != kind:
            continue
        if phrase and phrase not in item.text.lower():
            continue
        items.append(item.public())
        if len(items) >= limit:
            break
    return items


def source_lines(file, focus=1, context=54):
    file = str(file)
    accepted = {"arch.py","build.py","NOTES.md","result.json"}
    accepted.update("kb/"+x for x in FILES)
    if file not in accepted:
        raise ValueError("公開モデルの指定されたファイル以外は開けません")
    data = (SNAPSHOT/file).read_text(encoding="utf-8").splitlines()
    focus = max(1,min(len(data),int(focus)))
    context = max(10,min(120,int(context)))
    start = max(1,focus-context//2)
    end = min(len(data),start+context-1)
    return {
        "path":file, "total":len(data), "focus":focus,
        "url":source_url(file,focus),
        "lines":[{"line":n,"code":data[n-1]} for n in range(start,end+1)],
    }


# These questions are written for the classroom from identifiable released
# knowledge lines. They are NOT ARC benchmark questions and have no official
# accuracy label.
SCENARIOS = (
 {"id":"gravity","title":"Gravity / 重力","question":"Gravity pulls objects in which direction?",
  "options":["down toward Earth center","up away from Earth","toward the sun only","no motion"],"reference":"kb/facts_physics.txt:5"},
 {"id":"friction","title":"Friction / 摩擦","question":"Which materials and methods reduce friction?",
  "options":["oil grease lubricant wheels","sandpaper rough surfaces","more mass and gravity","no change"],"reference":"kb/facts_physics.txt:17"},
 {"id":"earth","title":"Earth / 地層","question":"Thickest layer earth: which layer is it?",
  "options":["mantle","crust","atmosphere","inner core"],"reference":"kb/facts_earth.txt:7"},
 {"id":"fossils","title":"Continental drift / 大陸移動","question":"Same fossils different continents: what does this suggest?",
  "options":["continents once joined together","separate origin and no motion","Earth has no crust","the oceans cannot move"],"reference":"kb/facts_g5_reason.txt:4"},
 {"id":"misconception","title":"Misconception / 誤概念","question":"What explains summer seasons?",
  "options":["Earth is closer to the sun","Earth tilted axis","magnetism","tides"],"reference":"kb/facts_g2_miscon.txt:3"},
)


def model_catalog():
    directory = ROOT/"sources"/"reference"
    answer = []
    for label,name in [("Opus・連想メモリ","../opus_mem_assoc2_g5/result.json"),
                       ("Sol・自由設計","sol_free5_result.json"),
                       ("Astra・自由設計","astra_free5_result.json")]:
        path = (directory/name).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        answer.append({"label":label,"writer":data["writer"],"architecture":data["arch"],
                       "test_accuracy":data["test_accuracy"]*100,
                       "validation_accuracy":data["validation"]["accuracy"]*100,
                       "weights":data.get("weights"),"nonzero":data.get("nonzero"),
                       "run":data["run_id"]})
    return answer
