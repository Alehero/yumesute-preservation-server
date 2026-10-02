# iOS版を対応バージョンに戻す

[English](IOS-ROLLBACK.en.md) · [セットアップへ戻る](README.md)

## 確認できた範囲

2026年9月30日、iOS 26.6のiPhone 14 Proで、Apple Accountから取得したIPAを使い、**3.0.0.432から2.31.3.425への上書きインストール**を確認しました。削除・復号・脱獄・再署名は行っていません。その後、ローカルサーバーから素材を取得し、ホーム到達と楽曲開始を確認しています。新規Playerの初期進行、初回ガチャ・引き直し・確定も実機確認済みです。1台での結果であり、すべての環境での成功を保証するものではありません。Windowsでの復元とDockerを使った一連の実機手順は未検証です。

**2.31.3で動いている端末は、この作業をする必要はありません。** 自動アップデートとアプリの自動取り除きを無効にし、アプリの削除・取り除きやゲーム内のデータ削除は避けてください。

## 1. 現在のデータを保管する

対象端末をバックアップし、自分のアカウント保存ZIPも別途保管してください。バックアップにはアプリ本体やダウンロード済みキャッシュが含まれない場合があり、完全な復元は保証できません。IPAとサーバー用素材は別に保管します。上書きに成功しても、すべてのセーブ・キャッシュが保持されるとは限りません。唯一動いている端末がある場合は、別の端末で試すことをおすすめします。

以下のインストールにはUSBケーブルが必要です。通常のプレイはWi-Fi接続です。

## 2. Macで旧版IPAを取得する

[ipatool](https://github.com/majd/ipatool)を使い、対象ストア地域でゲームを取得したApple Accountで認証します。パスワードと2段階認証コードは対話プロンプトで入力してください。ダウンロードだけなら端末の接続は不要です。

こちらではipatool 2.6.0の認証が失敗し、開発版コミット **387d1a4** で成功しました。これは検証時の版であり、現在の最新版を示すものではありません。導入は上流の案内に従ってください。同じ認証問題がある場合、検証時には次の方法で開発版を導入しました。

```sh
# Homebrewの安定版が既にリンクされている場合のみ:
brew unlink ipatool
cd /tmp
brew install --HEAD ipatool
```

HEADの内容、Appleの認証方式、旧版の配信状況は変わる可能性があります。

```sh
ipatool auth login --email YOUR_APPLE_ACCOUNT_EMAIL
ipatool list-versions -b com.kms.worlddaistar --platform ipad
ipatool get-version-metadata -b com.kms.worlddaistar --platform ipad --external-version-id 889438247
ipatool download -b com.kms.worlddaistar --platform ipad --external-version-id 889438247 --output "$HOME/Downloads/yumesute-2.31.3.ipa"
```

メタデータが **2.31.3 / 2.31.3.425** であることを確認してください。この`ipad`指定で取得したパッケージをiPhoneに導入できました。版IDを省略すると最新版が対象になるため、省略しないでください。取得したIPAが別のApple Accountでも導入できるとは限りません。

## 3. アプリを削除せず上書きする

```sh
brew install libimobiledevice ideviceinstaller
```

対象端末だけを接続してロックを解除し、「このコンピュータを信頼」を許可します。`DEVICE_UDID`を一覧に表示された識別子に置き換えます。

```sh
idevice_id -l
ideviceinstaller -u DEVICE_UDID list -b com.kms.worlddaistar --xml
ideviceinstaller -u DEVICE_UDID upgrade "$HOME/Downloads/yumesute-2.31.3.ipa"
ideviceinstaller -u DEVICE_UDID list -b com.kms.worlddaistar --xml
```

コマンド名は`upgrade`ですが、検証では旧版への上書きができました。`InstallComplete`を待ち、**2.31.3.425**とタイトル画面のバージョンを確認します。失敗した場合はエラーを残し、回避策としてすぐにアプリを削除しないでください。

## 4. サーバーへ接続して素材を取得する

展開したサーバーのフォルダーに戻り、[クイックスタート](README.md#クイックスタート)に沿って素材の準備、サーバー起動、WireGuard・証明書の設定を行います。**まずはタイトルから通常のログインを試してください。** 端末に残った公式ログイン情報で自動復元を試みます。元のアカウントが表示されない場合はREADMEの手動復元へ進んでください。ログイン情報のない端末ではローカルの初期セーブを利用します。

起動中のローカルサーバーから素材のダウンロードを完了させます。IPAだけに全楽曲・音声・MVが含まれるわけではありません。端末とPCを同じWi-Fiに接続し、PCをスリープさせず、ホーム → 楽曲 → リザルト → 再起動で保存を確認してください。

タイトルが3.0.0のままなら、対応版への変更が完了していません。接続エラーや画面が開かない場合は[困ったとき](README.md#困ったとき)を参照し、すぐにアプリやゲームデータを削除しないでください。
