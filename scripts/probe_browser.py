"""Run inside the container: proves Browser Use connects without an LLM call."""
import asyncio
import sys
from browser_use import Browser


async def main():
    browser = Browser(cdp_url="http://127.0.0.1:9222", keep_alive=True,
                      headless=False, enable_default_extensions=False)
    try:
        await browser.start()
        page = await browser.get_current_page()
        assert page is not None, "No visible Chromium page"
        if len(sys.argv) > 1 and sys.argv[1] == "write":
            await page.goto("https://example.com")
            await page.evaluate("() => localStorage.setItem('cloud-assistant-profile-test', 'persisted')")
        if len(sys.argv) > 1 and sys.argv[1] == "read":
            await page.goto("https://example.com")
            value = await page.evaluate("() => localStorage.getItem('cloud-assistant-profile-test')")
            assert value == "persisted", f"Profile not retained: {value!r}"
        print("PASS: Browser Use CDP connected; title:", await browser.get_current_page_title())
    finally:
        await browser.stop()


asyncio.run(main())
