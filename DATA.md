# Local data and backups / ローカルデータとバックアップ

[日本語ガイド](README.md) · [English guide](README.en.md)

This is the reference for **backups, moving an installation, using an existing
PostgreSQL server, and troubleshooting missing game files**. For ordinary setup and
automatic account recovery, follow the README; you do not need to read this document
from beginning to end.

この文書は **バックアップ・環境の移行・既存PostgreSQLの利用・素材不足の調査** のための詳細資料です。
通常の導入とアカウント自動復元はREADMEの手順で進められます。最初からすべて読む必要はありません。

## Game-data folder / ゲームデータの構成

Supply an ordinary local directory, not an account ZIP. `prepare` copies these paths:
アカウントZIPではなく、次の構成のフォルダーを用意してください。`prepare` はこれらをコピーします。

```text
game-data/
  master-original.db       # required / 必須：元のMasterMemoryバイナリー
  master-manifest.json     # required / 必須：マスターのマニフェスト
  help.bin                 # supplemental help index / 追加のヘルプ目次データ
  assets/                 # upstream _data/assets layout / 上流と同じ構成
    2d-assets/ios/catalog.json
    2d-assets/ios/...      # bundle paths relative to the catalog
    3d-assets/ios/catalog.json
    3d-assets/ios/...
    cri-assets/ios/catalog.json
    cri-assets/ios/...
    Notations/<music-id>/<file>.enc
  static-assets/
    production/static-assets/...   # banners, comics, etc. / バナー・コミック等
  scenes/                 # preserved binary story scripts / 保存済みシナリオ
  episode-manifest.json   # optional captured metadata / 任意の取得済みメタデータ
  episodes/               # optional upstream _data/episodes layout
```

Reference asset version is **1.96.0**. The manifest is the decoded `MasterDataManifest` object with snake_case fields such as `uri`, `version`, `publish_timestamp`, and `sas_token`. Keep the original master binary; typed JSON alone may have lost fields. The server strips the manifest SAS token and points clients at a locally served, date-adjusted copy. It does not change the source archive.

基準のアセット版は **1.96.0** です。マニフェストは `MasterDataManifest` のデコード済みJSON（`uri`、`version`、`publish_timestamp`、`sas_token` 等）です。型付きJSONのみでは欠落する項目があるため、元のマスターバイナリーが必要です。配信時にはSASトークンを除き、対象の終了日時を延長したローカルコピーを参照します。原本は変更しません。

An export from the account tool does **not** contain any of the above. Game data already cached on a device is not automatically accessible through USB or included in an ordinary backup. This repository supplies a direct official-CDN downloader, not a hosted data pack. If the pinned master becomes unavailable and you have no local copy, setup is blocked. Media directories are optional for the preparation command, but missing files will block whichever screens or songs need them; they are not optional for those features to work. Already cached media may suffice for some device actions, but that is not a complete preservation guarantee.

アカウント保存ツールのZIPには上記データは含まれません。端末のキャッシュはUSB接続だけで取得できるとは限らず、通常のバックアップにも必ず含まれるわけではありません。本リポジトリでは公式CDNから直接取得するツールを提供しますが、データ一式の再配布はしていません。指定マスターの配信が終了し、手元にもない場合はセットアップできません。素材フォルダーは準備コマンド上は省略可能ですが、その素材を必要とする画面・楽曲は動きません。キャッシュ済みの端末で一部動作しても、完全保存の保証にはなりません。

The first setup automatically downloads a specific version of **server-of-dreams**,
the backend this project builds on, into `vendor/server-of-dreams`. That repository
also supplies starter-save templates and some game-data files. Setup then converts
your downloaded master database into the tables the backend reads. You do not need
to perform these steps yourself.

For backups, the practical point is: **a GitHub source ZIP alone is not a complete
working installation**. Keep your prepared folder (including `vendor/`, `private/`
and configuration), downloaded game data, and a PostgreSQL backup. Rebuilding from
source otherwise depends on upstream downloads still being available. Keeping these
files reduces that dependency; offline reinstalling on a different computer may still
require the appropriate software and dependencies.

初回セットアップでは、このプロジェクトの土台である **server-of-dreams** の指定版を
`vendor/server-of-dreams` に自動取得します。その中の初期セーブのひな形や一部のゲームデータも利用し、
取得したマスターデータをサーバーが読める形式に変換します。手動で行う作業はありません。

バックアップで大事なのは、**GitHubから取得したソースZIPだけでは動作環境を保存したことにならない**点です。
準備済みフォルダー（`vendor/`・`private/`・設定を含む）、取得済みゲームデータ、PostgreSQLのバックアップを
保管してください。ソースから作り直す場合は、外部リポジトリなどが引き続き取得できる必要があります。
これらを保存しておけば再取得への依存を減らせますが、別のPCにオフラインで導入するには、対応する実行環境や依存ソフトも必要です。

