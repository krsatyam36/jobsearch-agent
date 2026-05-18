"""
Interactive Login Script — Phase 1

Run this ONCE to authenticate with LinkedIn and save the session state.
A browser window will open. Log in manually, solve any CAPTCHAs, then close
the browser. The authenticated cookies/local-storage are saved to
~/.linkedin_agent_profile for headless reuse.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".linkedin_agent_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = PROFILE_DIR / "state.json"


def main():
    print("=" * 60)
    print("  LinkedIn Interactive Login — Session Profiler")
    print("=" * 60)
    print()
    print("A Chromium window will open.")
    print("  1. Log in to LinkedIn normally")
    print("  2. Solve any Arkose / FunCAPTCHA challenges")
    print("  3. Navigate to https://www.linkedin.com/jobs/")
    print("  4. Close the browser window when done")
    print()
    input("Press Enter to launch the browser...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
            ],
        )

        page = browser.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        print("\nBrowser is open. Complete login, then close the window.")
        print("The script will detect closure and save session state.\n")

        try:
            page.wait_for_event("close")
        except Exception:
            pass

        browser.close()

    print("Session state saved to:", STATE_FILE)
    print("You can now run the main agent in headless mode.")


if __name__ == "__main__":
    main()
