# Implementer プロンプトへの前回試行コンテキスト追加

状態: 下書き
作成日: 2026-03-21
作成者: Claude

## 1. 目的

`loop run` の試行 2 以降で、implementer プロンプトに前回試行のサマリーを
含めることで、ステートレス構造を維持しつつ差分修正の効率を上げる。

## 2. 背景

- 現在の `loop run` はステートレス設計で、各試行の implementer には
  計画書・Finding Ledger・未解決 Findings のみが渡される。
  前回「何を書いたか」「どこを変えたか」のコンテキストは渡されない。
- 実際の観測（fitbit-mcp の Temperature API 実装）では、
  試行 2 の implementer (gemini-2.5-pro) が 1 関数の 1 行修正で済む finding に対し、
  4 ファイル全てを再読・再理解して ~4 分かけてフルリライトしていた。
- 前回試行の `summaryMd`・`changedFiles`・`responses` と
  review verdict・check 結果を提供すれば、試行 2 以降の implementer が
  「前回何を書いて、何が問題で、どこだけ直せばよいか」を即座に判断でき、
  フルリライトを回避できる。
- セッションフル化はクロスベンダー対応・耐障害性・コンテキスト枯渇の
  観点でトレードオフが大きいため、ステートレス＋差分情報の方針とする。

## 3. 変更対象

- `skills/implementation-review-loop/src/agent_loop/cli/workflow_agent.py`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`
- `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/implementer.md`

## 4. 影響範囲

- `workflow_agent.py` の `build_prompt()` — implementer 向けプロンプト組み立てにセクション追加
- `workflow_agent.py` の `load_context()` / `AgentContext` — 前回応答パスの環境変数追加
- `loop.py` の `build_workflow_environment()` — 新しい環境変数の受け渡し
- 試行 1 では前回試行が存在しないため何も変わらない（後方互換性あり）
- reviewer のプロンプトには変更なし
- プロバイダー呼び出し (`run_structured_prompt`) には変更なし

## 5. 非対象範囲

- セッションフル化 / 会話継続型の対応
- reviewer プロンプトへのコンテキスト追加
- checks 二重実行の削減（implementer 側 checks と agent-loop 側 checks の統合）
- `ImplementerOutput` JSON Schema の変更
- 計画書レビューフェーズ (`plan review`) への変更

## 6. 実装方針

### 6.1 新しい環境変数

`loop.py` の `build_workflow_environment()` で、`attempt >= 2` の場合に
前回試行の応答パスを環境変数として渡す。
`build_workflow_environment()` は implementer 呼び出しと reviewer 呼び出しの
両方で使われるが、環境変数は常に設定し、読む側 (`build_prompt()`) で
ロール判定する。

- `WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH` — 前回の `responses/{prev}.json`
- `WORKFLOW_PREV_REVIEW_OUTPUT_PATH` — 前回の `reviews/{prev}.json`
- `WORKFLOW_PREV_CHECKS_PATH` — 前回の `checks/{prev}.json`

注意: `build_workflow_environment()` は現在 implementer 呼び出し時には
`implementer_output_path` のみ、reviewer 呼び出し時には
`implementer_output_path` + `checks_path` + `review_output_path` を受け取る。
前回試行パスはどちらの呼び出しでも同じ値になるため、
`attempt` パラメータから機械的に構築する。

### 6.2 AgentContext の拡張

`AgentContext` は `@dataclass(frozen=True)` なので、新フィールドは
既存フィールドの最後 (`run_dir: str`) の後に
デフォルト値 `None` 付きで追加する。

- `prev_implementer_output_path: str | None = None`
- `prev_review_output_path: str | None = None`
- `prev_checks_path: str | None = None`

`load_context()` で対応する環境変数を `env.get()` で読み込む（未設定時は `None`）。
試行 1 では環境変数が設定されないため自然に `None` になる。

### 6.3 build_prompt() の変更

`role == "implementer"` かつ `attempt >= 2` かつ前回データが読み込める場合、
承認済み計画書と Finding Ledger の間に「前回試行サマリー」セクションを挿入する。

現在の `build_prompt()` のセクション順序:
1. prompt_template
2. 承認済み計画書
3. Finding Ledger JSON
4. 未解決 Findings JSON
5. (reviewer のみ: Implementer 出力 / Check 結果)
6. 試行回数
7. 出力 JSON Schema / 出力指示

変更後 (implementer, attempt >= 2):
1. prompt_template
2. 承認済み計画書
3. **前回試行サマリー** ← 新規挿入
4. Finding Ledger JSON
5. 未解決 Findings JSON
6. 試行回数
7. 出力 JSON Schema / 出力指示

```
## 前回試行サマリー

### Implementer 応答
- summaryMd: (前回の summaryMd)
- changedFiles: (前回の changedFiles リスト)
- responses: (前回の finding 応答)

### Review 結果
- verdict: (前回の verdict)
- findings: (前回のレビューで出た findings)

