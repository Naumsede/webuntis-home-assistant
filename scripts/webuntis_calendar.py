#!/usr/bin/env python3
"""
WebUntis → HA Local Calendar
Fetches current + next week timetable and writes it as an ICS file
to a Home Assistant local calendar.

Configuration: edit the YOUR CONFIGURATION section below.
Requirements: pip3 install requests --break-system-packages
"""
import requests, json, sys, re, hashlib
from datetime import date, timedelta, datetime, timezone

# ── YOUR CONFIGURATION ────────────────────────────────────────────────────────
USERNAME   = "your@email.com"           # WebUntis login email
PASSWORD   = "yourpassword"             # WebUntis password
SERVER     = "your-school.webuntis.com" # WebUntis server hostname
SCHOOL     = "your-school"              # school name (from login URL)
STUDENT_ID = 12345                      # from /api/rest/view/v1/app/data -> user.students
ICS_PATH   = "/config/.storage/local_calendar.your_calendar.ics"
CAL_ID     = "student1"                 # unique string for stable UIDs (no spaces)
CAL_NAME   = "Timetable"                # calendar display name
# ─────────────────────────────────────────────────────────────────────────────

DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:STANDARD
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
END:DAYLIGHT
END:VTIMEZONE"""

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})


def stable_uid(key):
    return hashlib.md5(key.encode()).hexdigest()


def periods_from_units(units):
    """Convert WebUntis time grid (e.g. 750 = 07:50) to (start_min, end_min) tuples."""
    result = []
    for u in sorted(units, key=lambda x: x["startTime"]):
        st = u["startTime"]
        et = u["endTime"]
        result.append((st // 100 * 60 + st % 100, et // 100 * 60 + et % 100))
    return result


def to_min(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def from_min(day_prefix, minutes):
    return f"{day_prefix}T{minutes//60:02d}:{minutes%60:02d}"


def split_entry(entry, periods):
    """Split double lessons into individual period slots. Events > 120 min stay as one block."""
    day   = entry["start"][:10]
    start = to_min(entry["start"][11:16])
    end   = to_min(entry["end"][11:16])
    if end - start > 120:
        return [(entry["start"], entry["end"])]
    slots = [(s, e) for s, e in periods if s >= start and e <= end]
    if not slots:
        return [(entry["start"], entry["end"])]
    return [(from_min(day, s), from_min(day, e)) for s, e in slots]


def ics_dt(iso):
    return iso.replace("-", "").replace(":", "") + "00"


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_title(entry):
    status          = entry["status"]
    subject         = entry["subject"]
    teacher_current = entry["teacher"]
    teacher_removed = entry["teacher_removed"]
    room_current    = entry["room"]
    room_removed    = entry["room_removed"]
    note            = entry.get("note", "")

    if status == "CANCELLED":
        return f"❌ {subject} fällt aus"

    if status == "CHANGED":
        parts = []
        if teacher_removed and teacher_current != teacher_removed:
            ziel = teacher_current if teacher_current else "–"
            parts.append(f"{teacher_removed}→{ziel}")
        if room_removed and room_current != room_removed:
            parts.append(f"Raum: {room_removed}→{room_current}")
        if parts:
            title = f"⚠️ {subject}: " + ", ".join(parts)
            if note:
                title += f" ({note})"
        else:
            title = f"⚠️ {subject}: {note}" if note else f"⚠️ {subject}"
        return title

    return subject


def make_description(entry):
    lines = []
    if entry["teacher"]:
        if entry["teacher_removed"] and entry["teacher"] != entry["teacher_removed"]:
            lines.append(f"Teacher: {entry['teacher_removed']} → {entry['teacher']}")
        else:
            lines.append(f"Teacher: {entry['teacher']}")
    if entry["room"]:
        if entry["room_removed"] and entry["room"] != entry["room_removed"]:
            lines.append(f"Room: {entry['room_removed']} → {entry['room']}")
        else:
            lines.append(f"Room: {entry['room']}")
    if entry["note"]:
        lines.append(f"Note: {entry['note']}")
    return "\n".join(lines)


def parse_entry(raw):
    subject = ""
    for p in (raw.get("position2") or []):
        if p.get("current"):
            subject = p["current"].get("longName", p["current"].get("shortName", ""))
        break

    teacher_current, teacher_removed = "", ""
    for p in (raw.get("position1") or []):
        if p.get("current"):
            teacher_current = p["current"].get("shortName", "")
        if p.get("removed"):
            teacher_removed = p["removed"].get("shortName", "")
        break

    room_current, room_removed = "", ""
    for p in (raw.get("position3") or []):
        if p.get("current"):
            room_current = p["current"].get("shortName", "")
        if p.get("removed"):
            room_removed = p["removed"].get("shortName", "")
        break

    return {
        "start":           raw["duration"]["start"],
        "end":             raw["duration"]["end"],
        "subject":         subject,
        "teacher":         teacher_current,
        "teacher_removed": teacher_removed,
        "room":            room_current,
        "room_removed":    room_removed,
        "status":          raw.get("status", "REGULAR"),
        "note":            raw.get("substitutionText", "").strip(),
        "_ids":            raw.get("ids", []),
    }


try:
    # Step 1: Web login → JSESSIONID cookie
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
        print(json.dumps({"status": "error", "error": "Login failed - check credentials"}))
        sys.exit(1)

    # Step 2: JWT Bearer token
    jwt = session.get(f"https://{SERVER}/WebUntis/api/token/new").text.strip()
    if not jwt.startswith("ey"):
        print(json.dumps({"status": "error", "error": "Invalid JWT token"}))
        sys.exit(1)

    # Step 3: Load app data → tenant ID + time grid (dynamic)
    app_data  = session.get(
        f"https://{SERVER}/WebUntis/api/rest/view/v1/app/data",
        headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"}
    ).json()
    tenant_id = app_data["tenant"]["id"]
    PERIODS   = periods_from_units(app_data["currentSchoolYear"]["timeGrid"]["units"])

    # Step 4: Fetch timetable (current + next week)
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=11)

    resp = session.get(
        f"https://{SERVER}/WebUntis/api/rest/view/v1/timetable/entries",
        params={
            "start":         monday.strftime("%Y-%m-%d"),
            "end":           friday.strftime("%Y-%m-%d"),
            "format":        "2",
            "resourceType":  "STUDENT",
            "resources":     str(STUDENT_ID),
            "periodTypes":   "",
            "timetableType": "MY_TIMETABLE",
            "layout":        "START_TIME",
        },
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept":        "application/json",
            "tenant-id":     tenant_id,
        }
    )
    if resp.status_code != 200:
        print(json.dumps({"status": "error", "error": f"Timetable API returned {resp.status_code}"}))
        sys.exit(1)

    data      = resp.json()
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Step 5: Build ICS
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HA WebUntis Script//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{CAL_NAME}",
    ]
    ics_lines += VTIMEZONE.strip().splitlines()

    event_count   = 0
    changes_count = 0
    changes_list  = []

    for day in data.get("days", []):
        day_date = day["date"]

        # Collect occupied period slots
        occupied = set()
        for raw in day.get("gridEntries", []):
            entry = parse_entry(raw)
            start = to_min(entry["start"][11:16])
            end   = to_min(entry["end"][11:16])
            for ps, pe in PERIODS:
                if ps >= start and pe <= end:
                    occupied.add(ps)

        # Invisible placeholder events up to last occupied slot
        # (keeps week-planner-card row heights consistent)
        last_occupied = max(occupied) if occupied else 0
        for ps, pe in PERIODS:
            if ps not in occupied and ps <= last_occupied:
                slot_start = from_min(day_date, ps)
                slot_end   = from_min(day_date, pe)
                ics_lines += [
                    "BEGIN:VEVENT",
                    f"UID:{stable_uid(slot_start + '-empty-' + CAL_ID)}",
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART;TZID=Europe/Berlin:{ics_dt(slot_start)}",
                    f"DTEND;TZID=Europe/Berlin:{ics_dt(slot_end)}",
                    "SUMMARY: ",
                    "END:VEVENT",
                ]
                event_count += 1

        # Real lessons
        for raw in day.get("gridEntries", []):
            entry  = parse_entry(raw)
            title  = make_title(entry)
            desc   = make_description(entry)
            slots  = split_entry(entry, PERIODS)

            for start, end in slots:
                # Stable UID based on WebUntis internal ID (survives content changes)
                webuntis_id = str(entry["_ids"][0]) if entry["_ids"] else start
                uid = stable_uid(webuntis_id + "-" + CAL_ID)
                ics_lines += [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART;TZID=Europe/Berlin:{ics_dt(start)}",
                    f"DTEND;TZID=Europe/Berlin:{ics_dt(end)}",
                    f"SUMMARY:{ics_escape(title)}",
                ]
                ics_lines.append(f"LOCATION:{ics_escape(entry['room']) if entry['room'] else ' '}")
                if desc:
                    ics_lines.append(f"DESCRIPTION:{ics_escape(desc)}")
                ics_lines.append("END:VEVENT")
                event_count += 1

            if entry["status"] != "REGULAR":
                changes_count += 1
                day_dt  = date.fromisoformat(entry["start"][:10])
                day_str = f"{DAYS_DE[day_dt.weekday()]} {day_dt.strftime('%d.%m.')}"
                changes_list.append({
                    "date": entry["start"][:10],
                    "day":  day_str,
                    "text": title,
                })

    ics_lines.append("END:VCALENDAR")

    with open(ICS_PATH, "w", encoding="utf-8") as f:
        f.write("\r\n".join(ics_lines) + "\r\n")

    print(json.dumps({
        "status":  "ok",
        "events":  event_count,
        "changes": changes_count,
        "items":   changes_list,
    }, ensure_ascii=False))

finally:
    try:
        session.post(f"https://{SERVER}/WebUntis/j_spring_security_logout")
    except Exception:
        pass
