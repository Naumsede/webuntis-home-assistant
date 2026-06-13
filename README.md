# WebUntis → Home Assistant (via REST API)

An alternative approach to integrating WebUntis timetable data into Home Assistant — using the **internal browser REST API** instead of the official JSON-RPC API.

> ⚠️ **Caution:** This project uses WebUntis' **undocumented internal REST API**. It may break without notice if Untis GmbH changes their backend. Use at your own risk. **Never commit credentials to a public repository.**

---

## Why this approach?

The official [homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis) integration uses the public JSON-RPC API which has significant limitations:

| Feature | JSON-RPC API (official) | REST API (this project) |
|---|---|---|
| Teacher substitution details | ❌ Only "changed" | ✅ Fr → Ar |
| Substitution text | ❌ | ✅ e.g. "Aufgabe Ko" |
| Lesson cancellation | ✅ | ✅ |
| Room changes | ✅ | ✅ with old → new room |
| Daily school messages | ❌ | ✅ |
| Dynamic time grid | ❌ | ✅ loaded from API |

---

## Features

- 📅 Full weekly timetable written to a local HA calendar (ICS)
- ⚠️ Teacher substitutions in the title
- ❌ Cancellations with strikethrough styling
- 🔀 Cancelled + replacement lessons at the same time merged into one event
  (e.g. `⚠️ Deutsch [statt: Musik] (Aufgabe Ko)`)
- 🏫 Room changes shown in the location line (`[MS2]→043`)
- 📢 Daily school messages as an HA sensor
- 🔔 Push notifications on genuinely new changes / messages only (no duplicates)
- 🕐 Dynamic time grid loaded from API (no hardcoded periods)
- 🌍 Correct DST handling via VTIMEZONE block
- 🎨 Reliable subject color coding via an invisible Braille-blank CSS anchor
- 📦 No external dependencies beyond `requests`

---

## Prerequisites

- Home Assistant with the `local_calendar` integration enabled
- Python 3 on your HA host (via the Terminal & SSH add-on)
- `requests` library:
  ```bash
  pip3 install requests --break-system-packages
  ```
  (Re-run after a Home Assistant Core update.)

---

## Authentication Flow

WebUntis uses a multi-step authentication for the REST API:

1. **Web login** → `POST /WebUntis/j_spring_security_check` → sets `JSESSIONID` cookie
2. **JWT token** → `GET /WebUntis/api/token/new` → returns a raw JWT string (not JSON-wrapped)
3. **REST calls** → send `Authorization: Bearer <jwt>` + `tenant-id: <id>` headers

The tenant ID and time grid are loaded dynamically from `/api/rest/view/v1/app/data`.

---

## Key API Endpoints

**App data (tenant ID, time grid, student IDs):**
```
GET /WebUntis/api/rest/view/v1/app/data
```

**Timetable entries:**
```
GET /WebUntis/api/rest/view/v1/timetable/entries
    ?start=YYYY-MM-DD&end=YYYY-MM-DD
    &format=2&resourceType=STUDENT&resources=<student_id>
    &periodTypes=&timetableType=MY_TIMETABLE&layout=START_TIME
```
Status values per entry: `REGULAR`, `CHANGED`, `CANCELLED`.

**Daily school messages:**
```
GET /WebUntis/main.do
```
Messages are embedded in the HTML, parsed from the `data-dojo-props` of
`grupet/widget/app/MessageOfDayList`. The JSON-RPC API does **not** expose them.

---

## Setup

1. **Enable Local Calendar** in `configuration.yaml`:
   ```yaml
   local_calendar:
   ```
   Then create one calendar per student under Settings → Integrations → Local Calendar.

2. **Find the ICS path** — create a test event via the HA UI, then:
   ```bash
   ls /config/.storage/local_calendar*.ics
   ```

3. **Find your IDs** — run the helper:
   ```bash
   python3 scripts/find_student_ids.py
   ```

4. **Configure scripts** — copy `scripts/webuntis_calendar.py` to
   `/config/scripts/` (one copy per student) and set `STUDENT_ID`, `ICS_PATH`,
   `CAL_ID`, `CAL_NAME` at the top of each. Credentials come from environment
   variables (see `examples/configuration.yaml`).

5. **Test:**
   ```bash
   WEBUNTIS_USER='...' WEBUNTIS_PASSWORD='...' \
   WEBUNTIS_SERVER='your-school.webuntis.com' WEBUNTIS_SCHOOL='your-school' \
   python3 /config/scripts/webuntis_calendar.py
   ```
   Expected: `{"status": "ok", "events": 42, "changes": 3, "items": [...]}`

6. **Add sensors** — see `examples/configuration.yaml`
7. **Add automations** — see `examples/automations.yaml`
8. **Add Lovelace cards** — see `examples/week_planner_card.yaml` and `examples/messages_card.yaml`

---

## Notes on the CSS color anchor

The week-planner-card colors subjects by matching the event title against
`data-summary*="Subject"`. In a merged event the cancelled subject also appears
in the title (`Deutsch [statt: Musik]`), which would match two colors at once.

To solve this, the script appends an invisible **Braille blank (U+2800)**
directly after the *active* subject. The CSS selectors match `Subject⠀`
(with the anchor), so only the active subject is colored — the cancelled subject
in brackets has no anchor and is ignored. The Braille blank survives copy/paste
in editors, unlike a zero-width space.

---

## Limitations

- ⚠️ Undocumented API — may break on WebUntis updates
- 🔄 Writes the current + next week only
- 👤 Tested with a `LEGAL_GUARDIAN` (parent) account
- 🏫 Tested on a German WebUntis instance

---

## Related

- [homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis) — official integration (JSON-RPC API)

---

## License

MIT
