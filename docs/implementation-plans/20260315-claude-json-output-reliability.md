# Claude JSON 出力信頼性改善 実装計画書

状態: 下書き
作成日: 2026-03-15
作成者: Claude

## 1. 目的

Claude プロバイダーの構造化 JSON 出力が agentic モードで不安定な問題を修正する。
プロンプトの JSON 出力指示を強化し、`--output-format text` を正式仕様として確定する。

## 2. 背景

- `claude.ts` は元々 `--output-format json` で実装されたが、これは会話ログ全体の JSON エンベロープを返すため、スキーマ準拠の生 JSON が直接取れなかった
- 未コミット変更で `--output-format text` + `--json-schema` に修正済み。この組み合わせが正しい（raw なスキーマ準拠 JSON が返る）
- しかし agentic モード（`--permission-mode bypassPermissions` でツール使用後）では `--json-schema` の強制が不安定で、Claude がテキスト（自然言語）を返すことがある
- 実際に plan-review で 6 回中 2 回が JSON ではなく完全なプレーンテキスト（Markdown）で返ってきた
- 一方、`workflow-agent.ts` では未コミット変更でプロンプトにスキーマ埋め込み + JSON 強制指示を追加済みであり、run-loop ではテキスト返却は観測されていない

### 失敗の原因分析

| コードパス | プロンプトの JSON 指示 | スキーマ埋め込み | テキスト返却 |
|---|---|---|---|
| `workflow-agent.ts` (run-loop) | 強い（未コミット変更で強化済み） | あり | 未観測 |
| `plan-review.ts` | 弱い（「JSONを返します」のみ） | なし | **6回中2回発生** |

**結論**: `--json-schema` フラグだけでは不十分。プロンプト側で明示的に JSON 出力を強制する指示が必要。

### 実験結果

プロンプトに以下を追加して plan-review を 3 回連続実行したところ、全て JSON で成功した（強化前は 33% 失敗率）:

```
## [重要] 出力形式

**必ず JSON 形式のみで出力してください。**

- 上記 JSON Schema に厳密に一致する JSON オブジェクトだけを返すこと
- JSON の前後にテキスト・説明・挨拶・要約を絶対に付けないこと
- コードブロック (```) で囲まないこと
- 出力の最初の文字は `{`、最後の文字は `}` であること
```

## 3. 変更対象

- `packages/agent-loop-cli/src/plan-review.ts` — プロンプトにスキーマ埋め込み + JSON 強制指示を追加
- `packages/agent-loop-core/src/claude.ts` — `--output-format text` の正式採用、`extractJson` 失敗時は即エラー（リトライしない）、タイムアウト値確定
- `packages/agent-loop-core/src/run-loop.ts` — タイムアウト値変更
- `packages/agent-loop-cli/src/code-review.ts` — タイムアウト値変更

## 4. 影響範囲

- `runStructuredClaudePrompt()` を呼ぶすべてのコードパス（plan-review、code-review、run-loop 経由の implementer/reviewer）
- plan-review のプロンプト構築（`buildPlanReviewPrompt`）

## 5. 非対象範囲

- Gemini / Codex プロバイダーの出力処理 — 別の仕組みで動作しており影響なし
- `workflow-agent.ts` のプロンプト強化 — 未コミット変更として既に実施済み。本計画では触らずそのまま採用する
- `--output-format` の値を `json` や `stream-json` に変更すること — `text` が正しいことを確認済み

## 6. 実装方針

### 6.1 プロンプト強化（根本対策）

`plan-review.ts` のプロンプト構築箇所に、以下を適用する（`workflow-agent.ts` は未コミット変更で既にスキーマ埋め込み + JSON 出力指示を実施済みかつテキスト返却未観測のため、本計画では触らない）:

1. **スキーマ本文をプロンプトに埋め込む** — `--json-schema` フラグだけに頼らず、プロンプト内でも参照可能にする
2. **[重要] タグ付きの強い JSON 強制指示** — テキスト出力を明示的に禁止する

```
## [重要] 出力形式

**必ず JSON 形式のみで出力してください。**

