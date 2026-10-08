# Yumesute Preservation Server

[日本語](README.md) · **English**

An unofficial local server for preserved **World Dai Star: Yume no Stellarium** data. Built on [UnknownSekai/server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), with additions and repairs for progression, upgrades, rewards, and customization. The upstream implementation made this work possible.

**Read first: this does not restore the official service or provide the game app. An account ZIP alone is not enough.** You need a compatible installed client, master data, and the media needed by that client. This repository does not distribute an IPA/APK, game media, or anyone's account.

- **3.0.0 is unsupported.** Use 2.31.3; see the [rollback guide](IOS-ROLLBACK.en.md) for installation and compatibility details. Do not delete or update a working older client.
- Home, solo play, results surviving restart, and several progression features were device-confirmed in the development setup. This is distinct from device-testing the entire release installer.
- This is an early **personal, home-LAN** package, not a public multi-user hosting service. Each installation supports one recovered official identity alongside its retained starter save. Windows instructions are provided but are not device-tested.

## Requirements

1. A device with a compatible game client. **“Fresh account” does not mean a fresh 3.0.0 app installation will work.**
2. Mac or Windows PC on the same Wi-Fi. No USB cable is required for play; the optional iOS rollback procedure needs one.
3. [uv](https://docs.astral.sh/uv/getting-started/installation/), [Git](https://git-scm.com/downloads), and running [Docker Desktop](https://docs.docker.com/desktop/) for PostgreSQL. Existing PostgreSQL users can follow [DATA.md](DATA.md).
4. The official [WireGuard app](https://www.wireguard.com/install/) on the device.
5. Roughly **45 GB of free space** for game data. The commands below download it while the official CDN remains available. If you already have a data folder, see [DATA.md](DATA.md).
6. Optional: an existing account-export ZIP, or your official linking ID/password. Automatic recovery can retrieve your save while the official authentication and account-data endpoints remain available; an exporter is not required for that path.

## Quick start

[Download ZIP](https://github.com/Alehero/yumesute-preservation-server/archive/refs/heads/main.zip), extract it, and open Terminal or PowerShell in that folder. Run all commands below from there. First setup downloads dependencies and the pinned upstream source, so internet access is needed for installation.

### 0. Check the app version

Use **2.31.3 (build 2.31.3.425)**. If you accidentally updated to 3.0.0, follow the [Mac/iOS rollback guide](IOS-ROLLBACK.en.md) first. It documents our verified in-place replacement and its limits. Keep an already-working older installation unchanged. USB is needed for rollback, not normal play.

### 1. Set up and start

Keep Docker Desktop running and the computer awake, then run:

```sh
uv run --locked python server.py setup
```

This checks prerequisites, downloads the reference iOS data, prepares the server,
starts PostgreSQL if needed, and launches the server. Interrupted downloads reuse
verified files. Rerun the same command after fixing a failure; an existing configured
account is reused, never recreated. Existing installations skip downloading and
preparation—use `repair-data` below for missing files.

**There are currently 30 known missing files:** the default chart/configuration paths
under `assets/Notations/901/`, `902/`, `903/`, `904/` and `10172/` return HTTP 404.
The mapped alternate charts for 901–904 and the released song entry 172 are included
in the download plan; these missing default paths do not mean those songs are entirely missing.

If setup stops with these 30 failures, check `data/download-report.jsonl`, then rerun:

```sh
uv run --locked python server.py setup --allow-missing
```

Verified downloads are reused. If you used `--data-dir`, keep that option on the retry.
The flag accepts **all** missing downloads, not just these 30, so investigate any additional
failures before continuing. It does not recover unavailable files; other missing media
may prevent corresponding songs or screens from working. Setup does not provide the app
or make 3.0.0 compatible.

Already have a game-data folder? Use:

```sh
uv run --locked python server.py setup --data-dir "/path/to/game-data" --skip-download
```

On Windows a path can be `"C:\Users\You\Documents\game-data"`.
[Existing PostgreSQL and individual setup commands](DATA.md) remain available.

### 2. Connect the device

A setup page opens in your browser. If it does not, open `private/setup.html`.

1. Set the device's Wi-Fi **HTTP Proxy to Off**. Disable other WireGuard tunnels, including the exporter tunnel.
2. In WireGuard, choose **Add a Tunnel → Create from QR code**, scan the setup-page QR, and turn it on. The QR contains a private key: do not share it.
3. Open the displayed certificate URL in device Safari.
4. Install the downloaded profile under **Settings → General → VPN & Device Management**.
5. Match the certificate name/fingerprint shown in setup; another “mitmproxy” profile may have a different key. Enable **full trust** under **General → About → Certificate Trust Settings**. Installing the profile alone is insufficient.
### 3. Log in and claim song tickets

**Try normal login first—no account ZIP or manual import is needed.** After connecting, fully close and reopen the game and tap the title screen. The server uses the official login
information already remembered by the client to attempt recovery. Once saved locally,
your account loads from this server on subsequent logins.

This requires the client to retain usable official login information and the official
account-retrieval endpoints to remain available. If your account does not appear,
use the manual recovery options below. A client with no saved login starts with a
local starter account; it cannot identify an old official account automatically.

All local accounts receive a one-time **10,000 song-ticket (歌劇目録)** gift.
Claim **楽曲解放サポート** from Presents. Normal song/chart unlock conditions still apply.

Once recovered, recognized logins use your local save even if the official service closes. If recovery is unavailable before any official account has been saved, login may select the local starter. Use manual recovery below if this happens; do not delete the starter or repeat setup. See [recovery details and backups](DATA.md#automatic-account-recovery--アカウントの自動復元).

Check that progress persists through **home → solo play → results → app restart**.

### Relaunch after a restart

Open Docker Desktop, then double-click **Start-Mac.command** or **Start-Windows.cmd**
in the same server folder. Alternatively, run:

```sh
uv run --locked python server.py start
```

`start` reuses the installation, starts the matching Docker database if necessary,
and detects the current LAN IP. It remembers custom server/tunnel/certificate ports.
It does not download game data. If setup is incomplete, it reports what needs fixing.
If the IP changed, update WireGuard's Endpoint as described under troubleshooting.

Keep the computer awake and terminal open while playing. To stop, turn WireGuard off
and press **Control+C**; optionally stop the database with `docker compose stop`.
On Mac, if double-clicking the launcher is blocked, use the terminal command above.

## Manual recovery if automatic login did not restore your account

**Only if automatic recovery did not restore your account**, choose **title Menu → データ連携 → 連携パスワード入力** and enter your **official linking ID and password**. Check the displayed account name. To select this installation's original starter or manually imported save instead, use the **local** credentials in `private/linking-credentials.txt`. Apple sign-in recovery is not implemented. Linking changes the account selected on the receiving device.

If in-game Data Link is unsuccessful or you want a backup before importing, use the browser recovery page.

With the server running, open **[Account recovery](http://127.0.0.1:8125/recovery)**

on the **server computer**, or follow its setup-page link. Use the chosen backend
port if you changed it. Enter your **official linking ID/password**, not your Apple
ID or local server credentials. The page downloads a verified ZIP and also keeps a
private copy under `private/recovered-exports`; this does not change your save.

The same page now offers **Export account** for current local progress, default-on
encrypted official-token preservation (with an opt-out), and a separate passphrase-protected credential
export. See [backup and recovery details](DATA.md#export-current-progress-and-preserve-credentials--セーブと認証情報の保存), including options for users already connected locally.

After saving the ZIP, optionally choose **Import locally** within 15 minutes.
The starter is retained, and progress on an already-recovered official account is
never overwritten. Then use your official linking credentials through the game's
Data Link screen to select the local recovered account. This explicit flow also
works when ordinary login is already linked to a starter. It never falls back to a
starter on failure. Initial recovery still requires working official endpoints.

Already have a saved export ZIP and official recovery is unavailable? Follow the
[saved-ZIP import instructions](DATA.md#restore-an-existing-export-zip--保存済みzipの復元).
That command requires a separate empty installation if this server has already created
an account; do not delete a working save to make room for it.

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

- **Stopped connecting after sleep or a Wi-Fi change:** follow the recovery steps below; the computer may have received a different LAN IP address.
- **Port conflict / “Error logged during startup”:** another server may already be running. Follow [Stop a duplicate server](#stop-a-duplicate-server-port-conflict) below before changing ports. Defaults: backend TCP 8125, WireGuard UDP 51822, certificate TCP 8766, PostgreSQL TCP 55433.
- **Certificate/tunnel failure:** check same LAN, guest-network isolation, computer firewall, and full certificate trust. Allow only the required traffic on your home network. Internet port forwarding is unnecessary.
- **Missing images/songs or HTTP 404:** check `uv run --locked python server.py doctor` and `logs/backend.log`. Use the repair command below for covered media; files unavailable from the CDN still need another local source. Do not clear the app cache to troubleshoot this.
- **EOS after linking on 3.0.0:** use the compatible client version described in the [rollback guide](IOS-ROLLBACK.en.md).
- **Database connection failure:** check Docker Desktop and `docker compose ps`. Changing `.env` does not change a password inside an existing database volume. Do not casually delete the volume.

See [DATA.md](DATA.md) for backups, data layout, and existing PostgreSQL. Issues in Japanese or English are welcome. Include OS/client versions, the failing step, and a sanitized error. **Do not upload account ZIPs, private folders, QR codes, or linking credentials.**

### Stop a duplicate server (port conflict)

`Error logged during startup` is a general message. Check the terminal and
`logs/backend.log` for **address already in use**, **Errno 48/98**, or **WinError
10048** before treating it as a port conflict. A server started in another terminal,
a launcher window, or a background session can still own the ports.

1. Finish any game action and turn the device's WireGuard tunnel off.
2. In the terminal/window running the old server, press **Control+C** and wait for
   it to exit. Closing the setup browser tab does **not** stop the server. Start only
   one copy of the same installation.
3. If you cannot find that window, identify the process before stopping anything.

**macOS — Terminal:**

```sh
lsof -nP -iTCP:8125 -iTCP:8766 -iUDP:51822
ps -p 12345 -o pid=,ppid=,command=
```

Replace `12345` with a PID from `lsof`; do not paste it unchanged. Check the command
and project path. A `tools/serve.py` entry is the backend child: inspect its PPID
with the same `ps` command to find this installation's `python server.py start`
parent. After confirming the correct parent PID, stop it gracefully:

```sh
kill -INT 12345
```

Use the confirmed **parent** PID here. Wait a few seconds and rerun `lsof`.
If a verified orphaned backend remains, inspect and stop that specific PID too.
Do not use `killall python`, `pkill python`, or force-kill unrelated processes.

**Windows — PowerShell:**

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 8125,8766 } | Select-Object LocalAddress,LocalPort,OwningProcess
Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 51822 } | Select-Object LocalAddress,LocalPort,OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId = 12345" | Select-Object ProcessId,ParentProcessId,CommandLine
```

Replace `12345` with the reported owning PID. Inspect the parent as needed to find
this installation's `server.py start` process. Prefer **Control+C** in its console.
If the console is unavailable, after checking the process and path, stop only that
server's process tree with `taskkill /PID 12345 /T` using the confirmed parent PID.
This is a fallback termination, not a guarantee of graceful shutdown. Recheck the
ports afterward. Never end every Python process. Windows steps are not device-tested.

Once the old server has exited, run from the same installation folder:

```sh
uv run --locked python server.py start
```

Wait for **Local server tunnel ready**, then enable the device tunnel again.
If the port belongs to another application that needs to stay running, choose free
ports instead, for example:

```sh
uv run --locked python server.py start --port 8126 --wg-port 51823 --cert-port 8767
```

Update the device's WireGuard endpoint port (or re-import the generated QR), and use
the new certificate URL shown in setup. Do not change ports merely to run two copies
against the same save. A database-port conflict is separate: inspect `docker compose
ps` and your PostgreSQL configuration; do not kill PostgreSQL or delete its volume to
free a game-server port. No account reset or certificate replacement is needed.

### Windows: certificate downloads on the PC, but hangs on the phone

Ethernet on the PC and Wi-Fi on the phone work together if the router allows communication between them. Use the PC's active Ethernet IPv4 address from `ipconfig`, with the certificate port shown in setup (default TCP 8766).

1. Keep the server running and confirm it prints **Local server tunnel ready**. Temporarily turn **WireGuard off on the phone** and open `http://YOUR_PC_IP:8766/cert.cer` in Safari. Downloading the certificate directly over the LAN does not require WireGuard.
2. If the URL works on the PC but hangs on the phone, check **Settings → Network & internet → Ethernet → Network profile type**. On a **trusted home network**, select **Private**. Firewall rules restricted to Private networks do not apply while Ethernet is marked Public. Do not mark public/shared networks as trusted just for this setup.
3. If needed, open **PowerShell as Administrator** and add these rules. Substitute your configured ports if different:

   ```powershell
   New-NetFirewallRule -DisplayName "Yumesute certificate" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8766 -Profile Private -RemoteAddress LocalSubnet
   New-NetFirewallRule -DisplayName "Yumesute tunnel" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 51822 -Profile Private -RemoteAddress LocalSubnet
   ```

   If you already added these rules, changing the trusted network profile to Private is enough; do not add duplicates. Keep the firewall enabled. No router port forwarding is needed.
4. Retry the certificate download. If it still hangs, check guest Wi-Fi/client isolation and other VPNs. After installing and trusting the certificate, turn the game tunnel back on. WireGuard being enabled alone does not prove connectivity; check for a recent handshake.

### Gacha screen hangs: check the active server's certificate

A gacha-screen hang was resolved by trusting the matching server certificate. This is a troubleshooting lead, not proof that every gacha freeze has the same cause.

- Download and install the certificate from the **currently running server's setup page**. A different computer or installation may use a different certificate, even if both profiles are named “mitmproxy”.
- Match the certificate identity shown in setup, then enable **Settings → General → About → Certificate Trust Settings → Full Trust** on the iPhone/iPad. Installing the profile alone is insufficient.
- Fully close and reopen the game. If it still hangs, report whether it happens when opening Gacha, during a pull, or returning from results, together with sanitized terminal TLS errors. Do not share certificate private keys or WireGuard QR codes.

### Connection stopped after sleep, reconnecting Wi-Fi, or a router restart

The computer must remain awake while playing. A WireGuard toggle showing “on” does
not prove the server is reachable. After waking, check the computer’s **current LAN
IPv4 address**; DHCP can assign a different address even if its MAC address is unchanged.

1. On Mac, open **System Settings → Wi-Fi → Details → TCP/IP** for the connected
   network. On Windows, run `ipconfig` and use the IPv4 address of the connected
   Wi-Fi/Ethernet adapter, not a VPN adapter or the default gateway.
2. Stop the old server with **Control+C**, make sure PostgreSQL is running, and restart
   using that address. For example (replace the example IP with your own):

   ```sh
   uv run --locked python server.py start --host 192.168.1.22
   ```

   Keep any custom `--port`, `--wg-port`, `--cert-port`, or `--ca-dir` options you use.
3. In the device’s WireGuard app, edit the existing tunnel’s peer **Endpoint** to the
   new computer IP, keeping its existing UDP port. For a default installation,
   `192.168.1.21:51822` would become `192.168.1.22:51822`. Do not change keys or the
   tunnel’s Interface Address. Alternatively, replace the profile using the refreshed
   setup-page QR; do not leave duplicate tunnels enabled.
4. Toggle the tunnel off/on, then fully close and reopen the game. If the computer’s
   IP did not change, restart the server and toggle the tunnel before changing settings.

An IP change alone does **not** require reinstalling certificates, importing the
account again, or clearing game data. If it still fails, check that both devices are
on the same LAN, the server terminal has no startup error, and the firewall allows
the configured UDP port. Keep the laptop awake for the session.

**IP address versus MAC address:** WireGuard’s Endpoint uses the computer’s IP
(e.g. `192.168.1.22`). A MAC address identifies its network interface to the local
network. Modern macOS offers **Private Wi-Fi Address: Off, Fixed, or Rotating** in
Wi-Fi → Details. “Fixed” keeps a private address for that network; “Rotating” changes
it periodically. See [Apple’s private Wi-Fi address guide](https://support.apple.com/en-us/102509).

For a home network you administer, a router **DHCP reservation** for the server
computer can reduce repeated Endpoint edits. If its private Wi-Fi address rotates,
consider **Fixed** for that home network and reserve the IP against the Wi-Fi MAC
actually shown for it. A fixed MAC alone does not guarantee a fixed IP. There is no
need to turn private addressing off on every network or change the phone/iPad’s MAC
to match the server. Changing the Mac’s Wi-Fi identity may itself require reconnecting
and updating the reservation/Endpoint once.

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
the game. If a screen hangs, check terminal TLS errors and the certificate identity.

### Missing images, songs or help pages

Stop the game server (Control+C), then run:

```sh
uv run --locked python server.py repair-data
```

This rechecks/downloads covered files and repairs the **installed copies**, preserving
accounts, configuration and keys. Verified files are reused. It can take time to check
the full data set. Use `--data-dir "/path/to/game-data"` if you downloaded elsewhere.
If some files remain unavailable, inspect `download-report.jsonl`; add `--allow-missing`
only to install the verified files while accepting those gaps. Rerun after interruption,
then restart with `uv run --locked python server.py start`. Do not clear the app cache.
A smaller banner/help-only repair remains available in [DATA.md](DATA.md).

## Development and attribution

Backend: [server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), pinned at `3cfca23267fb0f79d7336732db768e1510f20313`. Protocol reference: [OpenSiriusServer](https://github.com/TeamOpenSirius/OpenSiriusServer), `536004f17e174e2190d247edad2622ca2133b181`. These two backends have not been merged.

Server extensions are GPL-3.0. Exporter-derived code retains its MIT notice. See [THIRD_PARTY.md](THIRD_PARTY.md). This community project is unaffiliated with the game's operators or rights holders.

[Developer verification instructions](tests/README.md).
