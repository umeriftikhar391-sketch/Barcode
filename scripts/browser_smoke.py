"""Exercise the real built frontend/service. Run with service on loopback 8765."""

from pathlib import Path
import json, urllib.request, re
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
token = json.load(urllib.request.urlopen(BASE + "/api/session"))["token"]
headers = {"X-Session-Token": token, "Content-Type": "application/json"}
original = json.load(
    urllib.request.urlopen(urllib.request.Request(BASE + "/api/queue", headers=headers))
)


def restore():
    urllib.request.urlopen(
        urllib.request.Request(
            BASE + "/api/queue",
            data=json.dumps(original).encode(),
            headers=headers,
            method="PUT",
        )
    ).close()


try:
    empty = {**original, "products": []}
    urllib.request.urlopen(
        urllib.request.Request(
            BASE + "/api/queue",
            data=json.dumps(empty).encode(),
            headers=headers,
            method="PUT",
        )
    ).close()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Only loopback is allowed: no cloud/CDN dependency for this workflow.
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(BASE)
                else route.abort()
            ),
        )
        page.goto(BASE)
        page.get_by_role("heading", name="Add a product").wait_for()
        page.get_by_label("Product name", exact=True).fill("Chamakpatti Coaster")
        page.get_by_label("Barcode", exact=True).fill("1000111")
        page.get_by_label("Numeric price").fill("1200.50")
        page.get_by_label("Label quantity").fill("7")
        page.get_by_role("button", name="Save to queue").click()
        page.get_by_role("status").filter(has_text="Product saved").wait_for()
        page.get_by_role("button", name=re.compile("Print queue")).click()
        assert page.get_by_text("1000111 · manual").is_visible()
        page.get_by_role("button", name=re.compile("Print preview")).click()
        page.get_by_alt_text("Rendered physical row 3", exact=True).wait_for()
        assert page.locator(".preview img").count() == 3
        page.get_by_text("Invalid geometry — preview only", exact=True).wait_for()
        page.screenshot(path=str(ROOT / ".local/browser-preview.png"), full_page=True)
        page.get_by_label("Queue save status").filter(
            has_text="Saved locally"
        ).wait_for()
        page.reload()
        page.get_by_role("heading", name="Add a product").wait_for()
        page.get_by_role("button", name=re.compile("Print queue")).click()
        assert page.get_by_text("1000111 · manual").is_visible()
        page.get_by_role("button", name=re.compile("Excel import")).click()
        page.get_by_label("Product spreadsheet").set_input_files(
            str(ROOT / "tests/fixtures/odoo.xlsx")
        )
        page.get_by_text("odoo.xlsx", exact=True).wait_for()
        page.get_by_label("Labels per imported product").fill("2")
        page.get_by_label("I confirm the mappings", exact=False).check()
        page.get_by_role("button", name="Validate and preview import").click()
        page.get_by_role("heading", name="1 valid · 1 invalid").wait_for()
        page.get_by_label("I reviewed numeric barcode cells", exact=False).check()
        page.get_by_role("button", name="Validate and preview import").click()
        page.get_by_role("heading", name="2 valid · 0 invalid").wait_for()
        assert not errors, errors
        browser.close()
    print(
        "Browser smoke passed: manual entry, 7-label/3-row preview, reload persistence, supplied workbook mapping and numeric-barcode review; no external requests or page errors."
    )
finally:
    restore()
