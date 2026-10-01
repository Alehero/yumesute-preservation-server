# Preservation server changelog

Based on UnknownSekai/server-of-dreams at 3cfca23267fb0f79d7336732db768e1510f20313.
TeamOpenSirius/OpenSiriusServer at 536004f17e174e2190d247edad2622ca2133b181 is
an independent protocol reference, not a merged backend. Changes live in tools/
and are applied as overrides around the pinned Python backend.

## Counting convention

Count distinct user-facing feature groups implemented or substantially repaired in
our overrides. Do not count endpoints, bug fixes within the same feature, untouched
upstream functionality, or captured-but-unimplemented APIs as additional features.
This is a maintenance inventory, not a claim that all functionality was absent upstream.

### Previously implemented: 17 gameplay groups

1. Song purchases.
2. Olivier chart purchases.
3. Actor experience/level upgrades.
4. Actor sense upgrades.
5. Actor talent upgrades.
6. Accessory level upgrades.
7. Poster level upgrades.
8. Poster limit breaks.
9. Actor side-story unlock/read/rewards.
10. Poster story unlocking (some behavior remains provisional).
11. Character star-rank reward claims.
12. Mission reward claims and stage advancement.
13. Anthology progression and first-clear rewards.
14. Audition progression, phases and challenge skips (scoring parity incomplete).
15. Photo development, film use and persistent local image storage (rarity provisional).
16. Album layout persistence, including photos, themes, decorations and stamps.
17. Photo character tags.

Device checks confirm the main progression/upgrade flows, mission claims, Anthology,
ordinary auditions, and album saves. Tag and individual edge-case coverage also rely
on captured-request tests; this list is not blanket device certification.

### Supporting preservation work (not included in gameplay count)

- Account import/authentication and compatibility fixes for the iPad client.
- Capture/routing tooling and persistent local database deployment.
- Public account exporter with Japanese and English documentation.
- iOS asset/catalog, chart, script and media preservation and local serving.
- Gacha response compatibility fixes; underlying gacha implementation is upstream.
- Corrected imported vocal/concentration fields; full score equivalence unresolved.

## Customization/profile batch — September 28, 2026

Seven additional groups (24 total): selected outfits; favorite outfits; favorite
stamps; character-page portraits; home display customization; home background music;
profile editing. Includes beginner mission progress for favoriting stamps, editing
introductions and changing profile titles. Validation/deployment status below.

Lessons remain pending and are not included in the count. Friend routes already
exist upstream and are not claimed as new work. Comic/help assets are preservation
work, not new gameplay APIs.

Batch verification: 42 official captured requests matched in isolated database tests;
duplicate favorite and invalid-card tests passed; seven gameplay regression tests passed.
Deployed successfully; live private account loads 2,602 records, preserved images still
serve correctly. iPad testing of these seven groups is pending. Routing remains official.

Copy-ready update:
> Batch update: added outfit selection/favorites, favorite stamps, character portraits,
> home customization/BGM, and profile editing. Matched 42 captured official requests;
> iPad testing next. Lessons and scoring parity remain in progress.

## Priority diagnosis (no new implementation batch)

Customization testing switched to private. Audit found missing player-rank XP at live
finish, daily lesson usage misinterpreted as remaining allowance, empty sense-voice ID
lists despite preserved audio, and incomplete activity logs/story gating/mission triggers.
BannerMaster exists (998 entries); login bonus reward schedules are absent from raw
master but a successful two-bonus response is archived. See PRIORITY-AUDIT.md.
Feature count stays 24; these findings are not claimed as implemented fixes.

## Comic preservation completed

Preserved all 264 comic PNGs referenced by ComicMaster, rather than only the five
opened during capture. All 264 return HTTP 200 from the local backend with matching
SHA-256 hashes. Added tools/preserve_comics.py and private per-file report. User
confirmed the rest of the customization test batch looked good. Feature-group count
remains 24 (comics counted under supporting asset preservation).

Copy-ready update:
> All 264 comics are now preserved and served locally, with every image verified.
> Customization testing looks good. Next priority before shutdown: capturing circles
> and multiplayer behavior. Exact scoring and configurable limits remain pending.

