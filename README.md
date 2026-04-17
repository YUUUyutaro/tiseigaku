# 地政学ニュース図解ジェネレータ (Mock)

安全保障・地政学ニュースを自動取得し、Claude API で要点と関係性を抽出、Mermaid 図を埋め込んだ解説レポート(HTML / Markdown)を生成するツールのモックです。

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
