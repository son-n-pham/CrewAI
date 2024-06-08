import asyncio
from playwright.async_api import async_playwright
from markdownify import markdownify as md


async def setup_playwright(headless: bool = False):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context()
    page = await context.new_page()
    return playwright, browser, context, page


async def identify_send_button(page, input_selector: str, message: str):
    initial_disabled_elements = await page.query_selector_all(':disabled')
    await page.fill(input_selector, message)
    await asyncio.sleep(1)
    disabled_elements_after_input = await page.query_selector_all(':disabled')

    send_button = None
    for element in initial_disabled_elements:
        if element not in disabled_elements_after_input:
            send_button = element
            break

    return send_button


async def send_message(page, send_button):
    if send_button:
        await send_button.click()
    else:
        print("Send button not found.")
        return False
    return True


async def wait_for_response(page):
    # Wait for the send button to reappear by checking for a disabled state
    await page.wait_for_selector(':disabled', state='attached')

    # Wait for the "Stop generating" button to disappear
    stop_generating_button_selector = 'button[aria-label="Stop generating"]'
    await page.wait_for_selector(stop_generating_button_selector, state='detached')

    response_selector = 'div.text-message div.markdown'
    await page.wait_for_selector(response_selector)

    # Ensure all content is fully loaded
    # await asyncio.sleep(5)  # Wait additional time for content to fully load
    response_element = await page.query_selector(response_selector)

    response_html = await response_element.inner_html()
    response_markdown = md(response_html)
    return response_markdown


async def capture_screenshot(page, save_path: str):
    await asyncio.sleep(2)
    await page.screenshot(path=save_path, full_page=True)
    return save_path


async def interact_with_page(url: str, message: str, save_path: str) -> tuple:
    try:
        playwright, browser, context, page = await setup_playwright(headless=False)

        await page.goto(url)

        input_selector = 'textarea[placeholder="Message ChatGPT"]'
        await page.wait_for_selector(input_selector)

        send_button = await identify_send_button(page, input_selector, message)

        if not await send_message(page, send_button):
            return None, None

        response_markdown = await wait_for_response(page)
        screenshot_path = await capture_screenshot(page, save_path)

        await browser.close()
        await playwright.stop()

        return response_markdown, screenshot_path

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

# Example usage
response_text, screenshot_path = asyncio.run(interact_with_page(
    'https://chat.openai.com', 'You are an expert on writing poem, write a poem with 70 sentences about God and Jesus for me', 'screenshot.png'))
print(f"Response Text: {response_text}")
print(f"Screenshot Path: {screenshot_path}")
