# TS→Python 移植 実施回2 レビュー

対象: `feat/ts-to-python` ブランチ — Phase 2 (設定レイヤー) + Phase 3 (プロバイダーレイヤー)
レビュー日: 2026-03-15

## 完了条件

`uv run pytest` — **32 tests passed (0.21s) (PASS)**

## Phase 2: 設定レイヤー

### `core/checks.py` — 要修正

全関数 (`load_checks_config`, `resolve_configured_check_commands`, `run_checks`, `_deduplicate_commands`) を忠実に移植。定数 `DEFAULT_CHECK_COMMAND_TIMEOUT_MS = 120_000` も TS と一致。

**指摘 #1 (BUG): エラーハンドリングの到達不能分岐 (lines 57-71)**

`except (json.JSONDecodeError, Exception)` は `Exception` が基底クラスのため全例外を吸収する。内部の `isinstance(exc, FileNotFoundError)` 分岐 (line 58) は直前の `except FileNotFoundError` (line 55) で先に捕捉されるため到達不能。予期しないエラーも握り潰される。

**指摘 #2 (BUG): コマンド文字列の個別バリデーション欠如 (line 34)**

`ChecksConfig` の `commands` フィールドに `Field(min_length=0)` を設定しているが、これはリスト長の制約。TS の `z.array(z.string().trim().min(1))` に相当する「各コマンドが空文字/空白のみでないこと」のバリデーションがない。空文字列 `""` が有効なコマンドとして受け入れられる。

**指摘 #3 (テスト欠落): `tests/test_checks.py` が存在しない**

TS 側にも専用テストはないが、以下の関数はテストカバレッジが必要:
- `load_checks_config` — 正常系、ファイル欠落、不正 JSON、バリデーションエラー
- `resolve_configured_check_commands` — マージ + 重複排除
- `run_checks` — 逐次実行、exit code マッピング
- `_deduplicate_commands` — 順序保持、重複除去

### `core/repo_config.py` — OK (軽微な指摘あり)

全型 (`WorkflowProvider`, `CompatLoopRepoConfig`, `DelegatedRepoConfig`, `RepoConfig`) と全関数 (`get_effective_provider`, `get_repo_config_path`, `load_repo_config`, `load_compat_loop_repo_config`) を忠実に移植。Union パースは TS の `z.union()` と等価な手動フォールバック方式で実装。テストは TS の 12 件を全て移植済み。

**指摘 #4 (軽微): `or` vs `is not None` (line 76)**

`get_effective_provider` で `execution.defaultProvider or execution.provider` を使用。TS の `??` は `null`/`undefined` のみ fallback するが、Python の `or` は falsy 値全般 (空文字、`0` 等) で fallback する。現在の `WorkflowProvider` enum 値はいずれも truthy なため実害はないが、`is not None` の方が TS セマンティクスに忠実。

## Phase 3: プロバイダーレイヤー

### `core/providers/claude.py` — 要修正

`build_structured_claude_command`, `run_structured_claude_prompt`, `extract_json`, `_shell_escape` を忠実に移植。`extract_json` のブレース平衡 JSON 抽出アルゴリズムは文字列/エスケープ追跡を含め TS と同一の動作。定数 `DEFAULT_CLAUDE_EXEC_TIMEOUT_MS = 900_000` も一致。テスト 9 件 (command build 1 + extract_json 8) 全て PASS。

**指摘 #5 (BUG): `or` による timeout_ms のデフォルト処理 (line 51)**

`timeout_ms or DEFAULT_CLAUDE_EXEC_TIMEOUT_MS` — `timeout_ms=0` を渡した場合、TS では `0` がそのまま使われるが Python では `DEFAULT` に置換される。`timeout_ms if timeout_ms is not None else DEFAULT` にすべき。

### `core/providers/codex.py` — 要修正

`build_structured_codex_command`, `run_structured_codex_prompt`, `_shell_escape` を忠実に移植。コマンド文字列構造、定数 `DEFAULT_CODEX_EXEC_TIMEOUT_MS = 420_000` とも TS と一致。TS にも専用テストなし。

**指摘 #6 (BUG): 同 #5 — `or` による timeout_ms 処理 (line 48)**