## Official-CDN download / 公式CDNからの取得

```sh
uv run --locked python download_data.py --output data
```

This uses the original HTTPS host `assets-e.wds-stellarium.com`, without account credentials or a signed URL. The pinned raw master and compressed catalogs have known SHA256 checksums. Media downloads check response length and Content-MD5 when supplied, then retain local SHA256 receipts. Gzip/Brotli/deflate transfer encoding is decoded; response length and Content-MD5 apply to transferred bytes, while pinned SHA256 applies to decoded files. Existing files without receipts are downloaded again. Files are saved atomically; reruns verify completed files and retry failures. Redirects are not followed. `--workers 1` reduces concurrency (default 4, maximum 8).

公式のHTTPS配信元から、アカウント情報や署名付きURLを使わず取得します。固定版マスター・圧縮カタログは既知のSHA256で検証します。素材は転送時のサイズと、応答にあればContent-MD5を検証し、展開後のSHA256を保存します。HTTPのgzip等による圧縮にも対応しています。検証記録のない既存ファイルは再取得します。中断したファイルを完成扱いにせず、再実行時に完了済みファイルを確認して失敗分を再取得します。リダイレクトには従いません。並列数は既定4、`--workers 1` で減らせます（最大8）。

`--metadata-only` downloads only the master/catalogs and writes `download-plan.json`. `--limit 3` is a small download test, **not a usable complete install**. Neither option proves full coverage. The current plan has 34,057 iOS bundles, 2,012 chart/config paths, 264 comic images, story scripts, and 1,133 pinned supplemental files (1,132 static resources plus help.bin). Some paths may be unavailable. A full post-EOS download has not been tested; representative master/catalog/audio/chart/model/comic downloads have succeeded. This is iOS only; no Android catalog is downloaded.

`--metadata-only` はマスター・カタログと取得予定一覧のみ、`--limit 3` は素材3件のテストです。**どちらも一式の取得ではありません。** 現在の一覧はiOSアセット34,057件、譜面・設定2,012件、コミック264件、シナリオ、追加ファイル1,133件（静的素材1,132件とhelp.bin）です。取得できないパスもあります。サービス終了後の全件取得は未検証で、代表的なマスター・カタログ・音声・譜面・3D素材・コミックの取得を確認しています。Android用カタログは対象外です。

The output matches the folder layout above. `prepare --data-dir data` copies it into the release. Budget for both copies (~45 GB free is a starting estimate). This does not guarantee every static banner, story script, login/event response, or the app executable. An account export still provides only account state. Availability on the official CDN does not establish redistribution permission; this repository contains downloader code and identifiers, not those media files.

出力先は上記の構成になり、`prepare --data-dir data` で配布環境にコピーします。両方を保存する容量（空き約45 GBが目安）が必要です。全バナー・シナリオ・ログイン／イベント応答・アプリ本体の取得を保証するものではありません。アカウントZIPもアカウントの状態のみです。公式CDNで取得できることは再配布の許可を意味しません。本リポジトリに含めるのは取得用コードと識別情報で、素材そのものではありません。

For an already configured account, do not rerun `prepare`. Stop the local server, rerun the downloader, and copy recovered `data/assets/` files into `vendor/server-of-dreams/_data/assets/`, and `data/static-assets/` into `private/static-assets/`, preserving relative paths. Keep the existing account/configuration files. Restart afterward. Do not clear your device cache as a test.

アカウント設定後は `prepare` を再実行しないでください。ローカルサーバーを停止し、取得ツールを再実行して、取得できた `data/assets/` 内のファイルを `vendor/server-of-dreams/_data/assets/` へ、`data/static-assets/` 内を `private/static-assets/` へ、相対パスを保ってコピーします。アカウント・設定ファイルはそのままにし、その後再起動してください。テストのために端末のキャッシュを削除しないでください。

## Existing PostgreSQL / 既存のPostgreSQLを利用する場合

Run `prepare`, then edit **only this release folder's** `vendor/server-of-dreams/config.yml` database section to reference a dedicated empty database you own. PostgreSQL 17 is the reference version. Provide host, port, database, username, password. Do not point this at an existing live game database. Skip Docker commands, then continue with `uv run --locked python server.py start`; it creates the starter automatically. The command creates tables and refuses to overwrite accounts. Keep the generated JWT secret stable: changing it invalidates local login tokens.

