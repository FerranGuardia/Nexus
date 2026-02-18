"""Oculus Web — read-only web awareness via Playwright CDP.

Every function uses cdp_page() explicitly, takes typed params, returns a dict.
Tab targeting via `tab` param (default 0 = first tab).
Port targeting via `port` param (default 9222 = Chrome, other ports for Electron apps).
"""

from nexus.cdp import cdp_page, cdp_browser


def _cdp_url(port: int) -> str:
    return "http://localhost:%d" % port


def web_describe(tab: int = 0, full: bool = False, port: int = 9222) -> dict:
    """Describe the current web page.

    Default (concise): title, URL, focused element, visible form fields, CTA buttons, h1.
    full=True: all headings, all links, all inputs (original verbose behavior).
    """
    with cdp_page(_cdp_url(port)) as page:
        if full:
            data = page.evaluate("""() => {
                const headings = [...document.querySelectorAll('h1,h2,h3')].slice(0, 20).map(h => ({
                    level: h.tagName,
                    text: h.innerText.trim().substring(0, 120)
                }));
                const links = [...document.querySelectorAll('a[href]')].slice(0, 40).map(a => ({
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim().substring(0, 80),
                    href: a.href
                })).filter(l => l.text);
                const inputs = [...document.querySelectorAll('input,textarea,select')].slice(0, 15).map(el => ({
                    type: el.type || el.tagName.toLowerCase(),
                    name: el.name || el.id || '',
                    placeholder: el.placeholder || '',
                    label: el.labels?.[0]?.innerText?.trim() || el.getAttribute('aria-label') || '',
                    value: el.value?.substring(0, 50) || ''
                }));
                const buttons = [...document.querySelectorAll('button,[role="button"]')].slice(0, 20).map(b => ({
                    text: (b.innerText || b.getAttribute('aria-label') || '').trim().substring(0, 60)
                })).filter(b => b.text);
                return { headings, links, inputs, buttons };
            }""")
            return {
                "command": "web-describe",
                "title": page.title(),
                "url": page.url,
                "headings": data["headings"],
                "links": data["links"],
                "inputs": data["inputs"],
                "buttons": data["buttons"],
                "link_count": len(data["links"]),
            }
        else:
            # Concise mode: title, URL, h1, focused element, visible inputs, CTA buttons
            data = page.evaluate("""() => {
                const focused = document.activeElement;
                const focusedInfo = focused && focused !== document.body ? {
                    tag: focused.tagName.toLowerCase(),
                    text: (focused.innerText || focused.value || focused.getAttribute('aria-label') || '').trim().substring(0, 80),
                    type: focused.type || null,
                } : null;
                const inputs = [...document.querySelectorAll('input:not([type="hidden"]),textarea,select')]
                    .filter(el => {
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })
                    .slice(0, 10).map(el => ({
                        type: el.type || el.tagName.toLowerCase(),
                        label: el.labels?.[0]?.innerText?.trim() || el.getAttribute('aria-label') || el.placeholder || el.name || '',
                        value: el.value?.substring(0, 50) || ''
                    }));
                const buttons = [...document.querySelectorAll('button,[role="button"],a.btn,a.button,[type="submit"]')]
                    .filter(el => {
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })
                    .slice(0, 8).map(b => ({
                        text: (b.innerText || b.getAttribute('aria-label') || '').trim().substring(0, 60)
                    })).filter(b => b.text);
                const h1 = document.querySelector('h1');
                const heading = h1 ? h1.innerText.trim().substring(0, 120) : null;
                return { focused: focusedInfo, inputs, buttons, heading };
            }""")
            return {
                "command": "web-describe",
                "title": page.title(),
                "url": page.url,
                "heading": data.get("heading"),
                "focused": data.get("focused"),
                "inputs": data["inputs"],
                "buttons": data["buttons"],
            }


