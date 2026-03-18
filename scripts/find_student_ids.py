#!/usr/bin/env python3
"""
Helper script to find your student IDs, tenant ID and time grid from WebUntis.
Run this once during setup, then add the IDs to webuntis_calendar.py.
"""
import requests, json, re

# ── YOUR CONFIGURATION ────────────────────────────────────────────────────────
USERNAME = "your@email.com"
PASSWORD = "yourpassword"
SERVER   = "your-school.webuntis.com"
SCHOOL   = "your-school"
# ─────────────────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

login_page  = session.get(f"https://{SERVER}/WebUntis/")
token_match = re.search(r'name="token"\s+value="([^"]+)"', login_page.text)
csrf = token_match.group(1) if token_match else ""
session.post(f"https://{SERVER}/WebUntis/j_spring_security_check",
    data={"j_username": USERNAME, "j_password": PASSWORD, "school": SCHOOL, "token": csrf},
    allow_redirects=True)

jwt = session.get(f"https://{SERVER}/WebUntis/api/token/new").text.strip()

app_data = session.get(f"https://{SERVER}/WebUntis/api/rest/view/v1/app/data",
    headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"}).json()

print("=== YOUR CONFIGURATION VALUES ===")
print(f"Tenant ID : {app_data['tenant']['id']}")
print(f"School    : {app_data['tenant']['name']}")
print()
print("Students:")
for s in app_data["user"].get("students", []):
    print(f"  {s['displayName']:<30} ID: {s['id']}")
print()
print("Time grid (loaded dynamically by webuntis_calendar.py):")
for u in app_data["currentSchoolYear"]["timeGrid"]["units"]:
    st, et = u["startTime"], u["endTime"]
    print(f"  Period {u['unitOfDay']}: {st//100:02d}:{st%100:02d} – {et//100:02d}:{et%100:02d}")
