# EasyLeadz autopilot

Fully automatic run over a list of LinkedIn profiles: opens each profile,
clicks **View contact** in the EasyLeadz (Mr. E) side panel, reads the phone
and email and writes them to a local CSV **and** (optionally) straight into
your Google Sheet. Paced at 3 profiles/minute by default.

> Automating LinkedIn browsing and the EasyLeadz extension is against both
> services' terms. Accounts can be restricted. Keep the delays, keep runs at or
> under your daily cap, and stop if LinkedIn shows a warning or CAPTCHA.

## One-time setup (Windows)
1. Install **Node.js 22 or newer** from nodejs.org.
2. Download this folder (e.g. to `C:\easyleadz-autopilot`).
3. Double-click `start-chrome.bat`. It opens a *separate* Chrome profile
   (Chrome only allows remote control on a non-default profile).
4. In that window: log in to LinkedIn, install the EasyLeadz / Mr. E
   extension from the Chrome Web Store and log in to it.

macOS equivalent of step 3:
```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/easyleadz-chrome"
```

## Google Sheet setup (once, optional)
1. Open your leads sheet → **Extensions → Apps Script**, delete what's there,
   paste the contents of `sheet-webapp.gs`.
2. Change `TOKEN` at the top to a long random string. Save.
3. **Deploy → New deployment** → gear icon → **Web app**.
   Execute as: **Me**. Who has access: **Anyone**. Deploy, allow access,
   copy the **Web app URL** (ends in `/exec`).

The token is what stops anyone else using that URL — keep both private.
Results go into `phone / email / status / revealed_at / source` columns
(created automatically) on the row with the matching LinkedIn URL.

## Each run
1. Double-click `start-chrome.bat` (if that Chrome isn't already open).
2. **Open the Mr. E side panel** in that window and leave it open.
3. In a terminal in this folder, pick one:

   ```
   # Leads from your Google Sheet, results written back into it (+ local CSV)
   node autopilot.mjs --sheet https://script.google.com/macros/s/XXX/exec --token YOURTOKEN

   # Leads from a CSV, results to the Google Sheet + local CSV
   node autopilot.mjs leads.csv --sheet https://script.google.com/macros/s/XXX/exec --token YOURTOKEN

   # CSV only
   node autopilot.mjs leads.csv
   ```

Any column containing `linkedin.com/in/...` URLs is picked up automatically.
The local copy is `easyleadz-contacts.csv` (next to the input CSV, or in the
current folder when reading from the sheet).

Stop any time with **Ctrl+C**. Re-running resumes: profiles already in the
local CSV, or already given a status in the sheet, are skipped and cost nothing.
If a sheet write fails (network blip) it's kept in
`easyleadz-contacts.csv.sheet-pending.jsonl` and retried on the next run.

## Options
| flag | default | meaning |
|---|---|---|
| `--sheet URL` / `--token T` | — | Google Sheet web app (see above) |
| `--out file.csv` | `easyleadz-contacts.csv` | local CSV copy |
| `--max N` | 170 | stop after N phone numbers this run |
| `--per-minute N` | 3 | profiles per minute (each gap varies ±25%) |
| `--port P` | 9222 | Chrome's remote-debugging port |

It also stops when the panel shows 0 credits. At 3/min, 170 profiles take
about an hour.

## Notes
- The debugging port lets any program on your computer control that Chrome
  window. Close it when you're not running the autopilot, and don't use that
  profile for anything else.
- Profiles where EasyLeadz has no contact take ~25 s (the script waits for the
  panel to change before concluding "no data").
- Status values: `found` (phone), `email_only`, `no_data`.
