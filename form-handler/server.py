#!/usr/bin/env python3
"""
Form submission handler for okad.cc Canvas UGC lead form.
Saves submissions to submissions.json and sends Telegram notification.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import requests

PORT = 8901
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.json")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8469288572:AAE5o1Uq3uPQH1Jc0Y9PYUhNxF1ktm_w6tU")
NOTIFY_CHAT_ID = os.environ.get("NOTIFY_CHAT_ID", "-5586151871")


def load_submissions():
    if os.path.exists(SUBMISSIONS_FILE):
        with open(SUBMISSIONS_FILE, "r") as f:
            return json.load(f)
    return []


def save_submission(entry):
    subs = load_submissions()
    subs.append(entry)
    with open(SUBMISSIONS_FILE, "w") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)
    return len(subs)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": NOTIFY_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


class FormHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/submit":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 10000:
            self.send_error(413, "Too large")
            return

        body = self.rfile.read(content_length).decode("utf-8")

        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
        else:
            parsed = parse_qs(body)
            data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

        required = ["company", "email"]
        for field in required:
            if not data.get(field, "").strip():
                self._json_response(400, {"error": f"Missing field: {field}"})
                return

        entry = {
            "id": int(time.time() * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company": data.get("company", "").strip(),
            "website": data.get("website", "").strip(),
            "email": data.get("email", "").strip(),
            "budget": data.get("budget", "").strip(),
            "message": data.get("message", "").strip(),
            "source": data.get("source", "unknown").strip(),
        }

        count = save_submission(entry)

        msg = (
            f"<b>New Canvas UGC lead #{count}</b>\n\n"
            f"<b>Company:</b> {entry['company']}\n"
            f"<b>Email:</b> {entry['email']}\n"
        )
        if entry["website"]:
            msg += f"<b>Website:</b> {entry['website']}\n"
        if entry["budget"]:
            msg += f"<b>Budget:</b> {entry['budget']}\n"
        if entry["message"]:
            msg += f"<b>Message:</b> {entry['message']}\n"
        msg += f"\n<i>{entry['timestamp']}</i>"

        send_telegram(msg)

        self._json_response(200, {"ok": True, "id": entry["id"]})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "https://okad.cc")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}", file=sys.stderr)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), FormHandler)
    print(f"Form handler listening on 127.0.0.1:{PORT}", file=sys.stderr)
    server.serve_forever()
