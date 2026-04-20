#!/usr/bin/env python3
"""
WebUntis → HA Sensor (Daily School Messages)
Fetches today's school messages and outputs JSON for a command_line sensor.

Note: WebUntis messages are only available via HTML scraping of the "Today" page.
      The JSON-RPC API does NOT expose daily messages.

Configuration:
  Pass credentials as environment variables (recommended):
    WEBUNTIS_USER, WEBUNTIS_PASSWORD, WEBUNTIS_SERVER, WEBUNTIS_SCHOOL

Requirements:
  pip3 install requests --break-system-packages
"""
import requests, json, sys, re, os
from html import unescape

USERNAME = os.getenv("WEBUNTIS_USER")
PASSWORD = os.getenv("WEBUNTIS_PASSWORD")
SERVER   = os.getenv("WEBUNTIS_SERVER")
SCHOOL   = os.getenv("WEBUNTIS_SCHOOL")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

try:
    login_page  = session.get(f"https://{SERVER}/WebUntis/")
    token_match = re.search(r'name="token"\s+value="([^"]+)"', login_page.text)
    token = token_match.group(1) if token_match else ""
    session.post(
        f"https://{SERVER}/WebUntis/j_spring_security_check",
        data={"j_username": USERNAME, "j_password": PASSWORD,
              "school": SCHOOL, "token": token},
        allow_redirects=True
    )
    if "JSESSIONID" not in session.cookies:
        print(json.dumps({"count": 0, "items": [], "error": "Login failed"}))
        sys.exit(1)

    resp = session.get(f"https://{SERVER}/WebUntis/main.do",
                       params={"request.preventCache": "1"})

    # Note: &#034; is the HTML entity for " - must be matched before unescape()
    match = re.search(
        r'data-dojo-type="grupet/widget/app/MessageOfDayList"\s+data-dojo-props="([^"]*(?:&#034;[^"]*)*)"',
        resp.text
    )
    if not match:
        print(json.dumps({"count": 0, "items": [], "error": "MessageOfDayList not found"}))
        sys.exit(0)

    props_raw = unescape(match.group(1))
    msg_match = re.search(r'"messagesOfDay"\s*:\s*(\[.*?\])\s*,\s*"editable"', props_raw, re.DOTALL)
    if not msg_match:
        print(json.dumps({"count": 0, "items": [], "error": "messagesOfDay not found"}))
        sys.exit(0)

    messages = json.loads(msg_match.group(1))
    items = [{"title": m.get("subject", ""), "text": m.get("body", "")} for m in messages]
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))

finally:
    try:
        session.post(f"https://{SERVER}/WebUntis/j_spring_security_logout")
    except Exception:
        pass
