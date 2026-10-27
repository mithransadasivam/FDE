"""Applies with every CV in a folder, through the real apply page (Prompt 11).

Run (app already running):   python -m scripts.upload_cvs --job 1
Without a running app:       python -m scripts.upload_cvs --job 1 --in-process   (uses the app in this process)
"""
import argparse
import mimetypes
import time
from pathlib import Path

DEFAULT_FOLDER = Path("starter_kit/cvs/cloud_support_engineer")
CV_SUFFIXES = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}


def upload_all(client, job: int, folder: Path, wait_for_reading: bool = True) -> tuple[int, int]:
    """POSTs each CV to /jobs/{job}/apply with consent. Returns (accepted, refused)."""
    accepted = refused = 0
    for f in sorted(p for p in folder.iterdir() if p.suffix.lower() in CV_SUFFIXES):
        mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        r = client.post(f"/jobs/{job}/apply", data={"consent": "yes"}, files={"cv": (f.name, f.read_bytes(), mime)})
        if r.status_code in (200, 303) and "/applied/" in (r.headers.get("location", "") or str(r.url)):
            accepted += 1
        else:
            refused += 1
            print(f"  refused {f.name}: HTTP {r.status_code}")
    return accepted, refused


def wait_until_read(count_pending, timeout: float = 600) -> None:
    start = time.time()
    while count_pending() and time.time() - start < timeout:
        time.sleep(1)


def main() -> int:
    import httpx

    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, required=True, help="id of the published requisition")
    ap.add_argument("--folder", type=Path, default=DEFAULT_FOLDER)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    with httpx.Client(base_url=args.url, timeout=60, follow_redirects=False) as client:
        accepted, refused = upload_all(client, args.job, args.folder)
    print(f"{accepted} accepted, {refused} refused. The CVs are read in the background: watch /candidates.")
    return 0 if not refused else 1


if __name__ == "__main__":
    raise SystemExit(main())
