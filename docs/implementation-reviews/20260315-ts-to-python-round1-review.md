# TS→Python 移植 実施回1 レビュー

対象: `feat/ts-to-python` ブランチ — Phase 0 (スキャフォールド) + Phase 1 (基盤レイヤー)
レビュー日: 2026-03-15

## 完了条件

`uv run pytest tests/test_contracts.py tests/test_process.py` — **7 tests passed (PASS)**

## Phase 0: スキャフォールド

| チェック項目 | 状態 | 備考 |
|---|---|---|
| `_legacy_ts/` にTS ソースをコピー | OK | core/cli/test 全ファイルあり |
| `pyproject.toml` 作成 | OK | hatchling + click + pydantic、エントリポイント設定済み |
| パッケージ構造 `src/agent_loop/` | OK | `core/`, `cli/`, `core/providers/`, `core/run_loop/` に `__init__.py` あり |
| 静的アセット配置 | OK | schemas 3, templates 8, prompts 1 — 内容は元ファイルと同一 |
| `tests/conftest.py` | OK | 空ファイル（Phase 1 の範囲では十分） |
| `py.typed` マーカー | OK | |

## Phase 1: 基盤レイヤー

### `core/contracts.py` — OK

- Enum 8個、Pydantic Model 11個を忠実移植
- フィールド名は camelCase を維持（JSON 互換性のため）
- `NonEmptyStr = Annotated[str, Field(min_length=1)]` 等のバリデーション制約が TS の Zod 定義と一致
- `FindingLedger` 型エイリアス（`list[FindingLedgerEntry]`）も含め漏れなし

### `core/process.py` — OK

- `CommandExecutionResult` dataclass のフィールドが TS の `CommandExecutionResult` interface と一致
- タイムアウト処理: ms→s 変換、exit code 124、stderr メッセージ形式が TS と同一
- シェル: `/bin/zsh -lc` で TS の動作を正確に再現
- `stdin_text` パラメータによる stdin 入力対応済み

### `core/nested_workflow_guard.py` — OK

- `WORKFLOW_ACTIVE_COMMAND` 環境変数名を保持
- `assert_no_nested_workflow_invocation()` / `build_workflow_command_environment()` の 2 関数を忠実移植
- ネスト検出時に `RuntimeError` を送出（TS の `Error` に相当）

### `cli/assets.py` — BUG

**`resolve_asset_path()` が不正なパスを返す。**

`src/agent_loop/assets/__init__.py` が存在しないため、`importlib.resources.files("agent_loop.assets")` が `MultiplexedPath`（namespace package 用）を返す。`str()` すると:

```
MultiplexedPath('/Users/kegasawa/git/agent-loop/src/agent_loop/assets')
```

`/` で始まらない不正な文字列になり、`Path()` で包んでも存在しないパスを指す。

**修正方法**: `src/agent_loop/assets/__init__.py` を作成する。通常パッケージとして認識されれば `files()` が `pathlib.Path` を返し、`str()` が正しいファイルシステムパスになる。

**影響範囲**: Phase 1 では `assets.py` を直接使うテストがないため完了条件には影響しないが、Phase 2 以降で `checks.py` / `repo_config.py` がアセットパスを参照する際に壊れる。実施回2 の着手前に修正が必要。

## まとめ

実施回1 の完了条件は満たしている。`assets/__init__.py` の欠落を修正すれば実施回2 に進行可能。
