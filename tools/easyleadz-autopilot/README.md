# EasyLeadz Autopilot — setup & run guide

Goes through a list of LinkedIn profiles, clicks **View contact** in the
EasyLeadz (Mr. E) side panel on each one, and saves the phone number and email
to a CSV file and (optionally) straight into your Google Sheet.

> **Account risk.** Automating LinkedIn and EasyLeadz is against both services'
> terms and accounts can be restricted. Keep volume low, and if the script
> stops with a LinkedIn warning, take a break before running again.

---

## What's in this folder

| File | What it is |
|---|---|
| `run.bat` | **Double-click to run** (Windows). Settings are at the top. |
| `start-chrome.bat` | Opens the special Chrome window the script controls (Windows). |
| `autopilot.mjs` | The script itself. No need to touch it. |
| `sheet-webapp.gs` | Paste into your Google Sheet if you want results written there. |
| `leads.csv` | Example input file — replace with your own list. |
| `run-mac.command`, `start-chrome-mac.command` | Same as the .bat files, for Mac. |

---

## Part 1 — One-time setup (≈10 minutes)

### Step 1: Install Node.js
Download the **LTS** version from https://nodejs.org (must be **version 22
or newer**) and install it with the default options.

### Step 2: Unzip this folder
Put it somewhere simple, e.g. `C:\easyleadz-autopilot`.

### Step 3: Set up the special Chrome window
1. Close all Chrome windows.
2. Double-click **`start-chrome.bat`**. A Chrome window opens on LinkedIn.
   This is a *separate* Chrome profile — your normal Chrome isn't affected.
   (Chrome only allows a script to control a separate profile.)
3. In **this** window:
   - Log in to **LinkedIn**.
   - Install the **EasyLeadz / Mr. E** extension from the Chrome Web Store
     and log in to it.
4. You won't have to log in again. Next time, `start-chrome.bat` opens it
   still logged in.

### Step 4 (optional): Connect your Google Sheet
Skip this if you only want CSV files.

1. Open your Google Sheet with the LinkedIn URLs.
   Row 1 must be the headers (e.g. `Name | Company | LinkedIn URL`).
2. Menu **Extensions → Apps Script**. Delete any code there.
3. Open `sheet-webapp.gs` in Notepad, copy everything, paste it into Apps Script.
4. On the line `const TOKEN = 'change-this-to-a-long-random-string';`
   replace the text between the quotes with your own password, e.g.
   `const TOKEN = 'kq83hd92mxP0aa71';`
   If the leads aren't on the first tab, also set `SHEET_NAME` to the tab name.
5. Click 💾 **Save**.
6. Click **Deploy → New deployment**. Click the ⚙ gear next to
   "Select type" → **Web app**.
   - Execute as: **Me**
   - Who has access: **Anyone**
