"""Start SuperChat:  python run.py            (web chat on http://127.0.0.1:8000)
                    python run.py --cli      (chat in the terminal)
                    python run.py --port 9000"""
import argparse
import logging
import os
import sys
import threading

from superchat.app import SuperChat
from superchat.server import serve

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", action="store_true", help="chat in the terminal instead of the browser")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--api-demo", action="store_true",
                    help="Phase 2 demo: start the local fake API (with random failures) and run the chat on HTTP APIs")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO if a.api_demo else logging.WARNING, format="%(name)s: %(message)s")
    if a.api_demo:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        from fake_api import FakeAPI, make_server
        srv = make_server(FakeAPI(fail_rate=0.2), port=8100)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        for k in ("FLIGHTS", "SHOP", "CINEMA"):
            os.environ[f"{k}_API_URL"], os.environ[f"{k}_API_KEY"] = "http://127.0.0.1:8100", "demo-key"
        print("Fake API running on http://127.0.0.1:8100 (20% of calls fail on purpose; watch the retries in the log)")
    if a.cli:
        bot, sid = SuperChat(), "cli"
        print("SuperChat (type 'quit' to exit)")
        while True:
            try:
                msg = input("you › ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if msg.lower() in ("quit", "exit"):
                break
            r = bot.handle(sid, msg)
            print(f"[{r['category']}] bot › {r['reply']}\n")
    else:
        serve(a.host, a.port)
