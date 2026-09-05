"""
CBSE Schools Directory scraper - State = TAMILNADU.

Selects the state, submits the search, then walks every DataTables page by
clicking "Next", flushing each page's rows to CSV *before* moving on.

Usage:
    pip install playwright && playwright install chromium
    python scripts/cbse_tn_scraper.py                 # headless
    python scripts/cbse_tn_scraper.py --headed        # watch it work
    python scripts/cbse_tn_scraper.py --page-size 100 # fewer clicks
"""

import argparse
import csv
import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://saras.cbse.gov.in/saras/AffiliatedList/ListOfSchdirReport"
STATE_VALUE = "19"  # TAMILNADU

COLUMNS = [
    "s_no", "aff_no", "school_code", "state", "district", "status",
    "school_name", "head_name", "address", "website", "details_url",
]


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def after_label(text, label):
    """Pull the value that follows a bold label like 'Aff. No. :' in a cell."""
    m = re.search(re.escape(label) + r"\s*:?\s*(.*)", text, re.I)
    return clean(m.group(1)) if m else ""


def parse_row(row):
    """Row -> dict. Cells are label/value blobs, so split on <br> boundaries."""
    cells = row.query_selector_all("td")
    if len(cells) < 7:
        return None

    # Insert newlines at <br> so the two values in a cell stay separable.
    def cell_text(i):
        return clean(
            cells[i].inner_html()
            .replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        )

    def cell_lines(i):
        html = cells[i].inner_html()
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
        html = re.sub(r"<[^>]+>", "", html)
        return [clean(p) for p in html.split("\n") if clean(p)]

    aff_lines = cell_lines(1)
    loc_lines = cell_lines(2)
    name_lines = cell_lines(4)
    addr_lines = cell_lines(5)

    link = cells[6].query_selector("a")
    href = link.get_attribute("href") if link else ""
    if href and href.startswith("/"):
        href = "https://saras.cbse.gov.in" + href

    return {
        "s_no": clean(cells[0].inner_text()),
        "aff_no": after_label(" ".join(aff_lines), "Aff. No."),
        "school_code": after_label(" ".join(aff_lines), "Sch. Code"),
        "state": after_label(loc_lines[0] if loc_lines else "", "State"),
        "district": after_label(loc_lines[1] if len(loc_lines) > 1 else "", "District"),
        "status": clean(cells[3].inner_text()),
        "school_name": after_label(name_lines[0] if name_lines else "", "Name"),
        "head_name": after_label(
            name_lines[1] if len(name_lines) > 1 else "", "Head/Principal Name"
        ),
        "address": after_label(addr_lines[0] if addr_lines else "", "Address"),
        "website": after_label(
            addr_lines[1] if len(addr_lines) > 1 else "", "Website"
        ),
        "details_url": href,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cbse_tamilnadu_schools.csv")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--page-size", type=int, default=100, choices=[10, 25, 50, 100])
    ap.add_argument("--timeout", type=int, default=60000)
    args = ap.parse_args()

    seen = set()
    total = 0
    fresh = not os.path.exists(args.out)

    with sync_playwright() as p, open(args.out, "a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        if fresh:
            writer.writeheader()
            fh.flush()

        launch_kw = {"headless": not args.headed}
        try:
            browser = p.chromium.launch(**launch_kw)
        except Exception:
            # Pinned playwright version doesn't match the installed browser build;
            # fall back to whatever chromium is on the box.
            exe = os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium")
            browser = p.chromium.launch(executable_path=exe, **launch_kw)
        page = browser.new_page()
        page.set_default_timeout(args.timeout)

        page.goto(URL, wait_until="domcontentloaded")
        page.check("#SearchMainRadioState_wise")
        page.select_option("#State", STATE_VALUE)
        page.click("input[type=submit][value=Search]")
        page.wait_for_selector("#myTable tbody tr")

        # Bigger pages = fewer Next clicks, same data.
        if page.query_selector("select[name=myTable_length]"):
            page.select_option("select[name=myTable_length]", str(args.page_size))
            page.wait_for_timeout(500)

        page_no = 1
        while True:
            page.wait_for_selector("#myTable tbody tr")
            rows = page.query_selector_all("#myTable tbody tr")

            batch = []
            for row in rows:
                rec = parse_row(row)
                if not rec or not rec["aff_no"]:
                    continue
                if rec["aff_no"] in seen:
                    continue
                seen.add(rec["aff_no"])
                batch.append(rec)

            # Write this page BEFORE clicking Next, and flush to disk.
            writer.writerows(batch)
            fh.flush()
            os.fsync(fh.fileno())
            total += len(batch)
            info = page.query_selector("#myTable_info")
            print(
                f"page {page_no}: +{len(batch)} rows (total {total}) "
                f"| {clean(info.inner_text()) if info else ''}",
                flush=True,
            )

            nxt = page.query_selector("#myTable_next")
            if not nxt:
                break
            cls = nxt.get_attribute("class") or ""
            if "disabled" in cls:
                print("Next is disabled - reached the last page.")
                break

            first_before = rows[0].inner_text() if rows else ""
            nxt.click()
            # Wait until the table body actually changes.
            try:
                page.wait_for_function(
                    """(prev) => {
                        const r = document.querySelector('#myTable tbody tr');
                        return r && r.innerText !== prev;
                    }""",
                    arg=first_before,
                    timeout=args.timeout,
                )
            except Exception:
                page.wait_for_timeout(1500)
            page_no += 1

        browser.close()

    print(f"Done. {total} schools written to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