def web_text(tab: int = 0, port: int = 9222) -> dict:
    """Get the visible text content of the page."""
    with cdp_page(_cdp_url(port)) as page:
        text = page.inner_text("body")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return {
            "command": "web-text",
            "title": page.title(),
            "url": page.url,
            "text": "\n".join(lines[:200]),
            "line_count": len(lines),
            "truncated": len(lines) > 200,
        }


def web_find(query: str, tab: int = 0, port: int = 9222) -> dict:
    """Find visible elements on the page matching text."""
    with cdp_page(_cdp_url(port)) as page:
        results = page.evaluate("""(query) => {
            const q = query.toLowerCase();
            const all = document.querySelectorAll('a, button, [role="button"], h1, h2, h3, h4, span, p, li, td, label, input, [role="link"], [role="tab"]');
            const matches = [];
            for (const el of all) {
                const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                if (text.toLowerCase().includes(q)) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        matches.push({
                            tag: el.tagName.toLowerCase(),
                            text: text.substring(0, 120),
                            href: el.href || null,
                            role: el.getAttribute('role') || null,
                            bounds: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    }
                }
                if (matches.length >= 20) break;
            }
            return matches;
        }""", query)
        return {
            "command": "web-find",
            "query": query,
            "url": page.url,
            "matches": results,
            "count": len(results),
        }


def web_links(tab: int = 0, port: int = 9222) -> dict:
    """List all unique links on the current page."""
    with cdp_page(_cdp_url(port)) as page:
        links = page.evaluate("""() => {
            return [...document.querySelectorAll('a[href]')].map(a => ({
                text: (a.innerText || a.getAttribute('aria-label') || '').trim().substring(0, 100),
                href: a.href
            })).filter(l => l.text && l.href && !l.href.startsWith('javascript:'));
        }""")
        seen = set()
        unique = []
        for link in links:
            if link["href"] not in seen:
                seen.add(link["href"])
                unique.append(link)
        return {
            "command": "web-links",
            "url": page.url,
            "links": unique[:80],
            "count": len(unique),
        }


def web_tabs(port: int = 9222) -> dict:
    """List all open browser tabs."""
    with cdp_browser(_cdp_url(port)) as (page, browser):
        tabs = []
        for ctx in browser.contexts:
            for p in ctx.pages:
                tabs.append({
                    "title": p.title(),
                    "url": p.url,
                    "is_active": p == page,
                })
        return {"command": "web-tabs", "tabs": tabs, "count": len(tabs)}


def web_ax(tab: int = 0, port: int = 9222,
           focus: str = None, match: str = None) -> dict:
    """Fetch Chrome's CDP accessibility tree.

    Args:
        tab: Target tab index.
        port: CDP port.
        focus: Filter preset ("buttons", "inputs", "interactive", "navigation",
               "headings", "forms", "errors", "dialogs") or free text.
        match: Glob or regex pattern to match node names.
    """
    with cdp_page(_cdp_url(port)) as page:
        client = page.context.new_cdp_session(page)
        tree = client.send("Accessibility.getFullAXTree")
        nodes = []
        for node in tree.get("nodes", []):
            name = node.get("name", {}).get("value", "")
            role = node.get("role", {}).get("value", "")
            if name or role in ("button", "link", "textbox", "heading", "checkbox", "radio", "combobox", "tab", "menuitem", "listitem", "img"):
                props = {}
                for prop in node.get("properties", []):
                    props[prop["name"]] = prop.get("value", {}).get("value", "")
                nodes.append({
                    "role": role,
                    "name": name,
                    "focused": props.get("focused", False),
                    "disabled": props.get("disabled", False),
                    "expanded": props.get("expanded", None),
                    "checked": props.get("checked", None),
                    "level": props.get("level", None),
                })
                if len(nodes) >= 150:
                    break
        client.detach()

        # Apply filters if any
        if focus or match:
            from nexus.cortex.filters import filter_web_nodes
            nodes = filter_web_nodes(nodes, focus=focus, match=match)

        return {
            "command": "web-ax",
            "title": page.title(),
            "url": page.url,
            "nodes": nodes,
            "count": len(nodes),
        }


