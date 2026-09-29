# Verification

Run from the repository root: `uv run --locked python -m unittest discover -s tests -v`.

`check_running.py` checks a running local test installation on port 8125 using its private linking credentials. It does not print account data or tokens.

`check_story_rewards.py /path/to/disposable-installation` exercises fresh ticket inventory,
song purchase, first/repeat/full story rewards and locked/unlocked card stories against
real PostgreSQL. It intentionally mutates the test account and requires the database name
`yumesute_release_rewards`. Start with a newly created fresh account and default allowance.
It refuses other database names. It tests handlers, serialized responses and persisted
balances; it is not an iPad playback test. Do not use an account you want to keep.
