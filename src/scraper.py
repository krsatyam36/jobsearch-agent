import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
from config.settings import (
    PROFILE_DIR,
    TIME_BUCKETS,
    SCROLL_PAUSE_SEC,
    MAX_SCROLLS,
    SCRAPE_LIMIT_PER_BUCKET,
    LINKEDIN_JOBS_URL,
)
from src.database import JobDatabase
from src.time_bucket import parse_time_string, assign_bucket


def _build_search_url(keywords: str, location: str, time_filter: str) -> str:
    params = {"keywords": keywords, "sortBy": "DD"}
    if location:
        params["location"] = location

    filter_map = {
        "24h": "r86400",
        "week": "r604800",
        "month": "r2592000",
        "3month": "r7776000",
    }
    if time_filter in filter_map:
        params["f_TPR"] = filter_map[time_filter]

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{LINKEDIN_JOBS_URL}?{qs}"


def _is_login_redirect(page) -> bool:
    return "login" in page.url.lower() or "checkpoint" in page.url.lower()


class JobScraper:
    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda m: print(m))
        self.db = JobDatabase()
        self.db.connect()
        self.playwright = None
        self.context = None
        self.page = None

    def launch(self):
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
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
        self.page = self.context.new_page()

    def close(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        self.db.close()

    def _scroll_job_list(self):
        self.log("  Scrolling job list to load cards...")
        for i in range(MAX_SCROLLS):
            self.page.evaluate(
                "document.querySelector('.scaffold-layout__list')?.scrollBy(0, 800)"
            )
            time.sleep(SCROLL_PAUSE_SEC)

    def _extract_job_cards(self):
        cards = self.page.query_selector_all("li[data-occludable-job-id]")
        results = []
        for card in cards:
            job_id = card.get_attribute("data-occludable-job-id")
            if not job_id:
                continue

            title_el = card.query_selector(".artdeco-entity-lockup__title")
            title = title_el.inner_text().strip() if title_el else "Unknown"

            company_el = card.query_selector(".artdeco-entity-lockup__subtitle")
            company = company_el.inner_text().strip() if company_el else "Unknown"

            location_el = card.query_selector(
                ".artdeco-entity-lockup__caption li span, "
                ".job-card-container__metadata-wrapper li span"
            )
            location = location_el.inner_text().strip() if location_el else "Unknown"

            time_el = card.query_selector("time")
            time_str = time_el.get_attribute("datetime") if time_el else ""
            if time_str:
                time_str = time_el.inner_text().strip()

            minutes = parse_time_string(time_str)
            bucket = assign_bucket(minutes, TIME_BUCKETS)

            results.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "posted_minutes_ago": minutes,
                "time_bucket": bucket,
                "linkedin_url": f"https://www.linkedin.com/jobs/view/{job_id}",
            })
        return results

    def _click_job_and_get_description(self, job_id: str) -> str | None:
        try:
            card = self.page.query_selector(f'li[data-occludable-job-id="{job_id}"]')
            if card:
                card.click()
                time.sleep(2)
            else:
                self.page.goto(
                    f"https://www.linkedin.com/jobs/view/{job_id}",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                time.sleep(3)

            if _is_login_redirect(self.page):
                self.log("  SESSION EXPIRED — login redirect detected.")
                return "SESSION_EXPIRED"

            desc_el = self.page.query_selector(
                ".jobs-description__content, .description__text, "
                "#job-details, .show-more-less-html__markup, "
                ".jobs-details__main-content, article.jobs-description, "
                ".job-view-layout"
            )
            if desc_el:
                return desc_el.inner_text().strip()
        except PwTimeout:
            pass
        return None

    def run_sweep(
        self,
        keywords: str,
        location: str,
        model: str,
        llm_callback,
        score_threshold: int = 6,
    ) -> list[dict]:
        self.launch()
        approved = []

        time_filters = ["24h", "week", "month", "3month"]
        consecutive_dupes = 0
        max_consecutive_dupes = 20

        for tf in time_filters:
            self.log(f"\n--- Time filter: {tf} ---")
            url = _build_search_url(keywords, location, tf)
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PwTimeout:
                self.log(f"  Timeout loading {tf}, skipping.")
                continue
            time.sleep(3)

            if _is_login_redirect(self.page):
                self.log("SESSION EXPIRED — please re-run interactive_login.py")
                self.close()
                return approved

            self._scroll_job_list()
            cards = self._extract_job_cards()
            self.log(f"  Found {len(cards)} job cards.")

            new_count = 0
            for card_data in cards:
                if new_count >= SCRAPE_LIMIT_PER_BUCKET:
                    self.log(f"  Bucket limit reached ({SCRAPE_LIMIT_PER_BUCKET}).")
                    break

                job_id = card_data["job_id"]

                if self.db.exists(job_id):
                    consecutive_dupes += 1
                    if consecutive_dupes >= max_consecutive_dupes:
                        self.log("  Consecutive duplicates limit hit — stopping deep sweep.")
                        break
                    continue

                consecutive_dupes = 0
                self.log(f"  New job: {card_data['title']} at {card_data['company']}")

                desc = self._click_job_and_get_description(job_id)
                if desc == "SESSION_EXPIRED":
                    self.log("SESSION EXPIRED — please re-run interactive_login.py")
                    self.close()
                    return approved

                if not desc:
                    self.log("    No description found, skipping.")
                    continue

                card_data["description"] = desc

                self.log("    Sending to LLM for evaluation...")
                try:
                    llm_result = llm_callback(desc, model)
                except Exception as e:
                    self.log(f"    LLM error: {e}")
                    continue

                card_data.update(llm_result)
                self.db.insert(card_data)
                new_count += 1

                if llm_result.get("is_relevant_fit") and llm_result.get("match_score", 0) >= score_threshold:
                    approved.append(card_data)
                    self.log(f"    APPROVED (score: {llm_result.get('match_score')})")
                else:
                    self.log(f"    Rejected (score: {llm_result.get('match_score', 0)})")

            if consecutive_dupes >= max_consecutive_dupes:
                break

        self.close()
        return approved
