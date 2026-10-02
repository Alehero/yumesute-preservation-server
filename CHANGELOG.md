# Changelog

Player-facing changes to Yumesute Preservation Server, newest first.
**Device-confirmed** means the described flow was checked in the game;
**server-tested** means automated or database checks passed, without necessarily
covering every client interaction. Captured or archived data alone does not mean
that a feature is playable.

Built on [UnknownSekai/server-of-dreams](https://github.com/UnknownSekai/server-of-dreams),
pinned to `3cfca23267fb0f79d7336732db768e1510f20313`.
[TeamOpenSirius/OpenSiriusServer](https://github.com/TeamOpenSirius/OpenSiriusServer)
was an independent protocol reference, not a second backend merged into this release.

## October 1, 2026 — Circle compatibility under device test

- PR #2 by [tomyuan520](https://github.com/tomyuan520) adds safe empty Circle
  discovery/ranking responses and non-null support-company data, using the pinned
  upstream models. Conflicts with newer onboarding/reward handlers were resolved.
- **Server-tested and deployed to the development test server:** route precedence,
  response shapes and account-scoped support levels. The rank-30 unlock and Circle
  menu are awaiting device confirmation. PR #2 has been merged into main.
- Circle creation/joining and multiplayer remain unsupported. This compatibility
  test does not add a completed gameplay group; the inventory remains **30**.

## October 1, 2026 — Recover accounts from the local setup page

- Added a Japanese/English recovery page on the server computer. Enter official
  transfer credentials to download a verified account ZIP without changing any save.
  The page explicitly retries the official service even when normal login is already
  associated with a starter. Recovery errors never create a starter through this page.
- Optional import is a separate, confirmed action after downloading. It retains the
  starter and never overwrites progress for an official account already stored locally.
  Verified credentials previously assigned by outage fallback can be reassigned to the
  recovered save; ordinary login remains local-first.
- Backups are also retained in `private/recovered-exports`. Import sessions expire
  after 15 minutes or a server restart. The page accepts requests only on loopback
  with same-origin checks; it is not a public credential-collection website.
- **Server-tested:** ZIP validity, download without account mutation, credential and
  outage failures, explicit fallback reassignment, retained local progress, single-use
  import, and host/origin/request-token checks. The existing 34 tests also pass.
- **Device-confirmed:** browser backup/import followed by game login restored the
  account successfully. In-game transfer recovery into a clean local server is also
  device-confirmed. Normal title login using an official token also recovered the
  account into a clean local server successfully.
  Official API availability and compatible app/media remain prerequisites.
- Gameplay inventory remains **30 groups**. This extends account-preservation tooling
  around the credited pinned upstream backend, not gameplay or multiplayer support.

## October 1, 2026 — Recover official accounts directly at login

- Unknown official login tokens or transfer ID/password pairs can now retrieve the
  official account snapshot and save it locally, without a separate exporter.
  Recognized local credentials always use the local save before any official request.
- Imports and credential mappings commit together. Interrupted imports roll back;
  retries and additional verified credentials never overwrite existing local progress.
- Incorrect credentials return an error. Before any official recovery, an unavailable
  official service selects the existing starter without resetting it. After recovery,
  an unknown credential during an outage returns an error instead of changing accounts.
  Unknown faults and malformed data never trigger the starter fallback.
- **Live API-tested:** both official-token and transfer-password recovery retrieved a
  2,590-record snapshot after EOS. This is account state, not downloadable game media.
- **Server-tested:** concurrent retries, transaction rollback, invalid credentials,
  outages, malformed replies, service restart and real transfer/auth/data routes.
  A simulated total EOS forbids official calls for known accounts and verifies that
  local progression survives. The existing 34-test suite and running-server checks pass.
- **Device-confirmed:** entering official transfer credentials in game automatically
  recovered the account into a clean local server and allowed play. Normal title login
  using a retained official token also recovered the account after a separate reset.
- Recovery is enabled by default and configurable with `official_account_recovery`.
  One official identity is supported per personal installation, alongside its retained
  starter. Apple sign-in recovery is not implemented. Official availability is needed
  only for initial retrieval; preserve the database, secrets, app and media afterward.
  No guarantee of permanent official access or exact gameplay parity is implied.
- Updated Japanese/English setup and backup notes. The gameplay inventory remains
  **30 groups**; account recovery is supporting infrastructure.

## October 1, 2026 — Starter accounts and difficulty unlocks

### Start playing without an account import

- A prepared server now creates a Player starter save automatically when no account
  is configured. Existing accounts and nonempty databases are protected from overwrite.
- Registration accepts a player name once. Repeating registration does not reset
  progress, repeat starter grants, or rename an established account.
- **Device-confirmed:** the opening story and tutorial-skip option appear on a
  previously used installation. **Server-tested:** names submitted during registration
  persist correctly. Name entry on a genuinely clean installation remains unverified.
- Client inspection explains why resetting a server save does not necessarily show
  name entry: the client skips registration when it already has a saved login token.
  Tutorial progress and account registration are separate. Reinstalling or deleting
  cached assets is not required for normal starter-account use.

### A permanent song-ticket gift

- New and imported accounts receive a one-time, nonexpiring **「楽曲解放サポート」**
  gift containing **10,000 歌劇目録**. The quantity is configurable through
  `preservation_song_tickets`.
- This replaces the earlier default grant directly into starter inventory. Earlier
  grants are retained, and those accounts can also claim the gift. Song and chart
  unlock requirements still apply; this is not an unlock-all mode or an official event.
- Fixed an expiry-field compatibility issue that hid the gift, and an account-ID
  size issue that prevented some imported accounts from loading.
- **Device-confirmed:** gift display and claiming. **Server-tested:** duplicate and
  concurrent claims, migration of hidden gifts, and prevention of reissuance after
  inbox cleanup.

### Prevent an empty song list after switching accounts

- Starter accounts now include **「錆びついた胸に一雫の心を」** with **STELLA and
  OLIVIER I** unlocked. Existing starter saves receive the same fallback on login;
  imported accounts retain their progression.
- The client remembers the selected difficulty between accounts. Remembering OLIVIER
  on a save with no available OLIVIER charts can leave the list empty and hide the
  difficulty selector. Providing one accessible chart avoids that dead end.
- This is an intentional preservation fallback, not an original progression rule.
  It adds no scores or clear records. **Device-confirmed:** a new starter account
  displays the song list with OLIVIER already selected.

### Fix default-song STELLA progression

- Default songs now receive ownership records during starter initialization and when
  existing starter saves log in. Previously, the client allowed these songs to play,
  but the server could skip their difficulty unlocks because those records were absent.
- The recovered EXTRA requirement is a clear with **10 or fewer GOOD-or-worse
  judgments**. Server checks cover both sides of that boundary and repeat initialization.
- **Device-confirmed:** the reported default-song STELLA issue was resolved; OLIVIER
  availability also looked correct in subsequent testing. This is not verification
  of every unlock condition. The underlying STELLA/OLIVIER progression logic comes
  from upstream; this repair supplies the missing starter data.

The latest code checks passed 34 unit tests, alongside targeted database checks.
The feature inventory remains **30 groups**; these changes repair existing onboarding,
rewards and song progression rather than adding separate gameplay systems.

## September 30, 2026 — Reroll gacha and iOS setup

- Added persistent reroll sessions: the entry ticket is spent once, rerolls replace
  the pending result, and confirmation grants the selected result only once.
  Pending results survive reconnects. Reroll odds and limit interpretation remain
  approximations; supported guaranteed banners include at least one Rare4 actor.
- **Device-confirmed:** initial draw, reroll and confirmation. **Server-tested:**
  reconnect persistence, duplicate/concurrent confirmation and reward accounting.
  The device test used a separately granted entry ticket; this change does not grant
  every starter account extra reroll tickets.
- Improved certificate setup with reuse of an existing trusted certificate store,
  distinct names for newly generated certificates, fingerprint display and TLS
  diagnostics. Reusing the working certificate resolved a gacha-screen hang on the
  test phone; the precise client validation failure was not established.
- Added Japanese and English [iOS rollback instructions](IOS-ROLLBACK.md).
  **Device-confirmed:** an Apple-authorized 2.31.3.425 package replaced 3.0.0.432
  in place on an iPhone, followed by local asset downloads, home access and song entry.
  That test needed no uninstall, IPA decryption or re-signing. Windows rollback and
  full Docker setup remain unverified.
- **Archived only:** additional static resources, including all 826 distinct
  BannerMaster image paths and 30 help-index image references. This audit did not
  add them all to the public downloader or establish complete historical coverage.

Persistent reroll sessions bring the feature inventory from **29 to 30 groups**.
The base gacha implementation remains upstream work.

## September 29, 2026 — Portable preview and data preservation

### Local-server preview 0.1.0

- Packaged the preservation changes with a pinned backend, locked dependencies,
  account import, local account linking, starter creation and per-install secrets.
- Added a bilingual device setup page, WireGuard startup, certificate delivery,
  diagnostics, backup guidance and a PostgreSQL Compose recipe.
- Account setup refuses to overwrite an existing save. One installation hosts one
  shared save; this is not a public multi-user service.
- Initial server tests covered import, fresh creation, authentication, linking,
  master-data delivery and rejection of invalid setup. Later device milestones are
  recorded above. Windows and complete Compose orchestration remain unverified.
- Account exports, app packages, credentials and game media are not bundled with
  the public server repository.

### Download and archive coverage

- Added a resumable official-CDN downloader for master data, iOS 1.96.0 catalogs and
  bundles, charts, song configurations and comics. Downloads use integrity checks,
  atomic writes and explicit missing-file reports.
- Added 30 known missing story scripts to the standard download plan, with verified
  metadata. Story voices and backgrounds remain separate asset downloads; complete
  poster-story and unindexed-story coverage is not established.
- The local archive verified **34,057 catalog bundles** and **36,333 of 36,363 planned
  paths**. The remaining 30 chart/configuration URLs returned 404. A later audit tied
  those paths to future-dated entries; no guessed chart replacements were introduced.
- Download samples and repeat-download checks passed. These counts describe the
  preserved archive, not a promise that every URL remains available or that all
  content has been played on a fresh device. Android coverage remains incomplete.
- Starter accounts initially received 10,000 song tickets directly. The October 1
  inbox gift supersedes that default, so imported accounts can receive support too.

### Client 3.0.0 investigation

- Account-linking tests did not get a fresh 3.0.0 installation past the end-of-service
  notice. Server authentication checks alone did not establish client compatibility.
- The supported playback path remains 2.31.3. The investigation did not establish
  whether gameplay code was removed from 3.0.0.

## September 28–29, 2026 — Gameplay preservation around shutdown

### Progression, rewards and customization

- Added or repaired song/chart purchases, actor and equipment upgrades, story
  rewards, star-rank claims, missions, Anthology and Audition progression.
- Added photo development and persistent albums, including themes, decorations,
  stamps and character tags.
- Added outfit selection and favorites, favorite stamps, character portraits,
  home customization, home BGM and profile editing. Relevant beginner missions
  now advance with these actions.
- **Device-confirmed:** the main upgrade/progression flows, mission claims,
  Anthology, ordinary auditions, customization and album saves. Captured-request
  and database tests provide additional coverage, not certification of every edge case.
- Corrected actor EXP rounding per item. Seven captured upgrades across all four
  rarities matched level and remaining EXP, including multi-level jumps. Bulk-level
  and cap edge cases remain unverified.
- Preserved and verified local delivery of all **264 comics** listed in the master data.

### Lessons, courses and viewing records

- Implemented lesson lifecycle/rewards, player-rank XP and stamina restoration,
  daily usage/reset accounting, and multi-song course progression with entry costs
  and one-time rewards. These additions brought the inventory to **28 groups**.
- Server tests cover course failure, certification, retirement, duplicate finishes,
  daily resets and reward deduplication. Rank XP matches captured samples rather
  than every possible modifier. Lesson rewards and uncertain limits use documented
  generous approximations in `preservation-rules.json`.
- Added persistent theater/MV viewing records, bringing the inventory to **29 groups**.
  Repeated viewing reuses the record; invalid IDs are rejected. Preserved media
  delivery was checked separately. Viewing records do not establish complete
  asset coverage or verification of every cast/viewing combination.

### Keep content available after shutdown

- Extended 626 end-date fields at the final service boundary, including nested
  shop entries, schedules and Anthology-related content. The original master archive
  is retained; a new master revision refreshes the client without changing its clock.
- **Device-confirmed:** the revision resolved performance-menu error 81 after
  shutdown. Extending availability dates does not implement multiplayer or League.

## Remaining limitations

- Exact scoring parity, Audition challenge scoring and some reward/lesson formulas
  remain incomplete or approximate. Working solo-play flows are not a claim of
  complete official-server parity.
- Multiplayer, circles and Theater League remain incomplete. Captured requests and
  accessible menus do not establish playable matches or full social functionality.
- Some story behavior and media coverage remain provisional. Locally cached content
  can make a device test succeed even when a fresh installation would need more assets.
- A configurable client-wide no-limits mode and unlock-all mode are not implemented.
  Generous fallback rewards do not replace missing gameplay protocols.
- Clean-install name entry, Windows setup/rollback, and full Compose orchestration
  still need device or end-to-end confirmation.

## Feature inventory

**30 player-facing feature groups** have been added or substantially repaired around
our pinned upstream backend. This counts systems, not individual routes or bug fixes;
it does not mean every group was wholly absent upstream or is fully verified.

| # | Feature group | # | Feature group |
|---|---|---|---|
| 1 | Song purchases | 16 | Album layouts, themes, decorations and stamps |
| 2 | OLIVIER chart purchases | 17 | Photo character tags |
| 3 | Actor experience/levels | 18 | Selected outfits |
| 4 | Actor sense upgrades | 19 | Favorite outfits |
| 5 | Actor talent upgrades | 20 | Favorite stamps |
| 6 | Accessory levels | 21 | Character-page portraits |
| 7 | Poster levels | 22 | Home display customization |
| 8 | Poster limit breaks | 23 | Home BGM |
| 9 | Actor side stories/rewards | 24 | Profile editing |
| 10 | Poster story unlocking (provisional) | 25 | Lessons/rewards (approximate) |
| 11 | Character star-rank rewards | 26 | Player-rank XP/stamina restoration |
| 12 | Mission rewards/progression | 27 | Daily usage/reset accounting |
| 13 | Anthology progression/rewards | 28 | Multi-song courses and entry/rewards |
| 14 | Auditions (scoring incomplete) | 29 | Theater/MV viewing records |
| 15 | Photo development/storage (rarity provisional) | 30 | Persistent reroll sessions (approximate odds) |

Account export/import and automatic recovery, client compatibility, asset preservation, downloader tooling
and documentation support these features and are not additional gameplay groups.
