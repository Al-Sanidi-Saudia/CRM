"""Builds the three Daily & Monthly Insights diagrams (HTML) and renders them to PNG with Playwright.

  python3 diagrams/build_diagrams.py        # writes diagrams/*.html and diagrams/*.png

1. insights-erd.png        the 26 insight tables and the 13 synced tables they belong to (identifier columns only,
                           plus the period columns added on request: Day, Month, Year, Weekday)
2. scheduler-mechanism.png who starts a sync, how a request is dispatched and the steps of <Platform> - Run Sync
3. scheduler-timetable.png every flow, main and sub, and when / with which period it runs
"""
import html
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import spec  # noqa: E402

PLATFORMS = [  # name, colour, text colour on the colour, parent keys in hierarchy order
    ("Meta", "#1877F2", "#fff", ["metacampaign", "metaadset", "metaadvertisement"]),
    ("Snapchat", "#FFE600", "#111", ["snapcampaign", "snapadsquad", "snapadvertisement"]),
    ("Google Ads", "#34A853", "#fff", ["googleadscampaign", "googleadsadgroup", "googleadsadvertisement",
                                       "googleadsassetgroup"]),
    ("TikTok", "#111111", "#fff", ["tiktokcampaign", "tiktokadgroup", "tiktokadvertisement"]),
]
# Lookups between the synced tables (live metadata, 2026-11-01).
PARENT_LOOKUPS = {
    "metaadset": [("sanidi_metacampaignid", "metacampaign")],
    "metaadvertisement": [("sanidi_metacampaignid", "metacampaign"), ("sanidi_metaadsetid", "metaadset")],
    "snapadsquad": [("sanidi_snapcampaign", "snapcampaign")],
    "snapadvertisement": [("sanidi_snapadsquad", "snapadsquad")],
    "googleadsadgroup": [("sanidi_googleadscampaign", "googleadscampaign")],
    "googleadsadvertisement": [("sanidi_googleadsadgroup", "googleadsadgroup")],
    "googleadsassetgroup": [("sanidi_googleadscampaign", "googleadscampaign")],
    "tiktokadgroup": [("sanidi_tiktokcampaign", "tiktokcampaign")],
    "tiktokadvertisement": [("sanidi_tiktokadgroup", "tiktokadgroup")],
}
def short(display):
    """'Google Ads Ad Group' -> 'Ad Group': each band already names its platform."""
    for prefix in ("Google Ads ", "Meta ", "Snap ", "TikTok "):
        if display.startswith(prefix):
            return display[len(prefix):]
    return display


FONT = "font-family:'Segoe UI',Arial,sans-serif"
e = html.escape


# ---- 1. ERD (SVG) --------------------------------------------------------------------------------------------------

BOX_W, COL_W, ROW_H = 370, 410, 22


def box(x, y, title, sub, rows, head, head_text, border):
    """rows: (marker, column, note, highlight). Returns (svg, height)."""
    h = 46 + ROW_H * len(rows) + 8
    out = [f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{h}" rx="6" fill="#fff" stroke="{border}" stroke-width="1.5"/>',
           f'<path d="M{x} {y + 6} a6 6 0 0 1 6 -6 h{BOX_W - 12} a6 6 0 0 1 6 6 v40 h-{BOX_W} z" fill="{head}"/>',
           f'<text x="{x + 10}" y="{y + 19}" font-size="14" font-weight="700" fill="{head_text}">{e(title)}</text>',
           f'<text x="{x + 10}" y="{y + 37}" font-size="11.5" fill="{head_text}" opacity=".85">{e(sub)}</text>']
    ry = y + 46 + 4
    for marker, col, note, hi in rows:
        if hi:
            out.append(f'<rect x="{x + 3}" y="{ry}" width="{BOX_W - 6}" height="{ROW_H - 2}" rx="3" fill="#FFF1C2"/>')
        colour = {"PK": "#B42318", "FK": "#175CD3", "AK": "#6941C6"}.get(marker, "#475467")
        out.append(f'<text x="{x + 10}" y="{ry + 15}" font-size="10.5" font-weight="700" fill="{colour}">{marker}</text>')
        out.append(f'<text x="{x + 38}" y="{ry + 15}" font-size="12" fill="#101828">{e(col)}</text>')
        if note:
            out.append(f'<text x="{x + BOX_W - 10}" y="{ry + 15}" font-size="10.5" fill="#667085" '
                       f'text-anchor="end">{e(note)}</text>')
        ry += ROW_H
    return "\n".join(out), h


