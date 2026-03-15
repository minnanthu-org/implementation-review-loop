# TypeScript → Python 移植 実装計画書

状態: 完了
作成日: 2026-03-15
作成者: Claude

## 作業ブランチ

作業ブランチ: `feat/ts-to-python`

## 進捗

| 実施回 | Phase | 状態 | 完了日 |
|---|---|---|---|
| 1 | 0 + 1 | 完了 | 2026-03-15 |
| 2 | 2 + 3 | 完了 | 2026-03-15 |
| 3 | 4 | 完了 | 2026-03-15 |
| 4 | 5 + 6 | 完了 | 2026-03-15 |
| 5 | 7 | 完了 | 2026-03-15 |

## 1. 目的

agent-loop を TypeScript から Python に全面移植する。
`uv pip install -e .` または `pipx install .` でローカルインストールし、Node.js 依存を排除する。
プロトタイプ段階の今が移植コスト最小のタイミングであり、本格配布前にランタイムを最適化する。
PyPI への公開（パッケージ名の確保・公開ワークフロー構築）はこの計画の対象外とする。

## 2. 背景

- agent-loop の本質はシェルコマンド実行 + JSON パース + ファイル操作であり、Python の得意領域
- Python は macOS/Linux にプリインストール済みで、Node.js のインストールが不要になる
- AI SDK エコシステム（Claude API, OpenAI SDK）は Python がファーストクラス
- 現在はプロトタイプ段階（ソース約 3,600 行 + テスト約 1,800 行）のため移植コストが小さい
- 「動いている TS コードがある」は根拠として弱い — 本格配布前にベストな選択をすべき

## 3. 変更対象

### Core（`packages/agent-loop-core/src/` → `src/agent_loop/core/`）

| TS ファイル | 行数 | Python 移植先 |
|---|---|---|
| `contracts.ts` | 128 | `core/contracts.py` |
| `process.ts` | 104 | `core/process.py` |
| `checks.ts` | 134 | `core/checks.py` |
| `repo-config.ts` | 111 | `core/repo_config.py` |
| `doctor.ts` | 109 | `core/doctor.py` |
| `nested-workflow-guard.ts` | 25 | `core/nested_workflow_guard.py` |
| `run-loop.ts` | 787 | `core/run_loop/state.py`, `loop.py`, `findings.py`, `summary.py`, `io.py` |
| `structured-prompt.ts` | 63 | `core/providers/structured_prompt.py` |
| `claude.ts` | 124 | `core/providers/claude.py` |
| `codex.ts` | 53 | `core/providers/codex.py` |
| `gemini.ts` | 87 | `core/providers/gemini.py` |
| `index.ts` | 16 | `core/__init__.py` |

### CLI（`packages/agent-loop-cli/src/` → `src/agent_loop/cli/`）

| TS ファイル | 行数 | Python 移植先 |
|---|---|---|
| `init.ts` | 210 | `cli/init_cmd.py` |
| `doctor.ts` | 62 | `cli/doctor_cmd.py` |
| `new-plan.ts` | 173 | `cli/new_plan_cmd.py` |
| `plan-review.ts` | 340 | `cli/plan_review_cmd.py` |
| `code-review.ts` | 552 | `cli/code_review_cmd.py` |
| `run-loop.ts` | 220 | `cli/run_loop_cmd.py` |
| `workflow-agent.ts` | 233 | `cli/workflow_agent.py` |
| `claude-agent.ts` | 17 | （`workflow_agent.py` に統合） |
| `codex-agent.ts` | 17 | （`workflow_agent.py` に統合） |
| `gemini-agent.ts` | 18 | （`workflow_agent.py` に統合） |
| `agent-commands.ts` | 20 | `cli/agent_commands.py` |
| `assets.ts` | 7 | `cli/assets.py` |
| `index.ts` | 4 | `cli/main.py` |

### テスト（`test/` → `tests/`）

| テストファイル | 行数 |
|---|---|
| `process.test.ts` | 42 |
| `contracts.test.ts` | 100 |
| `repo-config.test.ts` | 293 |
| `init.test.ts` | 109 |
| `doctor.test.ts` | 174 |
| `claude.test.ts` | 37 |
| `gemini.test.ts` | 12 |
| `extract-json.test.ts` | 50 |
| `agent-commands.test.ts` | 28 |
| `new-plan.test.ts` | 99 |
| `plan-review.test.ts` | 119 |
| `plan-review-prompt.test.ts` | 49 |
| `code-review.test.ts` | 371 |
| `run-loop.test.ts` | 350 |

