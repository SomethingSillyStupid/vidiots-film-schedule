#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the generated Vidiots .ics file.")
    parser.add_argument("path", nargs="?", default="output/vidiots.ics")
    args = parser.parse_args()

    path = Path(args.path)
    raw = path.read_bytes()
    errors: list[str] = []

    if not raw:
        errors.append("calendar file is empty")
    if b"BEGIN:VEVENT" not in raw:
        errors.append("calendar contains no VEVENT entries")
    if not raw.endswith(b"END:VCALENDAR\r\n"):
        errors.append("calendar does not end with END:VCALENDAR followed by CRLF")
    if b"\r\n" not in raw:
        errors.append("calendar does not use CRLF line endings")
    if b"\n" in raw.replace(b"\r\n", b""):
        errors.append("calendar contains bare LF line endings")

    lines = raw.split(b"\r\n")
    overlong = [(index + 1, len(line)) for index, line in enumerate(lines) if len(line) > 75]
    if overlong:
        preview = ", ".join(f"line {line_no}: {length} bytes" for line_no, length in overlong[:5])
        errors.append(f"calendar has physical lines over 75 bytes: {preview}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        f"Validated {path}: {raw.count(b'BEGIN:VEVENT')} VEVENT entries, "
        f"max physical line length {max(len(line) for line in lines)} bytes, CRLF endings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
