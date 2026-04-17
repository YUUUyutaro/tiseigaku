# 地政学ニュース図解ジェネレータ (Mock)

安全保障・地政学ニュースを自動取得し、Claude API で要点と関係性を抽出、Mermaid 図を埋め込んだ解説レポート(HTML / Markdown)を生成するツールのモックです。

## サンプル出力

GitHub は Markdown 内の Mermaid ブロックを直接描画するので、生成物は
ブラウザで直接読めます。

- [docs/sample-report.md](docs/sample-report.md) — モック実行で出力された Markdown レポート (図が描画されます)
- [docs/sample-report.html](docs/sample-report.html) — HTML 版 (raw ダウンロード → ローカルで開く)

## 処理フロー

```
[RSS / Web]
    │ fetch
    ▼
[記事プール]
    │ analyze (Claude API)
    ▼
[構造化データ: 要約/当事者/争点/影響]
    │ visualize
    ▼
[Mermaid 図 + 本文]
    │ render
    ▼
[HTML / Markdown レポート]
```

## クイックスタート (モックモード)

API キーなしで、同梱のサンプルニュースからレポートを生成します。

```bash
pip install -r requirements.txt
python -m src.main --mock
# => output/report.html, output/report.md が生成されます
```

### Debian / Ubuntu での注意

`feedparser` の旧依存 `sgmllib3k` が `setuptools` のバージョン不整合で pip
ビルドに失敗することがあります。その場合は apt 版を使ってください。

```bash
sudo apt install -y python3-feedparser
pip install anthropic jinja2 pyyaml python-dateutil
```

### ブラウザでレポートを開く

`output/report.html` は Mermaid の CDN を読み込むため、`file://` では
CORS で図が描画されない場合があります。ローカルに簡易 HTTP サーバを立てて
開いてください。

```bash
python -m http.server 8000 --directory output
# ブラウザで http://localhost:8000/report.html を開く
```

## 本番モード

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m src.main --config config.yaml
```

## モジュール構成

| モジュール | 役割 |
| --- | --- |
| `fetcher.py` | RSS フィードから記事を取得 (モックは JSON 読込) |
| `analyzer.py` | Claude API で記事を構造化 (要約・当事者・争点など) |
| `visualizer.py` | 構造化データから Mermaid 図を生成 |
| `reporter.py` | Jinja2 で HTML / Markdown レポートを出力 |
| `main.py` | 上記を統合する CLI エントリポイント |

## 今後の拡張予定

- [ ] 重複記事の統合 (クラスタリング)
- [ ] 時系列タイムライン図
- [ ] 地図 (Leaflet) 埋め込み
- [ ] 配信(Slack / メール)
- [ ] スケジュール実行 (cron / GitHub Actions)
