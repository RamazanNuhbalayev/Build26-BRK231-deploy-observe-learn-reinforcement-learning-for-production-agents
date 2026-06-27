#!/usr/bin/env python3
"""
Universal setup for the toon-reader MCP server -- Windows / macOS / Linux.

    python setup_toon.py

Installs deps into THIS interpreter, writes the server, registers it in Cursor's
mcp.json (merge-safe), and verifies the MCP handshake. No bash required.
"""
import json, subprocess, sys
from pathlib import Path

PY = sys.executable                       # the exact interpreter running this script
HOME = Path.home()
SERVER = HOME / "toon-reader" / "server.py"
MCP_JSON = HOME / ".cursor" / "mcp.json"

SERVER_CODE = r'''#!/usr/bin/env python3
"""toon-reader MCP server - read/convert JSON, return TOON over stdio."""
from __future__ import annotations
import json, os
from typing import Any
from mcp.server.fastmcp import FastMCP

# TOON encoder: prefer python-toon, fall back to pytoony (both pure-Python, cross-platform).
_ENCODE = None; _ENCODER_NAME = None
try:
    from toon import encode as _toon_encode          # pip install python-toon
    _ENCODE, _ENCODER_NAME = (lambda d: _toon_encode(d)), "python-toon"
except Exception:
    try:
        from pytoony import json2toon                # pip install pytoony
        _ENCODE, _ENCODER_NAME = (lambda d: json2toon(json.dumps(d))), "pytoony"
    except Exception:
        _ENCODE = None

app = FastMCP("toon-reader")

class ToonError(Exception): ...

def _require():
    if _ENCODE is None:
        raise ToonError("No TOON encoder. Run: pip install python-toon")

def _load(path: str) -> Any:
    p = os.path.expanduser(os.path.expandvars(path))
    if not os.path.exists(p): raise ToonError(f"File not found: {p}")
    if os.path.isdir(p):      raise ToonError(f"Path is a directory: {p}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e: raise ToonError(f"Invalid JSON in {p}: {e}")
    except OSError as e:               raise ToonError(f"Cannot read {p}: {e}")

def _parse(text: str) -> Any:
    try: return json.loads(text)
    except json.JSONDecodeError as e: raise ToonError(f"Invalid JSON text: {e}")

def _toon(data: Any) -> str:
    _require()
    try: return _ENCODE(data)
    except Exception as e: raise ToonError(f"Encode failed: {e}")

@app.tool()
def read_json(path: str) -> str:
    """Read a JSON file and return TOON (30-60% fewer tokens).
    ALWAYS use this instead of reading a .json file directly."""
    try: return _toon(_load(path))
    except ToonError as e: return f"ERROR: {e}"

@app.tool()
def convert_json(text: str) -> str:
    """Convert a raw JSON string (e.g. an API response) to TOON."""
    try: return _toon(_parse(text))
    except ToonError as e: return f"ERROR: {e}"

@app.tool()
def toon_stats(path: str = "", text: str = "") -> str:
    """Report JSON->TOON size savings (characters). Provide exactly one of path|text."""
    try:
        if bool(path) == bool(text):
            raise ToonError("Provide exactly one of `path` or `text`.")
        data = _load(path) if path else _parse(text)
        toon = _toon(data)
        j = json.dumps(data, separators=(",", ":"))
        pct = round(100 * (1 - len(toon) / len(j)), 1) if j else 0.0
        return (f"encoder: {_ENCODER_NAME}\njson_chars: {len(j)}\ntoon_chars: {len(toon)}\n"
                f"saved: {pct}% (characters; token savings track this, vary by tokenizer)\n"
                f"--- TOON ---\n{toon}")
    except ToonError as e: return f"ERROR: {e}"

if __name__ == "__main__":
    app.run()
'''

def main():
    print("interpreter:", PY)

    print("\n== 1/4  install deps (into THIS interpreter) ==")
    subprocess.check_call([PY, "-m", "pip", "install", "--upgrade", "python-toon", "pytoony", "mcp"])

    print("\n== 2/4  write server ==")
    SERVER.parent.mkdir(parents=True, exist_ok=True)
    SERVER.write_text(SERVER_CODE, encoding="utf-8")
    print("wrote", SERVER)

    print("\n== 3/4  register in Cursor mcp.json (merge-safe) ==")
    MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if MCP_JSON.exists():
        try: cfg = json.loads(MCP_JSON.read_text(encoding="utf-8"))
        except Exception: cfg = {}       # malformed/empty -> start fresh
    cfg.setdefault("mcpServers", {})["toon-reader"] = {"command": PY, "args": [str(SERVER)]}
    MCP_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("registered ->", MCP_JSON)
    print("  command:", PY)
    print("  args:", [str(SERVER)])

    print("\n== 4/4  verify MCP handshake ==")
    proc = subprocess.Popen([PY, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    def send(o): proc.stdin.write(json.dumps(o) + "\n"); proc.stdin.flush()
    def read(): return json.loads(proc.stdout.readline())
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
              "protocolVersion": "2024-11-05", "capabilities": {},
              "clientInfo": {"name": "t", "version": "0"}}})
        print("init:", read()["result"]["serverInfo"])
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        print("tools:", [t["name"] for t in read()["result"]["tools"]])
    except Exception as e:
        print("verify FAILED:", e)
        print(proc.stderr.read())
    finally:
        proc.terminate()

    print("\nNext (Cursor GUI -- same on every OS):")
    print("  - Settings > Features > Editor > Global Cursor Ignore List: add  *.json  and  **/*.json")
    print("  - Settings > Rules > User Rules: paste the JSON-handling rule (tutorial Step 5)")
    print("  - Restart Cursor, then ask: \"Show me the contents of package.json\"")

if __name__ == "__main__":
    main()