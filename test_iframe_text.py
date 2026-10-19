import asyncio
from playwright.async_api import async_playwright

async def test_pc_iframe():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        url = "https://cafe.naver.com/jmeat/1017417"
        await page.goto(url, wait_until="load", timeout=20000)
        await page.wait_for_timeout(3000)

        # iframe 찾기
        frames = page.frames
        print("Total frames:", len(frames))
        for i, f in enumerate(frames):
            print(f"Frame {i}: name='{f.name}', url='{f.url}'")
            try:
                text = await f.inner_text("body")
                if len(text) > 50:
                    print(f"  Frame {i} text len: {len(text)}")
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    print("  Preview:", lines[:5])
            except Exception as e:
                pass
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_pc_iframe())
