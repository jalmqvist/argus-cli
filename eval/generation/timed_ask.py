"""Measure the existing CLI's generation call inside an evaluation-only subprocess."""

import contextlib
import io
import json
import sys
import time

from argus_cli import ask
from argus_cli.cli import main


def run(argv):
    options = argv[: argv.index("--")] if "--" in argv else argv
    agent = "--agent" in options
    generate = ask.generate
    elapsed = None

    def timed_generate(*args, **kwargs):
        nonlocal elapsed
        start = time.monotonic()
        try:
            return generate(*args, **kwargs)
        finally:
            elapsed = round(time.monotonic() - start, 4)

    output = io.StringIO()
    if not agent:
        ask.generate = timed_generate
    try:
        with contextlib.redirect_stdout(output):
            code = main(argv)
    finally:
        if not agent:
            ask.generate = generate
    if output.getvalue():
        report = json.loads(output.getvalue())
        if agent:
            samples = [attempt["generation_seconds"] for attempt in report["attempts"]]
            elapsed = round(sum(samples), 4) if samples else None
        print(json.dumps({"report": report, "generation_seconds": elapsed}))
    return code


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
