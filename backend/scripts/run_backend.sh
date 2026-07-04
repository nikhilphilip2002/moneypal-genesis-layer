#!/usr/bin/env bash
# Start the Genesis backend with the NixOS native-lib fix (needed for query-time bge-m3 embedding).
set -euo pipefail
cd "$(dirname "$0")/.."
export LD_LIBRARY_PATH="$(nix eval --raw nixpkgs#stdenv.cc.cc.lib)/lib:$(nix eval --raw nixpkgs#zlib)/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec ../.venv/bin/uvicorn app.main:app --port "${PORT:-8000}" "$@"
