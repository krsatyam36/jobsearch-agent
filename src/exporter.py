import csv
from datetime import datetime
from pathlib import Path

from config.settings import CSV_EXPORT_DIR


def export_to_csv(jobs: list[dict], filename: str | None = None) -> Path:
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"approved_jobs_{timestamp}.csv"

    out_path = CSV_EXPORT_DIR / filename

    if not jobs:
        out_path.touch()
        return out_path

    fieldnames = [
        "job_id", "title", "company", "location", "posted_minutes_ago",
        "time_bucket", "linkedin_url", "description",
        "is_relevant_fit", "requires_edge_hardware", "hardware_mentioned",
        "requires_robotics_stack", "protocols_mentioned",
        "years_experience_required", "remote_policy",
        "match_score", "red_flags", "created_at",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for job in jobs:
            job["is_relevant_fit"] = bool(job.get("is_relevant_fit"))
            job["requires_edge_hardware"] = bool(job.get("requires_edge_hardware"))
            job["requires_robotics_stack"] = bool(job.get("requires_robotics_stack"))
            writer.writerow(job)

    return out_path
