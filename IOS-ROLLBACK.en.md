# Restore the compatible iOS client

[日本語](IOS-ROLLBACK.md) · [Back to setup](README.en.md)

## Verified scope

On September 30, 2026, an iPhone 14 Pro on iOS 26.6 was replaced **in place** from 3.0.0.432 with **2.31.3.425**, using an Apple-account-authorized IPA. No uninstall, decryption, jailbreak or re-signing was needed. The phone downloaded local server assets, reached home and entered a song. Fresh Player onboarding and draw → reroll → confirmation subsequently worked. This is one-device evidence, not a guarantee. Windows rollback and a full Docker installation have not been device-tested.

**Already on working 2.31.3? Skip rollback.** Disable automatic app updates and offloading on the preservation device. Do not delete/offload the game or use its cache/data-deletion buttons.

## 1. Preserve existing data

Back up the target device and keep your account export separately. Backups may omit the app executable and downloaded caches; they do not guarantee rollback recovery. Keep saved IPAs and server media separately. In-place replacement is not proof that every save/cache survives. Prefer a spare device when protecting your only working installation.

USB is needed for the installation below; normal server play uses Wi-Fi.

## 2. Download the older IPA on a Mac

Use [ipatool](https://github.com/majd/ipatool) with the Apple Account that acquired the game in the relevant App Store region. Enter passwords and 2FA interactively. No connected device is required for downloading.

Our successful test used development commit **387d1a4** after ipatool 2.6.0 authentication failed. This records the tested version, not today's latest release. Follow upstream installation instructions. If stable has the same authentication problem, our development-build installation was:

```sh
# Only if a stable Homebrew version is already linked:
brew unlink ipatool
cd /tmp
brew install --HEAD ipatool
```

HEAD, Apple authentication, and old-version availability can change.

```sh
ipatool auth login --email YOUR_APPLE_ACCOUNT_EMAIL
ipatool list-versions -b com.kms.worlddaistar --platform ipad
ipatool get-version-metadata -b com.kms.worlddaistar --platform ipad --external-version-id 889438247
ipatool download -b com.kms.worlddaistar --platform ipad --external-version-id 889438247 --output "$HOME/Downloads/yumesute-2.31.3.ipa"
```

Verify metadata reports **2.31.3 / 2.31.3.425**. The `ipad` package above was successfully installed on our iPhone. Do not omit the external version ID: the default is the latest app. An account-authorized IPA is not universally installable by other Apple Accounts.

## 3. Replace without uninstalling

```sh
brew install libimobiledevice ideviceinstaller
```

Connect only the target device, unlock it, and accept **Trust This Computer**. Substitute its identifier for `DEVICE_UDID`:

```sh
idevice_id -l
ideviceinstaller -u DEVICE_UDID list -b com.kms.worlddaistar --xml
ideviceinstaller -u DEVICE_UDID upgrade "$HOME/Downloads/yumesute-2.31.3.ipa"
ideviceinstaller -u DEVICE_UDID list -b com.kms.worlddaistar --xml
```

Despite its name, `upgrade` performed our in-place downgrade. Wait for `InstallComplete`, then verify **2.31.3.425** and the title-screen version. If it fails, retain the error; do not automatically uninstall as a workaround.

## 4. Connect and download game data

Return to the [quickstart](README.en.md#quick-start) in the extracted server folder. Prepare the data, start the server, and follow its WireGuard and certificate instructions. **Try normal title-screen login first**: the server attempts to recover the official account remembered by the client. If it does not appear, follow the README's manual recovery options. A client without saved login information starts with a local starter.

Allow downloads from the running local server. The IPA alone does not contain all songs, voices or MVs. Keep the computer awake and both devices on the same Wi-Fi, then test home → song → results → restart.

If the title still says 3.0.0, the replacement did not complete. For connection errors or screens that hang, follow [troubleshooting](README.en.md#troubleshooting); do not uninstall or clear game data as a first response.
