# Attribution and licensing

- **UnknownSekai/server-of-dreams** — https://github.com/UnknownSekai/server-of-dreams — GPL-3.0; pinned commit `3cfca23267fb0f79d7336732db768e1510f20313`. This is the backend, not merely a protocol inspiration. Bootstrap clones it without modifying tracked source. Local overrides are in `tools/`; `server.py` creates private configuration and data. Full upstream source and license remain in the checkout.
- **TeamOpenSirius/OpenSiriusServer** — https://github.com/TeamOpenSirius/OpenSiriusServer — commit `536004f17e174e2190d247edad2622ca2133b181`, used as an independent protocol reference. Its backend code is not merged into this package.
- **Alehero/yumesute-account-exporter** — https://github.com/Alehero/yumesute-account-exporter — MIT. `exporter.py`, `protocol.py`, test fixtures and the original tunnel setup implementation derive from that project. MIT notice retained in `EXPORTER-LICENSE`; tunnel changes implement private routing rather than capture.
- Server extensions and packaging here are provided under GPL-3.0 (`LICENSE`). No ownership of the official game, characters, music, app, or other assets is claimed. Code licensing does not grant rights to distribute game assets.
- Runtime dependencies and exact versions are recorded in `uv.lock`; dependencies retain their respective licenses. PostgreSQL runs as a separate service.

日本語：本サーバーは server-of-dreams を基盤としています。OpenSiriusServer はプロトコルの参考であり、サーバー実装の統合ではありません。保存ツール由来のコードにはMITライセンスの表示を保持しています。公式アプリや素材の権利を主張するものではありません。
