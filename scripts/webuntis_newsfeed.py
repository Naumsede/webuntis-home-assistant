#!/usr/bin/env python3
"""
WebUntis → HA Sensor: Daily school messages (Nachrichten des Tages)

Messages are embedded in the HTML of the main.do page and are only visible
to logged-in users — they do NOT appear in the public RSS feed
(/WebUntis/NewsFeed.do) unless marked as public by the school.

Output (JSON to stdout):
  {"count": 2, "items": [{"title": "", "text": "Achtung: ..."}]}
"""
import requests, json, sys, re
from html import unescape

USERNAME = "your@email.com"
PASSWORD = "yourpassword"
SERVER   = "yourschool.webuntis.com"
SCHOOL   = "yourschool"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

try:
    login_page  = session.get(f"https://{SERVER}/WebUntis/")
    token_match = re.search(r'name="token"\s+value="([^"]+)"', login_page.text)
    csrf = token_match.group(1) if token_match else ""
    session.post(
        f"https://{SERVER}/WebUntis/j_spring_security_check",
        data={"j_username": USERNAME, "j_password": PASSWORD,
              "school": SCHOOL, "token": csrf},
        allow_redirects=True
    )
    if "JSESSIONID" not in session.cookies:
        print(json.dumps({"count": 0, "items": [], "error": "Login failed"}))
        sys.exit(1)

    resp = session.get(
        f"https://{SERVER}/WebUntis/main.do",
        params={"request.preventCache": "1"}
    )

    match = re.search(
        r'data-dojo-type="grupet/widget/app/MessageOfDayList"\s+data-dojo-props="([^"]*(?:&#034;[^"]*)*)"',
        resp.text
    )
    if not match:
        print(json.dumps({"count": 0, "items": []}))
        sys.exit(0)

    props_raw = unescape(match.group(1))
    msg_match = re.search(r'"messagesOfDay"\s*:\s*(\[.*?\])\s*,\s*"editable"', props_raw, re.DOTALL)
    if not msg_match:
        print(json.dumps({"count": 0, "items": []}))
        sys.exit(0)

    messages = json.loads(msg_match.group(1))
    items = [
        {"title": m.get("subject", ""), "text": m.get("body", "")}
        for m in messages
    ]
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))

finally:
    try:
        session.post(f"https://{SERVER}/WebUntis/j_spring_security_logout")
    except Exception:
        pass
