# WebUntis → Home Assistant (via REST API)

An alternative approach to integrating WebUntis timetable data into Home Assistant — using the **internal browser REST API** instead of the official JSON-RPC API.

> ⚠️ **Caution:** This project uses WebUntis' **undocumented internal REST API**. It may break without notice if Untis GmbH changes their backend. Use at your own risk. Credentials are stored in plain text in the script – consider using `secrets.yaml` in production. **Never commit credentials to a public repository.**

---

## Why this approach?

The official [homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis) integration uses the public JSON-RPC API which has significant limitations:

| Feature | JSON-RPC API (official) | REST API (this project) |
|---|---|---|
| Teacher substitution details | ❌ Only "changed" | ✅ Fr → Ar |
| Substitution text | ❌ | ✅ e.g. "Känguruwettbewerb" |
| Lesson cancellation | ✅ | ✅ |
| Room changes | ✅ | ✅ with old/new room |
| Daily school messages | ❌ | ✅ |
| Dynamic time grid | ❌ | ✅ loaded from API |

---

## Features

- 📅 Full weekly timetable written to a local HA calendar (ICS)
- ⚠️ Teacher substitutions: `Fr → Ar`
- ❌ Cancellations with strikethrough styling
- 🏫 Room changes: `TU3 → 043`
- 📝 Substitution text in event title
- 📢 Daily school messages as HA sensor
- 🔔 Push notifications on new changes only (no duplicates)
- 🕐 Dynamic time grid loaded from API (no hardcoded periods)
- 🌍 Correct DST handling via VTIMEZONE block
- 🔑 Stable UIDs via WebUntis internal IDs
- 📦 No external dependencies beyond `requests`

---

## ⚠️ Security Note

Your WebUntis credentials are stored in the script files. For better security, use HA's `secrets.yaml`:

```yaml
# secrets.yaml
webuntis_username: your@email.com
webuntis_password: yourpassword
```

**Never commit credentials to a public repository.**

---

## Prerequisites

- Home Assistant with `local_calendar` integration enabled
- Python 3 on your HA host (via Terminal & SSH add-on)
- `requests` library:
  ```bash
  pip3 install requests --break-system-packages
  ```

---

## Authentication Flow

WebUntis uses a two-step authentication for the REST API:

**Step 1 – Web Login (gets JSESSIONID cookie)**
```python
session.post(
    f"https://{SERVER}/WebUntis/j_spring_security_check",
    data={"j_username": USERNAME, "j_password": PASSWORD,
          "school": SCHOOL, "token": csrf_token}
)
```

**Step 2 – JWT Bearer Token**
```python
# Returns raw JWT string (not JSON-wrapped)
jwt = session.get(f"https://{SERVER}/WebUntis/api/token/new").text.strip()
```

**Step 3 – REST API calls**
```python
headers = {
    "Authorization": f"Bearer {jwt}",
    "tenant-id":     tenant_id,  # loaded dynamically from app/data
}
```

---

## Key API Endpoints

### App Data (tenant ID, time grid, student IDs)
```
GET /WebUntis/api/rest/view/v1/app/data
```

### Timetable Entries
```
GET /WebUntis/api/rest/view/v1/timetable/entries
    ?start=YYYY-MM-DD&end=YYYY-MM-DD
    &format=2&resourceType=STUDENT&resources=<student_id>
    &periodTypes=&timetableType=MY_TIMETABLE&layout=START_TIME
```

Example entry with teacher substitution:
```json
{
  "status": "CHANGED",
  "ids": [2600142],
  "duration": {"start": "2026-03-16T08:40", "end": "2026-03-16T09:25"},
  "position1": [{
    "current": {"shortName": "Ar", "status": "ADDED"},
    "removed": {"shortName": "Fr", "status": "REMOVED"}
  }],
  "position2": [{"current": {"longName": "Englisch"}}],
  "position3": [{"current": {"shortName": "043"}}],
  "substitutionText": "Aufgaben Fr"
}
```

Status values: `REGULAR`, `CHANGED`, `CANCELLED`

### Daily School Messages
```
GET /WebUntis/main.do
```
Messages are embedded in the HTML – parsed from `data-dojo-props` of `grupet/widget/app/MessageOfDayList`. The JSON-RPC API does **not** expose daily messages.

---

## Finding Your Configuration Values

**Server & School name** – from your WebUntis URL:
```
https://YOUR-SERVER.webuntis.com/WebUntis/?school=YOUR-SCHOOL
```

**Student IDs & Tenant ID** – run the helper script:
```bash
python3 scripts/find_student_ids.py
```

---

## Setup

1. **Enable Local Calendar** in `configuration.yaml`:
   ```yaml
   local_calendar:
   ```
   Then create a calendar per student under Settings → Integrations → Local Calendar.

2. **Find ICS path** – create a test event via HA UI, then:
   ```bash
   ls /config/.storage/local_calendar*.ics
   ```

3. **Configure scripts** – copy from `scripts/` to `/config/scripts/` and edit the configuration section at the top of each file.

4. **Test:**
   ```bash
   python3 /config/scripts/webuntis_calendar.py
   python3 /config/scripts/webuntis_newsfeed.py
   ```
   Expected output:
   ```json
   {"status": "ok", "events": 42, "changes": 3, "items": [...]}
   ```

5. **Add sensors** – see `examples/configuration.yaml`

6. **Add automations** – see `examples/automations.yaml`

7. **Add Lovelace cards** – see `examples/week_planner_card.yaml` and `examples/messages_card.yaml`

---

## Limitations

- ⚠️ Undocumented API – may break on WebUntis updates
- 🔄 Writes 2 weeks ahead only
- 👤 Tested with `LEGAL_GUARDIAN` account type
- 🏫 Tested on German WebUntis instances (March 2026)

---

## Related

- [homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis) – official integration using JSON-RPC API
- [Issue #266](https://github.com/JonasJoKuJonas/homeassistant-WebUntis/issues/266) – our API findings submitted to the official integration

---

## Contributing

Pull requests welcome! Especially:
- Teacher/student account support (currently tested with legal guardian only)
- Homework integration (endpoint discovered: `/api/rest/view/v2/calendar-entry/detail`)
- Additional WebUntis instances tested

---

## License

MIT
