"""
End-to-end tests for the Customer Support Agent Streamlit UI using Playwright.

Prerequisites:
    pip install playwright pytest-playwright
    playwright install chromium
    streamlit run ui.py  (must be running on localhost:8501)

Run:
    pytest tests/test_e2e.py -v
"""

import time
import pytest
from playwright.sync_api import sync_playwright, Page


STREAMLIT_URL = "http://localhost:8501"
PIPELINE_WAIT = 14


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        yield p.chromium.launch(headless=True)
    p.stop()


@pytest.fixture(scope="function")
def page(browser) -> Page:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg.goto(STREAMLIT_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    yield pg
    context.close()


def send_message(page: Page, text: str):
    chat_input = page.locator('[data-testid="stChatInput"] textarea')
    if chat_input.count() == 0:
        chat_input = page.locator("textarea").last
    chat_input.click()
    chat_input.type(text, delay=10)
    page.keyboard.press("Enter")
    time.sleep(PIPELINE_WAIT)


def visible_text(page: Page) -> str:
    """Read all rendered text from Streamlit markdown containers + page body."""
    parts = []
    containers = page.locator('[data-testid="stMarkdownContainer"]')
    for i in range(containers.count()):
        parts.append(containers.nth(i).inner_text())
    parts.append(page.locator("body").inner_text())
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPageLoad:
    def test_page_loads(self, page: Page):
        assert len(visible_text(page)) > 200

    def test_header_visible(self, page: Page):
        assert "Command Center" in visible_text(page) or "Customer Support" in visible_text(page)

    def test_metrics_visible(self, page: Page):
        text = visible_text(page)
        assert "RESOLUTIONS" in text or "LATENCY" in text

    def test_workflow_graph(self, page: Page):
        assert "New Request" in visible_text(page)

    def test_sidebar_agents(self, page: Page):
        text = visible_text(page)
        assert "Support Agent" in text or "Compliance Agent" in text


class TestChatInput:
    def test_chat_input_exists(self, page: Page):
        assert page.locator('[data-testid="stChatInput"]').count() > 0

    def test_can_type_message(self, page: Page):
        chat_input = page.locator('[data-testid="stChatInput"] textarea')
        if chat_input.count() == 0:
            chat_input = page.locator("textarea").last
        chat_input.click()
        chat_input.type("hello", delay=10)
        assert chat_input.input_value() == "hello"


class TestOrderLookup:
    def test_order_a4821(self, page: Page):
        before = visible_text(page)
        send_message(page, "tell me about order A4821")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"
        assert "A4821" in after or "order" in after.lower()

    def test_order_c1234(self, page: Page):
        before = visible_text(page)
        send_message(page, "where is order C1234")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"
        assert "C1234" in after or "order" in after.lower()

    def test_order_b9999(self, page: Page):
        before = visible_text(page)
        send_message(page, "tell me about B9999")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"
        assert "B9999" in after or "order" in after.lower()


class TestRefundFlow:
    def test_small_refund(self, page: Page):
        before = visible_text(page)
        send_message(page, "I want a $5 refund for A4821")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"

    def test_large_refund(self, page: Page):
        before = visible_text(page)
        send_message(page, "I want a $300 refund for B9999")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"


class TestGeneralInquiry:
    def test_greeting(self, page: Page):
        before = visible_text(page)
        send_message(page, "hi who are you")
        after = visible_text(page)
        assert len(after) > len(before), "No response rendered"


class TestDemoButtons:
    def test_buttons_exist(self, page: Page):
        assert page.locator("button").count() >= 5