7. Click **Deploy** → **Authorize access** → choose your Google account.
   If you see "Google hasn't verified this app": **Advanced → Go to … (unsafe)**
   → **Allow** (it's your own script).
8. Copy the **Web app URL** (looks like
   `https://script.google.com/macros/s/AKfy…/exec`).

Keep the URL and token private — together they let someone edit that sheet.

> If you later change the code in Apps Script, use **Deploy → Manage
> deployments → ✏ Edit → Version: New version → Deploy** so the URL keeps working.

---

## Part 2 — Settings (`run.bat`)

Right-click **`run.bat` → Edit** (opens Notepad). Change the lines at the top:

```
set SHEET_URL=https://script.google.com/macros/s/AKfy.../exec
set TOKEN=kq83hd92mxP0aa71
set CSV_FILE=leads.csv
set MAX=170
set PER_MINUTE=3
```

| Setting | Meaning |
|---|---|
| `SHEET_URL` / `TOKEN` | From Step 4. Leave **empty** for CSV-only. |
| `CSV_FILE` | Your list of LinkedIn URLs. Leave **empty** to read the list from the Google Sheet. |
| `MAX` | Stop after this many phone numbers (your daily cap is 170). |
| `PER_MINUTE` | Profiles per minute. 3 ≈ one every 20 s. Lower = safer. |

Save the file.

**Which combination do I want?**

| You want… | SHEET_URL + TOKEN | CSV_FILE |
|---|---|---|
| Read from Sheet, write results back into the Sheet | filled | *empty* |
| Read from a CSV, write results into the Sheet too | filled | `leads.csv` |
| CSV only, no Google | *empty* | `leads.csv` |

A local copy, `easyleadz-contacts.csv`, is **always** written in this folder
as well.

### Your CSV file
- Any column containing `linkedin.com/in/...` URLs works; other columns are
  kept and copied to the output.
- From Google Sheets: **File → Download → Comma-separated values (.csv)**,
  save it in this folder as `leads.csv` (or set `CSV_FILE` to its name).

---

## Part 3 — Running it (every day)

1. Double-click **`start-chrome.bat`** (if that Chrome window isn't open already).
2. In that window, open the **Mr. E side panel** (click the extension icon)
   and leave it open.
3. Double-click **`run.bat`**. A black window shows progress:

```
10:02:11 AM 120 profiles in list, 0 already done, 120 to go. Max this run: 170, ~3.0/min.
10:02:11 AM [1/120] https://www.linkedin.com/in/asha-rao/
10:02:16 AM    found  +919876543210  asha@acme.com  (credits left: 169)  → sheet
10:02:33 AM [2/120] https://www.linkedin.com/in/ravi-k/
10:02:58 AM    no_data      (credits left: 169)  → sheet
```

4. Leave the Chrome window alone while it runs (you can use other apps).
5. To stop: click the black window and press **Ctrl+C**.

**Run it again any time** — it continues where it left off. Profiles already
done (in `easyleadz-contacts.csv` or with a status in the Sheet) are skipped
and don't cost credits.

### First time? Test small
Set `MAX=3` in `run.bat`, run it, and watch the Chrome window. If all 3 look
right, set `MAX` back to 170.

---

## Results

Columns added to your Sheet / CSV:

| Column | Meaning |
|---|---|
| `phone` | Mobile number, e.g. `+919876543210` |
| `email` | Email if EasyLeadz shows one |
| `status` | `found` · `email_only` · `no_data` · `profile_not_found` |
| `revealed_at` | When it was captured |
| `source` | Where it came from (for your records / DPDP compliance) |

---

## When it stops by itself

| Message | What to do |
|---|---|
| `STOPPED: LinkedIn push-back — …` | LinkedIn showed a security check / CAPTCHA / warning. Resolve it by hand in the Chrome window. **Rest the account (a day is safest)**, then run again with lower `MAX` / `PER_MINUTE`. |
| `Reached --max …` | Hit your `MAX`. Done for today. |
| `EasyLeadz shows 0 credits` | Out of credits. |
| `Can't reach Chrome on port 9222` | Start Chrome with `start-chrome.bat` (close other Chrome windows first). |
| `EasyLeadz side panel not found` | Open the Mr. E side panel in that Chrome window. |
| `Lost the EasyLeadz side panel` | The panel was closed — reopen it and run again. |
| `sheet: bad token` | `TOKEN` in `run.bat` doesn't match the one in Apps Script. |
| `sheet web app didn't return JSON` | Re-check the deployment: Execute as **Me**, access **Anyone**, and that the URL ends in `/exec`. |
| `! sheet write failed … queued` | Internet hiccup. Results are safe in the CSV and will be sent to the Sheet on the next run. |

---

## Troubleshooting

- **Number never gets captured / every profile is `no_data`:** send the
  black-window output and a screenshot of the Mr. E panel after clicking
  View contact — the wording may differ from what the script expects.
- **"node is not recognized":** Node.js isn't installed, or restart the PC
  after installing it.
- **Chrome opens but isn't logged in:** make sure you're using the window from
  `start-chrome.bat`, not your normal Chrome.
- **Security note:** while that special Chrome window is open, other programs
  on your PC could control it. Close it when you're done, and don't use that
  profile for banking/email.

---

## Mac
Same steps, but use `start-chrome-mac.command` and `run-mac.command`
(edit settings with TextEdit). First time, right-click → **Open** to allow them.
