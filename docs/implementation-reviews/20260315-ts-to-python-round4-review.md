# TS→Python 移植 実施回4 レビュー

対象: `feat/ts-to-python` ブランチ — Phase 5 (モックフィクスチャ変換) + Phase 6 (CLI レイヤー)
レビュー日: 2026-03-15

## 完了条件

| 条件 | 結果 |
|---|---|
| `uv run pytest` 全テスト通過 | **OK** — 62/62 passed (0.97s) |
| `agent-loop --help` 動作 | **OK** — 全サブコマンド表示 |
| `uv run mypy src/` | **NG** — 12 errors in 4 files |

## 全体評価

Phase 5 (モックフィクスチャ 6 ファイル) + Phase 6 (CLI 9 モジュール、計 1,637 行) は機能的に完了。全テスト通過、CLI エントリポイントも動作する。ただし mypy エラー 12 件が残存しており、実施回 5 の必須 checks (`mypy --strict` エラーなし) の前に修正が必要。

### Phase 5: モックフィクスチャ変換

| Legacy (.mjs) | Python | 状態 |
|---|---|---|
| `mock-check.mjs` | `tests/fixtures/mock_check.py` | OK |
| `mock-implementer.mjs` | `tests/fixtures/mock_implementer.py` | OK |
| `mock-reviewer.mjs` | `tests/fixtures/mock_reviewer.py` | OK |
| `mock-plan-reviewer.mjs` | `tests/fixtures/mock_plan_reviewer.py` | OK |
| `mock-one-shot-code-reviewer.mjs` | `tests/fixtures/mock_one_shot_code_reviewer.py` | OK |
| `mock-one-shot-code-reviewer-assert.mjs` | `tests/fixtures/mock_one_shot_code_reviewer_assert.py` | OK |

### Phase 6: CLI レイヤー

| ファイル | 行数 | 状態 |
|---|---|---|
| `cli/main.py` | 65 | OK |
| `cli/init_cmd.py` | 162 | OK |
| `cli/doctor_cmd.py` | 29 | OK |
| `cli/new_plan_cmd.py` | 154 | OK |
| `cli/plan_review_cmd.py` | 296 | OK |
| `cli/code_review_cmd.py` | 463 | OK |
| `cli/run_loop_cmd.py` | 194 | 要修正 (mypy) |
| `cli/workflow_agent.py` | 234 | OK |
| `cli/agent_commands.py` | 19 | OK |
| `cli/assets.py` | 21 | OK |

## 指摘事項

### 指摘 #1 (BUG): `_build_options()` の Click デコレータ型推論エラー — `run_loop_cmd.py:120-161`

mypy 出力:
```
run_loop_cmd.py:120: error: Unused "type: ignore" comment  [unused-ignore]
run_loop_cmd.py:120: error: Value of type variable "FC" of function cannot be "object"  [type-var]
run_loop_cmd.py:124: error: Argument 1 has incompatible type "object"; expected "Callable[..., Any]"  [arg-type]
run_loop_cmd.py:125: error: Unused "type: ignore" comment  [unused-ignore]
run_loop_cmd.py:160: error: Argument 1 has incompatible type "object"; expected "Callable[..., Any]"  [arg-type]
run_loop_cmd.py:161: error: Unused "type: ignore" comment  [unused-ignore]
```

**原因**: `_build_options()` が `object` 型を返すか、もしくは `type: ignore` コメントがエラーコードと一致していない。Click の `@click.option()` デコレータチェーンを関数に切り出す際に型情報が失われている。

**修正方針**: `_build_options()` の戻り値型を `Callable` に明示するか、`click.option` を直接デコレータとして適用する構成に変更する。不要な `type: ignore` コメントは削除する。

---

### 指摘 #2 (BUG): `object` 型に対する `len()` / イテレーション — `summary.py:110,114`

mypy 出力:
```
summary.py:110: error: Argument 1 to "len" has incompatible type "object"; expected "Sized"  [arg-type]
summary.py:114: error: "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)  [attr-defined]
```

**原因**: `summary.py` 内で `object` 型の変数に対して `len()` やイテレーションを行っている。JSON をパースした結果が `dict[str, object]` のような型で、値にアクセスする際に適切なキャストや型ガードがない。

**修正方針**: 該当箇所で `isinstance` チェックまたは `cast()` を使って型を絞り込む。

---

### 指摘 #3 (WARN): `no-any-return` エラー — `summary.py:178`

mypy 出力:
```
summary.py:178: error: Unused "type: ignore" comment  [unused-ignore]
summary.py:178: error: Returning Any from function declared to return "dict[str, object] | None"  [no-any-return]
```

**原因**: `type: ignore` コメントが付いているが、エラーコードが一致していないため無視されず、かつ `Any` を返している。

**修正方針**: `type: ignore` を削除し、戻り値を明示的にキャストするか、`json.loads()` の戻り値に型アノテーションを付ける。

---

### 指摘 #4 (CLEANUP): 不要な `type: ignore` コメント — `io.py:32`, `doctor.py:40`

mypy 出力:
```
io.py:32: error: Unused "type: ignore" comment  [unused-ignore]
doctor.py:40: error: Unused "type: ignore" comment  [unused-ignore]
```

**原因**: 以前のコードや別の mypy 設定で必要だった `type: ignore` が、現在の設定では不要になっている。

**修正方針**: 該当行の `type: ignore` コメントを削除する。

---

## まとめ

機能面では実施回 4 の完了条件（全テスト通過 + CLI 動作）を満たしている。残存する mypy エラー 12 件は全て型アノテーション・`type: ignore` の問題であり、ランタイム動作には影響しない。実施回 5 開始前に修正すること。
