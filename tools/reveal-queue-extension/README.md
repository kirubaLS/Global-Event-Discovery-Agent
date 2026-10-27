# Reveal Queue — EasyLeadz helper extension

Walks a list of LinkedIn profile URLs. On each profile you click **Reveal** in
the EasyLeadz extension; this extension picks up the phone/email it shows,
saves it, waits a few random seconds and opens the next profile.

## Install (once)
1. Download this folder.
2. Chrome → `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → pick this folder.
3. Pin it; clicking its icon opens the queue page.

## Daily use
1. Queue page → upload CSV or paste rows from Google Sheets → **Add to queue**.
2. **Start**. A LinkedIn tab opens with a control bar bottom-left.
3. Click Reveal in EasyLeadz. When a mobile number appears the bar saves it
   after 3 s and moves on. Use **No data** / **Skip** when there's nothing.
4. It stops itself at the daily credit cap (default 170).
5. **Download CSV** from the queue page.

If the bar never picks up the number automatically (EasyLeadz renders in a
frame it can't read), copy the panel text and use **Read clipboard** or paste
into the bar — everything else stays automatic.

Data lives in Chrome's extension storage on this machine only; export regularly.
