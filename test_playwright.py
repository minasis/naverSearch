import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            url = "https://cafe.naver.com/jmeat/1017417"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=15000)

            # iframe 체크
            frame = page.frame(name="cafe_main")
            if frame:
                print("Found cafe_main iframe!")
                content = await frame.inner_text("body")
                print("Body text length:", len(content))
                print("Preview:", content[:300].replace('\n', ' '))
            else:
                print("No cafe_main iframe, checking page body...")
                content = await page.inner_text("body")
                print("Body len:", len(content))
            await browser.close()
    except Exception as e:
        print("Playwright error:", e)

if __name__ == "__main__":
    asyncio.run(test_playwright())
