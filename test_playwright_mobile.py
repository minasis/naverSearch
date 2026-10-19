import asyncio
from playwright.async_api import async_playwright

async def test_mobile_playwright():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # 모바일 뷰포트
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                viewport={"width": 390, "height": 844}
            )
            page = await context.new_page()
            url = "https://m.cafe.naver.com/jmeat/1017417"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            # 본문 셀렉터 확인
            content = await page.inner_text("body")
            print("Body length:", len(content))
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            print("Sample lines:")
            for l in lines[:15]:
                print("  >", l)
            await browser.close()
    except Exception as e:
        print("Playwright error:", e)

if __name__ == "__main__":
    asyncio.run(test_mobile_playwright())