Routing changed to official for final preservation captures; marker stored in
private/final-preservation-session.json. No unlimited-mode policy has been deployed.

## Small EXP correction batch

Fixed single-card leveling to round EXP per item before multiplying quantity. Seven
fresh official upgrades across rarities1–4 now match level and remaining EXP, including
level1->3 and a two-item request. Seven gameplay regressions also passed. Existing
feature correction; count stays24. Bulk-level/cap edge cases remain unverified.

Copy-ready update:
> Fixed per-item EXP rounding; seven official upgrade samples across all four rarities
> now match, including multi-level jumps. Captured repeat lessons, a rank-up, stamina/
> autoplay XP, and a failed multi-stage course. Broader mode implementation is next.

## Lesson, rank, daily usage and multi-song course batch

Four additional user-facing groups (28 total): lesson lifecycle and score rewards;
player rank XP/stamina restoration; daily usage/reset accounting; multi-song course
progression/certification/entry fees/rewards. Character key-mission claims extend the
existing character progression group and are not counted separately.

Lesson star points and uncertain limits use explicit generous preservation policy in
preservation-rules.json. Rank XP matches the captured lesson and stamina samples, not
all possible modifiers. Course failure matches the captured three-stage run; successful
certification/reward deduplication is tested synthetically. Full client no-limits support,
rating history, sense voices and multiplayer remain pending. iPad confirmation pending.

Copy-ready update:
> Added lessons and score rewards, player rank XP, daily usage/reset handling, and
> multi-song course progression with entry fees and one-time rewards. Unknown formulas
> use documented generous defaults. Server tests pass; iPad testing next. 28 feature
> groups now extended from the upstream backend. Circles/multiplayer capture continues.

Deployment verified: backed up live account, restarted private backend, authenticated
account fetch returns 2,607 records and preserved photo files still match. Routing
remains official. Validation: seven progression tests plus four live-mode, seven
upgrade/gameplay and four mission-claim regressions passed (22 tests total). Lesson
party edits, duplicate finishes, key claims, once-only course rewards, paid/waived/
unlimited server entry policies, retirement and daily reset are covered. Device tests
remain pending; this is not full numerical parity certification.

## Theater/MV viewing bookkeeping batch

Replaced inherited false-result placeholders for WatchTheaterStory and WatchMusicVideo
with master-validated, persistent watched records. Repeated views return the same record,
matching the captured MV behavior. One additional feature group: performance viewing
records (29 total); existing media transport is not counted again. Five photo/viewing
tests passed, including duplicate views, invalid IDs and existing photo/album regressions.
The two freshly requested theater bundles serve locally with byte-exact verification.
Private playback with custom/original casts and theater viewing still needs device testing.

Copy-ready update:
> Fixed theater/MV viewing records and verified the latest theater assets serve locally.
> Repeated views persist correctly; five photo/viewing tests pass. Custom/original cast
> playback still needs a private-server device check. 29 feature groups extended.

## Post-shutdown content windows

Added a private master-data revision extending 626 final-boundary end-date fields
(including nested shop entries) to the game's existing 2100 sentinel. Includes final
Anthology/Event, campaigns and live schedules. Preserves unknown columns and keeps the
original archived DB untouched; no system-clock changes or account rewrites. Cached
server master dates receive the same adjustment. New manifest version/URI forces a
client master refresh on login. This is a content availability correction, not a new
feature group: count stays 29. Extending display dates does not implement League or
multiplayer mechanics.

Validation: recursive master comparison permits only boundary timestamp replacements;
four live-mode regressions pass, including 256 Anthology stages/550 audition phases.
Deployed manifest/master bytes and authenticated account fetch verified; private routing
retained. Device confirmation pending. No failing solo-start API was observed at initial
report, so the solo client error's cause remains unconfirmed.

Copy-ready update:
> Added a preservation master-data revision extending final-service content windows,
> including Anthology and schedules. Original master archive retained. Server checks
> pass; restart the app to refresh. Solo-play error still needs device confirmation.

Device confirmation: user reports the post-shutdown master-date revision resolved
opening the performance menu (error81). The final private test batch was reported
working before the shutdown-boundary issue. Exact scoring and multiplayer remain
outside that confirmation. Client IPA/device-backup preservation is the next task.

