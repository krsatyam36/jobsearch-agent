import sys
import asyncio
import queue
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr
import pandas as pd
import requests

from config.settings import OLLAMA_BASE_URL, DEFAULT_MODEL, MATCH_SCORE_THRESHOLD
from src.scraper import JobScraper
from src.llm_processor import evaluate_job, passes_threshold
from src.database import JobDatabase
from src.exporter import export_to_csv


def fetch_ollama_models():
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return models if models else [DEFAULT_MODEL]
    except Exception:
        return [DEFAULT_MODEL]


def _run_sweep_in_thread(keywords, location, model, score_threshold, log_queue):
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        log_queue.put(msg)

    log("Initializing agent...")
    log(f"Model: {model}")
    log(f"Keywords: {keywords}")
    log(f"Location: {location or 'Any'}")
    log(f"Score threshold: {score_threshold}")

    db = JobDatabase()
    db.connect()
    snapshot_time = db._conn.execute("SELECT datetime('now')").fetchone()[0]

    def llm_cb(desc, mdl):
        return evaluate_job(desc, mdl)

    scraper = JobScraper(log_callback=log)

    try:
        approved = scraper.run_sweep(
            keywords=keywords,
            location=location,
            model=model,
            llm_callback=llm_cb,
            score_threshold=int(score_threshold),
        )
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        db.close()
        return log_lines, []

    log(f"\nSweep complete. {len(approved)} jobs approved.")

    all_jobs = db.get_new_since(snapshot_time)
    db.close()

    if not all_jobs:
        return log_lines, []

    csv_path = export_to_csv(all_jobs)
    log(f"CSV exported to: {csv_path}")
    return log_lines, all_jobs


async def run_agent(model, keywords, location, score_threshold):
    log_queue = queue.Queue()
    log_lines = []

    loop = asyncio.get_event_loop()
    task = loop.run_in_executor(
        None,
        _run_sweep_in_thread,
        keywords, location, model, score_threshold, log_queue,
    )

    while True:
        try:
            while True:
                msg = log_queue.get_nowait()
                log_lines.append(msg)
        except queue.Empty:
            pass

        if log_lines:
            df = pd.DataFrame()
            yield "\n".join(log_lines), df

        if task.done():
            break

        await asyncio.sleep(0.5)

    try:
        thread_log_lines, all_jobs = task.result()
    except Exception as e:
        yield f"FATAL ERROR: {e}", pd.DataFrame()
        return

    if log_lines:
        df = pd.DataFrame()
        if all_jobs:
            df = pd.DataFrame(all_jobs)
            cols = ["title", "company", "location", "time_bucket",
                    "match_score", "remote_policy", "linkedin_url"]
            df = df[cols] if all(c in df.columns for c in cols) else df
        else:
            df = pd.DataFrame(columns=[
                "title", "company", "location", "time_bucket",
                "match_score", "remote_policy", "linkedin_url",
            ])
        yield "\n".join(log_lines), df
    else:
        yield "\n".join(thread_log_lines), pd.DataFrame()


def refresh_table():
    db = JobDatabase()
    db.connect()
    all_jobs = db.get_all()
    db.close()

    if not all_jobs:
        return pd.DataFrame()

    df = pd.DataFrame(all_jobs)
    return df[[
        "title", "company", "location", "time_bucket",
        "match_score", "remote_policy", "linkedin_url",
    ]]


with gr.Blocks(title="LinkedIn Job Search Agent", theme=gr.themes.Soft()) as app:
    gr.Markdown("# LinkedIn Job Search Agent")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Configuration")

            models = fetch_ollama_models()
            model_dropdown = gr.Dropdown(
                choices=models,
                value=models[0] if models else DEFAULT_MODEL,
                label="Ollama Model",
            )
            refresh_models_btn = gr.Button("Refresh Models")

            keywords_input = gr.Textbox(
                label="Target Roles (comma-separated)",
                placeholder="Edge AI Engineer, AI/ML Engineer, Robotics Engineer",
                value="Edge AI Engineer",
            )
            location_input = gr.Textbox(
                label="Location (leave blank for any)",
                placeholder="Remote, San Francisco, etc.",
                value="",
            )
            threshold_input = gr.Slider(
                minimum=1,
                maximum=10,
                value=MATCH_SCORE_THRESHOLD,
                step=1,
                label="Match Score Threshold",
            )

            init_btn = gr.Button("Initialize Agent", variant="primary", size="lg")

        with gr.Column(scale=2):
            gr.Markdown("## Execution & Results")
            log_output = gr.Textbox(
                label="Live Log",
                lines=20,
                max_lines=50,
                interactive=False,
            )
            results_df = gr.Dataframe(
                label="Approved Jobs",
                interactive=False,
            )
            refresh_btn = gr.Button("Refresh Table")
            gr.Markdown(
                "*Tip: Run `python scripts/interactive_login.py` first to authenticate."
            )

    def _refresh_models():
        models = fetch_ollama_models()
        return gr.Dropdown(choices=models, value=models[0])

    refresh_models_btn.click(_refresh_models, outputs=[model_dropdown])

    init_btn.click(
        run_agent,
        inputs=[model_dropdown, keywords_input, location_input, threshold_input],
        outputs=[log_output, results_df],
    )

    refresh_btn.click(refresh_table, outputs=[results_df])


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
