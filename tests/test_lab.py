"""Zero-dependency tests for the educational WSP demo.

No test uses PyTorch or claims to reproduce the authors' 3,530 ARC tests.
Verbatim original knowledge text and published result.json are tested separately
from the locally defined explanatory scoring analogue.
"""
import json
import re
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from lab import data
from lab.associate import (
    released_subset_memory, pair_address, evaluate, H, PRIME, MIX
)
from lab.server import serve


class OriginalArtifactsTests(unittest.TestCase):
    def test_exact_upstream_facts(self):
        rows=data.facts()
        self.assertGreater(len(rows),450)
        sample=next(r for r in rows if r.text=="gravity pulls objects > down toward earth center")
        self.assertEqual(sample.kind,"support")
        self.assertEqual(sample.path,"kb/facts_physics.txt")
        self.assertIn("github.com/effl-lab",sample.public()["url"])
        negative=next(r for r in rows if r.text=="seasons summer >! closer to sun")
        self.assertEqual(negative.kind,"against")
        self.assertTrue(any(r.kind=="definition" for r in rows))
        self.assertTrue(any(r.kind=="topic" for r in rows))

    def test_original_model_metrics_are_reported_not_inferred(self):
        stats=data.statistics()
        self.assertEqual(stats["selected_model"]["weights"],152965194)
        self.assertEqual(stats["selected_model"]["nonzero"],6241790)
        self.assertAlmostEqual(stats["selected_model"]["test_accuracy"],52.3725212464,places=4)
        self.assertEqual(stats["published"]["test_questions"],3530)
        self.assertEqual(stats["published"]["writers"][0]["free_last"],54.4)
        self.assertFalse("correctness" in stats["selected_model"])

    def test_source_browser_rejects_traversal(self):
        detail=data.source_lines("arch.py",focus=15)
        self.assertIn("import torch", "\n".join(x["code"] for x in detail["lines"]))
        with self.assertRaises(ValueError):
            data.source_lines("../../etc/passwd")
        with self.assertRaises(ValueError):
            data.source_lines("sources/reference/LICENSE")
        self.assertEqual(detail["path"],"arch.py")
        self.assertIn("c3324efa",detail["url"])

    def test_fact_parser_preserves_original_syntax(self):
        self.assertIsNone(data.parse_line("# comment","kb/test.txt",1))
        self.assertEqual(data.parse_line("snow > ice","kb/test.txt",1).kind,"support")
        self.assertEqual(data.parse_line("winter >! heat","kb/test.txt",1).kind,"against")
        self.assertEqual(data.parse_line("stem = word","kb/test.txt",1).kind,"definition")
        self.assertEqual(data.parse_line("sun moon","kb/test.txt",1).kind,"topic")
        self.assertTrue(len(data.lookup("gravity"))>0)