## iPhone 3.0.0 compatibility probe (diagnostic only)

Fresh-install official capture reaches Environment only. Response retains asset version
1.96.0 and adds a trailing boolean true at index13, outside the old schema. iPhone-only
proxy now changes that field to false to test whether it controls shutdown mode; its
meaning is not yet confirmed. Original response remains archived before modification.
Wire-level check verifies this is the sole response change. This does not establish
v3 gameplay compatibility or add a completed feature; count remains29. iPad service
and account untouched. Device retry pending.

## Isolated iPhone 3.0.0 transfer experiment — September 29

- Implemented/deployed: separate cloned database, backend and iPhone tunnel routing;
  account-bound private linking credentials with password hashing and separate JWT
  secret. Original imported login-token bridge disabled on the experimental backend.
- Tested: incorrect password rejected; correct transfer returns identity/login token;
  authentication and user-data HTTP request succeed; iPad backend rejects iPhone token.
- Device confirmation pending: transfer UI, v3 account loading and asset downloads.
  The additional v3 Environment boolean remains experimentally set false; its meaning
  is unverified. This does not establish that v3 retains playable rhythm-game code.
- Working iPad service/database untouched; backup made before cloning. No official
  transfer credentials required. Feature-group inventory remains **29**; this is
  supporting preservation work, not a completed new gameplay group.

### iPhone device follow-up

- Phone reached the private GetTakeOverAccount endpoint and the user reports the
  transfer appeared accepted. On the subsequent title attempt it requested only
  Environment, then still displayed the EOS notice. No subsequent Authenticate,
  user-data, or asset-download request was observed from the phone. Earlier
  successful authentication/user-data checks were scripted backend tests.
- Account-transfer acceptance is therefore not confirmation of account-data loading
  or v3 gameplay compatibility. Investigate client startup before asset delivery.
  Feature inventory remains 29.

- iPhone cold-start retest: user again observed EOS notice. Captured phone traffic
  again stops after Environment (HTTP 200), with no Authenticate or download request.
  Restart did not resolve it. Further transfer retries are not justified by current
  evidence; v3 startup/protocol inspection or recovery of the older client is needed.
  This observation does not prove gameplay code was removed from v3.

## 0.1.0 — portable local-server preview (September 29, 2026)

- Packaged the working preservation overrides separately from the personal development
  environment. Pinned upstream backend and Python dependency lock; generated per-install
  secrets; no account files, captures, game assets, or personal diagnostic replay included.
- Added validated exporter-ZIP import, same-installation token-hash association, local
  linking credentials, and explicit fresh starter-account creation. One account per install;
  refuses existing accounts/nonempty databases. Fresh is not unlock-all.
- Added foreground server/tunnel lifecycle, private bilingual device setup page, local
  certificate-only endpoint, data diagnostics, PostgreSQL Compose recipe, English/Japanese
  quick starts, data requirements and backup guidance.
- Tested locally: 13 unit tests; real exporter ZIP imported into a disposable PostgreSQL 17
  database; fresh account created in another database. Both pass wrong-password rejection,
  linking, authentication, user-data serialization, Environment/master delivery and missing
  asset 404. Repeat account creation is rejected. WireGuard binds successfully; certificate
  endpoint serves the certificate and refuses private-key/credential paths.
- Device-confirmed behavior refers to the existing development iPad checks above.
  This portable release has not yet been device-tested end to end. Fresh tutorial/home
  onboarding, Windows, and Docker Compose orchestration remain unverified. iOS 3.0.0
  remains blocked at EOS. Multiplayer/circles, exact scoring and unlock-all remain incomplete.
- Captured-only APIs remain captured-only. The inventory stays at **29 gameplay feature
  groups**; packaging/import infrastructure is not counted as new gameplay.

Earlier entries describe development history. Personal comparison databases, captured-pull
replays and the separate iPhone v3 experiment are not active in this release.

## Documentation clarification — September 29, 2026

