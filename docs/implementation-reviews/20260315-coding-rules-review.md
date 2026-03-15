# コーディングルールレビュー

状態: レビュー済み
レビュー日: 2026-03-15
レビュー担当: Claude
対象: コードベース全体
基準: `.codex/coding-rules.md`

## 総評

コーディングルール違反の中心は**重複実装の放置**（8件）である。`_ensure_successful_command` が3箇所、`_format_tokyo_date` が3箇所にコピーされているのが最も顕著。Rule 3「新しいアプローチを導入したら完全に移行せよ」の精神に反しており、共通モジュールへの統合が必要。

後方互換レイヤー（`provider` フィールド、`dict` 入力パス）も「移行期間中のみ」と注記されたまま残存しており、Rule 7 違反。

## 指摘一覧

### CR-001: 重複実装 — `_ensure_successful_command`

- 重大度: `high`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/code_review_cmd.py:416`
  - `cli/plan_review_cmd.py:264`
  - `core/run_loop/loop.py:293`
- 内容: 同一の関数が3ファイルにコピペされている
- 修正方向: `core/process.py` に統合し、3箇所から参照する

### CR-002: 重複実装 — `_extract_plan_title`

- 重大度: `high`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/code_review_cmd.py:272`
  - `cli/plan_review_cmd.py:230`
- 内容: 同一の正規表現処理が2ファイルに存在
- 修正方向: 共通ユーティリティに統合

### CR-003: 重複実装 — `_format_tokyo_date`

- 重大度: `high`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/code_review_cmd.py:358`
  - `cli/plan_review_cmd.py:242`
  - `cli/new_plan_cmd.py:78`
- 内容: 同一の日付フォーマット関数が3ファイルに存在
- 修正方向: 共通ユーティリティに統合

### CR-004: 重複実装 — `_format_provider_display_name`

- 重大度: `medium`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/code_review_cmd.py:368`
  - `cli/plan_review_cmd.py:256`
- 内容: ほぼ同一のプロバイダ名変換が2ファイルに存在。`code_review_cmd` 版は `None` 入力を受け付ける点のみ異なる
- 修正方向: 共通ユーティリティに統合

### CR-005: 重複実装 — `_fenced_json`

- 重大度: `medium`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/plan_review_cmd.py:252`
  - `cli/workflow_agent.py:208`
- 内容: 同一のJSON コードブロック生成関数が2ファイルに存在
- 修正方向: 共通ユーティリティに統合

### CR-006: 重複実装 — `_write_json`

- 重大度: `medium`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `cli/code_review_cmd.py:410`
  - `core/run_loop/io.py:46`
- 内容: 同一のJSON書き出し関数が2ファイルに存在
- 修正方向: `code_review_cmd.py` が `run_loop/io.py` の `write_json` を使うよう変更

### CR-007: 重複実装 — `_shell_escape`

- 重大度: `medium`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `core/providers/claude.py:127`
  - `core/providers/codex.py:52`
- 内容: 同一のシェルエスケープ関数が2ファイルに存在
- 修正方向: `core/process.py` に統合

### CR-008: 重複実装 — `NonEmptyStr`

- 重大度: `low`
- 違反ルール: Rule 3 (Avoid dual implementations)
- 箇所:
  - `core/contracts.py:61`
  - `core/checks.py:34`
- 内容: 同一の型エイリアスが2ファイルで定義
- 修正方向: `checks.py` が `contracts.py` から import する

### CR-009: デッドコード — 未使用 import `os`

- 重大度: `medium`
- 違反ルール: Rule 2 (Remove dead code aggressively)
- 箇所: `core/run_loop/state.py:5`
- 内容: `import os` がファイル内で一度も使用されていない
- 修正方向: 削除

### CR-010: デッドコード — 未使用変数 `timed_out`

- 重大度: `low`
- 違反ルール: Rule 2 (Remove dead code aggressively)
- 箇所: `core/process.py:34`
- 内容: `timed_out = False` の初期代入が不要。try ブロックの return で `timed_out=False` がハードコードされ、except で `timed_out = True` に再代入されるため、この変数は意味を持たない
- 修正方向: 行34の `timed_out = False` を削除

### CR-011: デッドコード — 未使用 TYPE_CHECKING import

- 重大度: `low`
- 違反ルール: Rule 2 (Remove dead code aggressively)
- 箇所: `core/run_loop/summary.py:7,19-20`
- 内容: `TYPE_CHECKING` ガードで `AttemptCheckResults` をインポートしているが、ファイル内のどの型注釈にも使用されていない
- 修正方向: `if TYPE_CHECKING` ブロックごと削除

### CR-012: 後方互換レイヤーの残存 — `provider` フィールド

- 重大度: `high`
- 違反ルール: Rule 3 (Avoid dual implementations), Rule 7 (Code health over backward compatibility)
- 箇所:
  - `core/repo_config.py:30` — `provider` フィールド (コメントに「後方互換: 移行期間中のみ」)
  - `core/repo_config.py:32-38` — `@model_validator` で両方を許容
  - `core/repo_config.py:67-90` — `get_effective_provider` が `dict`/旧`provider`/新`defaultProvider` の3パターンを処理
- 内容: `defaultProvider` への移行が完了しているなら、旧 `provider` フィールドと dict 入力パスは不要
- 修正方向: `provider` フィールドを削除し、`defaultProvider` のみに統一。`get_effective_provider` から dict パスを除去

### CR-013: 不要な抽象 — `InitializedRun` と `CompletedRun`

- 重大度: `low`
- 違反ルール: Rule 5 (Simplify responsibility boundaries)
- 箇所: `core/run_loop/state.py:88-97`
- 内容: 両者は `runDir: str` + `state: RunState` の同一構造。型による意味的区別が必要な場面がない
- 修正方向: 1つの型に統合

### CR-014: 冗長な内部関数 — `_read_check_commands_file`

- 重大度: `low`
- 違反ルール: Rule 5 (Simplify responsibility boundaries)
- 箇所: `core/checks.py:105-109`
- 内容: `load_checks_config` と同じ処理（読み→パース→バリデーション）をエラーハンドリングなしで再実装している
- 修正方向: `load_checks_config` を使うよう変更し、`_read_check_commands_file` を削除

### CR-015: 冗長な内部関数 — `_read_optional_validated`

- 重大度: `low`
- 違反ルール: Rule 5 (Simplify responsibility boundaries)
- 箇所: `core/run_loop/summary.py:158-170`
- 内容: `io.py` の `read_optional_json` と同じ役割を TypeAdapter で再実装
- 修正方向: `read_optional_json` を使うよう変更し、`_read_optional_validated` を削除

### CR-016: ループ内インポート

- 重大度: `low`
- 違反ルール: コード品質
- 箇所: `core/run_loop/loop.py:121`
- 内容: `from pydantic import TypeAdapter` がループ本体（`run_loop` 関数）内でインポートされている
- 修正方向: ファイルのトップレベルに移動

### CR-017: TypeScript 移行の痕跡

- 重大度: `low`
- 違反ルール: Rule 2 (Remove dead code aggressively)
- 箇所: 全モジュールの docstring
- 内容: `"""... matching checks.ts."""` 等、TypeScript ファイルへの参照が全モジュールに残存。Python への完全移行後は情報価値がない
- 修正方向: docstring から TS ファイル参照を削除

## まとめ

| 重大度 | 件数 |
|--------|------|
| high   | 4    |
| medium | 5    |
| low    | 8    |

high の4件（CR-001, CR-002, CR-003, CR-012）を優先的に修正すべき。