class EducationalAnalogueTests(unittest.TestCase):
    def test_illustrative_pair_address_uses_source_formula(self):
        self.assertEqual(H,2**22)
        self.assertEqual(PRIME,1000003)
        self.assertEqual(pair_address(2,3),(2*1000003+3)%H)
        self.assertEqual(pair_address(3,2),pair_address(2,3))
        self.assertEqual(MIX,1.5)

    def test_rules_compile_to_first_and_second_order_links(self):
        model=released_subset_memory()
        m=model.public_metadata()
        self.assertGreater(m["first_links"],0)
        self.assertGreater(m["pair_links"],0)
        self.assertGreater(m["materialized_pair_slots"],0)
        self.assertLess(m["materialized_pair_slots"],2**22)
        self.assertEqual(m["label"].startswith("Educational analogue"),True)

    def test_four_option_trace_and_ablation(self):
        scenario=data.SCENARIOS[0]
        baseline=evaluate(scenario["question"],scenario["options"])
        self.assertEqual(baseline["mode"],"educational_analogue")
        self.assertFalse(baseline["original_model_executed"])
        self.assertEqual(len(baseline["baseline"]["scores"]),4)
        self.assertTrue(baseline["baseline"]["question_concepts"])
        self.assertTrue(baseline["baseline"]["pair_addresses"])
        evidence=[r for s in baseline["baseline"]["scores"] for r in s["evidence"]]
        self.assertTrue(evidence)
        target=next((r["id"] for r in evidence if "gravity pulls objects >" in r["text"]),evidence[0]["id"])
        changed=evaluate(scenario["question"],scenario["options"],disabled=[target])
        self.assertTrue(changed["disabled_count"]==1)
        self.assertTrue(any(abs(x)>0 for x in changed["changes"]))
        self.assertEqual(baseline["baseline"],changed["baseline"])

    def test_custom_rule_changes_only_teaching_copy(self):
        sc=data.SCENARIOS[0]
        baseline=evaluate(sc["question"],sc["options"])
        changed=evaluate(sc["question"],sc["options"],
                         custom="gravity pulls objects > upward")
        self.assertFalse(changed["original_model_executed"])
        self.assertEqual(changed["baseline"],baseline["baseline"])
        self.assertTrue(any(abs(x)>0 for x in changed["changes"]))
        self.assertEqual(data.statistics()["source_commit"],
                         "c3324efa7e8aeec9ff7b7303094799b67a20793b")
        self.assertFalse((data.SNAPSHOT/"kb"/"local/demo_added_rule.txt").exists())

    def test_inputs_rejected(self):
        with self.assertRaises(ValueError):
            evaluate("",["A","B","C","D"])
        with self.assertRaises(ValueError):
            evaluate("test",["A","B"])
        with self.assertRaises(ValueError):
            evaluate("test",["A","B","C","D"],custom="x"*301)
        with self.assertRaises(ValueError):
            evaluate("test",["A","B","C","D"],disabled=["bad"]*60)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url,cls.server=serve()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def get(self,path):
        with urlopen(self.url+path,timeout=30) as resp:
            return resp.read(),resp.headers

    def post(self,path,data):
        req=Request(self.url+path,data=json.dumps(data).encode("utf-8"),
                    headers={"Content-Type":"application/json"})
        with urlopen(req,timeout=30) as resp:
            return json.load(resp)

    def test_local_api_and_csp(self):
        body,headers=self.get("api/catalog")
        payload=json.loads(body)
        self.assertGreater(payload["statistics"]["bundled_fact_rows"],450)
        self.assertEqual(len(payload["scenarios"]),5)
        self.assertEqual(len(payload["models"]),3)
        page,h=self.get("")
        self.assertIn(b"WSP",page)
        self.assertIn(b"script-src 'self'",h.get("Content-Security-Policy",""))
        self.assertIn("facts_physics",self.get("api/facts?q=gravity")[0].decode("utf-8"))
        src=json.loads(self.get("api/source?file=arch.py&line=15")[0])
        self.assertEqual(src["path"],"arch.py")

    def test_http_evaluate_and_escape(self):
        sc=data.SCENARIOS[0]
        out=self.post("api/evaluate",{"question":sc["question"],"options":sc["options"]})
        self.assertFalse(out["original_model_executed"])
        self.assertIn("original torch",out["limitations"][1])
        self.assertEqual(len(out["edited"]["scores"]),4)
        with self.assertRaises(HTTPError) as ctx:
            self.get("api/source?file=../../etc/passwd")
        self.assertEqual(ctx.exception.code,400)

    def test_source_utf8_and_figure_integrity(self):
        for file in ("web/index.html","web/styles.css","web/app.js"):
            path=data.ROOT/file
            content=path.read_text(encoding="utf-8",errors="strict")
            self.assertNotIn("\ufffd",content)
        self.assertIn('charset="utf-8"',(data.ROOT/"web/index.html").read_text())
        for figure in ("original_teaser.png","original_architecture.png",
                       "original_designed_three.png","original_speed.png"):
            raw=(data.ROOT/"assets"/figure).read_bytes()
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__=="__main__":
    unittest.main()
