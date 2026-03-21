# 実装計画書: ループ完了時の所要時間サマリ表示

状態: 指摘対応済み (rev.3)
作成日: 2026-03-21
作成者: kegasawa

## 1. 目的

実装ループ完了時に、アテンプトごと・フェーズごとの所要時間をテーブル形式で表示する。
モデル選定やループ設定のチューニングに必要な定量データを提供する。

## 2. 背景

- 現状 `RunState` には `createdAt` / `updatedAt` のみ存在し、フェーズ別・アテンプト別の計測は未実装
- Sonnet は単価が安いがレビューターンが増え、トータルの時間・コストが増大するケースがある
- GPT-5.4 はレビュアーとして Opus より品質が良い実績があり、モデル組み合わせの最適化が進んでいる
- 所要時間データがあれば、モデル × ターン数 × コストの最適解を定量的に検証できる

## 3. 変更対象

- `skills/implementation-review-loop/src/agent_loop/core/run_loop/state.py`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/summary.py`
- `skills/implementation-review-loop/src/agent_loop/cli/run_loop_cmd.py`

## 4. 影響範囲

- `state.py` の `RunResult` — `timing: list[AttemptTiming]` フィールド追加（`default_factory=list`）。`initialize_run()` は空リストのまま返すため既存の `loop init` 経路に影響なし
- `loop.py` の `run_loop()` — 計測ロジック追加、戻り値に timing データを含める
- `summary.py` の `write_run_summary()` — timing データを引数で受け取り `summary.md` に追記
- `run_loop_cmd.py` — ループ完了後に timing テーブルを stderr に表示（表示責務は CLI 層に統一）
- 既存の `RunState` / `state.json` スキーマは変更しない

## 5. 非対象範囲

- `RunState` や `state.json` へのタイミング永続化（B案）は今回やらない
- トークン数やコストの自動計算は対象外
- 既存テストのリファクタ

## 6. 実装方針

**A案（軽量アプローチ）を採用。**

`loop.py` の各フェーズ前後で `time.monotonic()` を取得し、アテンプトごとのフェーズ別所要時間を蓄積する。

- 状態スキーマ（`RunState`）は変更しない → 互換性リスクなし
- 計測は `time.monotonic()` を使用 → 壁時計のずれに影響されない
- テーブル描画は標準ライブラリのみで実装（外部依存追加なし）
- **timing データの受け渡し**: `run_loop()` の戻り値 `RunResult` に timing リストを追加。`write_run_summary()` にも引数として渡す。ループ途中のスナップショット時点では timing は渡さない（完了時のみ）
- **表示責務**: stderr へのテーブル出力は CLI 層（`run_loop_cmd.py`）が担当。core 層は計測とデータ構築のみ
- **早期終了時**: 未実行フェーズは `None` で記録し、表示時は `-` とする。Total は実行済みフェーズの合計

### 不採用: B案（状態永続化アプローチ）

`RunState` や `state.json` にフェーズ別タイミングを保存する案。後から集計・比較が可能になるが、スキーマ変更の影響範囲が広く、現時点ではオーバーエンジニアリング。将来必要になった時点で検討する。

## 7. 実装手順

1. `state.py`: `RunResult` に `timing: list[AttemptTiming]` フィールドを追加（`AttemptTiming` は `TypedDict` で `attempt`, `implement`, `check`, `review` を持つ。各値は秒数 `float | None`）。`timing` は `default_factory=list` とし、`initialize_run()` は空リストを返す（`loop init` 経路は変更不要）
2. `loop.py`: 各フェーズ（implement / check / review）の前後に `time.monotonic()` 計測を追加し、アテンプトごとの timing を蓄積
3. `loop.py`: ループ終了時に `RunResult` の `timing` に蓄積データを渡して返す
4. `summary.py`: `write_run_summary()` に `timing` 引数（デフォルト `None`）を追加。`summary.md` 末尾に timing テーブルを Markdown 表形式で追記
5. `loop.py`: ループ完了時の `write_run_summary()` 呼び出しに timing を渡す（途中スナップショットでは渡さない）
6. `run_loop_cmd.py`: `RunResult` から timing を受け取り、テーブルを stderr に出力するヘルパー関数を追加
7. テストを追加（approve パス / 早期終了パスの両方で timing テーブルを検証）

### 出力イメージ（通常終了）

```
┌──────────┬────────────┬─────────┬──────────┬─────────┐
│ Attempt  │ Implement  │ Check   │ Review   │ Total   │
├──────────┼────────────┼─────────┼──────────┼─────────┤
│ 1        │ 2m 30s     │ 15s     │ 1m 45s   │ 4m 30s  │
│ 2        │ 1m 50s     │ 12s     │ 1m 20s   │ 3m 22s  │
├──────────┼────────────┼─────────┼──────────┼─────────┤
│ Total    │ 4m 20s     │ 27s     │ 3m 05s   │ 7m 52s  │
└──────────┴────────────┴─────────┴──────────┴─────────┘
```

### 出力イメージ（早期終了: replan）

```
┌──────────┬────────────┬─────────┬──────────┬─────────┐
│ Attempt  │ Implement  │ Check   │ Review   │ Total   │
├──────────┼────────────┼─────────┼──────────┼─────────┤
│ 1        │ 3m 10s     │ -       │ -        │ 3m 10s  │
├──────────┼────────────┼─────────┼──────────┼─────────┤
│ Total    │ 3m 10s     │ -       │ -        │ 3m 10s  │
└──────────┴────────────┴─────────┴──────────┴─────────┘
```

## 8. 必須確認項目

- `skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/summary.py`
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/state.py`
- `skills/implementation-review-loop/src/agent_loop/cli/run_loop_cmd.py`
- `tests/test_run_loop.py`

## 9. 必須 checks

- `uv run --project skills/implementation-review-loop pytest tests/ -x`

## 10. 受け入れ条件

- ループ完了時に stderr へアテンプト別・フェーズ別の所要時間テーブルが表示される
- `summary.md` にも同等のテーブルが Markdown 表形式で含まれる
- 早期終了（replan / human）時は未実行フェーズが `-` で表示される
- 既存の `RunState` スキーマに変更がない（`RunResult` への追加のみ）
- 既存テストが通る
- approve パスと早期終了パスの両方で timing テーブルの出力を検証するテストがある
- テストでは `time.monotonic` を monkeypatch で固定値にし、deterministic に検証する

## 11. エスカレーション条件

- `RunState` のスキーマ変更が必要になった場合は B案 への切り替えを検討
- 外部ライブラリの追加が必要になった場合は相談

## 12. 実装役向けメモ

- `time.monotonic()` を使うこと（`time.time()` は不可）
- テーブル描画に外部ライブラリ（rich, tabulate 等）は追加しない
- 計測データは `RunResult.timing` で返す。`RunState` には触れない
- stderr 出力は core 層ではなく CLI 層（`run_loop_cmd.py`）で行う
- 未実行フェーズの値は `None` で記録し、表示時に `-` へ変換する
