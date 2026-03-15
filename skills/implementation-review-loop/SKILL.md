---
name: implementation-review-loop
description: 'Start the agent-loop implementation and review cycle for an approved plan in the current repository. Determines --implementer-provider and --reviewer-provider from user intent. Triggers: 実装レビュー反復を開始, 実装とレビューを回す, approved plan を実装する.'
argument-hint: 'Plan path, for example: docs/implementation-plans/20260314-example.md'
allowed-tools: 'Bash(uvx:*)'
---

# Implementation Review Loop

## When to Use

- 承認済みの実装計画書から実装とレビューの反復を開始したいとき
- 対象リポジトリに `agent-loop` の初期化が入っているか確認しつつ `loop run` まで進めたいとき
- 実行後に run directory と最終 status を確認したいとき

## Assumptions

- 現在の作業ディレクトリが対象リポジトリ
- `uv` がインストール済み
- 対象計画書は承認済み

## Provider Determination

`--implementer-provider` と `--reviewer-provider` を以下のルールで決定する。

### Self Provider (自分自身)

あなたが何のエージェントかに基づいて self provider を決定する:
- Codex として動作中 → `codex`
- Claude として動作中 → `claude`
- Gemini として動作中 → `gemini`

### 決定ルール

| ユーザーの指示パターン | implementer-provider | reviewer-provider |
|---|---|---|
| 指定なし（例: 「実装開始」） | self | self |
| 「xxxでレビュー」 | self | xxx |
| 「実装はxxx レビューはyyy」 | xxx | yyy |

- **デフォルト**: 指定がなければ両方とも self provider を使う
- **レビュアーのみ指定**: 「gemini で実装同期開始」のようにプロバイダー名が1つだけ言及され、かつそれが self と異なる場合、implementer は self、reviewer が指定されたプロバイダーになる
- **両方指定**: 「実装はclaude、レビューはgemini」のように明示された場合はそのまま使う

有効なプロバイダー値: `codex`, `claude`, `gemini`

## Procedure

1. 現在のリポジトリに `.agent-loop/config.json` が無ければ、`uvx --from "${CLAUDE_SKILL_DIR}" agent-loop init --repo "$PWD" --mode compat-loop --provider <self>` を実行する（`<self>` は self provider）。
2. `uvx --from "${CLAUDE_SKILL_DIR}" agent-loop doctor --repo "$PWD"` を実行して設定を確認する。
3. 上記の Provider Determination ルールに従い `--implementer-provider` と `--reviewer-provider` を決定する。
4. `uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run` を実行する。両方同じプロバイダーの場合は `--provider` 短縮形を使ってよい。
5. 実行完了後、run directory と最終 status を報告する。
6. 途中で失敗した場合は、失敗したコマンドと原因を要約して止まる。

## Command Templates

```bash
# 両方同じプロバイダー（短縮形）
uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run --repo "$PWD" --plan <plan-path> --provider <self>

# クロスベンダー
uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run --repo "$PWD" --plan <plan-path> --implementer-provider <ip> --reviewer-provider <rp>
```