- Clarified the English/Japanese 3.0.0 notes: a newly installed client remained at
  the EOS notice after linking; compatibility is not guaranteed. Removed references
  that assumed readers knew the private iPhone experiment. Updated status tables
  and troubleshooting to describe observed results rather than a universal claim.
- Documentation only; no server behavior or verification status changed. Gameplay
  inventory remains 29 groups, based on the pinned server-of-dreams backend.

## Official-CDN downloader — September 29, 2026

- Implemented/tested: direct official-source downloader for pinned raw master, iOS
  1.96.0 catalogs/bundles, master-listed charts/configs and comics. No game API login
  required. File-level restart, checksum verification, atomic writes, bounded workers,
  explicit missing-file reports and English/Japanese setup instructions.
- Tests: all 18 unit tests pass, including corruption repair, hash/length rejection,
  path validation, 403/404/redirect handling and verified-file skipping. Eight initial
  official-CDN probes returned HTTP 200 and matched preserved bytes. The new downloader
  separately fetched master/catalogs, sample bundles/audio/chart/comic and skipped
  verified files on rerun. Enumerated 36,333 media paths; not a full download test.
- Device-confirmed: no new device result in this batch. Existing iPad results remain
  as documented. Fresh 3.0.0 onboarding remains unresolved. Some chart paths were
  previously 404; full static banners/story coverage and future CDN availability are
  not guaranteed. No game-media files or credentials are published.
- Captured-only features remain unchanged. Gameplay inventory stays at **29 groups**;
  downloader/setup infrastructure is not another gameplay feature. Backend remains
  UnknownSekai/server-of-dreams at 3cfca23267fb0f79d7336732db768e1510f20313.

## Supplemental story downloads — September 29, 2026

- Implemented/tested: default downloader now includes the 30 exact known story-script
  gaps (20 main, 10 card-side) through the normal download command. No separate
  story-only setup option is exposed.
  SHA256-verified scenes generate server metadata. Added gzip/Brotli/deflate transfer
  handling with separate wire-length/MD5 and decoded-file SHA256 verification.
- All 30 official-CDN downloads matched preserved scene bytes. Verified-file rerun
  and isolated preparation installed all scene paths/metadata. All 21 unit tests pass.
- Device-confirmed: no new playback result. Story voices/backgrounds remain separate
  catalog downloads; poster/unindexed story completeness, future CDN availability and
  fresh-client playback are not guaranteed. Captured-only features remain unchanged.
- Added bilingual coverage list and instructions. Only identifiers/metadata/hashes are
  published, no scenes or credentials. Gameplay inventory remains **29 groups** on
  pinned UnknownSekai/server-of-dreams; this is preservation/setup coverage.

## Organized archive and fresh-account resources — September 29, 2026

- Implemented/tested: fresh creation grants 10,000 歌劇目録 (item 130001) once, inside
  account initialization. Configurable via fresh_song_tickets (0 disables). This is a
  generous preservation policy; imported accounts receive no extra grant. Song/story/
  chart unlock conditions remain. Upstream seed otherwise remains unchanged.
- 24 unit tests pass. A disposable PostgreSQL account received 10,000 tickets; song
  purchase consumed 10 and persisted ownership. Story handler/database checks passed:
  initial read reward, read-all after skip, direct full read, repeat suppression and
  stored flags; locked side-story rejection and unlocked reward/character progression.
- Local archival verification: a separate setup-compatible data directory was assembled
  from preserved files with checksum comparisons, then checked with the downloader.
  All 34,057 catalog bundles are present. Of 36,363 download-plan paths, 36,333 verified;
  30 chart/config paths under 10172 and 901–904 returned 404. Additional saved scenes,
  upstream episodes and static media are included locally. No media/archive is published.
- Device-confirmed: no new device result. Fresh onboarding, all story categories and
  chapter-completion reward parity remain unverified. Captured-only features unchanged.
- Gameplay inventory remains **29 groups** on pinned UnknownSekai/server-of-dreams
  3cfca23267fb0f79d7336732db768e1510f20313; this updates setup policy and verifies existing
  story-reward behavior rather than adding a new gameplay group.


## September 30, 2026 — reroll gacha and iOS setup

