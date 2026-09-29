# Yumesute Preservation Server

[日本語](README.md) · **English**

An unofficial local server for preserved **World Dai Star: Yume no Stellarium** data. Built on [UnknownSekai/server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), with additions and repairs for progression, upgrades, rewards, and customization. The upstream implementation made this work possible.

**Read first: this does not restore the official service or provide the game app. An account ZIP alone is not enough.** You need a compatible installed client, master data, and the media needed by that client. This repository does not distribute an IPA/APK, game media, or anyone's account.

- Reference device: existing **iOS 2.31.3 client (build 2.31.3.425)**, M1 iPad Pro, iPadOS 26.6.1, macOS 26.2.
- **3.0.0 is unsupported.** The iPhone test still stops at the EOS notice after linking. Do not delete or update a working older client.
- Home, solo play, results surviving restart, and several progression features were device-confirmed in the development setup. This is distinct from device-testing the entire release installer.
- This is an early **one-account-per-installation, home-LAN** package, not a public multi-user hosting service. Windows instructions are provided but are not device-tested.

## Requirements

1. A device with a compatible game client. **“Fresh account” does not mean a fresh 3.0.0 app installation will work.**
2. Mac or Windows PC on the same Wi-Fi. No USB cable is required.
3. [uv](https://docs.astral.sh/uv/getting-started/installation/), [Git](https://git-scm.com/downloads), and running [Docker Desktop](https://docs.docker.com/desktop/) for PostgreSQL. Existing PostgreSQL users can follow [DATA.md](DATA.md).
4. The official [WireGuard app](https://www.wireguard.com/install/) on the device.
5. A local game-data folder arranged as described in [DATA.md](DATA.md). **It is not included in an account-export ZIP.** If you do not have these files, setup is blocked here. Having media cached on an iPad does not automatically make it exportable to the PC.
6. For import only: your own ZIP from the [account exporter](https://github.com/Alehero/yumesute-account-exporter). The exporter cannot fetch a new account from an offline official server.

## Quick start

[Download ZIP](https://github.com/Alehero/yumesute-preservation-server/archive/refs/heads/main.zip), extract it, and open Terminal or PowerShell in that folder. Run all commands below from there. First setup downloads dependencies and the pinned upstream source, so internet access is needed for installation.

### 1. Prepare data and start the database

Replace `/path/to/game-data` with your data folder. A Windows example is `"C:\Users\You\Documents\game-data"`.

```sh
uv run --locked python server.py prepare --data-dir "/path/to/game-data"
docker compose up -d --wait db
```

Preparation loads your master data and generates per-installation secrets. It copies supplied files without changing the originals. It does not automatically download missing songs/images from official servers.

### 2A. Import a saved account

```sh
uv run --locked python server.py import-account "/path/to/your-account.zip"
```

The importer validates checksums, format, and account identity. It refuses to overwrite an existing account or a nonempty database. Unsupported entity types stop import instead of silently dropping records. **Keep your original ZIP.**

If the export includes a login association (“bridge”), the same app installation should be able to log in normally. Without a bridge, or on another device, use Data Link below. Import preserves captured ownership; it does not grant everything.

### 2B. Create a fresh account

Use this instead of 2A in an empty installation:

```sh
uv run --locked python server.py fresh-account --name "Player"
```

This creates an independent local account using upstream starter data. **It is not an unlock-all preset**, nor a recovery of your official account. Fresh-account tutorial/home onboarding remains device-unverified. A compatible client and game media are still required.

### 3. Start and connect the device

```sh
uv run --locked python server.py doctor
uv run --locked python server.py start
```

A setup page opens in your browser. If it does not, open `private/setup.html`.

1. Set the device's Wi-Fi **HTTP Proxy to Off**. Disable other WireGuard tunnels, including the exporter tunnel.
2. In WireGuard, choose **Add a Tunnel → Create from QR code**, scan the setup-page QR, and turn it on. The QR contains a private key: do not share it.
3. Open the displayed certificate URL in device Safari.
4. Install the downloaded profile under **Settings → General → VPN & Device Management**.
5. Enable **full trust** under **General → About → Certificate Trust Settings**. Installing the profile alone is insufficient.
6. Fully close and reopen the game. For a bridged import on its original installation, try entering the title screen normally.
7. If normal login does not work, or for a fresh account, use **title Menu → データ連携 → 連携パスワード入力**. Enter the linking ID/password from `private/linking-credentials.txt`. These are **local credentials, not your official linking password or Apple ID**. Check the displayed account name. Linking replaces the account selection on the receiving device; preserve any existing account you want to keep first.
8. Test **home → solo play → results → app restart**, checking that progress persists.

Keep the computer awake and terminal open. To stop: **turn WireGuard off, then press Control+C**. Stop PostgreSQL with `docker compose stop`. Next time, run `docker compose up -d --wait db` and `server.py start`. Do not re-import your account each session.

## Status

| Area | Status |
|---|---|
| Solo gameplay and saved results | Device-confirmed on the existing development iPad |
| Purchases, upgrades, rewards, progression, customization | 29 implemented/repaired feature groups; see [CHANGELOG](CHANGELOG.md) for individual evidence |
| Final-service Anthology/performance end dates | Relevant end dates extended in the served master; original retained |
| Scoring, lessons, usage limits | Some values are approximations or generous preservation policies, not exact official parity |
| Fresh accounts | Creation/API validation supported; actual device onboarding remains unverified |
| Multiplayer, circles, Theater League | Unsupported/incomplete; captured traffic is not a working implementation |
| Unlock-all / complete no-limits mode | Not included in this release |
| Client 3.0.0 / new app installation | Unsupported; a server package does not solve client availability |

## Troubleshooting

- **Wrong LAN address:** `uv run --locked python server.py start --host 192.168.1.23` (use your computer's address). Re-import the changed QR configuration.
- **Port conflict:** defaults are backend TCP 8125 (loopback), WireGuard UDP 51822, certificate TCP 8766, and PostgreSQL TCP 55433 (loopback). Use `start --port 8126 --wg-port 51823 --cert-port 8767`. Change DB port in both `.env` and `vendor/server-of-dreams/config.yml` before initialization.
- **Certificate/tunnel failure:** check same LAN, guest-network isolation, computer firewall, and full certificate trust. Allow only the required traffic on your home network. Internet port forwarding is unnecessary.
- **Missing images/songs or HTTP 404:** check `doctor` and `logs/backend.log`. Missing media must be supplied locally. File counts are not proof of completeness. Do not clear the app cache to troubleshoot this.
- **EOS after linking:** known 3.0.0 limitation. Repeating the transfer will not fix it.
- **Database connection failure:** check Docker Desktop and `docker compose ps`. Changing `.env` does not change a password inside an existing database volume. Do not casually delete the volume.

See [DATA.md](DATA.md) for backups, data layout, and existing PostgreSQL. Issues in Japanese or English are welcome. Include OS/client versions, the failing step, and a sanitized error. **Do not upload account ZIPs, private folders, QR codes, or linking credentials.**

## Development and attribution

Backend: [server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), pinned at `3cfca23267fb0f79d7336732db768e1510f20313`. Protocol reference: [OpenSiriusServer](https://github.com/TeamOpenSirius/OpenSiriusServer), `536004f17e174e2190d247edad2622ca2133b181`. These two backends have not been merged.

Server extensions are GPL-3.0. Exporter-derived code retains its MIT notice. See [THIRD_PARTY.md](THIRD_PARTY.md). This community project is unaffiliated with the game's operators or rights holders.

Run the self-contained tests with `uv run --locked python -m unittest discover -s tests -v` (13 tests). `tests/check_running.py` additionally checks a running local test installation on port 8125 and reads its private linking credentials without printing them. Do not run it against someone else's server.
