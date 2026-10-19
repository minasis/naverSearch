import asyncio
from playwright.async_api import async_playwright

async def get_cafe_main_content():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        url = "https://cafe.naver.com/jmeat/1017417"
        await page.goto(url, wait_until="networkidle", timeout=20000)

        frame = page.frame(name="cafe_main")
        if frame:
            print("Found cafe_main! Waiting for content...")
            try:
                elem = await frame.wait_for_selector(".se-main-container, .article_viewer, .ContentRenderer", timeout=10000)
                text = await elem.inner_text()
                print("Article body length:", len(text))
                print("Body Preview:\n", text[:400])
            except Exception as e:
                print("Selector wait error:", e)
                # 프레임 전체 텍스트
                text = await frame.inner_text("body")
                print("Frame body text len:", len(text))
                print("Preview:", text[:300].replace('\n', ' '))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_cafe_main_content())