`prepare` 後、**今回の配布フォルダー内の** `vendor/server-of-dreams/config.yml` のdatabase項目を編集し、専用の空のDBを指定します。基準はPostgreSQL 17です。既存の稼働中ゲームDBを指定しないでください。Dockerのコマンドを省略し、`uv run --locked python server.py start` へ進みます。初期セーブは自動作成されます。テーブルは自動作成され、アカウント上書きは拒否されます。JWT秘密鍵を変更するとローカルログイントークンが無効になるため、保持してください。

## Song-ticket gift settings / 楽曲チケットの設定

Fresh creation retains the upstream starter seed. The default direct allowance (`fresh_song_tickets`) is now 0. Both fresh and imported accounts receive the permanent **楽曲解放サポート** inbox gift: 10,000 歌劇目録, once per account, without expiry. `preservation_song_tickets` configures new issuance; changing it does not rewrite an existing gift. Previously granted inventory is retained, and those accounts are eligible too. The issuance ledger survives claimed-inbox cleanup. Claiming is transactional and repeated/concurrent claims do not duplicate rewards. This is a local preservation policy, not an official event. Song exchange costs 10 tickets and chart exchange costs 1, subject to unlock conditions.

新規・インポート済みアカウントの両方に「楽曲解放サポート」（歌劇目録10,000個）を1回、期限なしで付与します。受取操作が必要です。初期所持への直接付与は既定で0になりました。既に受け取った初期所持分は減らしません。数量設定は新規付与にのみ反映し、受取済みプレゼントを整理しても再発行しません。公式イベントではなく保存用の設定です。

## Backup / バックアップ

Stop the game and the server terminal first. Keep PostgreSQL running while making its dump:
ゲームとサーバーを止め、PostgreSQLを起動した状態で実行します。

```sh
docker compose exec db pg_dump -U yumesute -d yumesute -Fc -f /tmp/yumesute-save.dump
docker compose cp db:/tmp/yumesute-save.dump ./yumesute-save.dump
```

Move the dump into a private backup folder immediately; it contains account data. Also back up `private/`, `.env`, `vendor/server-of-dreams/config.yml`, `preservation-rules.json`, and your local game-data files. The dump alone does not include photos stored on disk, login-association files, signing secrets, or assets. Keep the original exporter ZIP separately. The Docker volume persists across `docker compose stop` and `down`; **`docker compose down -v` deletes that volume**. Do not use it on saves you want to keep.

ダンプにはアカウント情報が入るため、直後に非公開のバックアップ先へ移動してください。`private/`、`.env`、`vendor/server-of-dreams/config.yml`、`preservation-rules.json`、ゲームデータも一緒に保存します。DBダンプだけでは写真ファイル、ログインの対応付け、秘密鍵、素材は保存されません。元のアカウントZIPも別途保管してください。Dockerの `stop` や `down` ではDBボリュームは残りますが、**`docker compose down -v` はボリュームを削除します**。

Restore first into a separate installation/database, using the same source revision and backed-up config/private files. For an empty new Docker database, copy the dump into the container and use `pg_restore -U yumesute -d yumesute --no-owner /tmp/yumesute-save.dump`. Never restore over a working account as an initial test. Run `doctor` before reconnecting a device. The original export contains only the state when it was captured; importing it again is not a backup of later private-server progress.

復元テストは別のインストール・空のDBに対して行い、同じソース版と保存した設定・privateファイルを使います。空のDocker DBにはダンプをコピーし、コンテナー内で `pg_restore -U yumesute -d yumesute --no-owner /tmp/yumesute-save.dump` を実行します。稼働中のアカウントへの上書きで試さないでください。端末を接続する前に `doctor` を実行します。元のZIPは取得時点の状態であり、その後のローカル進行は含みません。

## Verification boundaries / 検証範囲

Release checks use disposable databases: exporter ZIP validation/import, fresh starter creation, wrong-password rejection, linking/authentication, account-data serialization, master serving and missing-asset behavior. Automated success does not certify fresh-client onboarding or every gameplay feature. Docker Compose and Windows are documented paths; the tested setup uses an existing local PostgreSQL 17 instance. See CHANGELOG for final results.

配布用の検証では専用の使い捨てDBを使用します。ZIP検証・インポート、新規初期データ作成、誤パスワードの拒否、連携・認証、アカウントデータ、マスター配信、素材不足時の動作を確認します。自動テスト成功は新規端末の導入や全機能の実機動作を保証しません。確認済みの環境では既存のPostgreSQL 17を利用して検証しており、Docker ComposeおよびWindowsの手順自体は未検証です。結果はCHANGELOGに記録します。

## Automatic account recovery / アカウントの自動復元