def erd():
    tables = spec.tables()
    by_key = {(t["key"], t["period"]): (logical, t) for logical, t in tables.items()}
    svg, y0 = [], 120
    width = 40 + 7 * COL_W + 30 + 40
    layout = [[PLATFORMS[0], PLATFORMS[1]], [PLATFORMS[2], PLATFORMS[3]]]
    band_h = 700
    lines, boxes = [], []
    for r, row in enumerate(layout):
        x = 40
        for name, colour, text_colour, keys in row:
            bw = len(keys) * COL_W
            by = y0 + r * (band_h + 30)
            boxes.append(f'<rect x="{x - 15}" y="{by}" width="{bw}" height="{band_h}" rx="12" fill="{colour}" '
                         f'fill-opacity=".07" stroke="{colour}" stroke-opacity=".5"/>')
            boxes.append(f'<text x="{x}" y="{by + 30}" font-size="20" font-weight="700" fill="#101828">{e(name)}</text>')
            py = by + 50
            parent_rows = {}
            for k in keys:
                p = spec.PARENTS[k]
                rows = [("PK", f"sanidi_{k}id", "", False), ("", p["id"], "platform ID", False)]
                rows += [("FK", col, f"→ {short(spec.PARENTS[ref]['display'])}", False)
                         for col, ref in PARENT_LOOKUPS.get(k, [])]
                parent_rows[k] = rows
            row_h = max(46 + ROW_H * len(v) + 8 for v in parent_rows.values())
            centres = {}
            for i, k in enumerate(keys):
                p = spec.PARENTS[k]
                bx = x + i * COL_W
                s, ph = box(bx, py, p["display"], f"sanidi_{k}  (synced table)", parent_rows[k], "#344054", "#fff",
                            "#344054")
                boxes.append(s)
                centres[k] = (bx, py, ph)
                dy = py + row_h + 60
                for period in ("daily", "monthly"):
                    logical, t = by_key[(k, period)]
                    rows = [("PK", f"{logical}id", "", False),
                            ("FK", t["lookup"], f"→ {short(p['display'])}", False),
                            ("AK", "sanidi_insightkey", "<platform ID>_<period>", False),
                            ("", "sanidi_date", "date only", False)]
                    if period == "daily":
                        rows += [("", "sanidi_day", "whole number 1-31", True),
                                 ("", "sanidi_month", "choice Month", True),
                                 ("", "sanidi_year", "whole number", True),
                                 ("", "sanidi_weekday", "choice Weekday", True)]
                    else:
                        rows += [("", "sanidi_month", "choice Month", True), ("", "sanidi_year", "whole number", True)]
                    s, h = box(bx, dy, t["display"], logical, rows, colour, text_colour, colour)
                    boxes.append(s)
                    # N : 1 to the synced table: daily straight down, monthly down the left margin
                    if period == "daily":
                        lx = bx + 16
                        lines.append(f'<path d="M{lx} {py + ph} V{dy}" stroke="#667085" stroke-width="1.5" fill="none"/>')
                        lines.append(f'<path d="M{lx - 6} {dy} L{lx} {dy - 9} L{lx + 6} {dy}" stroke="#667085" '
                                     f'stroke-width="1.5" fill="none"/>')
                    else:
                        lx, my = bx + 32, dy + 23
                        lines.append(f'<path d="M{lx} {py + ph} V{py + ph + 12} H{bx - 10} V{my} H{bx}" '
                                     f'stroke="#667085" stroke-width="1.5" fill="none"/>')
                        lines.append(f'<path d="M{bx} {my - 6} L{bx - 9} {my} L{bx} {my + 6}" stroke="#667085" '
                                     f'stroke-width="1.5" fill="none"/>')
                    dy += h + 18
            # relationships between the synced tables (1 : N, parent on the left)
            skip = 0
            for child, refs in PARENT_LOOKUPS.items():
                if child not in centres:
                    continue
                for _, ref in refs:
                    px, pyy, ph = centres[ref]
                    cx, cy, ch = centres[child]
                    if keys.index(child) - keys.index(ref) == 1:
                        yy = pyy + 30
                        lines.append(f'<path d="M{px + BOX_W} {yy} H{cx}" stroke="#344054" stroke-width="1.5"/>')
                        lines.append(f'<path d="M{cx - 9} {yy - 6} L{cx} {yy} L{cx - 9} {yy + 6}" stroke="#344054" '
                                     f'stroke-width="1.5" fill="none"/>')
                    else:  # skips a column: route below the synced tables
                        ry = pyy + row_h + 28 + 12 * skip
                        skip += 1
                        lines.append(f'<path d="M{px + BOX_W - 30} {pyy + ph} V{ry} H{cx + BOX_W - 30} V{cy + ch}" '
                                     f'stroke="#344054" stroke-width="1.5" fill="none" stroke-dasharray="5 3"/>')
                        tx, ty = cx + BOX_W - 30, cy + ch
                        lines.append(f'<path d="M{tx - 6} {ty + 9} L{tx} {ty} L{tx + 6} {ty + 9}" stroke="#344054" '
                                     f'stroke-width="1.5" fill="none"/>')
            x += bw + 30
    svg = boxes[:0]
    bands = [b for b in boxes if 'fill-opacity=".07"' in b]
    svg = bands + lines + [b for b in boxes if b not in bands]
    total_h = y0 + 2 * band_h + 30 + 40
    legend_x = 40
    legend = [
        f'<text x="40" y="44" font-size="28" font-weight="700" fill="#101828">Social Media Daily &amp; Monthly '
        f'Insights: tables</text>',
        f'<text x="40" y="74" font-size="14" fill="#475467">26 new insight tables (one Daily and one Monthly per '
        f'synced table), each linked N : 1 to one of the 13 synced tables. Only identifier columns are shown; every '
        f'insight table also has the parent\'s metrics, Period Closed, No Data, Last Synced On and Raw Payload.</text>',
        f'<g transform="translate({legend_x},88)" font-size="12" fill="#344054">'
        f'<text x="0" y="14" font-weight="700" fill="#B42318">PK</text><text x="22" y="14">primary key</text>'
        f'<text x="110" y="14" font-weight="700" fill="#175CD3">FK</text><text x="132" y="14">lookup (N : 1)</text>'
        f'<text x="240" y="14" font-weight="700" fill="#6941C6">AK</text><text x="262" y="14">alternate key '
        f'(one row per item and period)</text>'
        f'<rect x="520" y="2" width="16" height="16" rx="3" fill="#FFF1C2"/><text x="542" y="14">period columns '
        f'added on request (set on every row; Month 1 = January, Weekday 1 = Sunday)</text>'
        f'<rect x="1090" y="2" width="16" height="16" rx="3" fill="#344054"/><text x="1112" y="14">synced table '
        f'(existing)</text><path d="M1270 10 h40" stroke="#344054" stroke-width="1.5"/>'
        f'<path d="M1301 4 L1310 10 L1301 16" stroke="#344054" stroke-width="1.5" fill="none"/>'
        f'<text x="1318" y="14">1 : N (arrow at the N side; dashed = skips a level)</text></g>',
    ]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" '
            f'viewBox="0 0 {width} {total_h}" style="{FONT}">'
            f'<rect width="100%" height="100%" fill="#F9FAFB"/>' + "\n".join(legend + svg) + "</svg>")


