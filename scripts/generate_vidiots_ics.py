#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SOURCE_URL = "https://vidiotsfoundation.org/coming-soon/"
CALENDAR_NAME = "Vidiots Film Schedule"
DEFAULT_DURATION_MINUTES = 120
TIMEZONE = ZoneInfo("America/Los_Angeles")
VENUE_ADDRESS = "4884 Eagle Rock Blvd, Los Angeles, CA 90041"


@dataclass(frozen=True)
class Screening:
    title: str
    movie_url: str
    ticket_url: str
    showtime_id: str
    starts_at: datetime
    ends_at: datetime
    runtime_minutes: int | None
    format: str | None
    rating: str | None
    release_year: str | None
    series: tuple[str, ...]
    sold_out: bool
    note: str | None
    summary: str | None

    @property
    def location(self) -> str:
        if any("MUBI Microcinema" in item for item in self.series):
            return f"MUBI Microcinema at Vidiots, {VENUE_ADDRESS}"
        if any("Eagle" in item for item in self.series):
            return f"The Eagle Theatre at Vidiots, {VENUE_ADDRESS}"
        return f"Vidiots, {VENUE_ADDRESS}"


def fetch(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def text_from_html(fragment: str) -> str:
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</p\s*>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    lines = [" ".join(line.split()) for line in fragment.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def find_first(pattern: str, text: str, flags: int = re.S) -> str | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return html.unescape(match.group(1)).strip()


def split_show_blocks(page_html: str) -> list[str]:
    parts = page_html.split('<div class="show-details">')
    return parts[1:]


def parse_specs(block: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    specs_match = re.search(r'<p class="show-specs">(.*?)</p>', block, re.S)
    if not specs_match:
        return specs

    for label, value in re.findall(
        r'<span class="show-spec-label">([^<:]+):</span>\s*(.*?)(?=</span>\s*<span|</span>\s*</p>)',
        specs_match.group(1),
        re.S,
    ):
        cleaned = text_from_html(value)
        if cleaned:
            specs[html.unescape(label).strip()] = cleaned
    return specs


def parse_runtime_minutes(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def parse_showtime_entries(block: str) -> Iterable[tuple[int, str, str, str, bool, str | None]]:
    pattern = re.compile(
        r'<li[^>]*data-date="(\d+)"[^>]*>\s*'
        r'<(?P<tag>a|span)\b(?P<attrs>[^>]*)class="(?P<class>[^"]*\bshowtime\b[^"]*)"(?P<attrs_after>[^>]*)>'
        r'(?P<body>.*?)</(?P=tag)>',
        re.S,
    )
    for match in pattern.finditer(block):
        attrs = match.group("attrs") + match.group("attrs_after")
        date_epoch = int(match.group(1))
        showtime_id = find_first(r'data-showtime_id="([^"]+)"', attrs) or ""
        href = find_first(r'href="([^"]+)"', attrs) or ""
        body = match.group("body")
        body_text = text_from_html(body)
        time_match = re.search(r"\b\d{1,2}:\d{2}\s*[ap]\.?m\.?\b", body_text, re.I)
        time_text = time_match.group(0).replace(".", "") if time_match else ""
        extra = find_first(r'<span class="extra">(.*?)</span>', body)
        sold_out = "sold-out" in match.group("class")
        yield date_epoch, time_text, href, showtime_id, sold_out, text_from_html(extra or "") or None


def parse_local_start(date_epoch: int, time_text: str) -> datetime:
    date = datetime.fromtimestamp(date_epoch, TIMEZONE).date()
    parsed_time = datetime.strptime(time_text.lower(), "%I:%M %p").time()
    return datetime.combine(date, parsed_time, tzinfo=TIMEZONE)


def parse_screenings(page_html: str) -> list[Screening]:
    screenings: list[Screening] = []

    for block in split_show_blocks(page_html):
        title = find_first(r'<h2 class="show-title">\s*<a class="title" href="([^"]+)">', block)
        movie_url = title or ""
        title_text = find_first(r'<h2 class="show-title">\s*<a class="title" href="[^"]+">(.*?)</a>', block)
        if not title_text:
            continue

        specs = parse_specs(block)
        runtime = parse_runtime_minutes(specs.get("Run Time"))
        duration = timedelta(minutes=runtime or DEFAULT_DURATION_MINUTES)
        series = tuple(
            dict.fromkeys(
                text_from_html(label)
                for label in re.findall(r'<a [^>]*class="pill [^"]*"[^>]*>(.*?)</a>', block, re.S)
                if text_from_html(label)
            )
        )
        summary = text_from_html(find_first(r'<div class="show-content">(.*?)(?:</div>\s*</div>|</div>)', block) or "")

        for date_epoch, time_text, ticket_url, showtime_id, sold_out, note in parse_showtime_entries(block):
            if not time_text:
                continue
            starts_at = parse_local_start(date_epoch, time_text)
            screenings.append(
                Screening(
                    title=title_text,
                    movie_url=movie_url,
                    ticket_url=ticket_url,
                    showtime_id=showtime_id,
                    starts_at=starts_at,
                    ends_at=starts_at + duration,
                    runtime_minutes=runtime,
                    format=specs.get("Format"),
                    rating=specs.get("Rating"),
                    release_year=specs.get("Release Year"),
                    series=series,
                    sold_out=sold_out,
                    note=note,
                    summary=summary or None,
                )
            )

    return sorted(screenings, key=lambda screening: (screening.starts_at, screening.title))


def escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", r"\n")
    )


def fold_line(line: str) -> list[str]:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return [line]

    lines: list[str] = []
    current = ""
    for char in line:
        prefix = " " if lines else ""
        candidate = current + char
        if len((prefix + candidate).encode("utf-8")) > 75:
            lines.append((prefix + current) if lines else current)
            current = char
        else:
            current = candidate
    if current:
        lines.append((" " + current) if lines else current)
    return lines


def add_line(lines: list[str], line: str) -> None:
    lines.extend(fold_line(line))


def format_local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def screening_uid(screening: Screening) -> str:
    if screening.showtime_id:
        return f"{screening.showtime_id}@vidiotsfoundation.org"
    digest = hashlib.sha1(
        f"{screening.title}|{screening.starts_at.isoformat()}|{screening.movie_url}".encode()
    ).hexdigest()[:16]
    return f"{digest}@vidiotsfoundation.org"


def unfold_ics_lines(raw: str) -> list[str]:
    logical_lines: list[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and logical_lines:
            logical_lines[-1] += line[1:]
        elif line:
            logical_lines.append(line)
    return logical_lines


def event_uid(event_block: str) -> str | None:
    for line in unfold_ics_lines(event_block):
        if line.startswith("UID:"):
            return line.split(":", 1)[1]
    return None


def event_start_date(event_block: str) -> date | None:
    for line in unfold_ics_lines(event_block):
        if line.startswith("DTSTART"):
            value = line.split(":", 1)[-1]
            match = re.match(r"(\d{8})", value)
            if match:
                return datetime.strptime(match.group(1), "%Y%m%d").date()
    return None


def existing_events_for_date(calendar_path: Path, target_date: date) -> dict[str, str]:
    if not calendar_path.exists():
        return {}

    raw = calendar_path.read_text(encoding="utf-8")
    events: dict[str, str] = {}
    for match in re.finditer(r"BEGIN:VEVENT(?:\r\n|\n|\r).*?END:VEVENT", raw, re.S):
        block = match.group(0).replace("\r\n", "\n").replace("\r", "\n")
        uid = event_uid(block)
        if uid and event_start_date(block) == target_date:
            events[uid] = block
    return events


def describe(screening: Screening) -> str:
    parts: list[str] = []
    if screening.note:
        parts.append(screening.note)
    if screening.sold_out and screening.note != "Limited Walk-Ups*":
        parts.append("Online tickets are sold out or limited.")
    facts = []
    if screening.runtime_minutes:
        facts.append(f"Run time: {screening.runtime_minutes} min")
    if screening.format:
        facts.append(f"Format: {screening.format}")
    if screening.rating:
        facts.append(f"Rating: {screening.rating}")
    if screening.release_year:
        facts.append(f"Release year: {screening.release_year}")
    if facts:
        parts.append(" | ".join(facts))
    if screening.series:
        parts.append("Series: " + ", ".join(screening.series))
    if screening.summary:
        parts.append(screening.summary)
    if screening.ticket_url:
        parts.append(f"Tickets: {screening.ticket_url}")
    parts.append(f"Details: {screening.movie_url}")
    return "\n\n".join(parts)


def build_ics(screenings: list[Screening], source_url: str, extra_event_blocks: Iterable[str] = ()) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Vidiots Film Schedule//Screenings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    add_line(lines, f"X-WR-CALNAME:{escape_ics(CALENDAR_NAME)}")
    add_line(lines, "X-WR-TIMEZONE:America/Los_Angeles")
    add_line(lines, f"X-WR-CALDESC:{escape_ics('Film screenings from ' + source_url)}")

    for screening in screenings:
        lines.append("BEGIN:VEVENT")
        add_line(lines, f"UID:{screening_uid(screening)}")
        add_line(lines, f"DTSTAMP:{format_utc(screening.starts_at)}")
        add_line(lines, f"DTSTART;TZID=America/Los_Angeles:{format_local(screening.starts_at)}")
        add_line(lines, f"DTEND;TZID=America/Los_Angeles:{format_local(screening.ends_at)}")
        add_line(lines, f"SUMMARY:{escape_ics(screening.title)}")
        add_line(lines, f"LOCATION:{escape_ics(screening.location)}")
        add_line(lines, f"URL:{escape_ics(screening.ticket_url or screening.movie_url)}")
        add_line(lines, f"DESCRIPTION:{escape_ics(describe(screening))}")
        if screening.sold_out:
            add_line(lines, "STATUS:TENTATIVE")
        lines.append("END:VEVENT")

    for event_block in extra_event_blocks:
        lines.extend(event_block.split("\n"))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an .ics calendar of Vidiots screenings.")
    parser.add_argument("--url", default=SOURCE_URL, help=f"Source page to scrape. Default: {SOURCE_URL}")
    parser.add_argument("--output", default="output/vidiots.ics", help="Output .ics path.")
    parser.add_argument("--html", help="Use a saved HTML file instead of fetching the source page.")
    parser.add_argument(
        "--today",
        help="Override today's date in America/Los_Angeles, in YYYY-MM-DD format. Useful for tests.",
    )
    args = parser.parse_args()

    page_html = Path(args.html).read_text(encoding="utf-8") if args.html else fetch(args.url)
    screenings = parse_screenings(page_html)
    if not screenings:
        print("No screenings found. The Vidiots page structure may have changed.", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else datetime.now(TIMEZONE).date()
    new_uids = {screening_uid(screening) for screening in screenings}
    preserved_events = {
        uid: block for uid, block in existing_events_for_date(output_path, today).items() if uid not in new_uids
    }
    with output_path.open("w", encoding="utf-8", newline="") as calendar_file:
        calendar_file.write(build_ics(screenings, args.url, preserved_events.values()))

    first = screenings[0].starts_at.strftime("%Y-%m-%d %I:%M %p %Z")
    last = screenings[-1].starts_at.strftime("%Y-%m-%d %I:%M %p %Z")
    print(f"Wrote {len(screenings)} screenings to {output_path}")
    if preserved_events:
        print(f"Preserved {len(preserved_events)} current-day screenings from the existing calendar")
    print(f"Date range: {first} through {last}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
