"""One-time month closing, the same rule as Social Media - Close Monthly Insights (PLAN.md §5.4), for an environment
whose monthly rows were all written open by a full load (e.g. Production after its first full load).

  python3 close_months_once.py 2026-11-01            # dry run: rows that would be closed, per table
  python3 close_months_once.py 2026-11-01 --apply    # set Period Closed = Yes on them ($batch, 500 per request)

The date is the "run day" (a 1st of the month): a month closes when its first day is before the first day of the
month of (run day + 1 - late-update days).
"""
import json
import sys
import time
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import spec  # noqa: E402
from dv import Dataverse  # noqa: E402
from deploy_flows import LATE_DAYS, LEVELS  # noqa: E402

BATCH = 500


def cutoff(run_day, days):
    d = run_day + timedelta(days=1 - days)
    return date(d.year, d.month, 1)


def batch_close(dv, table_set, pk_ids):
    boundary, changeset = f"batch_{uuid.uuid4()}", f"changeset_{uuid.uuid4()}"
    parts = []
    for n, rid in enumerate(pk_ids, 1):
        parts.append(f"--{changeset}\r\nContent-Type: application/http\r\nContent-Transfer-Encoding: binary\r\n"
                     f"Content-ID: {n}\r\n\r\nPATCH {dv.url}/api/data/v9.2/{table_set}({rid}) HTTP/1.1\r\n"
                     f"Content-Type: application/json\r\n\r\n{json.dumps({'sanidi_periodclosed': True})}\r\n")
    body = (f"--{boundary}\r\nContent-Type: multipart/mixed; boundary={changeset}\r\n\r\n" + "".join(parts) +
            f"--{changeset}--\r\n--{boundary}--\r\n")
    if time.time() > dv.token_expires:
        dv._sign_in()
    req = urllib.request.Request(f"{dv.url}/api/data/v9.2/$batch", data=body.encode(), method="POST", headers={
        "Authorization": "Bearer " + dv.token, "OData-Version": "4.0", "OData-MaxVersion": "4.0",
        "Content-Type": f"multipart/mixed; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        text = r.read().decode()
    if "HTTP/1.1 4" in text or "HTTP/1.1 5" in text:  # a failed change rolls the changeset back
        raise SystemExit(f"{table_set}: batch failed: {text[:1000]}")


def main(run_day, apply):
    dv = Dataverse()
    total = 0
    for platform, levels in LEVELS.items():
        before = cutoff(run_day, LATE_DAYS[platform])
        for parent_key, _, _ in levels:
            table = f"sanidi_{parent_key}monthlyinsight"
            pk = f"{table}id"
            ids, last = [], None
            while True:
                more = f" and {pk} gt {last}" if last else ""
                rows, _ = dv.request("GET", f"{table}s?$select={pk}&$orderby={pk}&$filter=sanidi_periodclosed eq false "
                                            f"and sanidi_date lt {before:%Y-%m-%d}{more}",
                                     headers={"Prefer": "odata.maxpagesize=5000"})
                ids += [r[pk] for r in rows["value"]]
                if len(rows["value"]) < 5000:
                    break
                last = ids[-1]
            if apply:
                for i in range(0, len(ids), BATCH):
                    batch_close(dv, table + "s", ids[i:i + BATCH])
            total += len(ids)
            print(f"{table:45} close before {before}: {len(ids)}{' closed' if apply else ''}", flush=True)
    print("total", total)


if __name__ == "__main__":
    main(date.fromisoformat(sys.argv[1]), "--apply" in sys.argv)