Implemented/tested:
- Persistent reroll sessions: spend the initial ticket once, preview without granting
  rewards, replace the preview on reroll, retrieve it after reconnect, and grant once
  on confirmation. Concurrent/repeated confirmation is idempotent. The real client
  route is `/api/Gachas/ReRoll`; the inferred legacy name remains an alias.
- Approximate reroll odds with at least one Rare4 for the supported guaranteed banners.
- Stable CA reuse with `start --ca-dir`, remembered between starts; unique names for
  newly generated certificates; active name/fingerprint in bilingual setup;
  signing-key/download-certificate validation and game TLS failure diagnostics.
- English/Japanese rollback guides linked from Quick start, with in-place Mac/iOS
  installation steps, account linking, asset download, and backup limitations.
- Four certificate tests, three routing tests, and disposable-database reroll
  integration checks pass.

Device-confirmed:
- Apple-authorized 2.31.3.425 IPA installed over 3.0.0.432 on iPhone 14 Pro/iOS 26.6,
  without uninstall, decryption or re-signing; local asset download/home/song entry.
- Fresh Player onboarding and gacha initial draw → reroll → confirmation.
- Two draw attempts consume one ticket; final confirmation saves ten pull-history
  entries and confirmed state in PostgreSQL.
- Reusing the previously working CA resolves gacha-screen loading on the test phone.
  Different CA keys had the same displayed mitmproxy name; the client's exact
  certificate-validation failure mechanism remains unconfirmed.

Limits: new unique-name certificate onboarding on a separate device, Windows
rollback, full Docker setup, and final reroll ownership after a device restart
remain unverified. Rates are approximations. A development ticket grant was used;
this release does not silently grant every fresh account extra reroll tickets.
Multiplayer/circles/Theater League remain incomplete. No-limits mode is still planned.

Feature-group inventory: **30** (the preceding 29 groups plus persistent reroll
sessions). Certificate and documentation fixes do not add gameplay groups.
Backend credit: UnknownSekai/server-of-dreams, pinned
`3cfca23267fb0f79d7336732db768e1510f20313`; no upstream migration in this release.


## October 1, 2026 — automatic starter onboarding

Implemented/tested:
- Starting a prepared installation without an account creates the same Player
  starter save as the CLI, retaining its empty-database and overwrite safeguards.
- Clean registration and explicit empty-token login select the configured fresh
  save. Repeat registration updates credentials only, without resetting progress
  or repeating starter grants. Imported saves require normal login or Data Link.
- Nonempty foreign tokens are not redirected to a different save. Missing/banned
  starter records are rejected. One installation remains one shared save.
- 33 unit tests pass. Live local API checks also pass for repeated registration,
  registered-token login, empty-token login, unchanged player data and foreign-token
  rejection. Deployed to the iPhone test server.
- English/Japanese setup and rollback guides updated.

Device confirmation: pending a clean-client test; do not delete an existing
working installation or its cached assets to test this. Clients retaining an old
login token still need Data Link. No new official traffic was captured.

Feature inventory remains **30**: this improves existing fresh-account onboarding,
not a separate gameplay group. Pinned backend: UnknownSekai/server-of-dreams
`3cfca23267fb0f79d7336732db768e1510f20313`. Existing scoring/lesson approximations
and incomplete multiplayer/circles/Theater League are unchanged.


## October 1, 2026 — in-game starter naming and simpler setup

Implemented/tested:
- Removed the fresh-account command from both README quick starts; only importing
  an existing account is an optional step. Moved phone rollback test context out
  of the README and kept the detailed evidence in the rollback guides.
- Newly created fresh accounts accept the name from the client's Register payload
  once, transactionally. Retrying registration cannot rename a save. Existing
  configured saves and imports do not opt into this behavior.
- Upstream starter data already uses tutorialStatus=Start (0); no tutorial skip
  was added. The one-time, configurable 10,000 song-ticket inventory allowance
  remains unchanged. No gift event was introduced.
- 34 unit tests pass. Disposable PostgreSQL integration confirms Japanese-name
  persistence, retry safety, tutorial start state, and imported-account rejection.
- Deployed to the local test server. Complete opening story/name-popup sequence
  remains device-unverified; the client must have its opening-scene assets.