def web_measure(selectors: str, tab: int = 0, port: int = 9222) -> dict:
    """Extract computed layout dimensions for comma-separated CSS selectors."""
    with cdp_page(_cdp_url(port)) as page:
        selector_list = [s.strip() for s in selectors.split(",")]
        results = page.evaluate("""(selectors) => {
            return selectors.map(sel => {
                const el = document.querySelector(sel);
                if (!el) return { selector: sel, error: "not found" };
                const rect = el.getBoundingClientRect();
                const cs = getComputedStyle(el);
                return {
                    selector: sel,
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    padding: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(v => parseInt(v) || 0),
                    margin: [cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft].map(v => parseInt(v) || 0),
                    font_size: cs.fontSize,
                    line_height: cs.lineHeight,
                    gap: cs.gap !== "normal" ? cs.gap : null,
                    display: cs.display,
                    position: cs.position,
                };
            });
        }""", selector_list)
        return {"command": "web-measure", "url": page.url, "elements": results}


def web_markdown(tab: int = 0, port: int = 9222) -> dict:
    """Extract clean article content using Mozilla Readability.js."""
    with cdp_page(_cdp_url(port)) as page:
        result = page.evaluate("""async () => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.js';
            document.head.appendChild(script);
            await new Promise((resolve, reject) => {
                script.onload = resolve;
                script.onerror = reject;
                setTimeout(reject, 5000);
            });

            const doc = document.cloneNode(true);
            const reader = new Readability(doc);
            const article = reader.parse();
            if (!article) return { error: "Could not extract article content" };
            return {
                title: article.title || '',
                byline: article.byline || '',
                excerpt: article.excerpt || '',
                content: article.textContent.substring(0, 8000),
                length: article.textContent.length,
            };
        }""")
        return {
            "command": "web-markdown",
            "url": page.url,
            "title": result.get("title", page.title()),
            "byline": result.get("byline", ""),
            "excerpt": result.get("excerpt", ""),
            "content": result.get("content", ""),
            "length": result.get("length", 0),
            "error": result.get("error"),
        }


def web_capture_api(url: str, filter_pattern: str = "", tab: int = 0, port: int = 9222) -> dict:
    """Navigate to a URL and capture all JSON API responses made during page load.

    Args:
        url: URL to navigate to.
        filter_pattern: optional substring to filter response URLs (e.g. "/api/").
        tab: target tab index.
        port: CDP port (default 9222).
    """
    MAX_BODY_SIZE = 10_000   # 10KB per response
    MAX_TOTAL_SIZE = 50_000  # 50KB total

    with cdp_page(_cdp_url(port)) as page:
        captured = []
        total_size = 0

        def _on_response(response):
            nonlocal total_size
            if total_size >= MAX_TOTAL_SIZE:
                return
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return
            resp_url = response.url
            if filter_pattern and filter_pattern not in resp_url:
                return
            try:
                body = response.text()
                if len(body) > MAX_BODY_SIZE:
                    body = body[:MAX_BODY_SIZE] + "...(truncated)"
                total_size += len(body)
                captured.append({
                    "url": resp_url,
                    "status": response.status,
                    "size": len(body),
                    "body": body,
                })
            except Exception:
                captured.append({
                    "url": resp_url,
                    "status": response.status,
                    "error": "Could not read response body",
                })

        page.on("response", _on_response)

        if not url.startswith("http"):
            url = "https://" + url
        try:
            page.goto(url, timeout=15000, wait_until="networkidle")
        except Exception:
            # networkidle may timeout on heavy pages — still return what we captured
            pass

        page.remove_listener("response", _on_response)

        return {
            "command": "web-capture-api",
            "url": page.url,
            "title": page.title(),
            "responses": captured,
            "count": len(captured),
            "total_size": total_size,
            "filter": filter_pattern or None,
        }


