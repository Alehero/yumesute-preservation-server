# Story coverage / シナリオの確認範囲

**Developer reference; no additional setup steps. / 開発者向け資料：追加の導入作業はありません。**

The pinned server-of-dreams archive supplies most scripts. Comparing its usable script/hash entries against the preserved master found these 30 missing scripts. They are now included in the official-CDN downloader; no guessing or authenticated game API is used.

固定版server-of-dreamsのシナリオ・ハッシュ一覧を保存マスターと比較し、不足30件を特定しました。公式CDNからの取得ツールに追加済みです。URLの総当たりや認証付きゲームAPIは使用していません。

| Category / 分類 | Pinned upstream / 上流 | Supplement / 補完 |
|---|---:|---:|
| Main episodes / メイン | 342/362 | 20 |
| Card side episodes / カードサイド | 758/768 | 10 |

- Main / メイン: `1050101`–`1050120` (story `10501`). These IDs also occur in the event table; they are the same 20 scripts, not another 20 missing files. イベント表にも同じIDがありますが、重複して数えません。
- 与那国緋花里「コンクリート・ジャム」: `141491`, `141492`
- 王雪「ストリート・スクリプト」: `141501`, `141502`
- 新妻八恵「主神はあなたを見初めて」: `142511`, `142512`
- 千寿暦「海神は宴の為に海を裂き」: `142521`, `142522`
- 静香「再び繋がる、希望の光へ！」: `150051`, `150052`

On September 29, 2026, all 30 direct URLs downloaded successfully and matched the locally preserved decoded scene bytes by SHA256. Rerunning skipped verified files. A separate preparation test installed all 30 scene files and their metadata in the expected server paths. These are download/installation checks, **not 30 device playback tests**. Voices, backgrounds and character assets come separately from the asset catalogs. Unlock logic and client compatibility still apply. Future CDN availability is not guaranteed.

2026年9月29日、30件すべての直接取得に成功し、展開後のSHA256が保存済み原本と一致しました。再実行時のスキップと、独立した準備環境でのファイル・メタデータ配置も確認しました。これは取得・配置の確認であり、**30件すべてを実機再生したという意味ではありません**。音声・背景・立ち絵等は別途アセットカタログから取得します。解放条件やクライアント互換性の制約は残り、今後の配信継続も保証できません。

The download plan also includes the 54 theater-story bundles, 7 theater bundles and catalog-listed MV resources. This is file coverage, not a claim that every performance or MV has been played through on a fresh client. No broader completeness claim is made for poster stories or unindexed content.

取得予定には劇の54ストーリーバンドル、7劇バンドル、カタログに記載されたMV素材も含まれます。ファイルの対象範囲であり、新規端末ですべての劇・MVの再生を確認したわけではありません。ポスターストーリーや一覧にない内容まで完全とはしていません。

Scene identifiers/metadata reference the preserved [wds-sirius/Adv-Resource](https://github.com/wds-sirius/Adv-Resource) manifest and official responses. Backend credit remains [UnknownSekai/server-of-dreams](https://github.com/UnknownSekai/server-of-dreams), pinned at `3cfca23267fb0f79d7336732db768e1510f20313`. No scene payloads or account credentials are included in this repository.
