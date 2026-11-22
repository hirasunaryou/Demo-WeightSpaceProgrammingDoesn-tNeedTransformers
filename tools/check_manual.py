"""Browser verification that the manual works as a single offline file."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    file=ROOT/"docs"/"MANUAL.html"
    text=file.read_text(encoding="utf-8")
    assert "<style>" in text
    assert text.count("data:image/png;base64,")>=4
    assert 'src="images/' not in text
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1440,"height":900},device_scale_factor=1)
        page.goto(file.as_uri(),wait_until="load")
        imgs=page.locator("img")
        assert imgs.count()>=4
        for img in imgs.all():
            assert img.evaluate("(node)=>node.complete&&node.naturalWidth>200"),"Unloaded source figure/screenshot"
        assert page.locator(".steps>div").count()==3
        assert page.locator(".cover").count()==0 # unrelated template must not leak
        assert page.locator(".mast").evaluate("(el)=>getComputedStyle(el).backgroundImage")!="none"
        page.screenshot(path=str(ROOT/"docs"/"images"/"manual-preview.png"),full_page=False)
        browser.close()
        print("PASS: CSS, four real/original images and offline HTML rendering")


if __name__=="__main__":
    main()
