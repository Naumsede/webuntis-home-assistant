# WebUntis → Home Assistant (via REST API)

An alternative approach to integrating WebUntis timetable data into Home Assistant — using the **internal browser REST API** instead of the official JSON-RPC API.

> ⚠️ **Caution:** This project uses an **undocumented, internal WebUntis API**. It may break without notice if Untis GmbH changes their backend. Use at your own risk.

---

## Why this approach?

The official [homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis) integration uses the public JSON-RPC API. This API is limited:

- No teacher substitution details (only a generic "changed" flag)
- No substitution text / notes
- No daily school messages

This project uses the same REST API that the WebUntis browser interface uses:

| Feature | JSON-RPC API | This project |
|---|---|---|
| Lesson cancellation | ✅ | ✅ |
| Room change | ✅ | ✅ |
| Teacher substitution detail | ❌ | ✅ `Fr → Ar` |
| Substitution text | ❌ | ✅ `Känguruwettbewerb` |
| Daily school messages | ❌ | ✅ |

---

## How it works

### Authentication flow

```
1. POST /WebUntis/j_spring_security_check  →  JSESSIONID cookie
2. GET  /WebUntis/api/token/new            →  JWT Bearer token (raw string)
```

The JWT token is passed as `Authorization: Bearer <token>` in all REST calls.

### Key endpoints

```
GET /WebUntis/api/rest/view/v1/app/data
    → tenant ID, time grid, student IDs

GET /WebUntis/api/rest/view/v1/timetable/entries
    ?start=YYYY-MM-DD&end=YYYY-MM-DD&format=2
    &resourceType=STUDENT&resources=<student_id>
    &periodTypes=&timetableType=MY_TIMETABLE&layout=START_TIME
    → full timetable with change details

GET /WebUntis/main.do
    → daily school messages (embedded in HTML)
```

### Timetable entry structure

```json
{
  "status": "CHANGED",
  "position1": [{
    "current": {"shortName": "Ar", "status": "ADDED"},
    "removed": {"shortName": "Fr", "status": "REMOVED"}
  }],
  "position2": [{"current": {"longName": "Englisch"}}],
  "position3": [{"current": {"shortName": "043"}}],
  "substitutionText": "Aufgaben Fr",
  "duration": {"start": "2026-03-16T08:40", "end": "2026-03-16T09:25"}
}
```

---

## What you get

- **Local HA calendar** with full timetable for this + next week
  - `⚠️ Englisch: Fr→Ar (Aufgaben Fr)` — teacher substitution with note
  - `❌ Englisch fällt aus` — cancellation (strikethrough via CSS)
  - `⚠️ Sport: Raum: TU3→043 (Känguruwettbewerb)` — room change with note
- **`command_line` sensor** with count and list of current changes
- **Push notification** when changes are detected
- **Daily school messages** as a sensor and Lovelace card

---

## Prerequisites

- Home Assistant (tested on HA OS 2026.3)
- Python 3 on your HA host
- A WebUntis parent/guardian or student account
- [week-planner-card](https://github.com/FamousWolf/week-planner-card) from HACS
- Scripts placed in `/config/scripts/`

---

## Setup

### 1. Find your credentials

- **Server**: hostname of your school's WebUntis instance (e.g. `myschool.webuntis.com`)
- **School**: school slug visible in the URL after login
- **Username / Password**: your WebUntis login

### 2. Find Student ID and Tenant ID

Run `scripts/find_ids.py` once after filling in your credentials.

### 3. Store credentials securely

> ⚠️ **Security note:** Never commit credentials to version control. The example scripts use inline variables for simplicity — store passwords in HA's `secrets.yaml` in production.

```yaml
# secrets.yaml
webuntis_username: "your@email.com"
webuntis_password: "yourpassword"
```

### 4. Create a local calendar in HA

**Settings → Integrations → Local Calendar** → Add a calendar per student.
Create one event to initialize the ICS file, then note the path:
```
/config/.storage/local_calendar.<calendar_name>.ics
```

### 5. Configure the scripts

Copy `scripts/webuntis_calendar.py` for each student and set:

```python
USERNAME   = "your@email.com"
PASSWORD   = "yourpassword"
SERVER     = "yourschool.webuntis.com"
SCHOOL     = "yourschool"
STUDENT_ID = 12345        # from find_ids.py
ICS_PATH   = "/config/.storage/local_calendar.student_calendar.ics"
CAL_ID     = "student1"   # unique string for stable UIDs
CAL_NAME   = "Student Timetable"
```

### 6. Configure HA sensors and automations

See `examples/configuration.yaml` and `examples/automations.yaml`.

### 7. Add Lovelace cards

See `examples/lovelace_timetable.yaml` and `examples/lovelace_messages.yaml`.

---

## Limitations

- Uses an **undocumented internal API** — may break with WebUntis updates
- Tested with a **Legal Guardian** account (`LEGAL_GUARDIAN` role)
- Tested on a German school WebUntis instance (Schleswig-Holstein)
- The time grid is loaded dynamically from the API
- Placeholder events (invisible, for consistent card heights in week-planner-card) are written to the calendar

---

## Contributing

Pull requests welcome. If you test this with other account types, school configurations, or WebUntis versions, please open an issue.

---

## License

MIT
