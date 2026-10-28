"""Run a maintenance job by hand or from a scheduler: `python -m app.jobs retention`."""

import asyncio
import json
import sys

from app.services import retention


def main(argv: list[str]) -> int:
    if argv != ["retention"]:
        print("Usage: python -m app.jobs retention", file=sys.stderr)
        return 2
    print(json.dumps(asyncio.run(retention.run())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
