"""Run the API on this Windows box exactly as a Linux box would see it.

    python -m tools.no_mt5_api      # serves on 8101, beside the real one

WHAT IT IS FOR. `MetaTrader5` ships no wheel outside Windows, so a Linux
deployment loses the terminal provider, the account panel and the auto-trade
path - and the only honest way to know what ELSE it loses is to take the module
away and use the app. Reading the code and reasoning about it is how you find
out afterwards that one route 500s.

Not a mock and not a flag inside the app - a meta_path finder that makes the
import fail the same way a missing wheel does, so `app/providers/mt5.py` takes
its real `except ImportError` branch. Anything that then works, works on Ubuntu.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class Block:
    def find_module(self, name, path=None):
        return self if name == "MetaTrader5" else None

    def find_spec(self, name, path=None, target=None):
        if name == "MetaTrader5":
            raise ImportError("No module named 'MetaTrader5'")
        return None


sys.meta_path.insert(0, Block())
try:
    import MetaTrader5  # noqa: F401
    print("BLOCK FAILED: MetaTrader5 still importable", flush=True)
    raise SystemExit(1)
except ImportError:
    print("MetaTrader5 blocked, as on Linux", flush=True)

import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8101, log_level="warning")
