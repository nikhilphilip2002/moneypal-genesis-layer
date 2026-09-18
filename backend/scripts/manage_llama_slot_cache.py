#!/usr/bin/env python3
"""Restore, warm, save, inspect, or erase the configured llama.cpp slot cache."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from app.services.nlq.llm.slot_cache import (
    SlotCacheError,
    build_warmup_bundle,
    restore_or_warm,
    slot_action,
    warm_slot,
)


async def run(command: str) -> dict:
    if command == "erase":
        return {"outcome": "erased", "slot": await slot_action("erase")}
    bundle = await build_warmup_bundle()
    if command == "fingerprint":
        return {"outcome": "fingerprinted", "identity": asdict(bundle.identity)}
    if command == "restore":
        result = await slot_action("restore", filename=bundle.identity.filename)
        return {"outcome": "restored", "identity": asdict(bundle.identity), "slot": result}
    if command == "warm-save":
        erased = await slot_action("erase")
        warmed = await warm_slot(bundle)
        saved = await slot_action("save", filename=bundle.identity.filename)
        return {
            "outcome": "warmed_and_saved",
            "identity": asdict(bundle.identity),
            "erase": erased,
            "warmup": warmed,
            "slot": saved,
        }
    return await restore_or_warm(bundle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="restore-or-warm",
        choices=("restore-or-warm", "restore", "warm-save", "fingerprint", "erase"),
    )
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args.command)), indent=2, sort_keys=True))
    except (SlotCacheError, RuntimeError) as exc:
        print(json.dumps({"outcome": "error", "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
