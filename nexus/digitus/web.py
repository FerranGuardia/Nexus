"""Digitus Web — web actions with side effects via Playwright CDP."""

import base64
import os

from nexus.cdp import cdp_page


def _cdp_url(port: int) -> str:
    return "http://localhost:%d" % port


def web_click(text: str, port: int = 9222, heal: bool = False) -> dict:
    """Click an element by its visible text.

    Args:
        text: Visible text of element to click.
        port: CDP port.
        heal: If True, attempt self-healing recovery on failure.
    """
    with cdp_page(_cdp_url(port)) as page:
        try:
            locator = page.get_by_text(text, exact=False).first
            locator.click(timeout=5000)
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            return {
                "command": "web-click",
                "success": True,
                "clicked": text,
                "new_url": page.url,
                "new_title": page.title(),
            }
        except Exception as e:
            error_msg = str(e)[:200]

            # Attempt self-healing if enabled
            if heal:
                from nexus.digitus.healing import heal_web_click
                heal_result = heal_web_click(page, text, error_msg)
                if heal_result.get("healed"):
                    return {
                        "command": "web-click",
                        "success": True,
                        "clicked": text,
                        "healed": True,
                        "heal_strategy": heal_result.get("strategy", ""),
                        "new_url": page.url,
                        "new_title": page.title(),
                    }
                # Healing failed — include suggestions
                return {
                    "command": "web-click",
                    "success": False,
                    "target": text,
                    "error": error_msg,
                    "heal_attempted": True,
                    "suggestions": heal_result.get("suggestions", []),
                }

            # Gather clickable text alternatives so Claude can self-correct
            try:
                links_and_buttons = page.evaluate("""() => {
                    const els = document.querySelectorAll('a, button, [role="button"], [role="link"], input[type="submit"]');
                    return Array.from(els).map(el => el.innerText.trim()).filter(t => t.length > 0 && t.length < 80).slice(0, 10);
                }""")
            except Exception:
                links_and_buttons = []

            suggestions = []
            if links_and_buttons:
                suggestions.append("Clickable elements on page: %s" % ", ".join("'%s'" % t for t in links_and_buttons))
            suggestions.append("Use web_find to search for the element by partial text")

            return {
                "command": "web-click",
                "success": False,
                "target": text,
                "error": error_msg,
                "context": {"url": page.url, "title": page.title()},
                "suggestions": suggestions,
            }


def web_navigate(url: str, port: int = 9222) -> dict:
    """Navigate to a URL."""
    with cdp_page(_cdp_url(port)) as page:
        if not url.startswith("http"):
            url = "https://" + url
        try:
            page.goto(url, timeout=10000, wait_until="domcontentloaded")
            return {
                "command": "web-navigate",
                "success": True,
                "url": page.url,
                "title": page.title(),
            }
        except Exception as e:
            return {
                "command": "web-navigate",
                "success": False,
                "url": url,
                "error": str(e)[:200],
            }


def web_input(selector: str, value: str, port: int = 9222) -> dict:
    """Fill an input field by label, placeholder, or CSS selector."""
    with cdp_page(_cdp_url(port)) as page:
        try:
            locator = page.get_by_label(selector)
            if locator.count() == 0:
                locator = page.get_by_placeholder(selector)
            if locator.count() == 0:
                locator = page.locator(selector)
            locator.first.fill(value, timeout=5000)
            return {
                "command": "web-input",
                "success": True,
                "selector": selector,
                "value": value,
            }
        except Exception as e:
            # Gather available inputs so Claude can self-correct
            try:
                inputs = page.evaluate("""() => {
                    const els = document.querySelectorAll('input, textarea, select, [contenteditable="true"]');
                    return Array.from(els).map(el => {
                        const label = el.labels?.[0]?.innerText?.trim() || '';
                        return label || el.placeholder || el.name || el.id || el.type || '';
                    }).filter(t => t.length > 0).slice(0, 10);
                }""")
            except Exception:
                inputs = []

            suggestions = []
            if inputs:
                suggestions.append("Available inputs: %s" % ", ".join("'%s'" % i for i in inputs))
            suggestions.append("Try a CSS selector like 'input[name=...]' or use web_ax to inspect the form")

            return {
                "command": "web-input",
                "success": False,
                "selector": selector,
                "error": str(e)[:200],
                "context": {"url": page.url},
                "suggestions": suggestions,
            }


# Page format presets: name → (width_inches, height_inches)
_PAGE_FORMATS = {
    "A4": (8.27, 11.69),
    "Letter": (8.5, 11),
    "A3": (11.69, 16.54),
    "Legal": (8.5, 14),
}


def web_pdf(output: str = None, page_format: str = "A4",
            landscape: bool = False, port: int = 9222) -> dict:
    """Export current page to PDF via CDP Page.printToPDF."""
    with cdp_page(_cdp_url(port)) as page:
        try:
            dims = _PAGE_FORMATS.get(page_format, _PAGE_FORMATS["A4"])
            width, height = dims
            if landscape:
                width, height = height, width

            client = page.context.new_cdp_session(page)
            result = client.send("Page.printToPDF", {
                "paperWidth": width,
                "paperHeight": height,
                "marginTop": 0.4,
                "marginBottom": 0.4,
                "marginLeft": 0.4,
                "marginRight": 0.4,
                "printBackground": True,
                "landscape": landscape,
            })

            pdf_data = base64.b64decode(result["data"])

            if output:
                out_path = os.path.abspath(output)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(pdf_data)
                return {
                    "command": "web-pdf",
                    "success": True,
                    "path": out_path,
                    "size_bytes": len(pdf_data),
                    "format": page_format,
                    "url": page.url,
                }

            return {
                "command": "web-pdf",
                "success": True,
                "size_bytes": len(pdf_data),
                "format": page_format,
                "url": page.url,
                "data_b64": result["data"][:100] + "...(truncated)",
            }
        except Exception as e:
            return {
                "command": "web-pdf",
                "success": False,
                "error": str(e)[:200],
            }
