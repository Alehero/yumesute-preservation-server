# Developer verification

Run from the repository root: `uv run --locked python -m unittest discover -s tests -v`.

`check_running.py` checks a running local test installation on port 8125 using its private linking credentials. It does not print account data or tokens.

`check_story_rewards.py /path/to/disposable-installation` exercises fresh ticket inventory,
song purchase, first/repeat/full story rewards and locked/unlocked card stories against
real PostgreSQL. It intentionally mutates the test account and requires the database name
`yumesute_release_rewards`. Start with a newly created fresh account and default allowance.
It refuses other database names. It tests handlers, serialized responses and persisted
balances; it is not an iPad playback test. Do not use an account you want to keep.

`check_recovery_transport.py --snapshot /private/user-data.response.bin` tests the
recovery HTTP protocol through MockTransport, including rejection, EOS, malformed
responses, redirects and timeouts. It never contacts the official server.

`check_official_recovery.py --snapshot /private/user-data.response.bin` requires a
prepared installation and an **empty schema** in the disposable PostgreSQL database
`yumesute_recovery_checks`. It refuses a populated database. It imports a real private
fixture, injects a transaction failure, tests concurrent retries, and simulates total
EOS with an official stub that fails if called for known local credentials. It checks
service restart, preserved local progress, and actual transfer/auth/data HTTP routes.
It intentionally changes disposable data. Keep the fixture private; never use a live
save database for this test. Run both scripts from a prepared installation with the
normal dependencies available.

After the disposable recovery check, run `check_recovery_page.py --snapshot
/private/user-data.response.bin` in the same prepared installation. It uses a mocked
official service and the disposable `yumesute_recovery_checks` database to test
browser request protection, no-mutation export, archive verification, and explicit
starter-fallback reassignment without overwriting local progress. Reinitialize the
disposable database and run the preceding recovery check before repeating it.

`check_circle_compat.py` checks the Circle compatibility handlers against the pinned
MessagePack models using an in-memory database stub. It verifies route precedence,
empty discovery/ranking lists, missing-circle status, all four company objects and
account-scoped support progress/date serialization. It makes no external requests or
account changes. Passing these checks does not certify playable circles or the
reported rank-30 client crash; those require device testing.

`test_supplemental_resources.py` checks pinned resource metadata, invalid paths,
validation-before-write, account preservation, repeated installation, and missing-file
reporting. Existing downloader tests cover interrupted/corrupt files and checksum
failures. `check_supplement_serving.py` checks all 1,133 pinned resources over HTTP on
localhost:8125, plus missing-static-file 404 behavior; run only on your prepared local
server with the supplement installed. It reads files and does not mutate account data.

[Story resource audit](STORY_COVERAGE.md) records download coverage; it is not a player setup guide.

`test_lifecycle.py` uses isolated temporary folders and mocked service/download boundaries
for setup reuse, exclusive operation locking, repair validation and interruption,
Compose startup decisions, and backup publication/integrity. It does not contact the
CDN or modify a real account. `uv run --locked python tests/check_backup_restore.py` creates an isolated temporary
PostgreSQL cluster, verifies a real dump/restore and shuts it down afterward. It requires
PostgreSQL tools including initdb and pg_ctl. Clean-device, Windows and full-size backup
validation remain open.

`check_song_shop.py` requires a disposable clone named
`yumesute_shop_regression_20261003` with one recovered official account, missing default
song rows for 224/237/260, enough tickets and a cleared OLIVIER level of at least IV.
It changes only that disposable database: checks default ownership materialization,
retained existing progress, purchases, duplicate/insufficient-ticket protection and
expired drops against the pinned master. Recreate the clone before rerunning.
Never point it at a save you intend to keep. Pure date-boundary checks also run in
the normal unit suite.

`check_account_exports.py --database yumesute_export_checks_<suffix>` requires a
disposable clone of a recovered installation. It uses synthetic credentials and
offline official-service stubs; never point it at a live database. It checks export
round trips, credential preservation, local-first outages and unchanged progress.

`check_music_bookmarks.py --database yumesute_pr5_checks_<suffix>` requires a
disposable clone with two accounts and prepared master data. It changes bookmarks
only in that clone and checks room-list responses, input validation, concurrency,
account isolation and persistence through reload/import compatibility overlays.
