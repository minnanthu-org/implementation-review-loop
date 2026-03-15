---
name: implementation-review-loop
description: 'Run plan review or implementation-review loop for a plan in the current repository. Triggers: 計画書をレビュー, 計画をレビュー, plan review, 実装を開始, 実装レビュー反復を開始, 実装とレビューを回す, approved plan を実装する.'
argument-hint: 'Plan path, for example: docs/implementation-plans/20260314-example.md'
allowed-tools: 'Bash(uvx:*)'
---

# Implementation Review Loop

## Mode Detection

ユーザーの指示から実行モードを判定する。

| ユーザーの指示パターン | モード |
|---|---|
| 「計画書をレビュー」「計画をレビューして」「plan review」 | plan-review |
| 「実装を開始」「実装とレビューを回す」「approved plan を実装」 | loop-run |

## Assumptions

- 現在の作業ディレクトリが対象リポジトリ
- `uv` がインストール済み

## Provider Determination

### Self Provider (自分自身)

あなたが何のエージェントかに基づいて self provider を決定する:
- Codex として動作中 → `codex`
- Claude として動作中 → `claude`
- Gemini として動作中 → `gemini`

### 決定ルール

| ユーザーの指示パターン | provider |
|---|---|
| 指定なし | self |
| 「xxxで」「xxxに」 | xxx |

loop-run モードでは implementer と reviewer を個別に指定できる:

| ユーザーの指示パターン | implementer-provider | reviewer-provider |
|---|---|---|
| 指定なし（例: 「実装開始」） | self | self |
| 「xxxでレビュー」 | self | xxx |
| 「実装はxxx レビューはyyy」 | xxx | yyy |

有効なプロバイダー値: `codex`, `claude`, `gemini`

## Procedure: plan-review

1. 現在のリポジトリに `.agent-loop/config.json` が無ければ、`uvx --from "${CLAUDE_SKILL_DIR}" agent-loop init --repo "$PWD" --mode compat-loop --provider <self>` を実行する。
2. `uvx --from "${CLAUDE_SKILL_DIR}" agent-loop plan review --repo "$PWD" --plan <plan-path> --provider <provider>` を実行する。
3. 出力されたレビュー結果のパスと verdict を報告する。
4. 途中で失敗した場合は、失敗したコマンドと原因を要約して止まる。

## Procedure: loop-run

1. 現在のリポジトリに `.agent-loop/config.json` が無ければ、`uvx --from "${CLAUDE_SKILL_DIR}" agent-loop init --repo "$PWD" --mode compat-loop --provider <self>` を実行する。
2. `uvx --from "${CLAUDE_SKILL_DIR}" agent-loop doctor --repo "$PWD"` を実行して設定を確認する。
3. Provider Determination ルールに従い `--implementer-provider` と `--reviewer-provider` を決定する。
4. `uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run` を実行する。両方同じプロバイダーの場合は `--provider` 短縮形を使ってよい。
5. 実行完了後、run directory と最終 status を報告する。
6. 途中で失敗した場合は、失敗したコマンドと原因を要約して止まる。

## Command Templates

```bash
# plan-review
uvx --from "${CLAUDE_SKILL_DIR}" agent-loop plan review --repo "$PWD" --plan <plan-path> --provider <provider>

# loop-run: 両方同じプロバイダー（短縮形）
uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run --repo "$PWD" --plan <plan-path> --provider <self>

# loop-run: クロスベンダー
uvx --from "${CLAUDE_SKILL_DIR}" agent-loop loop run --repo "$PWD" --plan <plan-path> --implementer-provider <ip> --reviewer-provider <rp>
```