### `core/providers/gemini.py` — 要修正

`build_structured_gemini_command`, `run_structured_gemini_prompt` を忠実に移植。JSON 抽出 regex `r"(\{[\s\S]*\})"` は TS の `/(\{[\s\S]*\})/` と等価。エラーハンドリングは TS の二重ラップを回避する改善あり（`RuntimeError` を直接 re-raise）。定数 `DEFAULT_GEMINI_EXEC_TIMEOUT_MS = 420_000` 一致。テスト 1 件 PASS。

**指摘 #7 (BUG): 同 #5 — `or` による timeout_ms 処理 (line 59)**

**指摘 #8 (コード品質): `import re` が関数内 (line 76)**

`re` モジュールのインポートが `run_structured_gemini_prompt` 関数内にある。モジュールレベルに移動すべき。

### `core/providers/structured_prompt.py` — OK

`run_structured_prompt` でプロバイダーディスパッチを実装。`WorkflowProvider` enum との比較は `str` 継承により正しく動作。Claude/Gemini/Codex (デフォルト) の分岐が TS と一致。

### `core/doctor.py` — OK

`run_doctor`, `_validate_compat_loop_repo`, `_assert_directory_exists`, `_assert_file_exists` を忠実に移植。TS の `safeStat` は Python の `Path.exists()` / `Path.is_dir()` / `Path.is_file()` で代替。Python 固有の例外型 (`FileNotFoundError`, `NotADirectoryError`, `IsADirectoryError`) の使用は TS の汎用 `Error` からの改善。テスト 3 件全て PASS。

## 指摘一覧

| # | 種別 | ファイル | 内容 |
|---|---|---|---|
| 1 | BUG | `checks.py:57-71` | 到達不能分岐 + catch-all でエラー握り潰し |
| 2 | BUG | `checks.py:34` | コマンド文字列の個別バリデーション欠如 |
| 3 | テスト欠落 | — | `tests/test_checks.py` が存在しない |
| 4 | 軽微 | `repo_config.py:76` | `or` → `is not None` にすべき |
| 5 | BUG | `claude.py:51` | `timeout_ms or DEFAULT` → `is not None` チェックに |
| 6 | BUG | `codex.py:48` | 同 #5 |
| 7 | BUG | `gemini.py:59` | 同 #5 |
| 8 | コード品質 | `gemini.py:76` | `import re` をモジュールレベルに移動 |

## 許容される差異

- `doctor.py`: Python 固有例外型の使用 (`FileNotFoundError`, `NotADirectoryError`) — 改善
- `gemini.py`: `RuntimeError` 直接 re-raise で二重ラップ回避 — 改善
- 全体: sync 実行 — 計画通り (`subprocess.run` 使用)
- `repo_config.py`: Union パースで独自エラーメッセージ結合 — 機能的に等価

## 修正確認 (2026-03-15)

全 8 指摘に対応済み。再レビューで確認:

| # | 状態 | 確認内容 |
|---|---|---|
| 1 | 修正済み | `checks.py` — `FileNotFoundError` / `JSONDecodeError` / `ValidationError` を個別 try-except に分離 |
| 2 | 修正済み | `checks.py` — `NonEmptyStr = Annotated[str, Field(min_length=1)]` で個別コマンドバリデーション追加 |
| 3 | 修正済み | `test_checks.py` — 8 テスト追加 (正常系、ファイル欠落、不正JSON、スキーマ不正、空文字拒否、マージ+重複排除、run_checks、空リスト) |
| 4 | 修正済み | `repo_config.py` — `is not None` チェックに変更 (dict 分岐 + CompatLoopExecution 分岐) |
| 5 | 修正済み | `claude.py` — `timeout_ms if timeout_ms is not None else DEFAULT` |
| 6 | 修正済み | `codex.py` — 同上 |
| 7 | 修正済み | `gemini.py` — 同上 |
| 8 | 修正済み | `gemini.py` — `import re` をモジュールレベルに移動 |

`uv run pytest` — **40 tests passed (0.22s) (PASS)**

## まとめ

実施回2 の完了条件を満たし、全指摘事項も解消済み。実施回3 に進行可能。
