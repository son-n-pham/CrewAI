import asyncio
from playwright.async_api import async_playwright, Page


async def wait_for_stable_network(page: Page, timeout: int = 30000):
    """
    Waits for the network to be stable by ensuring no requests are ongoing for a short period.
    """
    idle_count = 0
    max_idle_count = 5
    interval = 500  # Check every 500ms

    def increment_idle_count():
        nonlocal idle_count
        idle_count += 1

    def reset_idle_count():
        nonlocal idle_count
        idle_count = 0

    page.on("request", reset_idle_count)
    page.on("requestfinished", increment_idle_count)
    page.on("requestfailed", increment_idle_count)

    elapsed_time = 0

    while idle_count < max_idle_count and elapsed_time < timeout:
        await asyncio.sleep(interval / 1000)
        elapsed_time += interval

    if elapsed_time >= timeout:
        raise TimeoutError(f"Network did not stabilize within {timeout} ms")


async def capture_screenshot(url: str, save_path: str) -> str:
    try:
        # Launch Playwright browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to the webpage
            await page.goto(url)

            # Wait for the body element to ensure the initial load
            await page.wait_for_selector('body')

            # Wait for the network to be stable
            await wait_for_stable_network(page)

            # Capture screenshot of the full page
            await page.screenshot(path=save_path, full_page=True)

            # Close the browser
            await browser.close()

        # Return the file path to the saved screenshot
        return save_path

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Wrapper function to run the async function


def take_screenshot(url: str, output_path: str) -> str:
    return asyncio.run(capture_screenshot(url, output_path))


# Example usage:
url = "https://chat.openai.com"
output_path = "screenshot.png"
saved_image_path = take_screenshot(url, output_path)
print(f"Screenshot saved to {saved_image_path}")