Captured-only: no new official captures. Feature inventory remains **30**, based
 on pinned UnknownSekai/server-of-dreams
`3cfca23267fb0f79d7336732db768e1510f20313`. Existing scoring/lesson approximations
and incomplete multiplayer/circles/Theater League remain documented limitations.


## October 1, 2026 — permanent song-ticket gift

Implemented/tested: new and imported local accounts receive a one-time, nonexpiring
「楽曲解放サポート」inbox gift of 10,000 song tickets. New issuance is configurable
with preservation_song_tickets. Default direct fresh-account allowance is now zero;
previous direct grants remain, and those accounts can also claim this gift.
Issuance persists separately from inbox rows, preventing reissue after cleanup.
Inbox claims now run transactionally with per-account locking and deduplicated IDs.
Disposable database tests confirm one-time issuance, no inventory change before
claiming, concurrent/duplicate claim safety, and no reissue after inbox cleanup.
34 unit tests pass. Deployed to the starter test server; gift display and claim
on a physical device remain unverified. No new official captures.

This is a local preservation gift, not a recreated official event or an unlock-all
feature. Stella/Olivier requirements still apply and remain under investigation.
Feature inventory stays **30** (existing rewards group). Backend remains pinned to
UnknownSekai/server-of-dreams 3cfca23267fb0f79d7336732db768e1510f20313.


## October 1, 2026 — gift deadline compatibility

Captured evidence: official non-time-limited Inbox data uses deadline
4102358400000000 rather than zero. Implemented/tested: the preservation gift now
uses that sentinel with isTimeLimited=false; previously issued, unclaimed zero-
deadline gifts are repaired and marked unchecked for delivery, without reissue.
Disposable database tests cover this migration plus repeat/concurrent claims.
Deployed locally; device visibility/claim confirmation remains pending. The iPad
now reaches the shared starter save; its completed tutorial is from the iPhone
test, not evidence of clean registration/name-popup behavior. Inventory remains
30 groups on pinned UnknownSekai/server-of-dreams 3cfca23267fb0f79d7336732db768e1510f20313.

## 2026-10-01 — Imported-account gift compatibility

- Implemented/tested: gift creation and claiming now use a 64-bit PostgreSQL advisory lock, supporting original account IDs above 2,147,483,647. Imported-save user-data request returns HTTP 200; 34 unit tests pass.
- Device-confirmed: starter song-ticket gift displayed and was claimed.
- Pending device test: original-account song list on iPad; starter song list still empty on iPad but works on iPhone. No chart-visibility fix claimed.
- Captured-only: no new official captures. Feature-group inventory remains 30; this repairs the existing gift feature. Backend remains pinned to UnknownSekai/server-of-dreams at 3cfca23267fb0f79d7336732db768e1510f20313.

## 2026-10-01 — Starter difficulty fallback

- Implemented/tested: fresh saves receive default song 244, 「錆びついた胸に一雫の心を」, with STELLA and OLIVIER I released. Existing starter saves are repaired at login; imported saves are unchanged. Repeated grants are idempotent and create no scores or clear records. This is an intentional preservation fallback, not an official unlock rule.
- Device-confirmed diagnosis: the same starter save displayed songs after the iPad switched from its remembered OLIVIER selection to NORMAL using the imported save. The new fallback still needs device confirmation.
- Captured-only: no new captures. Inventory remains 30 feature groups; this is a starter-account compatibility repair on the pinned UnknownSekai/server-of-dreams backend.

## 2026-10-01 — Default-song STELLA progression

- Implemented/tested: fresh saves now initialize ownership rows for visible default songs (excluding the tutorial chart), including existing starter saves at login. Missing rows previously caused finish-time STELLA progression to skip playable default songs. Verified EXTRA clear boundary: 10 GOOD-or-worse qualifies, 11 does not; repeated initialization creates no duplicates.
- Repaired the test starter's earned song 21 STELLA unlock using its recorded All Perfect clear. No scores were fabricated. Other chart progression still needs device testing.
- Device-reported: qualifying play did not unlock STELLA before this repair. Captured-only: no new official captures. Inventory remains 30 groups; pinned upstream unchanged.
