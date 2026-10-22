"""Converts source/AlSanidi-Seasons.xlsx into season_calendar_2026.csv (the rows deploy.py loads).

  python3 build_data.py

The workbook's dates say 2021 but its content is the 2026 calendar (Ramadan 18 Feb - 19 Mar), so each day and
month is kept and the year is set to spec.YEAR. A "*" in a season column means Yes, an empty cell No.
"""
import csv
import datetime
from pathlib import Path

import openpyxl

import spec

HERE = Path(__file__).parent
SOURCE = HERE / "source" / "AlSanidi-Seasons.xlsx"
OUT = HERE / f"season_calendar_{spec.YEAR}.csv"


def main():
    ws = openpyxl.load_workbook(SOURCE, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    headers = list(next(rows))
    expected = [f[3] for f in spec.FLAGS]
    if headers[1:] != expected:
        raise SystemExit(f"workbook headers differ from spec.FLAGS:\n{headers[1:]}\n{expected}")
    days = {}
    for r in rows:
        if r[0] is None:
            continue
        day = r[0].date().replace(year=spec.YEAR)
        if day in days:
            raise SystemExit(f"{day} appears twice")
        for v in r[1:]:
            if v not in (None, "*"):
                raise SystemExit(f"{day}: unexpected value {v!r}")
        days[day] = [v == "*" for v in r[1:]]
    first = datetime.date(spec.YEAR, 1, 1)
    missing = [first + datetime.timedelta(i) for i in range(365) if first + datetime.timedelta(i) not in days]
    if missing:
        raise SystemExit(f"missing days: {missing[:10]}")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "year"] + [c for c, *_ in spec.FLAGS])
        for day in sorted(days):
            w.writerow([day.isoformat(), spec.YEAR] + ["Yes" if b else "No" for b in days[day]])
    print(f"{OUT.name}: {len(days)} days")


if __name__ == "__main__":
    main()
