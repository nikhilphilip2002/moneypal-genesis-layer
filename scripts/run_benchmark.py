#!/usr/bin/env python3
"""Canonical entry point for Moneypal Workbench benchmarks.

Modes:
  single       200-question mixed-source, single-turn corpus
  multi        100 five-turn loan-book chains without database checks
  reconcile    the same chains with PostgreSQL reconciliation and telemetry
"""

from __future__ import annotations

import argparse
import sys

try:
    from scripts import run_200_mixed_queries, run_500_loanbook_benchmark
except ImportError:
    import run_200_mixed_queries
    import run_500_loanbook_benchmark


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("mode", choices=("single", "multi", "reconcile"))
    if not values or values[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    args, forwarded = parser.parse_known_args(values)

    if args.mode == "single":
        return run_200_mixed_queries.main(forwarded)
    if args.mode == "multi":
        return run_500_loanbook_benchmark.main(["--no-reconcile", *forwarded])
    return run_500_loanbook_benchmark.main(forwarded)


if __name__ == "__main__":
    sys.exit(main())
