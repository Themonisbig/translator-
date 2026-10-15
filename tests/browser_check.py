"""CPU-only real-browser checks; no GPU/audio inference claims."""
import functools
import http.server
import shutil
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def main():
    handler = functools.partial(QuietHandler, directory=str(ROOT / "vendor/personaplex/client/dist"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            options = {"headless": True, "args": ["--no-sandbox"]}
            system_browser = shutil.which("chromium")
            if system_browser:
                options["executable_path"] = system_browser
            browser = p.chromium.launch(**options)
            for width in (390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 844})
                # Deterministic denial tests UI errors, without microphone or GPU.
                context.add_init_script("navigator.mediaDevices.getUserMedia = async () => {throw new DOMException('Denied', 'NotAllowedError')}")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                assert page.get_by_role("heading", name="PersonaPlex", exact=True).is_visible()
                assert page.locator('#voice-prompt option').count() == 18
                page.get_by_role("button", name="Energetic, funny & hyperactive").click()
                assert 'hyperactive' in page.locator('#text-prompt').input_value()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.get_by_role("button", name="Start conversation", exact=True).click()
                page.get_by_text("Could not start audio.", exact=False).wait_for()
                assert not errors, errors
                print(f"PASS browser width={width}: voices, persona, layout, denied microphone message")
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    main()