Known local tokens and transfer credentials are resolved before any official request.
For an unknown official identity, recovery uses HTTPS transfer/authentication and
`GET /api/data/user`; it does not call the official login-reward endpoint. Local
credentials are never forwarded when their linking ID matches the configured local ID.
Unknown official credentials are sent only to the fixed official API host; redirects
are refused. Passwords and login tokens are represented locally by keyed digests,
not stored in plaintext by this feature. Separate diagnostic traffic captures may
contain credentials; keep any such captures private.

Imports, the raw snapshot, its compatibility baseline and credential mappings commit
in one PostgreSQL transaction. Failure rolls everything back. Recovering an identity
already stored locally adds credential mappings without replacing its progress.
The preview supports one recovered official identity per installation, alongside the
original starter; it is not a general multi-account hosting service. An outage before
recovery binds the attempted credential to the existing starter permanently. Unknown
credentials after recovery fail during outages, preserving account selection.

Timeouts, network unavailability, HTTP 5xx and recognized explicit service-closure
faults allow the pre-recovery starter fallback. Incorrect credentials, unknown faults,
HTTP 4xx, redirects and malformed account data do not. Future official EOS responses
may differ; unknown responses deliberately fail without creating or replacing a save.
Set `official_account_recovery` to `false` to stop official requests. Existing local
mappings remain usable. This option does not disable initial game-data downloads.

A normal database dump includes `preservation_recovery` and
`preservation_credentials`. Preserve the configuration's `jwt_secret` as well: it
signs local tokens and keys credential digests. Keep `private/account.json`, local
linking credentials and the other files listed in the backup section. Do not rotate
secrets casually or publish snapshots/database dumps. Media and filesystem photos
still need their own backups. The initial official retrieval is an availability
window, not a promise of permanent official access.

登録済みのアカウントは公式へ問い合わせず、ローカルから読み込みます。未登録の場合のみ
公式の連携・認証・アカウント取得APIを使用し、ログイン報酬のAPIは呼びません。
復元データ・元の応答・連携情報の対応付けはDBにまとめて保存し、途中で失敗した場合は
全体を取り消します。同じ公式アカウントを再取得しても、ローカルで進めた状態を上書きしません。
公式アカウントは1環境につき1件で、元の初期セーブも残します。復元前の接続不能時に
初期セーブへ紐付けた連携情報は、以後もローカルを優先します。

連携情報は秘密鍵付きのハッシュとして保存します。この機能はパスワードやトークンを
平文で保存しませんが、別途行う通信記録には含まれる場合があります。
DBのバックアップに加えて `jwt_secret` を含む設定と `private/` も保管してください。
初回の公式データ取得は配信状況に依存し、将来の取得を保証するものではありません。

## Pinned static resources and help / バナー・ヘルプの補完

For missing banners/help, use the [troubleshooting repair commands](README.en.md#missing-banners-or-help-pages). Normal first-time download and preparation already include these resources. The installer validates all supplemental inputs before copying, replaces each destination file atomically, and leaves accounts and configuration unchanged. If interrupted during copying, rerun it. Download availability is not guaranteed; see [CHANGELOG](CHANGELOG.md) for coverage and verification history.

バナー・ヘルプの不足には[困ったときの補完手順](README.md#バナーやヘルプが表示されない場合)を使ってください。通常の初回取得・準備には含まれています。全入力の検証後にファイル単位で置き換え、アカウント・設定は変更しません。コピー中に中断した場合は再実行できます。配信継続は保証できません。収録範囲と検証履歴は[CHANGELOG](CHANGELOG.md)を参照してください。

## Restore an existing export ZIP / 保存済みZIPの復元

Try automatic login and then official Data Link/browser recovery first. If those
cannot retrieve the account and you already have an export ZIP, prepare a **separate
empty installation/database**, start its database, and run this before its first
`server.py start`:

```sh
uv run --locked python server.py import-account "/path/to/your-account.zip"
```

The importer refuses to overwrite existing accounts. Keep your original ZIP and any
working installation. The ZIP restores the state at export time, not subsequent local
progress. Start the new server and connect using its setup page. Try normal login if
the export contains a bridge for that device; otherwise use the **local** credentials
in its `private/linking-credentials.txt` through the game's Data Link menu.

まずは通常ログインによる自動復元、次に公式のデータ連携やブラウザー復元を試してください。
取得できず、以前保存したZIPがある場合は、**別の空の環境・DB**を準備してDBを起動し、
サーバーの初回起動前に上記コマンドを実行します。既存アカウントへの上書きは拒否します。
元のZIPと動作中の環境は保持してください。ZIPは保存時点の状態で、その後のローカル進行は含みません。
新しいサーバーを起動して接続し、通常ログインできなければ、新環境の `private/linking-credentials.txt` にある
ローカル連携情報をゲームの「データ連携」で入力してください。
