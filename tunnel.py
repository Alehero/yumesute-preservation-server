"""Cross-platform local WireGuard capture with a device setup page."""

import argparse
import asyncio
import html
import io
import ipaddress
import json
import os
from pathlib import Path
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import webbrowser

import mitmproxy_rs
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
import qrcode
import qrcode.image.svg

class LocalServer:
    def __init__(self, port): self.port = port
    def request(self, flow):
        host = flow.request.pretty_host
        names = (host, getattr(flow.server_conn, "sni", None))
        host = next((n for n in names if n in ("lb-api.wds-stellarium.com", "assets-e.wds-stellarium.com", "lb-realtime.wds-stellarium.com")), host)
        if host in ('lb-api.wds-stellarium.com', 'assets-e.wds-stellarium.com', 'lb-realtime.wds-stellarium.com'):
            flow.request.host = '127.0.0.1'
            flow.request.port = self.port
            flow.request.scheme = 'http'
            flow.request.headers['Host'] = host


ROOT = Path(__file__).resolve().parent


def lan_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # Route lookup only: UDP connect sends no data.
        sock.connect(("192.0.2.1", 9))
        return sock.getsockname()[0]


def write_private(path, text):
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def setup_page(private, host, wg_port, cert_port):
    keys_path = private / "wireguard-keys.json"
    if keys_path.exists():
        keys = json.loads(keys_path.read_text())
    else:
        keys = {
            name: mitmproxy_rs.wireguard.genkey()
            for name in ("server_key", "client_key")
        }
        write_private(keys_path, json.dumps(keys))
    config = (
        "[Interface]\nPrivateKey = "
        + keys["client_key"]
        + "\nAddress = 10.0.0.1/32\nDNS = 10.0.0.53\n\n"
        "[Peer]\nPublicKey = "
        + mitmproxy_rs.wireguard.pubkey(keys["server_key"])
        + f"\nAllowedIPs = 0.0.0.0/0\nEndpoint = {host}:{wg_port}\nPersistentKeepalive = 25\n"
    )
    write_private(private / "iPad.conf", config)
    qr = qrcode.make(config, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    qr.save(buffer)
    svg = buffer.getvalue().decode().split("?>")[-1]
    url = f"http://{host}:{cert_port}/cert.cer"
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Yumesute local server / ローカルサーバー</title>
<style>body{{font:18px system-ui;max-width:850px;margin:40px auto;padding:20px;line-height:1.6;background:#faf8f6;color:#26202a}}svg{{width:330px;height:330px;background:white}}code{{background:#eee;padding:4px}}li{{margin:14px 0}}</style>
<h1>Yumesute local server / ローカルサーバー</h1><p>This page and QR code are private. Keep the terminal running.</p>
<ol><li>Connect the iPad/iPhone and computer to the same Wi-Fi. In iPad Wi-Fi settings, set HTTP Proxy to Off.</li>
<li>Install the official WireGuard app on the iPad. Choose Add a Tunnel → Create from QR code, scan below, name it Yumesute Local, and switch it on.</li>
<li>On the iPad, open Safari and type <strong>{html.escape(url)}</strong>. Download the certificate.</li>
<li>Open Settings → General → VPN &amp; Device Management → downloaded mitmproxy profile → Install.
Then General → About → Certificate Trust Settings → enable full trust for this mitmproxy certificate.</li>
<li>Fully close and reopen the compatible game. Imported accounts with a bridge should log in normally. Otherwise use Menu → Data Link → linking password, with private/linking-credentials.txt.</li>
<li>Test home → solo play → results → restart to check persistence. Keep your original account export.</li>
<li>Switch WireGuard off, stop the terminal with Control+C, and remove the certificate profile and export tunnel when finished.</li></ol>
<h2>日本語</h2><ol><li>端末とパソコンを同じWi-Fiに接続し、端末のHTTPプロキシをオフにします。</li>
<li>WireGuardでQRコードを読み取り、トンネルを有効にします。他の保存用トンネルはオフにしてください。</li>
<li>Safariで上記の証明書URLを開き、設定 → 一般 → VPNとデバイス管理からインストールします。さらに「一般 → 情報 → 証明書信頼設定」で完全な信頼を有効にします。</li>
<li>対応版のゲームを終了して開き直します。自動ログインできない場合は、タイトル画面のメニュー → データ連携 → 連携パスワード入力で private/linking-credentials.txt の情報を入力します。</li>
<li>ホーム → ソロプレイ → リザルト → 再起動の順で保存を確認してください。終了時はWireGuardをオフにします。</li></ol>
<p>このQR・連携情報・privateフォルダーは公開しないでください。3.0.0は未対応です。元の保存ZIPは保管してください。</p>
{svg}<p>Connection: {host}, UDP {wg_port}. Certificate download: TCP {cert_port}. Allow these on your private LAN if the firewall prompts.</p>
<p>No USB cable, jailbreak, Apple ID password, purchases, or resource spending is needed. Requires a compatible installed client and locally supplied game data. Version 3.0.0 is not supported.</p>
<p>If certificate download fails: check tunnel is on, both devices are on the same Wi-Fi, no guest-network isolation, and the computer firewall allows Python.
If login fails, see README.md. Missing assets cannot be recovered from an account ZIP.</p></html>"""
    path = private / "setup.html"
    write_private(path, page)
    return path


class CertificateServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve_certificate(host, port, cert):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # No directory listing, arbitrary paths, account exports, or CA private keys.
            if self.path != "/cert.cer" or not cert.is_file():
                self.send_error(404)
                return
            data = cert.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-x509-ca-cert")
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Content-Disposition", 'attachment; filename="yumesute-export-ca.cer"'
            )
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = CertificateServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def run(args):
    os.umask(0o077)
    host = str(ipaddress.IPv4Address(args.host or lan_ip()))
    private = ROOT / "private"
    private.mkdir(mode=0o700, exist_ok=True)
    page = setup_page(private, host, args.wg_port, args.cert_port)
    # Keep non-game TLS connections opaque. The certificate download has no TLS.
    opts = options.Options(
        confdir=str(private / "mitmproxy"),
        listen_host=host,
        mode=[f"wireguard:{private / 'wireguard-keys.json'}@{args.wg_port}"],
        allow_hosts=[r"^(lb-api|assets-e|lb-realtime)\.wds-stellarium\.com:443$"],
        ssl_insecure=False,
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.options.update(upstream_cert=False, connection_strategy="lazy")
    master.addons.add(LocalServer(args.port))
    task = asyncio.create_task(master.run())
    server = None
    try:
        # Do not display a ready page until the tunnel actually starts.
        for _ in range(100):
            await asyncio.sleep(0.1)
            if task.done():
                await task
                raise RuntimeError("Capture server exited during startup")
            instances = list(master.addons.get("proxyserver").servers)
            if instances and all(s.is_running for s in instances):
                break
        else:
            raise RuntimeError(
                "Tunnel startup timed out; check the selected IP and UDP port"
            )
        server = serve_certificate(
            host, args.cert_port, private / "mitmproxy/mitmproxy-ca-cert.cer"
        )
        print(
            f"Local server tunnel ready at {host}. Follow the setup page:\n{page}\nWaiting for private-server play...",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open(page.as_uri())
        await task
    finally:
        if server:
            server.shutdown()
            server.server_close()
        master.shutdown()
        await task
        print(
            "Server tunnel stopped. Turn off the device WireGuard tunnel.",
            flush=True,
        )