### 静的アセット（変更なし、パッケージ内に同梱）

- `schemas/*.schema.json` — 3 ファイル（内容変更なし）
- `templates/config/`, `templates/plans/`, `templates/prompts/`
- `prompts/plan-reviewer.md`

## 4. 影響範囲

- **CLI コマンド体系**: `npm run <cmd>` → `agent-loop <subcommand>` に変更（Click サブコマンド）
- **パッケージマネージャ**: npm → uv / pip
- **ビルドシステム**: TypeScript compiler → hatchling
- **テストフレームワーク**: vitest → pytest
- **スキーマバリデーション**: Zod → Pydantic v2
- **skills/**: コマンドパスの参照を更新（`node dist/xxx.js` → `agent-loop <subcommand>`）
- **AGENTS.md, README.md**: セットアップ手順の更新
- **`.gitignore`**: `dist/`, `node_modules/` → `__pycache__/`, `.venv/`, `*.egg-info/`

## 5. 非対象範囲

- 機能追加・仕様変更 — 1:1 の移植のみ行う
- JSON Schema ファイルの内容変更 — バイト単位で同一を維持
- `WORKFLOW_*` / `PLAN_REVIEW_*` 環境変数の名前・値変更 — プロセス間契約を完全に保持
- `state.json`, `finding-ledger.json` のフォーマット変更
- 新しいプロバイダーの追加
- asyncio の導入 — TS 側が同期実行のため sync `subprocess.run` で十分
- docs/implementation-plans, docs/plan-reviews, docs/implementation-reviews の内容変更

## 6. 実装方針

### 6.1 技術選定

| 項目 | 選定 | 理由 |
|---|---|---|
| パッケージ管理 | `uv` + `pyproject.toml` + `hatchling` | 最速の Python パッケージマネージャ、ネイティブ pyproject.toml 対応 |
| CLI フレームワーク | `click` | 現在の手動 argv パースと 1:1 対応、サブコマンド対応、ゼロ推移的依存 |
| スキーマバリデーション | `pydantic` v2 | Zod の直接置換、Rust コアでコンパイル済み、JSON Schema 生成対応 |
| テスト | `pytest` | `tmp_path` fixture が mkdtemp を置換、Python 標準テスト |
| Python バージョン | 3.11+ | `tomllib`, `StrEnum`, `ExceptionGroup` を利用 |
| サブプロセス | 同期 `subprocess.run` | TS コードが既に逐次実行のため asyncio 不要 |
| シェル | `/bin/zsh -lc` | TS の動作を正確に再現。`-l` で `claude`, `codex`, `gemini` 等の PATH を確保 |

### 6.2 構造上の判断

- **単一パッケージ**: TS の 2 パッケージ（core + cli）構成は npm の慣習による分割。Python では単一パッケージ `agent_loop` に統合
- **run-loop の分割**: 787 行のモノリス `run-loop.ts` を 4 ファイルのサブパッケージ（`state.py`, `loop.py`, `findings.py`, `summary.py`）+ `io.py` に分解
- **Agent エントリポイントの統合**: 3 つの同一構造ファイル（`claude-agent.ts`, `codex-agent.ts`, `gemini-agent.ts`）を `workflow_agent.py` + `--provider` フラグに統合
- **アセット配置**: `src/agent_loop/assets/` 配下に配置し `importlib.resources` で参照
- **日本語テキスト**: 文字列リテラル中の日本語はそのまま保持

### 6.3 外部契約の保持

以下は移植後も完全に同一でなければならない:

1. **WORKFLOW_* / PLAN_REVIEW_* 環境変数** (18 変数):

   run-loop / code-review 系 (15 変数):
   - `WORKFLOW_REPO_PATH`, `WORKFLOW_RUN_DIR`, `WORKFLOW_PLAN_PATH`
   - `WORKFLOW_ATTEMPT`, `WORKFLOW_OPEN_FINDINGS_PATH`, `WORKFLOW_FINDING_LEDGER_PATH`
   - `WORKFLOW_IMPLEMENTER_PROMPT_PATH`, `WORKFLOW_CODE_REVIEWER_PROMPT_PATH`
   - `WORKFLOW_IMPLEMENTER_SCHEMA_PATH`, `WORKFLOW_CODE_REVIEW_SCHEMA_PATH`
   - `WORKFLOW_IMPLEMENTER_OUTPUT_PATH`, `WORKFLOW_CHECKS_PATH`
   - `WORKFLOW_CODE_REVIEW_OUTPUT_PATH`, `WORKFLOW_REVIEW_RECORD_PATH`
   - `WORKFLOW_ACTIVE_COMMAND`

   plan-review 系 (3 変数):
   - `PLAN_REVIEW_OUTPUT_PATH`, `PLAN_REVIEW_PLAN_PATH`, `PLAN_REVIEW_REPO_PATH`

2. **JSON Schema ファイル**: `code-review-output.schema.json`, `implementer-output.schema.json`, `plan-review-output.schema.json`

3. **ファイル構造**: `.agent-loop/config.json`, `.loop/runs/`, `docs/implementation-plans/`, `docs/plan-reviews/`, `docs/implementation-reviews/`

4. **出力フォーマット**: `state.json`, `finding-ledger.json`, Markdown レビューレコード

## 7. 実装手順

コンテキストウィンドウの制約を考慮し、5 回の実施に分割する。各回は独立してコミット・レビュー可能。

| 実施回 | Phase | 主な作業量 | 完了条件 |
|---|---|---|---|
| 1 | 0 + 1 | スキャフォールド + 基盤（~270 行） | `uv run pytest tests/test_contracts.py tests/test_process.py` 通過 |
| 2 | 2 + 3 | 設定 + プロバイダー（~450 行） | `uv run pytest` で Phase 1 含む全テスト通過 |
| 3 | 4 | run-loop 分解（787 行） | `uv run pytest tests/test_run_loop.py` 通過 |
| 4 | 5 + 6 | フィクスチャ + CLI（~1,300 行） | `uv run pytest` 全テスト通過 + `agent-loop --help` 動作 |
| 5 | 7 | 統合・クリーンアップ | 必須 checks 全項目通過 |

---

### 実施回 1: Phase 0 + 1 — スキャフォールド + 基盤レイヤー

#### Phase 0: スキャフォールディング

1. 既存 TS ソースとテストを `_legacy_ts/` に **コピー**（仕様参照用。元の `packages/` と `test/` はこの時点では削除しない）
   - `packages/` → `_legacy_ts/`
   - `test/` → `_legacy_ts/test/`
2. `pyproject.toml` を作成（`hatchling` ビルドバックエンド、`click` + `pydantic` 依存）
3. パッケージディレクトリ構造を作成:
   ```
   src/agent_loop/__init__.py
   src/agent_loop/py.typed
   src/agent_loop/assets/schemas/
   src/agent_loop/assets/templates/
   src/agent_loop/assets/prompts/
   src/agent_loop/core/__init__.py
   src/agent_loop/core/providers/__init__.py
   src/agent_loop/core/run_loop/__init__.py
   src/agent_loop/cli/__init__.py
   ```
4. 静的アセット（JSON Schema, テンプレート, プロンプト）をパッケージ内にコピー
5. `tests/conftest.py` を作成
6. `uv sync` で開発環境を確認

#### Phase 1: 基盤レイヤー

依存関係のないモジュールから順に移植:

1. **`contracts.py`** — 全 Zod スキーマを Pydantic v2 モデルに変換。`CodeReviewOutput`, `ImplementerOutput`, `PlanReviewOutput`, `FindingLedgerEntry` 等。バリデーション動作が TS 版と一致することをテストで検証（JSON Schema ファイルは静的アセットをそのまま同梱するため、Pydantic からの生成一致は不要）
2. **`process.py`** — `subprocess.run` ラッパー。タイムアウト、stdin パス、stdout/stderr キャプチャを実装
3. **`nested_workflow_guard.py`** — `WORKFLOW_ACTIVE_COMMAND` 環境変数によるネスト起動防止
4. **`assets.py`** — `importlib.resources` によるアセットパス解決

各モジュールの対応テストも同時に移植。

**完了条件**: `uv run pytest tests/test_contracts.py tests/test_process.py` 通過

---

### 実施回 2: Phase 2 + 3 — 設定 + プロバイダーレイヤー

#### Phase 2: 設定レイヤー

1. **`checks.py`** — チェックコマンド設定の読み込みとバリデーション
2. **`repo_config.py`** — リポジトリ設定の読み込み。`compat-loop` / `delegated` モード対応

対応テスト (`test_checks.py`, `test_repo_config.py`) も同時に移植。

#### Phase 3: プロバイダーレイヤー

1. **`claude.py`** — Claude CLI 呼び出し。`extract_json()` を含む
2. **`codex.py`** — Codex CLI 呼び出し。シェルエスケープ処理
3. **`gemini.py`** — Gemini CLI 呼び出し。JSON Schema インジェクション
4. **`structured_prompt.py`** — プロバイダーディスパッチャ
5. **`doctor.py`** — リポジトリ設定バリデーション

対応テスト移植。

**完了条件**: `uv run pytest` で Phase 1 含む全テスト通過

---

### 実施回 3: Phase 4 — Run Loop

787 行の `run-loop.ts` を分解して移植:

1. **`io.py`** — JSON ファイル読み書きヘルパー
2. **`state.py`** — `RunState` 管理（初期化、更新、永続化）
3. **`findings.py`** — Finding Ledger の管理（追加、更新、ステータス変更）
4. **`summary.py`** — 実行サマリーの Markdown 生成
5. **`loop.py`** — メインループ（implementer → checks → reviewer サイクル）

`test_run_loop.py` で統合テストを移植。

**完了条件**: `uv run pytest tests/test_run_loop.py` 通過

---

### 実施回 4: Phase 5 + 6 — フィクスチャ + CLI レイヤー

#### Phase 5: モックフィクスチャ変換

テストで使用する `.mjs` モックスクリプトを Python スタンドアロンスクリプトに変換。
`#!/usr/bin/env python3` で直接実行可能にする。

#### Phase 6: CLI レイヤー

Click サブコマンドとして全 CLI コマンドを実装:

1. **`main.py`** — Click グループ定義（エントリポイント）
2. **`init_cmd.py`** — `agent-loop init`
3. **`doctor_cmd.py`** — `agent-loop doctor`
4. **`new_plan_cmd.py`** — `agent-loop plan new`
5. **`plan_review_cmd.py`** — `agent-loop plan review`
6. **`code_review_cmd.py`** — `agent-loop code review`
7. **`run_loop_cmd.py`** — `agent-loop loop run` / `agent-loop loop init`
8. **`workflow_agent.py`** — `agent-loop agent run --provider <provider> --role <role>`
9. **`agent_commands.py`** — デフォルトコマンドパス生成

CLI コマンドマッピング:

```
npm run init           →  agent-loop init
npm run doctor         →  agent-loop doctor
npm run plan:new       →  agent-loop plan new
npm run plan:review    →  agent-loop plan review
npm run code:review    →  agent-loop code review
npm run loop:init      →  agent-loop loop init
npm run loop:run       →  agent-loop loop run
```

**完了条件**: `uv run pytest` 全テスト通過 + `agent-loop --help` 動作

---

### 実施回 5: Phase 7 — 統合・クリーンアップ

1. 全テストスイート実行（`pytest`）
2. skills/ 内のコマンド参照を更新
3. README.md, AGENTS.md を更新
4. `.gitignore` を Python 用に更新
5. `package.json`, `tsconfig*.json`, `node_modules/`, `dist/` を削除
6. 元の `packages/` と `test/` ディレクトリを削除（この時点で `_legacy_ts/` が唯一の TS 参照元になる）
7. `_legacy_ts/` を別コミットで削除

**完了条件**: セクション 9「必須 checks」の全項目通過

## 8. 必須確認項目

### 移植元（TS 仕様参照）

- `_legacy_ts/agent-loop-core/src/contracts.ts` — 全データ契約の定義
- `_legacy_ts/agent-loop-core/src/run-loop.ts` — メインループロジック（最大ファイル、787 行）
- `_legacy_ts/agent-loop-cli/src/code-review.ts` — 最複雑 CLI モジュール（552 行、git 統合含む）
- `_legacy_ts/agent-loop-cli/src/workflow-agent.ts` — WORKFLOW_* 環境変数契約の中心（233 行）
- `_legacy_ts/agent-loop-cli/src/plan-review.ts` — PLAN_REVIEW_* 環境変数契約（340 行）
- `_legacy_ts/agent-loop-core/src/claude.ts` — `extract_json()` のエッジケース処理

### 外部契約

- `schemas/*.schema.json` — 3 ファイル（内容同一を維持）
- `WORKFLOW_*` / `PLAN_REVIEW_*` 環境変数 — 18 変数の名前と値形式
- `state.json`, `finding-ledger.json` — JSON 構造

### テスト

- `test/run-loop.test.ts` — 統合テスト（受け入れ条件の定義）
- `test/code-review.test.ts` — 最大テストファイル（371 行）
- `test/repo-config.test.ts` — 設定バリデーションテスト（293 行）

## 9. 必須 checks

- `uv run pytest` — 全テスト通過
- `uv run mypy src/` — 型チェック通過（厳密モード推奨）
- `uv pip install -e .` → `agent-loop --help` — CLI エントリポイント動作確認
- `pipx install .` → `agent-loop init --repo /tmp/test` — ローカルからの配布形態での動作確認

## 10. 受け入れ条件

- 全 14 テストファイルの Python 移植が完了し、`pytest` で全テスト通過
- `pipx install .`（ローカルソースから）で Node.js なし環境にインストール可能
- 全 CLI サブコマンド（`init`, `doctor`, `plan new`, `plan review`, `code review`, `loop init`, `loop run`）が TS 版と同一の動作をすること
- `WORKFLOW_*` / `PLAN_REVIEW_*` 環境変数の名前・値が TS 版と完全一致
- JSON Schema ファイル 3 つは既存の静的ファイルをそのままパッケージに同梱し、内容を変更しないこと（Pydantic からの再生成は不要）
- `state.json`, `finding-ledger.json` の出力フォーマットが TS 版と互換
- Markdown レビューレコードの出力形式が TS 版と同一
- skills/ 内のコマンド参照が更新済み
- `mypy --strict` でエラーなし

## 11. エスカレーション条件

次のような場合は `replan` または `human` に戻す:

- Pydantic v2 で Zod スキーマの制約を正確に再現できない場合
- `subprocess.run` の動作が TS の `child_process` と異なる挙動を示す場合（シグナル処理等）
- `click` のサブコマンド構造で既存の CLI インターフェースを再現できない場合
- プロバイダー CLI（claude, codex, gemini）の呼び出し方が Python 環境で異なる動作をする場合
- `importlib.resources` でアセット解決が期待通り動作しない場合
- テストのモックフィクスチャ変換で `.mjs` → Python の動作差異が発生する場合

## 12. 実装役向けメモ

- **仕様参照は `_legacy_ts/` の TS ソース**: 移植時は必ず対応する TS ファイルを先に読むこと。推測で実装しない。Phase 0 完了後は元の `packages/` も残っているが、仕様参照は `_legacy_ts/` を正とする
- **1:1 移植に徹する**: 機能追加・リファクタ・「Python らしい改善」は一切行わない。TS の動作を忠実に再現する
- **Phase 順を厳守**: 依存関係順に組んであるため、Phase をスキップしない
- **run-loop.ts の分割は慎重に**: 787 行のモノリスを 4+1 ファイルに分解する際、関数の境界を TS ソースで確認してから分割する
- **テストは各 Phase で同時に書く**: Phase 完了後にまとめてテストを書くのではなく、モジュールごとにテストも移植する
- **JSON Schema ファイルは生成しない**: 既存の静的 `.schema.json` ファイルをそのままパッケージに同梱する。Pydantic の `model_json_schema()` からの再生成は行わない（差分で移植が止まるリスクを回避）
- **JSON 出力の互換性テストを追加**: `state.json` や `finding-ledger.json` 等の出力で、キー名・構造が TS 版と一致することを検証する
- **日本語文字列はそのまま**: プロンプトやテンプレート中の日本語を翻訳・変更しない
- **この計画の範囲外の最適化はしない**: asyncio 化、型の改善、エラーハンドリングの強化等は別タスク
