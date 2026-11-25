"""Measure the existing CLI's generation call inside an evaluation-only subprocess."""

import contextlib
import io
import json
import sys
import time

from argus_cli import ask
from argus_cli.cli import main


def run(argv):
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
    ask.generate = timed_generate
    try:
        with contextlib.redirect_stdout(output):
            code = main(argv)
    finally:
        ask.generate = generate
    if output.getvalue():
        print(json.dumps({"report": json.loads(output.getvalue()), "generation_seconds": elapsed}))
    return code


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
