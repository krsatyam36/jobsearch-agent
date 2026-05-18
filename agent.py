import os
import sqlite3
import time
import json
from datetime import datetime, timedelta
import pandas as pd
from playwright.sync_api import sync_playwright
import gradio as gr
import ollama

# Constants
# PROFILE_DIR: Stores LinkedIn session data for persistent login
# DB_PATH: SQLite database for job storage and deduplication
# CSV_EXPORT_DIR: Directory for exporting job results to CSV files
# THROTTLE_MS: Delay between job clicks to avoid LinkedIn detection/throttling
PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".linkedin_agent_profile")
DB_PATH = "jobs.db"
CSV_EXPORT_DIR = "exports"
THROTTLE_MS = 2000  # Throttle between job clicks to avoid detection

# Ensure directories exist
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(CSV_EXPORT_DIR, exist_ok=True)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            posted_time TEXT,
            raw_description TEXT,
            is_relevant_fit BOOLEAN,
            requires_edge_hardware BOOLEAN,
            hardware_mentioned TEXT,
            requires_robotics_stack BOOLEAN,
            protocols_mentioned TEXT,
            years_experience_required INTEGER,
            remote_policy TEXT,
            match_score INTEGER,
            red_flags TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Save job to database
def save_job_to_db(job_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO jobs (
            job_id, title, company, location, url, posted_time, raw_description,
            is_relevant_fit, requires_edge_hardware, hardware_mentioned,
            requires_robotics_stack, protocols_mentioned, years_experience_required,
            remote_policy, match_score, red_flags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        job_data.get('job_id'),
        job_data.get('title'),
        job_data.get('company'),
        job_data.get('location'),
        job_data.get('url'),
        job_data.get('posted_time'),
        job_data.get('raw_description'),
        job_data.get('is_relevant_fit'),
        job_data.get('requires_edge_hardware'),
        json.dumps(job_data.get('hardware_mentioned', [])),
        job_data.get('requires_robotics_stack'),
        json.dumps(job_data.get('protocols_mentioned', [])),
        job_data.get('years_experience_required'),
        job_data.get('remote_policy'),
        job_data.get('match_score'),
        json.dumps(job_data.get('red_flags', []))
    ))
    conn.commit()
    conn.close()

