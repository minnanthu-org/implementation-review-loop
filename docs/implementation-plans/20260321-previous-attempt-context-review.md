# 計画書検証レポート: Implementer プロンプトへの前回試行コンテキスト追加

対象: `docs/implementation-plans/20260321-previous-attempt-context.md`
検証日: 2026-03-21
検証者: Claude

## 検証結果サマリー

- 指摘: 1 件 (軽微な記述誤り)
- 実装方針・手順・後方互換性の分析はすべて実コードと整合

## 指摘

### [軽微] Section 6.2 — `run_dir` を optional フィールドと誤記

**該当箇所** (計画書 L73-74):

> `AgentContext` は `@dataclass(frozen=True)` なので、新フィールドは
> 既存の optional フィールド (`review_record_path`, `run_dir`) の後に

**問題**:

`run_dir` の型は `str` であり、nullable でない必須フィールド。
optional (nullable) なのは `review_record_path: str | None` のみ。

実コード (`workflow_agent.py` L34-35):

```python
review_record_path: str | None
run_dir: str
```

新フィールドを `= None` 付きで末尾に追加する方針自体は Python dataclass のルール上正しく、実装に影響はない。

**修正案**:

> 既存フィールドの最後 (`run_dir: str`) の後に、デフォルト値 `None` 付きで追加する。

## 検証済み項目一覧

| # | セクション | 検証項目 | 結果 |
|---|---|---|---|
| 1 | 3. 変更対象 | 3 ファイルパスが実在する | OK |
| 2 | 4. 影響範囲 | `build_prompt()` L79, `AgentContext` L21, `load_context()` L38, `build_workflow_environment()` L263 が存在 | OK |
| 3 | 6.1 | `build_workflow_environment()` が implementer (L110) と reviewer (L190) 両方で使用される | OK |
| 4 | 6.1 | implementer 呼び出し時は `checks_path`/`review_output_path` なし、reviewer 呼び出し時はあり | OK |
| 5 | 6.1 | `format_attempt()` が `state.py` L168 に存在し `loop.py` L41 でインポート済み | OK |
| 6 | 6.3 | `build_prompt()` のセクション順序がコード L106-148 と一致 | OK |
| 7 | 6.5 | `_read_optional_file()` L203 が `FileNotFoundError`/`OSError` で `None` を返す。再利用可能 | OK |
| 8 | 8 | `format_attempt()` が `state.py` に存在するという記述 | OK |
| 9 | 8 | `tests/test_run_loop.py`, `tests/fixtures/mock_implementer.py` が実在 | OK |
| 10 | 9 | 必須 checks の `AgentContext` コンストラクタ引数名が既存フィールドと一致 | OK |
| 11 | 12 | `write_prompt_file()` L159 のフォーマット `{zfill(3)}-{role}.md` | OK |
| 12 | — | `mock_implementer.py` が `WORKFLOW_PREV_*` を読まないため新環境変数追加で壊れない | OK |
