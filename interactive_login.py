"""
Interactive Login Script for LinkedIn Job Search Agent
This script helps you set up your LinkedIn authentication session.
Run this once to log in manually, then the agent will reuse this session.
"""

import os
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".linkedin_agent_profile")

def main():
    print("🔐 LinkedIn Interactive Login Setup")
    print("=" * 50)
    print("This script will help you set up your LinkedIn authentication.")
    print("Follow these steps:")
    print("1. A browser window will open")
    print("2. Log in to LinkedIn manually")
    print("3. Solve any security challenges (CAPTCHA, etc.)")
    print("4. Once you're on your LinkedIn feed, close the browser")
    print("5. Your session will be saved for the agent to use")
    print()

    # Ensure profile directory exists
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        print("🚀 Launching browser...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,  # Visible browser for manual login
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()

        print("🌐 Navigating to LinkedIn...")
        page.goto("https://www.linkedin.com/login")

        print("\n" + "="*50)
        print("📝 PLEASE LOG IN TO LINKEDIN MANUALLY")
        print("="*50)
        print("After logging in:")
        print("- Complete any security challenges")
        print("- Navigate to your LinkedIn feed/homepage")
        print("- Then close this browser window to continue")
        print("="*50)

        # Wait for user to close the browser
        try:
            page.wait_for_timeout(300000)  # 5 minutes max
        except:
            pass  # User closed browser or timeout

        browser.close()
        print("\n✅ Session saved successfully!")
        print(f"📁 Profile stored in: {PROFILE_DIR}")
        print("🤖 You can now run the main agent in headless mode.")

if __name__ == "__main__":
    main()