### Check 結果
- allPassed: (true/false)
- 失敗した checks: (あれば列挙)
```

### 6.4 プロンプトサイズの制御

- 前回試行サマリーのみを追加する（前々回以前は追加しない）。
  Finding Ledger が累積履歴を既に保持しているため、冗長にならない。
- `summaryMd` はそのまま含める（通常 1-3 文程度）。
- `changedFiles` はファイル名リストのみ（パス文字列）。
- check 結果は `allPassed` と失敗 check のみ（成功した check の stdout は省略）。

### 6.5 後方互換性

- 試行 1 では `WORKFLOW_PREV_*` 環境変数が設定されないため、
  `load_context()` は `None` を返し、`build_prompt()` はセクションをスキップする。
- 既存の `implementer.md` テンプレートに
  「前回試行サマリーがある場合はそれを優先的に参照し、差分修正を優先せよ」
  というガイダンスを 1 行追加する。

## 7. 実装手順

1. `loop.py` の `build_workflow_environment()` に前回試行パスの環境変数追加を実装する。
   - `attempt >= 2` の場合のみ、`WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH` 等を設定
   - パスは `responses/{format_attempt(attempt - 1)}.json` 等から構築
2. `workflow_agent.py` の `AgentContext` に 3 つの optional フィールドを `= None` 付きで末尾に追加する。
   - `frozen=True` dataclass のため、デフォルト値なしのフィールドの後にデフォルト値ありのフィールドを置く
   - 既存の `run_dir: str` の後に追加
3. `workflow_agent.py` の `load_context()` で `env.get()` を使い新しい環境変数を読み込む。
   - 既存テスト (`mock_implementer.py`) はこれらの環境変数を設定しないが、`env.get()` が `None` を返すので壊れない
4. `workflow_agent.py` の `build_prompt()` に前回試行サマリーセクションの組み立てロジックを追加する。
   - `role == "implementer"` かつ前回データありの場合のみ
   - 前回の response / review / checks の JSON を読み込み
   - Markdown 形式でセクションを組み立て
   - 既存の Finding Ledger セクションの直前に挿入
5. `implementer.md` テンプレートに前回試行コンテキスト活用の指示を追加する。
6. 必須 checks を実行し、すべてパスすることを確認する。

## 8. 必須確認項目

- `skills/implementation-review-loop/src/agent_loop/cli/workflow_agent.py` — `build_prompt()` と `AgentContext`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py` — `build_workflow_environment()`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/state.py` — `format_attempt()` ユーティリティ
- `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/implementer.md` — テンプレート元
- `tests/test_run_loop.py` — 既存テストが `WORKFLOW_PREV_*` 未設定でも壊れないことの確認
- `tests/fixtures/mock_implementer.py` — 既存 mock が新環境変数を無視しても動作することの確認

## 9. 必須 checks

- `uv run python -m py_compile skills/implementation-review-loop/src/agent_loop/cli/workflow_agent.py`
- `uv run python -m py_compile skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`
- `uv run python -m pytest tests/ -x -q`
- `uv run python -c "from agent_loop.cli.workflow_agent import AgentContext; ac = AgentContext(attempt=2, checks_path=None, code_reviewer_prompt_path='x', code_review_schema_path='x', finding_ledger_path='x', implementer_output_path=None, implementer_prompt_path='x', implementer_schema_path='x', open_findings_path='x', output_path='x', plan_path='x', repo_path='x', review_record_path=None, run_dir='x', prev_implementer_output_path='/tmp/test.json', prev_review_output_path=None, prev_checks_path=None); assert ac.prev_implementer_output_path == '/tmp/test.json'"`
- `uv run python -c "from agent_loop.cli.workflow_agent import AgentContext; ac = AgentContext(attempt=1, checks_path=None, code_reviewer_prompt_path='x', code_review_schema_path='x', finding_ledger_path='x', implementer_output_path=None, implementer_prompt_path='x', implementer_schema_path='x', open_findings_path='x', output_path='x', plan_path='x', repo_path='x', review_record_path=None, run_dir='x'); assert ac.prev_implementer_output_path is None; assert ac.prev_review_output_path is None; assert ac.prev_checks_path is None"`

## 10. 受け入れ条件

- 試行 1 のプロンプトに「前回試行サマリー」セクションが含まれないこと。
- 試行 2 以降のプロンプトに「前回試行サマリー」セクションが含まれ、
  前回の `summaryMd`・`changedFiles`・`responses`・review verdict・check 結果が読めること。
- 前回の応答ファイルが存在しない場合（異常終了等）でもエラーにならず、
  セクションがスキップされること。
- 既存のテストがすべてパスすること。
- 既存の `implementer.md` テンプレートに差分修正を優先する旨のガイダンスが追加されていること。

## 11. エスカレーション条件

次のような場合は `replan` または `human` に戻す。

- 前回試行サマリーの追加によりプロンプトが大幅に肥大化し、
  プロバイダーのトークン上限に近づく場合
- `AgentContext` の変更が `ImplementerOutput` の JSON Schema 変更を
  必要とする設計に発展した場合
- reviewer プロンプトにも同様の変更が必要と判断された場合

## 12. 実装役向けメモ

- `build_prompt()` の変更は implementer ロール専用。reviewer ブランチには触れない。
- 前回データの読み込みには既存の `_read_optional_file()` を再利用する。
  ファイルが無い場合は `None` を返すので追加のエラーハンドリングは不要。
- 前回試行サマリーは人間が読む Markdown としても機能するよう、
  `prompts/{003d}-implementer.md` にそのまま書き出される設計を活かす。
- `WORKFLOW_PREV_*` 環境変数名は既存の `WORKFLOW_*` 命名規約に揃える。
- テストは `tests/` 配下の既存テストが通ることを最低限とする。
  新規テストを書く場合は `build_prompt()` の分岐（attempt=1 vs attempt>=2）を
  カバーするユニットテストとする。
