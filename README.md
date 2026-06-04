# Vidiots Film Schedule

Generate an `.ics` calendar file from the public Vidiots "Coming Soon" screenings page.

## Run locally

```sh
python3 scripts/generate_vidiots_ics.py
```

The calendar is written to:

```text
output/vidiots.ics
```

Import that file into Apple Calendar with `File > Import`.

## Options

```sh
python3 scripts/generate_vidiots_ics.py --output output/vidiots.ics
python3 scripts/generate_vidiots_ics.py --html saved-coming-soon.html
python3 scripts/generate_vidiots_ics.py --html saved-coming-soon.html --today 2026-06-04
```

## Verify locally

```sh
PYTHONPYCACHEPREFIX=/tmp/vidiots-pycache python3 -m py_compile scripts/generate_vidiots_ics.py scripts/validate_ics.py
python3 -m unittest discover -s tests
python3 scripts/generate_vidiots_ics.py
python3 scripts/validate_ics.py output/vidiots.ics
```

The validation step confirms the calendar contains at least one `VEVENT`, ends with
`END:VCALENDAR`, uses CRLF line endings, and has no physical line longer than 75
bytes.

The script uses only the Python standard library, so there is no package install step.

## GitHub updater

This repo includes a GitHub Actions workflow at `.github/workflows/update-calendar.yml`.
GitHub Actions refreshes `output/vidiots.ics` every six hours and publishes it with GitHub Pages.

Apple Calendar can subscribe to the GitHub Pages URL:

```text
https://somethingsillystupid.github.io/vidiots-film-schedule/vidiots.ics
```

The raw GitHub file URL is also available after the first workflow run commits the generated calendar:

```text
https://raw.githubusercontent.com/SomethingSillyStupid/vidiots-film-schedule/main/output/vidiots.ics
```
