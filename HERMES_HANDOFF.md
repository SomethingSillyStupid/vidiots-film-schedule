# Hermes Handoff: Vidiots Film Schedule

## Mission

Maintain a public, automatically refreshed `.ics` calendar containing upcoming film screenings from Vidiots.

- Source: https://vidiotsfoundation.org/coming-soon/
- Repository: https://github.com/SomethingSillyStupid/vidiots-film-schedule
- Public guide: https://somethingsillystupid.github.io/vidiots-film-schedule/
- Calendar subscription URL: https://somethingsillystupid.github.io/vidiots-film-schedule/vidiots.ics

The calendar refreshes through GitHub Actions every six hours.

## Important Files

- `scripts/generate_vidiots_ics.py`
  - Fetches and parses the Vidiots "Coming Soon" HTML.
  - Generates `output/vidiots.ics`.
  - Uses only the Python standard library.
- `.github/workflows/update-calendar.yml`
  - Runs the generator every six hours, on pushes to `main`, and manually.
  - Commits calendar changes back to `output/vidiots.ics`.
  - Builds and deploys the GitHub Pages site.
  - Contains the entire public webpage as inline HTML/CSS.
- `output/vidiots.ics`
  - Generated calendar checked into the GitHub repository.
  - Also used as the previous calendar when preserving today's events.
- `README.md`
  - Basic local and deployment instructions.

## Generator Behavior

The generator:

1. Downloads the Vidiots "Coming Soon" page.
2. Splits the page into `.show-details` blocks.
3. Extracts titles, movie URLs, showtimes, purchase URLs, runtime, format, rating, release year, series tags, sold-out status, and descriptions.
4. Uses `America/Los_Angeles` for event dates and times.
5. Uses the Vidiots showtime ID as the stable event UID when available.
6. Uses the listed runtime for `DTEND`, falling back to 120 minutes.
7. Writes a standards-friendly `.ics` file with CRLF endings and folded lines capped at 75 bytes.

Do not replace stable UIDs or add a changing generation timestamp. Either change would cause unnecessary calendar churn.

## Critical Rule: Preserve Today's Events

Vidiots may remove screenings from its source page during the day. A refresh must not remove events scheduled for the current Los Angeles date.

Before overwriting `output/vidiots.ics`, the generator:

1. Reads the existing calendar.
2. Finds events whose `DTSTART` date equals today in `America/Los_Angeles`.
3. Preserves any of those events missing from the fresh scrape.
4. Stops preserving them after the local date rolls over.

This depends on `output/vidiots.ics` existing in the checked-out repository before generation. Do not delete it before running the generator in GitHub Actions.

The `--today YYYY-MM-DD` option exists to test this behavior deterministically.

## Local Commands

Generate the live calendar:

```sh
python3 scripts/generate_vidiots_ics.py
```

Compile-check the generator:

```sh
PYTHONPYCACHEPREFIX=/tmp/vidiots-pycache python3 -m py_compile scripts/generate_vidiots_ics.py
```

Generate using saved HTML:

```sh
python3 scripts/generate_vidiots_ics.py --html saved-coming-soon.html
```

Override today's date for preservation testing:

```sh
python3 scripts/generate_vidiots_ics.py --html saved-coming-soon.html --today 2026-06-04
```

## Required Verification

After generator changes:

1. Run the Python compile check.
2. Generate a calendar.
3. Confirm the output contains at least one `VEVENT`.
4. Confirm it ends with `END:VCALENDAR`.
5. Confirm physical lines are no longer than 75 bytes.
6. Confirm the file uses CRLF line endings.
7. Test today's-event preservation using a temporary existing calendar and a fresh scrape that omits that event.

Expected preservation test results:

- A previous event dated today but missing from the scrape remains.
- A previous event dated yesterday is removed.
- Newly scraped future events remain.
- Existing and freshly scraped events with the same UID are not duplicated.

After workflow or webpage changes:

1. Push the workflow update to `main`.
2. Confirm the `Update Vidiots calendar` GitHub Actions run succeeds.
3. Confirm the public guide loads.
4. Confirm `/vidiots.ics` returns a calendar file.

## GitHub Pages

GitHub Pages is configured to deploy using GitHub Actions.

The public webpage is not a standalone file in the repository. It is written into `public/index.html` by a heredoc inside `.github/workflows/update-calendar.yml`.

The page currently provides:

- A `webcal://` subscribe button.
- A direct `.ics` download button.
- Subscription instructions for Mac Calendar, iPhone/iPad, Windows Outlook, and Android/Google Calendar.

When changing the page, edit the inline HTML/CSS in the workflow and allow the workflow to redeploy Pages.

## GitHub Actions Notes

Schedule:

```yaml
cron: "17 */6 * * *"
```

This runs every six hours at minute 17 in UTC.

The workflow has these required permissions:

```yaml
contents: write
pages: write
id-token: write
```

The generator uses deterministic `DTSTAMP` values based on event start times. This prevents a no-op refresh from changing every event and committing a new calendar unnecessarily.

The workflow uses `git status --porcelain -- output/vidiots.ics` so it detects both changed and newly created calendar files.

## Known Risks

- The scraper depends on Vidiots' current HTML structure and class names.
- Vidiots may change its showtime markup without notice.
- Regex parsing is intentionally dependency-free but more fragile than a structured API.
- Sold-out screenings are kept and marked `STATUS:TENTATIVE`.
- Preserved same-day events retain their previous details if Vidiots removes them from the source page.
- If the source returns no screenings, the generator exits without overwriting the existing calendar.

## Ownership and Access

GitHub account/repository owner:

```text
SomethingSillyStupid
```

The ChatGPT Codex Connector GitHub App was installed on the account with repository write access during initial setup. If a future agent can read but cannot update files, check the GitHub App installation and repository access.

## Good Next Improvements

- Add committed automated tests for parsing and same-day preservation.
- Move the inline GitHub Pages HTML into a standalone source file.
- Add a scraper health check that fails if the event count drops unexpectedly.
- Add a lightweight validation step for generated `.ics` structure in GitHub Actions.
- Preserve a short rolling window of recent events if calendar clients need more history.
