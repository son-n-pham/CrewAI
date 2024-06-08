import asyncio
import os
from playwright.async_api import async_playwright
from markdownify import markdownify as md
from utils import get_env_key

OPENAI_EMAIL = get_env_key("OPENAI_EMAIL")
OPENAI_PASSWORD = get_env_key("OPENAI_PASSWORD")


async def setup_playwright(headless: bool = False, use_auth_state: bool = False):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(storage_state="auth_state.json" if use_auth_state else None)
    page = await context.new_page()
    return playwright, browser, context, page


async def login_chat_openai(page, url: str = "https://chat.openai.com"):
    await page.goto(url)

    # Wait for the login button to appear
    await page.wait_for_selector('[data-testid="login-button"]')
    await page.click('[data-testid="login-button"]')

    # Wait for the email input box to appear
    await page.wait_for_selector('#email-input.email-input')
    await page.fill('#email-input.email-input', OPENAI_EMAIL)

    # Wait for the continue button to appear
    await page.wait_for_selector('.continue-btn:has-text("Continue")')
    await page.click('.continue-btn:has-text("Continue")')

    # Input password, then click Continue to complete the login
    await page.wait_for_selector('#password')
    await page.fill('#password', OPENAI_PASSWORD)
    await page.wait_for_selector('._button-login-password:has-text("Continue")')
    await page.click('._button-login-password:has-text("Continue")')

    # Await for chat input box to appear to define that the login is successful
    input_selector = 'textarea[placeholder="Message ChatGPT"]'
    await page.wait_for_selector(input_selector)

    # Save authentication state to a file
    await page.context.storage_state(path="auth_state.json")


async def select_temporary_chat(page):
    await page.wait_for_selector('div[type="button"][aria-haspopup="menu"]')
    await page.click('div[type="button"][aria-haspopup="menu"]')

    await page.wait_for_selector('button[role="switch"]')
    aria_checked = await page.get_attribute('button[role="switch"]', 'aria-checked')
    is_temporary_chat = aria_checked == "true"

    if not is_temporary_chat:
        await page.click('button[role="switch"]')


async def select_gpt4o(page):
    await page.wait_for_selector('div[type="button"][aria-haspopup="menu"]')
    await page.click('div[type="button"][aria-haspopup="menu"]')

    await page.wait_for_selector('div:has-text("Newest and most advanced model")')
    gpt4o_div = await page.query_selector('div:has-text("Newest and most advanced model")')
    await gpt4o_div.click()


async def upload_file(page, file_path):
    await page.wait_for_selector('#prompt-textarea')
    await page.wait_for_selector('input[type="file"][multiple][style*="display: none"] + button ~ button')

    await page.click('input[type="file"][multiple][style*="display: none"] + button ~ button')

    await page.wait_for_selector('div[role="menu"] > :last-child')
    await page.click('div[role="menu"] > :last-child')

    # Handle the file chooser dialog
    async with page.expect_file_chooser() as fc_info:
        await page.click('input[type="file"][multiple][style*="display: none"] + button ~ button')
    file_chooser = await fc_info.value
    await file_chooser.set_files(file_path)


async def reuse_authentication_state(url: str):
    try:
        playwright, browser, context, page = await setup_playwright(headless=False, use_auth_state=True)
        await page.goto(url)

        input_selector = 'textarea[placeholder="Message ChatGPT"]'
        await page.wait_for_selector(input_selector, timeout=5000)

        return playwright, browser, context, page
    except Exception as e:
        print(f"An error occurred during session reuse: {e}")
        await browser.close()
        await playwright.stop()
        return None, None, None, None


async def identify_send_button(page, input_selector: str, message: str = None, file_path: str = None):
    initial_disabled_elements = await page.query_selector_all(':disabled')

    has_input = False

    if file_path:
        await upload_file(page, file_path)
        await asyncio.sleep(1)
        has_input = True

    if message:
        await page.fill(input_selector, message)
        await asyncio.sleep(1)
        has_input = True

    if has_input:
        disabled_elements_after_input = await page.query_selector_all(':disabled')

        send_button = None
        for element in initial_disabled_elements:
            if element not in disabled_elements_after_input:
                send_button = element
                break

        return send_button

    print("No input of file or message.")
    return None


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
    response_element = await page.query_selector(response_selector)

    response_html = await response_element.inner_html()
    response_markdown = md(response_html)
    return response_markdown


async def capture_screenshot(page, save_path: str):
    await asyncio.sleep(2)
    await page.screenshot(path=save_path, full_page=True)
    return save_path


async def interact_with_chatgpt_page(url: str = "https://chat.openai.com",
                                     message: str = "Hello, how are you?",
                                     file_path: str = None,
                                     save_path: str = "screenshot.png"):
    try:
        if os.path.exists("auth_state.json"):
            playwright, browser, context, page = await reuse_authentication_state(url)
            if page is not None:
                await select_temporary_chat(page)
                await select_gpt4o(page)

                input_selector = 'textarea[placeholder="Message ChatGPT"]'
                await page.wait_for_selector(input_selector)

                send_button = await identify_send_button(page, input_selector, message, file_path)

                if not await send_message(page, send_button):
                    return None, None

                response_markdown = await wait_for_response(page)
                screenshot_path = await capture_screenshot(page, save_path)

                await asyncio.sleep(10)
                await browser.close()
                await playwright.stop()
                return response_markdown, screenshot_path

        playwright, browser, context, page = await setup_playwright(headless=False, use_auth_state=False)
        await login_chat_openai(page, url)
        await select_temporary_chat(page)
        await select_gpt4o(page)

        input_selector = 'textarea[placeholder="Message ChatGPT"]'
        await page.wait_for_selector(input_selector)

        send_button = await identify_send_button(page, input_selector, message, file_path)

        if not await send_message(page, send_button):
            return None, None

        response_markdown = await wait_for_response(page)
        screenshot_path = await capture_screenshot(page, save_path)

        await asyncio.sleep(10)
        await browser.close()
        await playwright.stop()
        return response_markdown, screenshot_path
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
asyncio.run(interact_with_chatgpt_page(
    url="https://chat.openai.com",
    message="Summarize what you see from the attachment",
    file_path="c:/development/CrewAI/web_scrapping/screenshot.png",
    save_path="screenshot_from_gpt4o.png"))
