# Verification

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