# Check if job exists in database
def job_exists(job_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# Normalize posted time string to minutes
# Converts LinkedIn time strings (e.g., "2 hours ago") to integer minutes
def parse_posted_time(time_str):
    time_str = time_str.lower().strip()
    if 'just now' in time_str or 'moments ago' in time_str:
        return 0
    if 'minute' in time_str:
        mins = int(''.join(filter(str.isdigit, time_str)))
        return mins
    if 'hour' in time_str:
        hours = int(''.join(filter(str.isdigit, time_str)))
        return hours * 60
    if 'day' in time_str:
        days = int(''.join(filter(str.isdigit, time_str)))
        return days * 24 * 60
    if 'week' in time_str:
        weeks = int(''.join(filter(str.isdigit, time_str)))
        return weeks * 7 * 24 * 60
    if 'month' in time_str:
        months = int(''.join(filter(str.isdigit, time_str)))
        return months * 30 * 24 * 60
    return 999999  # Large number for unparseable

# Bucket the posted time
def time_bucket(minutes):
    if minutes < 30:
        return "<30m"
    elif minutes < 60:
        return "<1h"
    elif minutes < 180:
        return "<3h"
    elif minutes < 360:
        return "<6h"
    else:
        return "<24h"

# Evaluate job description with local LLM via Ollama
# Sends job description to Ollama model for relevance scoring
# Returns structured JSON with job fit analysis
def evaluate_job_with_llm(job_description, target_role):
    prompt = f"""
    You are an expert technical recruiter specializing in Edge AI, Robotics, and Embedded Systems roles.
    Analyze the following job description and determine if it is a relevant fit for a "{target_role}" position.
    Output ONLY a valid JSON object with the following fields:

    {{
      "is_relevant_fit": boolean,
      "requires_edge_hardware": boolean,
      "hardware_mentioned": ["list", "of", "hardware"],
      "requires_robotics_stack": boolean,
      "protocols_mentioned": ["list", "of", "protocols"],
      "years_experience_required": integer,
      "remote_policy": "string (e.g., Remote, Hybrid, On-site)",
      "match_score_1_to_10": integer (1-10),
      "red_flags": ["list", "of", "red flags"]
    }}

    Job Description:
    {job_description}
    """
    try:
        response = ollama.generate(
            model='ollama',  # This will be overridden by the dropdown in Gradio
            prompt=prompt,
            format='json'
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"Error in LLM evaluation: {e}")
        return {
            "is_relevant_fit": False,
            "requires_edge_hardware": False,
            "hardware_mentioned": [],
            "requires_robotics_stack": False,
            "protocols_mentioned": [],
            "years_experience_required": 0,
            "remote_policy": "Unknown",
            "match_score_1_to_10": 0,
            "red_flags": ["LLM evaluation failed"]
        }

# Scrape LinkedIn jobs
def scrape_linkedin_jobs(role, location, throttle_ms, progress=gr.Progress()):
    # Initialize Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()

        # Navigate to LinkedIn jobs search
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={role.replace(' ', '%20')}&location={location.replace(' ', '%20')}&f_TPR=r86400&sortBy=DD"
        page.goto(search_url)
        page.wait_for_timeout(5000)  # Wait for initial load

        # Scroll to load more jobs
        for _ in range(5):
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

        # Get job cards
        job_cards = page.query_selector_all(".jobs-search-results__list-item")
        progress(0, desc=f"Found {len(job_cards)} job cards. Processing...")

        new_jobs = []
        for idx, card in enumerate(job_cards):
            progress((idx + 1) / len(job_cards), desc=f"Processing job {idx+1}/{len(job_cards)}")

            # Extract job ID from the card
            job_id_elem = card.query_selector(".job-card-container--clickable")
            if not job_id_elem:
                continue
            job_id = job_id_elem.get_attribute("data-job-id")

            # Skip if already in database
            if job_exists(job_id):
                continue

            # Extract basic info from the card
            title_elem = card.query_selector(".job-card-list__title")
            company_elem = card.query_selector(".job-card-container__company-name")
            location_elem = card.query_selector(".job-card-container__metadata-item")
            time_elem = card.query_selector(".job-card-container__listed-time")

            title = title_elem.inner_text() if title_elem else "Unknown"
            company = company_elem.inner_text() if company_elem else "Unknown"
            location_text = location_elem.inner_text() if location_elem else "Unknown"
            posted_time_text = time_elem.inner_text() if time_elem else "Unknown"

            # Parse posted time to minutes and bucket
            minutes_ago = parse_posted_time(posted_time_text)
            bucket = time_bucket(minutes_ago)

            # Click the job to load the description
            card.click()
            page.wait_for_timeout(throttle_ms)  # Throttle to avoid detection

            # Wait for the job description to load
            page.wait_for_selector(".jobs-description-content__text", timeout=10000)
            desc_elem = page.query_selector(".jobs-description-content__text")
            raw_description = desc_elem.inner_text() if desc_elem else ""

            # Get the job URL
            url_elem = card.query_selector(".job-card-list__title--link")
            job_url = url_elem.get_attribute("href") if url_elem else f"https://www.linkedin.com/jobs/view/{job_id}/"

            # Evaluate with LLM
            llm_result = evaluate_job_with_llm(raw_description, role)

            # Prepare job data
            job_data = {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location_text,
                'url': job_url,
                'posted_time': posted_time_text,
                'raw_description': raw_description,
                'is_relevant_fit': llm_result.get('is_relevant_fit', False),
                'requires_edge_hardware': llm_result.get('requires_edge_hardware', False),
                'hardware_mentioned': llm_result.get('hardware_mentioned', []),
                'requires_robotics_stack': llm_result.get('requires_robotics_stack', False),
                'protocols_mentioned': llm_result.get('protocols_mentioned', []),
                'years_experience_required': llm_result.get('years_experience_required', 0),
                'remote_policy': llm_result.get('remote_policy', 'Unknown'),
                'match_score': llm_result.get('match_score_1_to_10', 0),
                'red_flags': llm_result.get('red_flags', [])
            }

            # Save to database if relevant
            if job_data['is_relevant_fit'] and job_data['match_score'] >= 7:  # Threshold of 7
                save_job_to_db(job_data)
                new_jobs.append(job_data)

        browser.close()

        # Export new jobs to CSV
        if new_jobs:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(CSV_EXPORT_DIR, f"jobs_{timestamp}.csv")
            df = pd.DataFrame(new_jobs)
            df.to_csv(csv_path, index=False)

        return new_jobs

# Gradio interface
def create_interface():
    with gr.Blocks(title="Job Search Agent") as interface:
        gr.Markdown("# 🔍 Local Job Search Agent")
        gr.Markdown("A private, local-only agent for scraping and filtering LinkedIn jobs using Ollama LLMs.")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ Configuration")

                # Model dropdown (will be populated dynamically)
                model_dropdown = gr.Dropdown(
                    label="Ollama Model",
                    choices=["Loading models..."],
                    value=None
                )

                role_input = gr.Textbox(
                    label="Target Role",
                    placeholder="e.g., Edge AI Engineer, AI/ML Engineer",
                    value="Edge AI Engineer"
                )

                location_input = gr.Textbox(
                    label="Location",
                    placeholder="e.g., Remote, New York, San Francisco",
                    value="Remote"
                )

                throttle_slider = gr.Slider(
                    minimum=1000,
                    maximum=5000,
                    value=2000,
                    step=500,
                    label="Throttle Between Jobs (ms)",
                    info="Higher values reduce detection risk but slow scraping."
                )

                init_button = gr.Button("🚀 Initialize Agent", variant="primary")

                refresh_models_button = gr.Button("🔄 Refresh Ollama Models")

            with gr.Column(scale=2):
                gr.Markdown("## 📊 Execution & Results")

                status_box = gr.Textbox(
                    label="Status",
                    lines=5,
                    max_lines=10,
                    interactive=False,
                    placeholder="Agent status will appear here..."
                )

                jobs_dataframe = gr.Dataframe(
                    label="Approved Jobs",
                    headers=["Job ID", "Title", "Company", "Location", "Posted Time", "Match Score", "URL"],
                    datatype=["str", "str", "str", "str", "str", "number", "str"],
                    col_count=7
                )

        # Function to refresh Ollama models
        def refresh_ollama_models():
            try:
                models = ollama.list()
                model_names = [m['model'] for m in models['models']]
                return gr.update(choices=model_names, value=model_names[0] if model_names else None)
            except Exception as e:
                return gr.update(choices=["Error connecting to Ollama"], value=None)

        # Function to run the agent
        def run_agent(model, role, location, throttle):
            if not model:
                return "Error: Please select an Ollama model first.", None

            # Update status
            status = f"Starting agent with model: {model}\n"
            status += f"Role: {role}, Location: {location}\n"
            status += f"Throttle: { throttle }ms\n"

            try:
                # Scrape jobs
                new_jobs = scrape_linkedin_jobs(role, location, throttle)

                if new_jobs:
                    status += f"\nFound {len(new_jobs)} new relevant jobs!\n"
                    # Prepare data for dataframe
                    df_data = []
                    for job in new_jobs:
                        df_data.append([
                            job['job_id'],
                            job['title'],
                            job['company'],
                            job['location'],
                            job['posted_time'],
                            job['match_score'],
                            job['url']
                        ])
                    return status, df_data
                else:
                    status += "\nNo new relevant jobs found in this sweep."
                    return status, None
            except Exception as e:
                return f"Error during execution: {str(e)}", None

        # Event handlers
        refresh_models_button.click(
            fn=refresh_ollama_models,
            inputs=[],
            outputs=[model_dropdown]
        )

        init_button.click(
            fn=run_agent,
            inputs=[model_dropdown, role_input, location_input, throttle_slider],
            outputs=[status_box, jobs_dataframe]
        )

        # Load models on startup
        interface.load(
            fn=refresh_ollama_models,
            inputs=[],
            outputs=[model_dropdown]
        )

    return interface

if __name__ == "__main__":
    # Initialize database
    init_db()

    # Create and launch interface
    interface = create_interface()
    interface.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False
    )