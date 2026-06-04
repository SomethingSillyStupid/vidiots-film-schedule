#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_vidiots_ics.py"

spec = importlib.util.spec_from_file_location("generate_vidiots_ics", GENERATOR_PATH)
assert spec is not None
assert spec.loader is not None
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)

LA = ZoneInfo("America/Los_Angeles")


def epoch_for_local_date(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, 0, tzinfo=LA).timestamp())


def show_block(title: str, slug: str, showtime_id: str, date_epoch: int, time_text: str) -> str:
    return f'''
    <div class="show-details">
      <h2 class="show-title"><a class="title" href="https://vidiotsfoundation.org/movies/{slug}/">{title}</a></h2>
      <p class="show-specs"><span class="show-spec-label">Run Time:</span> 91 min</span></p>
      <div class="show-content"><p>A useful test description.</p></div>
      <ul>
        <li data-date="{date_epoch}">
          <a href="https://vidiotsfoundation.org/tickets/{showtime_id}" data-showtime_id="{showtime_id}" class="showtime">{time_text}</a>
        </li>
      </ul>
    </div>
    '''


def event_block(uid: str, yyyymmdd: str, summary: str) -> str:
    return "\r\n".join(
        [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{yyyymmdd}T190000Z",
            f"DTSTART;TZID=America/Los_Angeles:{yyyymmdd}T120000",
            f"DTEND;TZID=America/Los_Angeles:{yyyymmdd}T140000",
            f"SUMMARY:{summary}",
            "END:VEVENT",
        ]
    )


class VidiotsGeneratorTests(unittest.TestCase):
    def test_parses_screenings_and_writes_valid_ics(self) -> None:
        html = show_block(
            "Fresh Movie",
            "fresh-movie",
            "fresh-1",
            epoch_for_local_date(2026, 6, 5),
            "7:00 pm",
        )
        screenings = generator.parse_screenings(html)
        self.assertEqual(len(screenings), 1)
        self.assertEqual(screenings[0].title, "Fresh Movie")
        self.assertEqual(generator.screening_uid(screenings[0]), "fresh-1@vidiotsfoundation.org")

        ics = generator.build_ics(screenings, generator.SOURCE_URL)
        raw = ics.encode("utf-8")
        self.assertIn("BEGIN:VEVENT", ics)
        self.assertTrue(raw.endswith(b"END:VCALENDAR\r\n"))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertLessEqual(max(len(line) for line in raw.split(b"\r\n")), 75)

    def test_preserves_only_missing_current_day_events_without_duplicates(self) -> None:
        today_epoch = epoch_for_local_date(2026, 6, 4)
        future_epoch = epoch_for_local_date(2026, 6, 5)
        html = "\n".join(
            [
                show_block("Fresh Movie", "fresh-movie", "fresh-1", today_epoch, "7:00 pm"),
                show_block("Future Movie", "future-movie", "future-1", future_epoch, "8:30 pm"),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            html_path = tmp_path / "coming-soon.html"
            output_path = tmp_path / "vidiots.ics"
            html_path.write_text(html, encoding="utf-8")
            output_path.write_bytes(
                (
                    "BEGIN:VCALENDAR\r\n"
                    "VERSION:2.0\r\n"
                    + event_block("old-today@vidiotsfoundation.org", "20260604", "Old Today")
                    + "\r\n"
                    + event_block("old-yesterday@vidiotsfoundation.org", "20260603", "Old Yesterday")
                    + "\r\n"
                    + event_block("fresh-1@vidiotsfoundation.org", "20260604", "Stale Duplicate")
                    + "\r\nEND:VCALENDAR\r\n"
                ).encode("utf-8")
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR_PATH),
                    "--html",
                    str(html_path),
                    "--output",
                    str(output_path),
                    "--today",
                    "2026-06-04",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Preserved 1 current-day", completed.stdout)
            generated = output_path.read_text(encoding="utf-8")
            self.assertIn("UID:old-today@vidiotsfoundation.org", generated)
            self.assertNotIn("UID:old-yesterday@vidiotsfoundation.org", generated)
            self.assertIn("UID:future-1@vidiotsfoundation.org", generated)
            self.assertEqual(generated.count("UID:fresh-1@vidiotsfoundation.org"), 1)


if __name__ == "__main__":
    unittest.main()
