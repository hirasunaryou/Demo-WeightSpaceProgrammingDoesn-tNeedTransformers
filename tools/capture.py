"""Capture ACTUAL WSP study app with verbatim published knowledge lines.

Playwright is used ONLY by documentation CI and is not required by users.
"""
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab.server import serve


def main():
    from playwright.sync_api import sync_playwright
    url,server=serve()
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    images=ROOT/"docs"/"images"
    images.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1600,"height":1080},device_scale_factor=1)
            errors=[]
            page.on("pageerror",lambda exc:errors.append(str(exc)))
            page.emulate_media(color_scheme="dark")
            page.goto(url,wait_until="domcontentloaded")
            page.locator("#status").get_by_text("実際の公開知識行").wait_for(timeout=50000)
            assert page.locator("#scenarioChips button").count()==5
            page.locator("#evaluate").click()
            page.locator("#scoreBars .score-item").first.wait_for(timeout=20000)
            assert page.locator("#scoreBars .score-item").count()==4
            assert page.locator("#evidenceRows .evidence-row").count()>=1
            assert page.locator("#question").input_value().startswith("Gravity")
            page.locator("#stageLast").click()
            assert page.locator("#stageSeek").input_value()=="4"
            page.locator("#stageFirst").click()
            page.locator("#stagePlay").click()
            page.wait_for_timeout(320)
            page.locator("#stagePlay").click()
            assert int(page.locator("#stageSeek").input_value())<=4
            page.locator("#stageNext").click()
            assert int(page.locator("#stageSeek").input_value())>=1
            page.locator("#stageSeek").evaluate("""(el)=>{el.value="3";
              el.dispatchEvent(new Event("input",{bubbles:true}));}""")
            assert page.locator("#stageSeek").input_value()=="3"
            page.screenshot(path=str(images/"overview.png"),full_page=True)
            print("PASS: real authored source facts, four-choice evaluation, stage seek and screenshot")

            page.locator("#evidenceRows .evidence-row input[type=checkbox]").first.uncheck()
            page.locator("#scoreBars .score-delta").first.wait_for(timeout=20000)
            assert page.locator("#scoreBars .score-delta").count()>=1
            page.locator("#customRule").fill("gravity pulls objects > up away from earth")
            page.locator("#applyChanges").click()
            page.locator("#scoreBars .score-item").first.wait_for(timeout=20000)
            assert "Δ" in page.locator("#scoreBars").inner_text()
            page.screenshot(path=str(images/"ablation.png"),full_page=True)
            print("PASS: one-row ablation, added rule and real score-difference screenshot")

            page.locator('[data-tab="source"]').first.click()
            page.locator('[data-source="arch.py"]').first.click()
            page.locator("#editorCode .source-line.highlight").first.wait_for(timeout=15000)
            assert "arch.py" in page.locator("#editorPath").inner_text()
            assert "c3324efa" in page.locator("#editorLink").get_attribute("href")
            page.screenshot(path=str(images/"code.png"),full_page=True)
            print("PASS: original arch.py source viewer, line highlighting and screenshot")

            page.locator('[data-tab="research"]').first.click()
            assert page.locator("#resultChart .chart-group").count()==3
            assert page.locator("#modelMetrics .metric-card").count()==3
            assert page.locator(".paper-lead img").evaluate("(el)=>el.complete&&el.naturalWidth>200")
            page.screenshot(path=str(images/"research.png"),full_page=True)
            print("PASS: published data chart and official figure screenshot")

            page.locator('[data-tab="play"]').first.click()
            page.locator("#theme").click()
            assert page.locator("html").get_attribute("data-theme")=="light"
            page.screenshot(path=str(images/"light.png"),full_page=True)
            prior=float(page.locator(".visual-stage-description h3").evaluate(
                "(el)=>parseFloat(getComputedStyle(el).fontSize)"))
            page.locator("#fontUp").click()
            after=float(page.locator(".visual-stage-description h3").evaluate(
                "(el)=>parseFloat(getComputedStyle(el).fontSize)"))
            assert after>prior*1.2
            page.locator("#projector").click()
            assert page.locator("html").get_attribute("data-present")=="on"
            page.locator("#projector").click()
            assert page.locator("html").get_attribute("data-present")=="off"
            print("PASS: light/dark, projector mode, font scaling")
            assert not errors,errors

            mobile=browser.new_page(viewport={"width":390,"height":844})
            mobile.goto(url,wait_until="domcontentloaded")
            mobile.locator("#scenarioChips button").first.wait_for(timeout=40000)
            width=mobile.locator("html").evaluate("(el)=>({view:el.clientWidth,scroll:el.scrollWidth})")
            assert width["scroll"]<=width["view"]+1,("unexpected horizontal overflow",width)
            mobile.close()
            print("PASS: mobile 390px layout without horizontal overflow")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__=="__main__":
    main()
