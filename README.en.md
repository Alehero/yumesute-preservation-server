# Yumesute Preservation Server

[日本語](README.md) · **English**

An unofficial local server for preserved **World Dai Star: Yume no Stellarium** data. Built on [UnknownSekai/server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), with additions and repairs for progression, upgrades, rewards, and customization. The upstream implementation made this work possible.

**Read first: this does not restore the official service or provide the game app. An account ZIP alone is not enough.** You need a compatible installed client, master data, and the media needed by that client. This repository does not distribute an IPA/APK, game media, or anyone's account.

- Reference device: existing **iOS 2.31.3 client (build 2.31.3.425)**, M1 iPad Pro, iPadOS 26.6.1, macOS 26.2.
- **Compatibility with 3.0.0 is not guaranteed.** Use 2.31.3; see the [rollback guide](IOS-ROLLBACK.en.md) for installation and compatibility details. Do not delete or update a working older client.
- Home, solo play, results surviving restart, and several progression features were device-confirmed in the development setup. This is distinct from device-testing the entire release installer.
- This is an early **personal, home-LAN** package, not a public multi-user hosting service. Each installation supports one recovered official identity alongside its retained starter save. Windows instructions are provided but are not device-tested.

## Requirements

1. A device with a compatible game client. **“Fresh account” does not mean a fresh 3.0.0 app installation will work.**
2. Mac or Windows PC on the same Wi-Fi. No USB cable is required for play; the optional iOS rollback procedure needs one.
3. [uv](https://docs.astral.sh/uv/getting-started/installation/), [Git](https://git-scm.com/downloads), and running [Docker Desktop](https://docs.docker.com/desktop/) for PostgreSQL. Existing PostgreSQL users can follow [DATA.md](DATA.md).
4. The official [WireGuard app](https://www.wireguard.com/install/) on the device.
5. A local game-data folder arranged as described in [DATA.md](DATA.md). **It is not included in an account-export ZIP.** You can try the official-CDN downloader below while those files remain available. Having media cached on an iPad does not automatically make it exportable to the PC.
6. Optional: an existing account-export ZIP, or your official linking ID/password. Automatic recovery can retrieve your save while the official authentication and account-data endpoints remain available; an exporter is not required for that path.

## Quick start

[Download ZIP](https://github.com/Alehero/yumesute-preservation-server/archive/refs/heads/main.zip), extract it, and open Terminal or PowerShell in that folder. Run all commands below from there. First setup downloads dependencies and the pinned upstream source, so internet access is needed for installation.

### 0. Check the app version

Use **2.31.3 (build 2.31.3.425)**. If you accidentally updated to 3.0.0, follow the [Mac/iOS rollback guide](IOS-ROLLBACK.en.md) first. It documents our verified in-place replacement and its limits. Keep an already-working older installation unchanged. USB is needed for rollback, not normal play.

### 1. Prepare data and start the database

For a new setup, download the reference iOS data directly from the official CDN:

```sh
uv run --locked python download_data.py
uv run --locked python server.py prepare --data-dir data
docker compose up -d --wait db
```

The downloader does not need an official game login. It fetches master data, iOS 1.96.0 asset bundles (including audio/MV resources), chart/config files, master-listed comics, 30 supplemental story scripts missing from the pinned upstream archive, and 1,132 additional static resources plus the help index. Allow roughly **45 GB of free space** for the downloaded source plus the prepared copy; actual usage varies. Keep the computer awake. Rerun the same download command after interruption: completed files are checksum-checked and skipped; an interrupted file restarts from its beginning.

**Availability was sampled on September 29, 2026; it is not guaranteed.** Read `data/download-report.jsonl` for failures. Some master-listed charts already returned 404 in the preservation capture. The command exits with code 2 if any media is missing; review the report before proceeding. A partial download may support some features, but is not a complete installation. This downloader does not supply the app, fix 3.0.0, or guarantee every story/banner. The identified main/card story-script gaps are covered; see [story coverage](STORY_COVERAGE.md). See [DATA.md](DATA.md).

If you already have local game data, skip downloading and use `uv run --locked python server.py prepare --data-dir "/path/to/game-data"`, then start the database. A Windows path can be `"C:\Users\You\Documents\game-data"`. Preparation generates per-installation secrets and copies supplied files without changing the originals.

### Existing installation: add banners and help resources

After updating the server code, stop the server and run:

```sh
uv run --locked python download_data.py --supplemental-only --output data
uv run --locked python server.py install-supplement --data-dir data
```

Then start the server normally. This downloads **1,132 pinned static resources plus
`help.bin` (about 50 MB)**, without downloading bundles again. It includes all 826
archived BannerMaster paths and all 30 help-index images. The installer validates the
complete supplement before copying files and does not touch accounts or configuration.
Do not rerun `prepare` on an existing installation. A download failure is listed in
`data/download-report.jsonl`; rerun to retry. Availability is not guaranteed.

Fresh setups include these resources in the normal download/prepare commands.
The complete supplement was downloaded into an empty folder and verified over local
HTTP on October 1, 2026; in-game help rendering remains unverified. This is known
resource coverage, not proof that every historical asset or event is supported.

### 2. Restore a saved account (optional)

**Starting fresh or trying automatic official recovery? Skip this step.** The server creates your starter save automatically when first started. New saves begin at the opening tutorial; the registration request saves the name entered in game.

All local accounts, including imports, receive a **permanent gift of 10,000 song tickets (歌劇目録)**. Claim **楽曲解放サポート** from Presents; it is available once per account with no expiry. Set `preservation_song_tickets` in `preservation-rules.json` before the gift is issued to change the amount (0 disables new issuance). Earlier direct starter grants are retained, so those accounts can also claim this gift. This is a local preservation reward, not an official event or unlock-all preset; song and chart unlock conditions still apply.

To restore an account export instead, run this **before the first server start**:

```sh
uv run --locked python server.py import-account "/path/to/your-account.zip"
```

Import preserves captured ownership and refuses to overwrite existing accounts. **Keep the original ZIP.** If your export includes a login bridge, try normal login on the original installation; otherwise use Data Link below.

### 3. Start and connect the device

```sh
uv run --locked python server.py start
```

A setup page opens in your browser. If it does not, open `private/setup.html`.

1. Set the device's Wi-Fi **HTTP Proxy to Off**. Disable other WireGuard tunnels, including the exporter tunnel.
2. In WireGuard, choose **Add a Tunnel → Create from QR code**, scan the setup-page QR, and turn it on. The QR contains a private key: do not share it.
3. Open the displayed certificate URL in device Safari.
4. Install the downloaded profile under **Settings → General → VPN & Device Management**.
5. Match the certificate name/fingerprint shown in setup; another “mitmproxy” profile may have a different key. Reuse a working local store with `server.py start --ca-dir "/path/to/old/private/mitmproxy"` (saved for future starts). Enable **full trust** under **General → About → Certificate Trust Settings**. Installing the profile alone is insufficient.
6. Fully close and reopen the game and enter from the title screen. Known local accounts load locally. An unrecognized official login token triggers an attempt to recover your official save.
7. To recover using official credentials, choose **title Menu → データ連携 → 連携パスワード入力** and enter your **official linking ID and password**. Check the displayed account name. To select this installation's original starter or manually imported save instead, use the **local** credentials in `private/linking-credentials.txt`. Apple sign-in recovery is not implemented. Linking changes the account selected on the receiving device.
8. Test **home → solo play → results → app restart**, checking that progress persists.

**Recovery behavior:** a successful official fetch is saved transactionally; future logins with recognized credentials use the local copy without contacting the official server. Incorrect credentials return an error. If the official service is unavailable before any official save has been recovered, the server selects its existing starter without resetting it; that credential then stays linked locally. After recovery, an unknown credential during an outage returns an error rather than selecting a starter. Malformed responses and unrecognized errors never cause fallback. Set `official_account_recovery` to `false` in `preservation-rules.json` to disable official requests; known local accounts still work. See [recovery and backups](DATA.md#automatic-account-recovery--アカウントの自動復元).

A clean client with no token uses the local starter. Registration reuses that save without resetting progress; it does not create a separate save per device. API checks cover registration, but clean-client name entry remains unverified. Official recovery retrieves account state, not the app or media. Its initial availability is not guaranteed; back up the recovered database and configuration.

Keep the computer awake and terminal open. To stop: **turn WireGuard off, then press Control+C**. Stop PostgreSQL with `docker compose stop`. Next time, run `docker compose up -d --wait db` and `server.py start`. Do not re-import your account each session.

## Download an official-account backup from your browser

With the server running, open **[Account recovery](http://127.0.0.1:8125/recovery)**
on the **server computer**, or follow its setup-page link. Use the chosen backend
port if you changed it. Enter your **official linking ID/password**, not your Apple
ID or local server credentials. The page downloads a verified ZIP and also keeps a
private copy under `private/recovered-exports`; this does not change your save.

After saving the ZIP, optionally choose **Import locally** within 15 minutes.
The starter is retained, and progress on an already-recovered official account is
never overwritten. Then use your official linking credentials through the game's
Data Link screen to select the local recovered account. This explicit flow also
works when ordinary login is already linked to a starter. It never falls back to a
starter on failure. Initial recovery still requires working official endpoints.

## Status

| Area | Status |
|---|---|
| Solo gameplay and saved results | Supported; see CHANGELOG for validation details |
| Purchases, upgrades, rewards, progression, customization | 30 implemented/repaired feature groups; see [CHANGELOG](CHANGELOG.md) for individual evidence |
| Final-service Anthology/performance end dates | Relevant end dates extended in the served master; original retained |
| Scoring, lessons, usage limits | Some values are approximations or generous preservation policies, not exact official parity |
| Fresh accounts | Automatic creation and initial name saving supported; full opening sequence awaits device verification |
| Multiplayer, circles, Theater League | Unsupported/incomplete; captured traffic is not a working implementation |
| Unlock-all / complete no-limits mode | Not included in this release |
| Client 3.0.0 / new app installation | Use 2.31.3; see the rollback guide for compatibility details |

## Troubleshooting

- **Wrong LAN address:** `uv run --locked python server.py start --host 192.168.1.23` (use your computer's address). Re-import the changed QR configuration.
- **Port conflict:** defaults are backend TCP 8125 (loopback), WireGuard UDP 51822, certificate TCP 8766, and PostgreSQL TCP 55433 (loopback). Use `start --port 8126 --wg-port 51823 --cert-port 8767`. Change DB port in both `.env` and `vendor/server-of-dreams/config.yml` before initialization.
- **Certificate/tunnel failure:** check same LAN, guest-network isolation, computer firewall, and full certificate trust. Allow only the required traffic on your home network. Internet port forwarding is unnecessary.
- **Missing images/songs or HTTP 404:** check `doctor` and `logs/backend.log`. Rerun the downloader for covered files, then copy recovered files into the matching server paths in DATA.md. Do not rerun prepare after configuring an account; it intentionally refuses that. Other missing media must be supplied locally. File counts are not proof of completeness. Do not clear the app cache to troubleshoot this.
- **EOS after linking on 3.0.0:** use the compatible client version described in the [rollback guide](IOS-ROLLBACK.en.md).
- **Database connection failure:** check Docker Desktop and `docker compose ps`. Changing `.env` does not change a password inside an existing database volume. Do not casually delete the volume.

See [DATA.md](DATA.md) for backups, data layout, and existing PostgreSQL. Issues in Japanese or English are welcome. Include OS/client versions, the failing step, and a sanitized error. **Do not upload account ZIPs, private folders, QR codes, or linking credentials.**

## Development and attribution

Backend: [server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), pinned at `3cfca23267fb0f79d7336732db768e1510f20313`. Protocol reference: [OpenSiriusServer](https://github.com/TeamOpenSirius/OpenSiriusServer), `536004f17e174e2190d247edad2622ca2133b181`. These two backends have not been merged.

Server extensions are GPL-3.0. Exporter-derived code retains its MIT notice. See [THIRD_PARTY.md](THIRD_PARTY.md). This community project is unaffiliated with the game's operators or rights holders.

Run the self-contained tests with `uv run --locked python -m unittest discover -s tests -v` (38 tests). `tests/check_running.py` additionally checks a running local test installation on port 8125 and reads its private linking credentials without printing them. Do not run it against someone else's server.

### Certificate identity and reuse

Each installation normally keeps its CA in `private/mitmproxy`. Preserve this
directory across upgrades. The setup page shows the active certificate name and
SHA-256 fingerprint: installing or trusting another certificate also named
“mitmproxy” is not equivalent.

If a previous local installation already works on your device, reuse its CA:

```sh
uv run --locked python server.py start --ca-dir "/absolute/path/to/previous/private/mitmproxy"
```

The directory choice is remembered for later starts. Keep it available locally;
never upload or distribute its private keys. Fresh stores receive a distinct
`Yumesute Local …` name. Existing certificates are never silently replaced.
Enable full trust for the exact certificate shown in setup, then fully restart
the game. If login works but gacha hangs, check terminal TLS errors and certificate
identity before clearing game data. Reusing the working CA resolved this symptom
in our device test; the game's internal certificate-validation behavior remains
unconfirmed.

Starter accounts include 「錆びついた胸に一雫の心を」 with STELLA and OLIVIER I unlocked, so a device remembering those difficulties has a selectable chart. This preservation fallback also applies to existing local starter saves; imported accounts retain their progression.
