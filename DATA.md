# Local data and backups / ローカルデータとバックアップ

[日本語ガイド](README.md) · [English guide](README.en.md)

## Game-data folder / ゲームデータの構成

Supply an ordinary local directory, not an account ZIP. `prepare` copies these paths:
アカウントZIPではなく、次の構成のフォルダーを用意してください。`prepare` はこれらをコピーします。

```text
game-data/
  master-original.db       # required / 必須：元のMasterMemoryバイナリー
  master-manifest.json     # required / 必須：マスターのマニフェスト
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

Upstream's pinned repository includes its own starter-account data, typed master tables and episode resources. Bootstrap fetches that repository as published; our preparation replaces typed master tables using your raw master. Our source repository does not embed a copy of those resources. Upstream availability is a first-install dependency. Save your prepared installation locally if you need offline reinstallation.

固定コミットの上流リポジトリには初期アカウントデータ、型付きマスター、エピソードのリソースが含まれています。初回準備では上流を取得し、型付きマスターを自分の原本から生成し直します。本リポジトリ内にこれらのコピーは含めません。初回は上流へのアクセスが必要です。再インストールに備え、準備済み環境も手元で保管してください。

## Official-CDN download / 公式CDNからの取得

```sh
uv run --locked python download_data.py --output data
```

This uses the original HTTPS host `assets-e.wds-stellarium.com`, without account credentials or a signed URL. The pinned raw master and compressed catalogs have known SHA256 checksums. Media downloads check response length and Content-MD5 when supplied, then retain local SHA256 receipts. Gzip/Brotli/deflate transfer encoding is decoded; response length and Content-MD5 apply to transferred bytes, while pinned SHA256 applies to decoded files. Existing files without receipts are downloaded again. Files are saved atomically; reruns verify completed files and retry failures. Redirects are not followed. `--workers 1` reduces concurrency (default 4, maximum 8).

公式のHTTPS配信元から、アカウント情報や署名付きURLを使わず取得します。固定版マスター・圧縮カタログは既知のSHA256で検証します。素材は転送時のサイズと、応答にあればContent-MD5を検証し、展開後のSHA256を保存します。HTTPのgzip等による圧縮にも対応しています。検証記録のない既存ファイルは再取得します。中断したファイルを完成扱いにせず、再実行時に完了済みファイルを確認して失敗分を再取得します。リダイレクトには従いません。並列数は既定4、`--workers 1` で減らせます（最大8）。

`--metadata-only` downloads only the master/catalogs and writes `download-plan.json`. `--limit 3` is a small download test, **not a usable complete install**. Neither option proves full coverage. The current plan has 34,057 iOS bundles, 2,012 chart/config paths, 264 comic images and 30 supplemental scene scripts. Some paths may be unavailable. A full post-EOS download has not been tested; representative master/catalog/audio/chart/model/comic downloads have succeeded. This is iOS only; no Android catalog is downloaded.

`--metadata-only` はマスター・カタログと取得予定一覧のみ、`--limit 3` は素材3件のテストです。**どちらも一式の取得ではありません。** 現在の一覧はiOSアセット34,057件、譜面・設定2,012件、コミック264件、補完シナリオ30件です。取得できないパスもあります。サービス終了後の全件取得は未検証で、代表的なマスター・カタログ・音声・譜面・3D素材・コミックの取得を確認しています。Android用カタログは対象外です。

The output matches the folder layout above. `prepare --data-dir data` copies it into the release. Budget for both copies (~45 GB free is a starting estimate). This does not guarantee every static banner, story script, login/event response, or the app executable. The 30 identified main/card script gaps are now fetched and verified; see STORY_COVERAGE.md. An account export still provides only account state. Availability on the official CDN does not establish redistribution permission; this repository contains downloader code and identifiers, not those media files.

出力先は上記の構成になり、`prepare --data-dir data` で配布環境にコピーします。両方を保存する容量（空き約45 GBが目安）が必要です。全バナー・シナリオ・ログイン／イベント応答・アプリ本体の取得を保証するものではありません。確認したメイン・カードシナリオの不足30件は取得・検証対象です。STORY_COVERAGE.mdをご覧ください。アカウントZIPもアカウントの状態のみです。公式CDNで取得できることは再配布の許可を意味しません。本リポジトリに含めるのは取得用コードと識別情報で、素材そのものではありません。

For an already configured account, do not rerun `prepare`. Stop the local server, rerun the downloader, and copy recovered `data/assets/` files into `vendor/server-of-dreams/_data/assets/`, and `data/static-assets/` into `private/static-assets/`, preserving relative paths. Keep the existing account/configuration files. Restart afterward. Do not clear your device cache as a test.

アカウント設定後は `prepare` を再実行しないでください。ローカルサーバーを停止し、取得ツールを再実行して、取得できた `data/assets/` 内のファイルを `vendor/server-of-dreams/_data/assets/` へ、`data/static-assets/` 内を `private/static-assets/` へ、相対パスを保ってコピーします。アカウント・設定ファイルはそのままにし、その後再起動してください。テストのために端末のキャッシュを削除しないでください。

### Supplemental stories / 不足シナリオの補完

The normal download includes the 30 identified missing scene scripts. Each must match its preserved SHA256 before its metadata is written to `data/episode-manifest.json`. The usual `prepare --data-dir data` installs both scripts and metadata in their server locations. No separate story command is needed. The repository contains only IDs, metadata, paths and hashes in `story-supplement.json`; scene payloads are downloaded from the official CDN.

通常の一括取得に、判明している不足シナリオ30件も含まれます。各ファイルのSHA256を確認してから `data/episode-manifest.json` に対応情報を追加し、通常の `prepare --data-dir data` でシナリオとメタデータを所定の場所に配置します。別のシナリオ用コマンドは不要です。リポジトリの `story-supplement.json` にはID・メタデータ・パス・ハッシュだけを収録し、本体は公式CDNから取得します。

## Existing PostgreSQL / 既存のPostgreSQLを利用する場合

Run `prepare`, then edit **only this release folder's** `vendor/server-of-dreams/config.yml` database section to reference a dedicated empty database you own. PostgreSQL 17 is the reference version. Provide host, port, database, username, password. Do not point this at an existing live game database. Skip Docker commands, then run import or fresh creation. The command creates tables and refuses to overwrite accounts. Keep the generated JWT secret stable: changing it invalidates local login tokens.

`prepare` 後、**今回の配布フォルダー内の** `vendor/server-of-dreams/config.yml` のdatabase項目を編集し、専用の空のDBを指定します。基準はPostgreSQL 17です。既存の稼働中ゲームDBを指定しないでください。Dockerのコマンドを省略し、インポートまたは新規作成へ進みます。テーブルは自動作成され、アカウント上書きは拒否されます。JWT秘密鍵を変更するとローカルログイントークンが無効になるため、保持してください。

## Fresh-account resources and story rewards / 新規リソースとシナリオ報酬

Fresh creation starts with the pinned upstream seed: 21 starter actors, zero directly held coins/jewels, and 36 unclaimed inbox entries. This release adds 10,000 歌劇目録 directly to item inventory once during fresh account creation. Inbox rewards are separate and must be claimed. This is a configurable preservation policy, not a reconstruction of official starting balances. Imports receive no extra allowance. The current song exchange consumes 10 tickets; chart exchange consumes 1, subject to existing unlock conditions.

新規作成は固定版上流の初期データ（アクター21体、直接所持するコイン・ジュエル0、未受取プレゼント36件）を使い、保存用の設定として歌劇目録10,000個を作成時に1回だけ追加します。プレゼントの報酬は別途受取が必要です。公式の初期所持数を再現したものではありません。インポートには追加しません。現在の楽曲交換は10個、譜面交換は1個を消費し、既存の解放条件も適用されます。

Story read rewards are implemented from master reward packages. Backend/database checks confirm first-read rewards, the main-story full-read bonus, reading fully after skipping, and no repeated grants. Locked card side stories are rejected; an unlocked side story grants its read reward once and updates character reading progress. For the tested main episode 1010101, read/skip grants 50 free jewels, 1 歌劇目録 and 30 pieces of item 141001; full reading grants one additional 歌劇目録. These examples are not universal rewards for every story. Chapter-completion reward parity and all story categories are not certified by these checks. No new device playback test was performed.

シナリオの読了報酬はマスターの報酬設定から付与します。バックエンドとDBで、初回報酬、メインストーリーの全文読了ボーナス、スキップ後の全文読了、再読時の重複付与防止を確認しました。未解放のカードサイドストーリーは拒否し、解放済みでは報酬と読了進行を保存します。確認したメイン1010101は読了／スキップで無償ジュエル50、歌劇目録1、アイテム141001を30個、全文読了でさらに歌劇目録1を付与します。全話共通の報酬ではありません。この確認だけで章完了報酬の完全一致や全カテゴリの動作を保証するものではなく、今回の実機再生確認は行っていません。

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

Release checks use disposable databases: exporter ZIP validation/import, fresh starter creation, wrong-password rejection, linking/authentication, account-data serialization, master serving and missing-asset behavior. Automated success does not certify fresh-client onboarding or every gameplay feature. Docker Compose and Windows are documented paths; this Mac's validation uses an existing local PostgreSQL 17 instance. See CHANGELOG for final results.

配布用の検証では専用の使い捨てDBを使用します。ZIP検証・インポート、新規初期データ作成、誤パスワードの拒否、連携・認証、アカウントデータ、マスター配信、素材不足時の動作を確認します。自動テスト成功は新規端末の導入や全機能の実機動作を保証しません。このMacでは既存のPostgreSQL 17を利用して検証しており、Docker ComposeおよびWindowsの手順自体は未検証です。結果はCHANGELOGに記録します。