# ---- 2. Scheduler mechanism (HTML) ---------------------------------------------------------------------------------

CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #F9FAFB; {FONT}; color: #101828; }}
.page {{ padding: 36px 40px 40px; width: max-content; }}
h1 {{ font-size: 28px; margin: 0 0 6px; }}
.lead {{ font-size: 14px; color: #475467; margin: 0 0 24px; max-width: 1500px; }}
.flow {{ border-radius: 10px; padding: 12px 14px; background: #fff; border: 1.5px solid #D0D5DD; }}
.flow > b {{ display: block; font-size: 15px; }}
.flow small {{ display: block; font-size: 12px; color: #475467; margin-top: 3px; line-height: 1.45; }}
.main {{ border-color: #6941C6; background: #F4F3FF; }}
.disp {{ border-color: #175CD3; background: #EFF8FF; }}
.run {{ border-color: #344054; background: #F2F4F7; }}
.tag {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 10px;
        margin-right: 4px; color: #fff; }}
.arrow {{ text-align: center; font-size: 22px; color: #667085; line-height: 1; padding: 6px 0; }}
.note {{ font-size: 12px; color: #475467; }}
table {{ border-collapse: collapse; background: #fff; font-size: 13px; }}
th, td {{ border: 1px solid #D0D5DD; padding: 7px 10px; text-align: left; vertical-align: top; }}
th {{ background: #F2F4F7; font-weight: 700; }}
"""


def platform_tags():
    return "".join(f'<span class="tag" style="background:{c};color:{t}">{n}</span>' for n, c, t, _ in PLATFORMS)


def mechanism():
    steps = [
        ("1. Data", "05:00 run, and All Time with <i>Data and Insights</i>",
         "Get &lt;Platform&gt; Campaigns, then the cascade (Dataverse triggers on the parent ID column): "
         "ad sets / ad squads / ad groups / asset groups → ads.<br>Waits until no child data flow is running "
         "(checked every 2 min, two quiet checks in a row, at most 30 min)."),
        ("2. Lifetime", "every run", "Get &lt;Platform&gt; Insights: lifetime metrics on the synced tables."),
        ("3. Daily", "every run", "Get &lt;Platform&gt; Daily Insights (start date, end date, closed through): one row "
         "per item and day with delivery."),
        ("4. Monthly", "every run", "Get &lt;Platform&gt; Monthly Insights (first month, last month): one row per item and "
         "month from the source; months without data get an empty row (No Data = Yes)."),
        ("5. Result", "every run", "Steps Log and status on the Integration Sync Request (Succeeded / Failed / "
         "Skipped). A failed step is logged and the next step still runs."),
    ]
    step_html = "".join(
        f'<div class="flow" style="margin-bottom:8px"><b>{s}</b><small><i>{w}</i></small><small>{d}</small></div>'
        for s, w, d in steps)
    cover = """
<table>
<tr><th>Sync type</th><th>Data</th><th>Lifetime</th><th>Daily</th><th>Monthly</th><th>Period Closed</th></tr>
<tr><td><b>Scheduled Daily</b> (05:00)</td><td>Yes</td><td>Yes</td><td>D-2 … today</td><td>months of D-2 … today</td><td>day D-2</td></tr>
<tr><td>+ <b>Weekly</b> (Friday 05:00)</td><td></td><td></td><td>+ last 28 days<br>(Google Ads 90)</td><td>+ current and previous month<br>(Google Ads: months of the 90 days)</td><td>+ previous month on the<br>last Friday of the month</td></tr>
<tr><td><b>Scheduled Intraday</b> (08:00, 12:00, 16:00)</td><td>No</td><td>Yes</td><td>today</td><td>current month</td><td>nothing</td></tr>
<tr><td><b>Day &amp; Month to Date</b> (button)</td><td>No</td><td>Yes</td><td>D-2 … today</td><td>months of D-2 … today</td><td>same rules</td></tr>
<tr><td><b>All Time</b> (button, pop-up)</td><td>Insights Only: No<br>Data and Insights: Yes</td><td>Yes</td><td>Full Load From (or first campaign) … today</td><td>its month … current month</td><td>same rules</td></tr>
</table>"""
    closed = """
<table>
<tr><th>Period Closed rules (scheduler and buttons)</th></tr>
<tr><td>Day: closed when it is the day before yesterday (D-2) or older.</td></tr>
<tr><td>Month: closed when older than the previous month; the previous month closes on the current month's last Friday.</td></tr>
<tr><td>Today and the current month are never closed.</td></tr>
</table>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="page">
<h1>Social Media Daily &amp; Monthly Insights: sync mechanism</h1>
<p class="lead">Every sync, scheduled or from a button, is an <b>Integration Sync Request</b> row. The dispatcher runs
it through one <b>&lt;Platform&gt; - Run Sync</b> flow, which runs the steps one after the other. The 4 platforms run in
parallel; one platform never runs two syncs at once. All times are Riyadh time.</p>
<div style="display:flex; gap:28px; align-items:flex-start">
 <div style="width:520px">
  <div style="display:flex; gap:12px">
   <div class="flow main" style="flex:1"><b>Social Media - Scheduled Sync</b>
    <small>Recurrence: every day 05:00, 08:00, 12:00, 16:00</small>
    <small>One request per platform with <i>Set Up</i> = Yes and <i>Connection Active</i> not No.<br>
    05:00 → <b>Scheduled Daily</b> (with data; <i>Weekly Run</i> on Fridays)<br>08 / 12 / 16 → <b>Scheduled Intraday</b><br>
    Triggered By = Schedule (no notification)</small></div>
   <div class="flow main" style="flex:1"><b>Sync Control page</b>
    <small>Buttons per platform:<br>• <b>Data</b> (existing data sync)<br>• <b>Day &amp; Month to Date</b><br>
    • <b>All Time</b>: pop-up <i>Insights Only</i> / <i>Data and Insights</i>, from the platform's <i>Full Load From</i><br>
    Triggered By = Button (notification to the presser)</small></div>
  </div>
  <div class="arrow">▼ creates</div>
  <div class="flow" style="border-style:dashed"><b>Integration Sync Request</b>
   <small>Platform, Sync Type, Status = Requested, Triggered By, Include Data, Weekly Run, Steps Log</small></div>
  <div class="arrow">▼ on create</div>
  <div class="flow disp"><b>Sync Control - Run Sync Request</b> <small>(dispatcher)</small>
   <small>If the same platform already has a sync <i>Running</i>: a scheduled request waits up to 60 min, then is
   marked <b>Skipped</b> (the next run covers the same periods). Buttons are disabled while a sync runs.<br>
   Then sets Running and calls the platform's Run Sync flow.</small></div>
  <div class="arrow">▼ one per platform, in parallel</div>
  <div class="flow run"><b>Meta - Run Sync · Snap - Run Sync · Google Ads - Run Sync · TikTok - Run Sync</b>
   <small>{platform_tags()}</small></div>
 </div>
 <div style="width:560px">
  <div style="font-size:16px; font-weight:700; margin:2px 0 10px">Inside &lt;Platform&gt; - Run Sync (in order)</div>
  {step_html}
 </div>
 <div style="width:700px">
  <div style="font-size:16px; font-weight:700; margin:2px 0 10px">What each run covers</div>
  {cover}
  <div style="height:16px"></div>
  {closed}
  <p class="note" style="margin-top:14px">D-2 = the day before yesterday. Platforms can still revise older numbers
  (Meta up to 28 days, Google Ads conversions up to 90 days); the Friday reloads pick them up.
  Days without delivery get no daily row.</p>
 </div>
</div></div></body></html>"""


# ---- 3. Timetable (HTML) -------------------------------------------------------------------------------------------

def timetable():
    names = {
        "data": ["Get Meta Campaigns", "Get Snap Campaigns", "Get Google Ads Campaigns", "Get TikTok Campaigns"],
        "child1": ["Get Meta AdSets", "Get Snap Ad Squads", "Get Google Ads Ad Groups · Get Google Ads Asset Groups",
                   "Get TikTok Ad Groups"],
        "child2": ["Get Meta Advertisements", "Get Snap Advertisements", "Get Google Ads Advertisements",
                   "Get TikTok Advertisements"],
        "life": ["Get Meta Insights", "Get Snap Insights", "Get Google Ads Insights", "Get TikTok Insights"],
        "daily": ["Get Meta Daily Insights", "Get Snap Daily Insights", "Get Google Ads Daily Insights",
                  "Get TikTok Daily Insights"],
        "monthly": ["Get Meta Monthly Insights", "Get Snap Monthly Insights", "Get Google Ads Monthly Insights",
                    "Get TikTok Monthly Insights"],
        "run": ["Meta - Run Sync", "Snap - Run Sync", "Google Ads - Run Sync", "TikTok - Run Sync"],
    }
    cols = ["05:00<br><small>Sat – Thu</small>", "05:00<br><small>Friday</small>",
            "05:00<br><small>last Friday of the month</small>", "08:00 · 12:00 · 16:00<br><small>every day</small>",
            "Button<br><small>Data</small>", "Button<br><small>Day &amp; Month to Date</small>",
            "Button<br><small>All Time</small>"]
    Y = '<span class="y">●</span>'
    N = '<span class="n">–</span>'
    rows = [
        ("Main", "Social Media - Scheduled Sync", "Recurrence; creates one sync request per platform",
         [Y + " Scheduled Daily", Y + " Scheduled Daily + Weekly Run", Y + " Scheduled Daily + Weekly Run",
          Y + " Scheduled Intraday", N, N, N]),
        ("Main", "Sync Control - Run Sync Request", "Dispatcher: runs when a sync request is created",
         [Y] * 7),
        ("Platform", " · ".join(names["run"]), "Run the steps below in order, one platform per flow",
         [Y] * 4 + [N + "<br><small>the dispatcher calls Step 1 directly</small>", Y, Y]),
        ("Step 1: Data", " · ".join(names["data"]), "Campaigns; starts the cascade below",
         [Y, Y, Y, N, Y, N, Y + " with <i>Data and Insights</i>"]),
        ("cascade", " · ".join(names["child1"]), "Run on their own when their parent rows change",
         [Y, Y, Y, N, Y, N, Y + " with <i>Data and Insights</i>"]),
        ("cascade", " · ".join(names["child2"]), "Run on their own when their parent rows change",
         [Y, Y, Y, N, Y, N, Y + " with <i>Data and Insights</i>"]),
        ("Step 2: Lifetime", " · ".join(names["life"]), "Lifetime metrics on the 13 synced tables",
         [Y] * 4 + [N, Y, Y]),
        ("Step 3: Daily", " · ".join(names["daily"]), "Daily insight tables",
         [Y + " D-2 … today<br><small>closes D-2</small>",
          Y + " last 28 days<br><small>Google Ads 90; closes D-2</small>",
          Y + " last 28 days<br><small>Google Ads 90; closes D-2</small>",
          Y + " today", N, Y + " D-2 … today", Y + " Full Load From … today"]),
        ("Step 4: Monthly", " · ".join(names["monthly"]), "Monthly insight tables (empty months included)",
         [Y + " months of D-2 … today", Y + " current + previous month<br><small>Google Ads: months of the 90 days</small>",
          Y + " current + previous month<br><small>closes the previous month</small>",
          Y + " current month", N, Y + " months of D-2 … today", Y + " every month from the start"]),
    ]
    group_colour = {"Main": "#F4F3FF", "Platform": "#F2F4F7", "cascade": "#FCFCFD"}
    body = []
    for group, flows, what, cells in rows:
        bg = group_colour.get(group, "#fff")
        label = "↳ cascade" if group == "cascade" else group
        flows = "<br>".join(flows.split(" · ")) if group not in ("Main",) else flows
        body.append(f'<tr style="background:{bg}"><td class="g">{label}</td><td><b>{flows}</b><br>'
                    f'<small>{what}</small></td>' + "".join(f"<td class=c>{c}</td>" for c in cells) + "</tr>")
    head = "".join(f"<th class=c>{c}</th>" for c in cols)
    css = CSS + """
td.g { font-weight: 700; white-space: nowrap; color: #344054; }
td.c, th.c { text-align: center; min-width: 150px; }
.y { color: #12B76A; font-size: 15px; } .n { color: #98A2B3; }
small { color: #475467; }
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="page">
<h1>Social Media Daily &amp; Monthly Insights: timetable</h1>
<p class="lead">Which flows run when (Riyadh time), and which period each insight step covers. Every column runs
for all 4 platforms in parallel: {platform_tags()}. A sync that would overlap the same platform's running sync waits
up to 60 minutes, then is Skipped. The Data button (data only) works as before: the dispatcher runs the campaigns flow directly.</p>
<table><tr><th>Level</th><th>Flows (Meta · Snap · Google Ads · TikTok)</th>{head}</tr>{''.join(body)}</table>
<p class="note" style="margin-top:12px">D-2 = the day before yesterday. Typical duration of a run in UAT: 05:00
12 – 60 min, intraday 5 – 35 min per platform; an All Time full load takes hours (Snap / TikTok ≈ 19 h).</p>
</div></body></html>"""


def render(name, content):
    page = HERE / f"{name}.html"
    page.write_text(content if content.startswith("<!doctype") else
                    f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">{content}</body></html>',
                    encoding="utf-8")
    return page


def main():
    pages = [render("insights-erd", erd()), render("scheduler-mechanism", mechanism()),
             render("scheduler-timetable", timetable())]
    script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 800, height: 600 } });
  for (const file of process.argv.slice(1)) {
    await page.goto('file://' + file);
    const el = await page.$('svg') || await page.$('.page');
    await el.screenshot({ path: file.replace(/\\.html$/, '.png') });
  }
  await browser.close();
})();
"""
    subprocess.run(["node", "-e", script, *[str(p.resolve()) for p in pages]], check=True)
    for p in pages:
        print(p.with_suffix(".png"))


if __name__ == "__main__":
    main()