- 上記 JSON Schema に厳密に一致する JSON オブジェクトだけを返すこと
- JSON の前後にテキスト・説明・挨拶・要約を絶対に付けないこと
- コードブロック (```) で囲まないこと
- 出力の最初の文字は `{`、最後の文字は `}` であること
- JSON のキー名は schema の `properties` に記載されたとおりに保ち、人間向けの Markdown 文字列は日本語で書くこと
```

### 6.2 `--output-format text` の正式採用

未コミット変更を正式仕様とする。理由:

- `--output-format json` は会話メタデータのエンベロープを返すため、スキーマ準拠の生 JSON を直接取得できない
- `--output-format text` + `--json-schema` が Claude CLI でスキーマ準拠の raw JSON を得る正しい組み合わせ

### 6.3 `extractJson` — 失敗時は即エラー

`extractJson` は安全ネットとして維持するが、JSON 抽出に失敗した場合はリトライせず即座にエラーとする（exit code != 0）。プロンプト強化により JSON が返る前提で、テキスト返却は異常系として扱う。

### 6.4 タイムアウトの整理

llm-quality-judge での個別 Claude 呼び出し実績（8 成功 run のファイルタイムスタンプから計測）:

**Implementer:**

| Run | 時間 |
|---|---|
| phase1-config-schema | 22-43s |
| phase2-executor | 67s (1.1m) |
| phase3-llm-client | 98s (1.6m) |
| phase7-docs | 134s (2.2m) |
| phase5-judge | 139s (2.3m) |
| phase6-consistency | 190s (3.1m) |
| phase4-inference | 403s (6.7m) |
| coding-rules-cleanup | 486s (8.1m) |

**Reviewer:**

| Run | 時間 |
|---|---|
| phase1-config-schema | 40s |
| phase6-consistency | 96s (1.6m) |
| phase3-llm-client | 98s (1.6m) |
| phase4-inference | 108s (1.8m) |
| phase5-judge | 119s (1.9m) |
| phase2-executor | 122s (2.0m) |
| coding-rules-cleanup | 125s (2.0m) |
| phase7-docs | 127s (2.1m) |

**分析:**
- Reviewer は安定: 最大 127s (2.1分)
- Implementer はバラつき大: 最大 486s (8.1分)
- 旧デフォルト 420s (7分) では coding-rules-cleanup の Implementer (486s) がタイムアウトする

タイムアウト設計（リトライなし）:

現在のコードの値（未コミット変更を含む）:

| 定数 | コミット済み | 未コミット（現在動作中） |
|---|---|---|
| `claude.ts` `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` | 420,000ms (7分) | 900,000ms (15分) |
| core `run-loop.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | 240,000ms (4分) | 600,000ms (10分) |
| `code-review.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | 480,000ms (8分) | 480,000ms (8分、変更なし) |

本計画での変更:

| 定数 | 新値 | 理由 |
|---|---|---|
| `claude.ts` `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` | 900,000ms (15分) | 未コミット値を据え置き。最大実績 486s に対して十分な余裕 |
| core `run-loop.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | 1,200,000ms (20分) | 外側タイムアウトは内側の `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS`（900,000ms）を上回る必要がある。1,200,000ms は 900,000ms に対して十分な余裕を持つ |
| `code-review.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | 1,200,000ms (20分) | 同上。外側タイムアウトは内側の 900,000ms を上回る必要がある |

**タイムアウト階層制約**: `run-loop.ts` / `code-review.ts`（外側）→ `runShellCommand` → workflow-agent プロセス → `runStructuredClaudePrompt`（内側 `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS`）。外側タイムアウトが内側より短いと、Claude の応答を待たずにプロセスが kill される。将来 `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` を変更する際は、外側タイムアウトも連動して調整すること。

リトライなしのため、タイムアウトは 1回の実行を収容すれば十分。

## 7. 実装手順

### Step 1: `plan-review.ts` — プロンプト強化

`buildPlanReviewPrompt` にスキーマ埋め込みと JSON 強制指示を追加する（実験で検証済みのコードを正式採用）。

### Step 2: `claude.ts` — `--output-format text` を正式コメント化 + リトライ削除

`buildStructuredClaudeCommand` 内の `--output-format text` にコメントを追加し、なぜ `text` なのかを記録する。

```typescript
return [
  "claude -p",
  // text を使用: json はエンベロープを返すため、--json-schema と組み合わせて
  // スキーマ準拠の raw JSON を得るには text が正しい
  "--output-format text",
  "--input-format text",
  "--permission-mode bypassPermissions",
  "--no-session-persistence",
  `--json-schema ${escapedSchema}`,
].join(" ");
```

`extractJson` は維持するが、失敗時はリトライせず即座に例外を投げる（現在の動作と同じ）。リトライ機構は追加しない。

### Step 3: タイムアウト整理

| 定数 | 変更 |
|---|---|
| `claude.ts` `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` | `900_000` 据え置き |
| core `run-loop.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | `600_000` → `1_200_000` に延長 |
| `code-review.ts` `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` | `480_000` → `1_200_000` に延長 |

### Step 4: `extractJson` と `buildPlanReviewPrompt` を export 化

テスト可能にするため、以下を export する:
- `claude.ts` から `extractJson`
- `plan-review.ts` から `buildPlanReviewPrompt`

### Step 5: テスト追加

1. `extractJson` のユニットテスト — raw JSON、コードブロック付き、テキスト混在、JSON なしのケースを検証
2. `buildPlanReviewPrompt` のテスト — スキーマ埋め込みと JSON 強制指示が含まれることを検証

## 8. 必須確認項目

- `packages/agent-loop-core/src/claude.ts` — `--output-format text`、タイムアウト値、`extractJson` の export
- `packages/agent-loop-cli/src/plan-review.ts` — プロンプト構築
- `packages/agent-loop-core/src/run-loop.ts` — タイムアウト値
- `packages/agent-loop-cli/src/code-review.ts` — タイムアウト値
- 既存テスト

## 9. 必須 checks

- `npm run build`
- `npm test`

## 10. 受け入れ条件

- `--output-format text` が正式採用され、コード内にその理由がコメントとして記録されていること
- plan-review のプロンプトにスキーマ埋め込みと JSON 強制指示が含まれること
- JSON 抽出失敗時はリトライせず即座にエラーになること
- `extractJson` のユニットテストが追加されていること
- plan-review を 3 回連続実行して全て JSON で成功すること

## 11. エスカレーション条件

- プロンプト強化後もテキスト返却が再発する場合 → Claude API 直接呼び出し（`output_config` による constrained decoding）への移行を検討
- `--json-schema` の不安定さが Claude CLI のバージョンアップで解消された場合 → プロンプト内の冗長な指示を簡素化

## 12. 実装役向けメモ

- `workflow-agent.ts` のプロンプト強化（スキーマ埋め込み + JSON 強制指示）は未コミット変更として既に存在する。本計画では触らずそのまま採用する
- `plan-review.ts` の変更は既に実験済み（3 回連続成功）。Step 1 はこの実験コードを正式採用するだけ
- Gemini / Codex プロバイダーにはこの問題は存在しない
- リトライ機構は不要。プロンプト強化が根本対策であり、それでもテキスト返却が起きた場合は即エラーとする