def web_research(query: str, max_results: int = 3, engine: str = "duckduckgo",
                 max_content: int = 4000, port: int = 9222) -> dict:
    """Search the web, visit top results, extract content from each.

    Args:
        query: search query string.
        max_results: number of results to visit (default 3, max 5).
        engine: "duckduckgo" or "brave" (default: duckduckgo).
        max_content: max chars per extracted page (default 4000).
        port: CDP port.

    Returns:
        {"command": "web-research", "query": ..., "results": [{url, title, content}], ...}
    """
    max_results = min(max_results, 5)

    if engine == "brave":
        search_url = "https://search.brave.com/search?q=" + query.replace(" ", "+")
    else:
        search_url = "https://duckduckgo.com/?q=" + query.replace(" ", "+")

    with cdp_page(_cdp_url(port)) as page:
        # Step 1: Search
        try:
            page.goto(search_url, timeout=10000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)  # let results render
        except Exception as e:
            return {
                "command": "web-research",
                "query": query,
                "error": "Search failed: %s" % str(e)[:200],
                "results": [],
                "count": 0,
            }

        # Step 2: Extract result links
        if engine == "brave":
            links_js = """() => {
                return [...document.querySelectorAll('#results .snippet a.result-header')]
                    .slice(0, %d)
                    .map(a => ({ url: a.href, title: a.textContent.trim() }))
                    .filter(l => l.url && !l.url.includes('brave.com'));
            }""" % max_results
        else:
            links_js = """() => {
                return [...document.querySelectorAll('article[data-testid="result"] a[data-testid="result-title-a"]')]
                    .slice(0, %d)
                    .map(a => ({ url: a.href, title: a.textContent.trim() }))
                    .filter(l => l.url && !l.url.includes('duckduckgo.com'));
            }""" % max_results

        try:
            search_links = page.evaluate(links_js)
        except Exception:
            search_links = []

        if not search_links:
            # Fallback: try generic organic result extraction
            try:
                search_links = page.evaluate("""() => {
                    const links = [...document.querySelectorAll('a[href]')]
                        .filter(a => {
                            const h = a.href;
                            return h.startsWith('http') && !h.includes('duckduckgo.com') && !h.includes('brave.com')
                                && !h.includes('google.com') && !h.includes('bing.com')
                                && a.closest('nav, header, footer') === null
                                && a.textContent.trim().length > 10;
                        })
                        .slice(0, %d)
                        .map(a => ({ url: a.href, title: a.textContent.trim().substring(0, 120) }));
                    // Deduplicate by URL
                    const seen = new Set();
                    return links.filter(l => { if (seen.has(l.url)) return false; seen.add(l.url); return true; });
                }""" % max_results)
            except Exception:
                search_links = []

        # Step 3: Visit each result and extract content
        readability_js = """async () => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.js';
            document.head.appendChild(script);
            await new Promise((resolve, reject) => {
                script.onload = resolve;
                script.onerror = reject;
                setTimeout(reject, 5000);
            });
            const doc = document.cloneNode(true);
            const reader = new Readability(doc);
            const article = reader.parse();
            if (!article) return { error: "Could not extract content" };
            return {
                title: article.title || '',
                content: article.textContent.substring(0, %d),
                length: article.textContent.length,
            };
        }""" % max_content

        results = []
        for link in search_links:
            url = link["url"]
            try:
                page.goto(url, timeout=8000, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                extracted = page.evaluate(readability_js)
                results.append({
                    "url": page.url,
                    "title": extracted.get("title", link.get("title", "")),
                    "content": extracted.get("content", ""),
                    "length": extracted.get("length", 0),
                    "error": extracted.get("error"),
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "title": link.get("title", ""),
                    "content": "",
                    "error": str(e)[:200],
                })

        return {
            "command": "web-research",
            "query": query,
            "engine": engine,
            "results": results,
            "count": len(results),
        }
