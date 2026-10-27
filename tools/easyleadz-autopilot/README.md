# EasyLeadz autopilot

Fully automatic run over a list of LinkedIn profiles: opens each profile,
clicks **View contact** in the EasyLeadz (Mr. E) side panel, reads the phone
and email, appends them to a CSV, waits a random 8–20 s, moves on.

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

## Each run
1. Double-click `start-chrome.bat` (if that Chrome isn't already open).
2. **Open the Mr. E side panel** in that window and leave it open.
3. Export your Google Sheet as CSV (File → Download → CSV) — any column with
   `linkedin.com/in/...` URLs is picked up automatically.
4. In a terminal in this folder:
   ```
   node autopilot.mjs C:\path\to\leads.csv --max 170
   ```
5. Results are appended to `easyleadz-contacts.csv` next to your input file,
   with your original columns + phone, email, status, time, source.

Stop any time with **Ctrl+C**. Re-running the same command resumes — profiles
already in the output file are skipped and cost nothing.

## Options
| flag | default | meaning |
|---|---|---|
| `--out file.csv` | `easyleadz-contacts.csv` | output file |
| `--max N` | 170 | stop after N phone numbers this run |
| `--min-delay S` / `--max-delay S` | 8 / 20 | random pause between profiles (seconds) |
| `--port P` | 9222 | Chrome's remote-debugging port |

It also stops when the panel shows 0 credits.

## Notes
- The debugging port lets any program on your computer control that Chrome
  window. Close it when you're not running the autopilot, and don't use that
  profile for anything else.
- Profiles where EasyLeadz has no contact take ~25 s (the script waits for the
  panel to change before concluding "no data").
- Status values: `found` (phone), `email_only`, `no_data`.
