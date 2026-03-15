# TS→Python 移植 実施回3 レビュー

対象: `feat/ts-to-python` ブランチ — Phase 4 (Run Loop)
レビュー日: 2026-03-15

## 完了条件

`uv run pytest tests/test_run_loop.py` — **要確認 (タイムスタンプ不一致の影響あり)**

## 全体評価

787行の `run-loop.ts` を 5 モジュール + `__init__.py` に分解して移植。構造は良好で、WORKFLOW_* 環境変数 (12変数)、JSON 出力フォーマット、テストカバレッジともに TS 版と同等。

| ファイル | 行数 | 状態 |
|---|---|---|
| `core/run_loop/__init__.py` | 6 | OK |
| `core/run_loop/io.py` | 52 | OK |
| `core/run_loop/state.py` | 188 | 要修正 |
| `core/run_loop/findings.py` | 169 | OK |
| `core/run_loop/summary.py` | 179 | OK |
| `core/run_loop/loop.py` | 335 | 要修正 (軽微) |
| `tests/test_run_loop.py` | 269 | OK |

## 指摘事項

### 指摘 #1 (BUG): `format_timestamp()` のフォーマット不一致 — `state.py:171`

TS の `formatTimestamp` (`run-loop.ts:696-697`):
```typescript
function formatTimestamp(now: Date): string {
  return now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}
// 出力例: "20260315T143045Z"
```

Python の `format_timestamp` (`state.py:169-171`):
```python
def format_timestamp(now: datetime) -> str:
    return now.isoformat().replace("-", "").replace(":", "").replace("+00:00", "Z")
# 出力例: "20260315T143045.123456Z"
```

**問題点:**
- TS の `Date.toISOString()` はミリ秒3桁 (`.123Z`) を含み、regex で除去している
- Python の `datetime.isoformat()` はマイクロ秒6桁 (`.123456`) を含むが、除去していない
- 結果として run ID が TS と異なる (`20260315T143045Z-myplan` vs `20260315T143045.123456Z-myplan`)
- `state.json` の `startedAt` 等のタイムスタンプフィールドも影響する可能性あり

**修正案:**
```python
def format_timestamp(now: datetime) -> str:
    ts = now.replace(microsecond=0)
    return ts.isoformat().replace("-", "").replace(":", "").replace("+00:00", "Z")
```

### 指摘 #2 (コード品質): `loop.py` での不要な `.model_dump()` 変換 — `loop.py:153`, `loop.py:222-225`

`update_state()` に `openFindings` を渡す際、Pydantic モデルを一旦 dict に変換している:

```python
# loop.py:153
openFindings=[f.model_dump() for f in state.openFindings],

# loop.py:222-225
openFindings=[
    f.model_dump()
    for f in review_output.findings
    if f.status.value == "open"
],
```

`update_state()` は Pydantic の `model_validate()` を通すため dict でも動作するが、モデルオブジェクトをそのまま渡す方が TS の動作に忠実かつ効率的。機能上は正しく動作する。

## 問題なし

- **`io.py`** — `read_json`, `write_json`, `read_optional_json` いずれも TS と等価。UTF-8 (日本語) 対応済み
- **`findings.py`** — `validate_implementer_responses`, `validate_review_output`, `apply_implementer_responses`, `apply_review_output` すべて TS のロジックと一致
- **`summary.py`** — Markdown 生成フォーマット、日本語テキスト、ファイル欠落時の処理すべて TS と一致
- **`__init__.py`** — 適切なエクスポート
- **WORKFLOW_* 環境変数** — `WORKFLOW_REPO_PATH`, `WORKFLOW_RUN_DIR`, `WORKFLOW_PLAN_PATH`, `WORKFLOW_ATTEMPT`, `WORKFLOW_OPEN_FINDINGS_PATH`, `WORKFLOW_FINDING_LEDGER_PATH`, `WORKFLOW_IMPLEMENTER_PROMPT_PATH`, `WORKFLOW_CODE_REVIEWER_PROMPT_PATH`, `WORKFLOW_IMPLEMENTER_SCHEMA_PATH`, `WORKFLOW_CODE_REVIEW_SCHEMA_PATH`, `WORKFLOW_IMPLEMENTER_OUTPUT_PATH`, `WORKFLOW_CHECKS_PATH` — 全て正しくセット
- **JSON 出力互換性** — `state.json`, `finding-ledger.json`, `open-findings.json` の構造が TS 版と一致
- **テストカバレッジ** — ネスト起動拒否、ディレクトリ作成、設定ロード、フルループ実行 (2attempt 完了) を網羅

## 指摘一覧

| # | 種別 | ファイル | 内容 |
|---|---|---|---|
| 1 | BUG | `state.py:171` | `format_timestamp()` がマイクロ秒を除去せず、run ID が TS と不一致 |
| 2 | コード品質 | `loop.py:153, 222-225` | 不要な `.model_dump()` 変換 |

## 修正確認 (2026-03-15)

全 2 指摘に対応済み。再レビューで確認:

| # | 状態 | 確認内容 |
|---|---|---|
| 1 | 修正済み | `state.py` — `now.replace(microsecond=0)` でマイクロ秒を除去してからフォーマット |
| 2 | 修正済み | `loop.py` — `.model_dump()` を除去し、Pydantic モデルをそのまま渡すように変更 |

`uv run pytest tests/test_run_loop.py` — **4 tests passed (0.29s) (PASS)**

## 許容される差異

- `run-loop.ts` 787行 → 5ファイル分解 — 計画通りの構造変更
- sync `subprocess.run` 使用 — 計画通り
- Pydantic v2 モデルバリデーション — Zod の直接置換として機能的に等価
