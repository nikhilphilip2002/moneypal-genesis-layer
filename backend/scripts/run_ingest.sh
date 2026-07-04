#!/usr/bin/env bash
# Ingest module documents into Qdrant with the NixOS native-lib fix applied.
# Usage: ./backend/scripts/run_ingest.sh [all|macro|competitive|regulatory]
set -euo pipefail
cd "$(dirname "$0")/../.."
export LD_LIBRARY_PATH="$(nix eval --raw nixpkgs#stdenv.cc.cc.lib)/lib:$(nix eval --raw nixpkgs#zlib)/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec .venv/bin/python backend/scripts/ingest.py "${1:-all}"
