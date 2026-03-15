# agent-loop

実装計画書のレビューと、実装・コードレビューの反復ループを自動で回すスキル。

プロンプトで実装者・レビュアーの役割を定義し、CLI がループを制御する。各ラウンドでエージェントがプロンプトに従って実装・レビューを行い、approve されるまで繰り返す。実装とレビューに異なるプロバイダー (Claude, Codex, Gemini) を指定するクロスベンダー構成にも対応。

## インストール

対象リポジトリに `skills/implementation-review-loop/` をコピーする。

```bash
cp -r skills/implementation-review-loop /path/to/your-repo/.claude/skills/implementation-review-loop
```

要件: Python 3.11+, `uv`

## 使い方

エージェントに自然言語で指示する。

### 計画書のレビュー

```
docs/implementation-plans/my-plan.md の計画を codex でレビューして
```

### 実装とレビューの反復ループ

```
docs/implementation-plans/my-plan.md の実装を開始 実装はcodex レビューはgemini
```

指定がなければ、自分自身で実装・レビュー:

```
docs/implementation-plans/my-plan.md の実装を開始
```

## 開発

このリポジトリ自体の開発用。

```bash
uv pip install -e .
uvx --from skills/implementation-review-loop agent-loop --help
```

### Layout

```text
skills/
  implementation-review-loop/
    SKILL.md                    # スキル定義
    pyproject.toml              # パッケージ設定
    src/agent_loop/             # ソースコード
      core/                     # コアロジック (contracts, providers, run-loop)
      cli/                      # CLI コマンド
      assets/                   # スキーマ、テンプレート、プロンプト
pyproject.toml                  # 開発用 (tests, mypy)
tests/
docs/
  implementation-plans/
  plan-reviews/
```

### CLI リファレンス

```bash
agent-loop init --repo <repo> --mode compat-loop [--provider claude|codex|gemini]
agent-loop doctor --repo <repo>
agent-loop plan new --repo <repo> --slug <slug> --title <title>
agent-loop plan review --repo <repo> --plan <plan-path>
agent-loop code review --repo <repo> --plan <plan-path>
agent-loop loop init --repo <repo> --plan <plan-path>
agent-loop loop run --repo <repo> --plan <plan-path> [--provider <provider>]
```
