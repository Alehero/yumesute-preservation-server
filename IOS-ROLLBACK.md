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

上流には[復号済みIPA](https://github.com/UnknownSekai/server-of-dreams/releases/tag/XAPK%2FIPA)もありますが、こちらではコード解析に使用したもので、**通常の端末へのインストール手順は未検証**です。復号だけで有効なインストール署名が付くわけではなく、この手順で使ったApple認証済みIPAの代わりには扱えません。

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

[クイックスタート](README.md#クイックスタート)に戻り、素材の準備、アカウント作成または取込、サーバー起動を行います。保存ツール用など他のWireGuardトンネルをオフにし、このサーバーのトンネルだけを有効にします。設定ページに表示された**その証明書**をインストールし、「完全な信頼」を有効にしてください。同じ「mitmproxy」という名前でも別の証明書の場合があります。以前動いていたローカル環境の証明書を再利用する場合：

```sh
uv run --locked python server.py start --ca-dir "/以前の環境へのパス/private/mitmproxy"
```

証明書フォルダーと秘密鍵は公開しないでください。新規登録ではローカルの初期セーブを自動選択できます。古いトークンが残る場合や保存アカウントを使う場合は、タイトルの **メニュー → データ連携 → 連携パスワード入力** から`private/linking-credentials.txt`の情報を入力します。Appleや公式ゲームの認証情報とは別の、ローカル専用情報です。

起動中のローカルサーバーから素材のダウンロードを完了させます。IPAだけに全楽曲・音声・MVが含まれるわけではありません。端末とPCを同じWi-Fiに接続し、PCをスリープさせず、ホーム → 楽曲 → リザルト → 再起動で保存を確認してください。

引き直しガチャは、受け取れる初期プレゼントを受け取り、必要なチケットを確認して試してください。排出率は保存用の近似値です。開発中はテスト用チケットも付与したため、全アカウントが最初から2枚持つわけではありません。

HE01-001-APP100の場合はサーバー起動とWireGuard接続先のLAN IPを確認します。ログイン後ガチャが開かない場合は、データ削除の前に証明書とターミナルのTLSエラーを確認してください。タイトルが3.0.0のままなら、対応版への変更ができていません。
