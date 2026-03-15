# Claude JSON 出力信頼性改善 計画レビュー記録

状態: レビュー済み
レビュー日: 2026-03-15
レビュー担当: Claude
対象計画書: `docs/implementation-plans/20260315-claude-json-output-reliability.md`

## 1. 結論

- `needs-fix`

## 2. 総評

計画の方向性（プロンプト強化を根本対策とし `--output-format text` を正式採用、リトライなし）は正しく、実験データに裏付けられている。ただし、タイムアウトの正当化に事実誤認があり、テスト計画に未記載の前提がある。修正自体は軽微で人間判断は不要。

## 3. 指摘一覧

### F-01

- 種別: `ambiguity`
- 重大度: `medium`
- 内容: セクション 6.1 で「JSON 出力を使う **全て** のプロンプト構築箇所で、以下を統一的に適用する」と宣言しているが、`workflow-agent.ts` は非対象範囲として除外されている。`workflow-agent.ts` の出力指示（`## 出力指示` セクション、lines 158-163）は `plan-review.ts` の `## [重要] 出力形式` より明らかに弱い（ `{` で始まり `}` で終わること、コードブロック禁止、挨拶禁止などの指示がない）。現時点で `workflow-agent.ts` でテキスト返却が観測されていないのは事実だが、「統一的に適用する」という記述と非対象範囲が矛盾している。
- 修正案: セクション 6.1 の「全てのプロンプト構築箇所で」を「plan-review.ts のプロンプト構築箇所で」に修正するか、`workflow-agent.ts` を非対象にする理由（テキスト返却未観測 + 既にコミット予定の変更として存在）を 6.1 内で明示する。

### F-02

- 種別: `ambiguity`
- 重大度: `medium`
- 内容: セクション 6.4 の `run-loop.ts` タイムアウト正当化で「implementer + checks + reviewer の **合計** 最大実績 611s に余裕を持たせる」と記載されているが、`run-loop.ts` の `DEFAULT_AGENT_COMMAND_TIMEOUT_MS` は **コマンド単位** で適用される（implementer 呼び出し: line 185、reviewer 呼び出し: line 253）。合計ではなく個別のコマンドタイムアウトなので、この正当化は事実と異なる。

真の制約は **タイムアウトの階層**: `run-loop.ts`（外側）→ `runShellCommand` → workflow-agent プロセス → `runStructuredClaudePrompt`（内側 `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS = 900,000ms`）。外側タイムアウトが内側より短いと、Claude の応答を待たずにプロセスが kill される。現在の `600,000ms < 900,000ms` は既にこの問題を抱えている。`code-review.ts` も同様（`480,000ms < 900,000ms`）。
- 修正案: セクション 6.4 のタイムアウト設計表の「理由」列を修正する:
- `run-loop.ts`: 「外側タイムアウトは内側の `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS`（900,000ms）を上回る必要がある。1,200,000ms は 900,000ms に対して十分な余裕を持つ」
- `code-review.ts`: 同上

また、この階層制約を計画書に明記し、将来 `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` を変更する際の注意点として残す。

### F-03

- 種別: `missing-check`
- 重大度: `low`
- 内容: Step 5 で `buildPlanReviewPrompt` のテスト追加を記載しているが、この関数は `plan-review.ts` 内の非公開関数（`function buildPlanReviewPrompt`、line 224）である。テストするには export が必要だが、Step 4 では `extractJson` の export のみ言及しており、`buildPlanReviewPrompt` の export について記載がない。
- 修正案: Step 4 に `buildPlanReviewPrompt` の export も追加するか、Step 5 のテスト方針を「`runPlanReview` の統合テスト経由でプロンプト内容を検証する」等に修正する。

## 4. 影響範囲レビュー

影響範囲の記述は正確。`runStructuredClaudePrompt()` を呼ぶ全コードパス（plan-review、code-review、run-loop 経由の implementer/reviewer）が対象として挙げられている。Gemini/Codex プロバイダーへの影響なしという判断も `structured-prompt.ts` のルーティングコードと整合する。

`plan-review.ts` の未コミット変更（スキーマ埋め込み + JSON 強制指示）は既にコード上に存在しており（lines 231-255）、計画書の記述と一致する。`claude.ts` の `--output-format text` も既にコード上に反映済み（line 24）。

## 5. checks レビュー

`npm run build` と `npm test` は必須 checks として妥当。既存テストは `test/process.test.ts`（vitest）のみで、`extractJson` やプロンプト構築のテストは存在しない。Step 5 でこれらを追加する方針は適切。

受け入れ条件の「plan-review を 3 回連続実行して全て JSON で成功すること」は手動検証であり自動化されないが、プロンプト強化の有効性を確認する最終チェックとして合理的。

## 6. 人間判断が必要な点

人間判断が必要な点はない。全ての指摘は計画書の記述修正で解決可能。方針・アーキテクチャ・スコープに関する大きな判断は不要。

## 7. 再レビュー条件

- タイムアウトの正当化（F-02）を修正し、階層制約を明記した場合
- セクション 6.1 の「統一的に適用」の記述を修正した場合
- `buildPlanReviewPrompt` のテスト方針を明確にした場合

上記 3 点が修正されれば再レビューなしで実装に進めてよい。

