# 地政学ニュース図解ジェネレータ (Mock)

安全保障・地政学ニュースを自動取得し、Claude API で要点と関係性を抽出、Mermaid 図を埋め込んだ解説レポート(HTML / Markdown)を生成するツールのモックです。

## サンプル出力 / 公開サイト

GitHub Pages で `docs/` を公開サイトとして配信する前提の構成です。

- 入口: `docs/index.html` (一覧ページ / レポートカード表示)
- 各号: `docs/reports/YYYY-MM-DD.{html, md, json}`
  - `.html` … Mermaid を CDN で描画するフルレポート
  - `.md` … GitHub 上でもネイティブに Mermaid が描画される
  - `.json` … `index.html` 再生成時に読み込むメタデータ

GitHub 上でそのまま読むならこのあたり:

- [docs/reports/ の一覧](docs/reports)
- 最新号(例): [docs/reports/2026-04-17.md](docs/reports/2026-04-17.md)

### GitHub Pages の有効化

リポジトリの **Settings → Pages** で以下を設定します。

1. **Source:** `Deploy from a branch`
2. **Branch:** `main` / フォルダ: `/docs`
3. Save すると数十秒〜1分で `https://<user>.github.io/<repo>/` で公開される

(開発用ブランチでそのまま確認したい場合は、そのブランチを Pages のソース
に一時指定してください。)

### サイトの再ビルド

```bash
python -m src.main --mock --site
# => docs/reports/<today>.html / .md / .json を書き出し、
#    docs/index.html を全レポートから再生成
```

本番モード(Claude API 利用)でも `--site` を付ければ同じ構造で更新されます。
`git add docs/ && git commit && git push` すれば GitHub Pages に反映されます。

### GitHub Actions による定期実行

`.github/workflows/build-site.yml` が以下のタイミングでサイトを自動再ビルドします。

- 毎日 **07:00 JST (22:00 UTC)** の定期実行
- Settings → Actions から **Run workflow** で手動実行
- `main` ブランチの `src/`, `templates/`, `config.yaml` などが更新された push 時

挙動:

1. `apt` で `python3-feedparser` を導入 → 共有 site-packages つきの venv に
   その他の Python 依存をインストール
2. Repository secret に `ANTHROPIC_API_KEY` があれば本番モード、無ければ
   モックモードで `python -m src.main --site` を実行
3. `docs/` に差分があれば `github-actions[bot]` で commit & push

**本番モードを有効化するには:** Repository の Settings → Secrets and variables
→ Actions で `ANTHROPIC_API_KEY` を登録してください。

### メールダイジェスト配信

Actions ワークフローの末尾で `src.digest` が走り、当日号の見出しと
「全文を読む」ボタンを添えたダイジェストメールを SMTP で送信します。
**`SMTP_HOST` と `MAIL_TO` が secrets に設定されている時だけ** 配信が発動する
ので、未設定ならサイトビルドのみ行われます。

必要な Repository Secret:

| Key | 内容 | 例 |
| --- | --- | --- |
| `SMTP_HOST` | SMTP サーバ | `smtp.gmail.com` |
| `SMTP_PORT` | ポート(465 は SSL、587 は STARTTLS) | `587` |
| `SMTP_USER` | 送信アカウント | `you@gmail.com` |
| `SMTP_PASSWORD` | アプリパスワード等 | `xxxx xxxx xxxx xxxx` |
| `MAIL_TO` | 宛先(カンマ区切り可) | `a@example.com, b@example.com` |
| `MAIL_FROM` | 任意。未指定なら `SMTP_USER` を流用 | `"図解便 <you@gmail.com>"` |

Gmail で送る場合は 2段階認証を有効化した上で
[アプリパスワード](https://myaccount.google.com/apppasswords) を発行し、
そのパスワードを `SMTP_PASSWORD` に入れてください。

手元でドライランして見た目を確認:

```bash
python -m src.digest --manifest docs/reports/2026-04-17.json \
                     --site-url https://example.github.io/tiseigaku/ \
                     --dry-run
```

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

- [x] 時系列タイムライン図
- [x] 当事者の関係ネットワーク図
- [x] 参考リンク
- [x] 静的サイト化(`docs/` + GitHub Pages)
- [x] GitHub Actions での定期実行(日次 build & commit)
- [x] メールダイジェスト配信(本文+サイトへのリンク)
- [ ] 重複記事の統合(クラスタリング)
- [ ] 地図 (Leaflet) 埋め込み
