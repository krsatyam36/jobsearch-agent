import json
from config.settings import OLLAMA_BASE_URL, MATCH_SCORE_THRESHOLD
import requests

SYSTEM_PROMPT = """You are an expert technical recruiter evaluating job descriptions for a candidate specializing in Edge AI, Robotics, and Embedded ML.

Evaluate the job description and respond with STRICT JSON only. No markdown, no code fences, no explanation.

Fields:
- is_relevant_fit: true if the role involves edge AI, embedded ML, robotics, computer vision on edge, or hardware-accelerated inference
- requires_edge_hardware: true if the role mentions deploying models on edge devices (Jetson, Hailo, Coral, NPU, etc.)
- hardware_mentioned: list of specific hardware platforms named (e.g., "Jetson", "Hailo-8", "Coral TPU", "Raspberry Pi", "NPU")
- requires_robotics_stack: true if the role involves ROS, ROS2, MAVLink, drone autonomy, or robot control systems
- protocols_mentioned: list of protocols/frameworks named (e.g., "MAVLink", "ROS 2", "DDS", "gRPC", "MQTT")
- years_experience_required: integer years of experience required (infer from description, default 0 if not stated)
- remote_policy: one of "Remote", "Hybrid", "On-site", "Unknown"
- match_score_1_to_10: integer 1-10 how well this matches an Edge AI / Robotics / Embedded ML profile
- red_flags: list of concerning items (e.g., "requires 15+ years", "unpaid", "MLM", empty list if none)

Respond with valid JSON only."""


def evaluate_job(description: str, model: str) -> dict:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Job Description:\n\n{description}"},
            ],
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()["message"]["content"]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        result = json.loads(cleaned)

    result["match_score"] = result.get("match_score_1_to_10", 0)
    result["is_relevant_fit"] = result.get("is_relevant_fit", False)
    result["hardware_mentioned"] = ", ".join(result.get("hardware_mentioned", []))
    result["protocols_mentioned"] = ", ".join(result.get("protocols_mentioned", []))
    result["red_flags"] = ", ".join(result.get("red_flags", []))
    result["llm_raw_json"] = raw

    return result


def passes_threshold(llm_result: dict, threshold: int = MATCH_SCORE_THRESHOLD) -> bool:
    return llm_result.get("is_relevant_fit", False) and llm_result.get("match_score", 0) >= threshold
