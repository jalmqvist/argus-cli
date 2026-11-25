"""Run the separate M3 generation fixture with the actual Argus CLI."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def run(questions):
    result = []
    for item in questions:
        start = time.monotonic()
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "argus_cli",
                "ask",
                "--timeout",
                "300",
                "--",
                item["question"],
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if not process.stdout:
            raise RuntimeError(f"{item['id']}: Argus returned no JSON: {process.stderr.strip()}")
        report = json.loads(process.stdout)
        observed = {
            key: report[key]
            for key in (
                "verification",
                "argv",
                "env",
                "structural_validation",
                "preflight_validation",
                "intent_status",
            )
        }
        observed["command_rendered"] = report["command"] is not None
        observed["preflight_codes"] = [
            issue["code"] for issue in (report["preflight"] or {}).get("issues", [])
        ]
        if "error" in report:
            observed["error"] = report["error"]
        result.append(
            {
                "id": item["id"],
                "match": all(observed[key] == value for key, value in item["expected"].items()),
                "observed": observed,
                "elapsed_seconds": round(time.monotonic() - start, 1),
                "model": report["model"],
                "source": report["provenance"],
                "retrieval": report["retrieval"],
            }
        )
    return result


if __name__ == "__main__":
    questions = json.loads(Path(__file__).with_name("questions.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[question["id"] for question in questions])
    args = parser.parse_args()
    selected = [question for question in questions if args.case in (None, question["id"])]
    print(json.dumps(run(selected), indent=2))
