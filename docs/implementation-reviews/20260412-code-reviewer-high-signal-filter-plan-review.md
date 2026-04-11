# 計画書レビュー: `20260412-code-reviewer-high-signal-filter.md`

作成日: 2026-04-12
対象計画: `docs/implementation-plans/20260412-code-reviewer-high-signal-filter.md`
レビュー種別: plan review（実装前の検証）

## 概要

計画の方針（prompt 1 枚の編集で Anthropic 公式 `/code-review` プラグインの high-signal 基準と false-positive deny-list を取り込む）は妥当で、スコープ制御も丁寧。ただし、本文に **修正前に解消しておくべき矛盾・不正確な記述・運用漏れが 3 件** あり、そのまま実装に入ると実装者が解釈を誤る可能性がある。

## 前提事実の確認

| 項目 | 結果 | 確認ポイント |
|---|---|---|
| `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/code-reviewer.md` のパス | ✅ 一致 | 計画 §3 |
| 現行構造「Role / レビュー観点 / Verdict ルール / やってはいけないこと」 | ✅ 一致 | 計画 §2 の記述通り |
| `implementer.md` の反論許容条項 | ✅ 存在 | `implementer.md:31`「根拠が不十分または事実誤認に基づく指摘には修正で対応せず、具体的な根拠を示して反論する」 |
| `code-review-output.schema.json` の severity enum = `low / medium / high` | ✅ 一致 | `additionalProperties: false` の厳格 schema |
| reviewer invocation に `WORKFLOW_IMPLEMENTER_OUTPUT_PATH` が渡る | ✅ 存在 | `loop.py:214-222` の `build_workflow_environment(..., implementer_output_path=implementer_output_path)` |
| `resolve_run_loop_options` の所在 | ✅ `loop.py:341` |
| `init_cmd.py` が template を `.agent-loop/prompts/code-reviewer.md` にコピー | ✅ `init_cmd.py:67-71` |
| `uv run --project skills/implementation-review-loop pytest tests/ -x` が動く | ✅ 78 passed |
| `code-reviewer.md` の文字列に依存する既存テスト | ❌ **無し** — 全テストが `# Code Reviewer\n` プレースホルダで上書きしてから使う |

## 指摘

### [P1] §6 draft と §12 実装メモが矛盾している

- 対象:
  - `docs/implementation-plans/20260412-code-reviewer-high-signal-filter.md` §6 L64-66（改訂後の prompt 構造の draft）
  - 同 §12 L159（実装役向けメモ）
- 内容:
  - §6 の draft は `WORKFLOW_IMPLEMENTER_OUTPUT_PATH が指す JSON の summaryMd フィールドで取得できる` と **環境変数名を hard-code** している。
  - 一方 §12 は `環境変数名を hard code せず、「直近試行の implementer 出力」と自然文で書き、運用側の env 名に依存しない表現にする` と **hard-code を明確に禁じている**。
  - 実装者は §6 と §12 のどちらに従うかを自分で判断しなければならず、判断を誤ると「自然文で書け」という §12 の原則が空文化する。
- 影響:
  - prompt が runtime 詳細（env 変数名）と疎結合である、という本計画の肝の一つが損なわれ得る。
  - reviewer prompt に runtime 名が固定されると、将来 env 変数を rename した際に prompt も同時に追従しないと意味が通らなくなる。
- 対応案:
  - §6 の draft 冒頭に「draft は illustrative であり、実際の文言は §12 に従う」と注記を追加する。
  - もしくは §6 L64-66 を直接書き換えて、env 変数名を出さない自然文（例: 「直近試行の implementer response の JSON に含まれる `summaryMd` を参照する」）にする。

### [P2] §6 の env 変数に関する parenthetical が事実と異なる

- 対象:
  - `docs/implementation-plans/20260412-code-reviewer-high-signal-filter.md` §6 L53
- 内容:
  - 計画は `loop.py が既に WORKFLOW_IMPLEMENTER_OUTPUT_PATH (前試行では WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH) を reviewer 環境に渡しており` と書いている。
  - 実際の `loop.py:321-338` の挙動:
    - `WORKFLOW_IMPLEMENTER_OUTPUT_PATH` = **現在の attempt** の implementer response（reviewer に常に渡される）
    - `WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH` = **前 attempt** の implementer response（`attempt >= 2` のときのみ追加で set される）
  - 両者は「前試行では名前が違う」ではなく、attempt 2 以降は **両方同時に** set される別々の変数。
- 影響:
  - 実装者が parenthetical を鵜呑みにすると、reviewer prompt に誤った説明を書き込む可能性がある（例: 「前試行の出力は `WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH` にある」としか書かず、現試行の出力経路を見落とす等）。
  - §12 に従って env 変数名を hard-code しない自然文で書けば実害は出ないが、計画本文としては不正確。
- 対応案:
  - parenthetical を削除する、または正確な記述（「現 attempt の出力と、attempt 2 以降は前 attempt の出力も併せて渡る」）に書き換える。

### [P2] 自リポジトリの `.agent-loop/prompts/code-reviewer.md` への反映が漏れている

- 対象:
  - `skills/implementation-review-loop/src/agent_loop/cli/init_cmd.py:86-88`（既存ファイルのスキップ挙動）
  - `/Users/kegasawa/git/implementation-review-loop/.agent-loop/prompts/code-reviewer.md`（このリポジトリ自身の live copy）
- 内容:
  - `init_cmd.py` は `if Path(dest).exists(): skipped_files.append(dest); continue` のため、`agent-loop init` を再実行しても既存の `.agent-loop/prompts/code-reviewer.md` は **上書きされない**。
  - このリポジトリにも既に `.agent-loop/prompts/code-reviewer.md` があり、template との差分は末尾改行のみ（= 内容は完全一致）。
  - 計画通り template だけを編集した場合、
    - 新規 `init` されるリポジトリ → 新仕様が適用される
    - 既存リポジトリ（このリポジトリを含む） → 変化なし
  - 計画 §10 の受け入れ条件は「init_cmd 経由で新規リポジトリに prompt を配置した場合」に限定しており、厳密には矛盾していないが、**この変更を自リポジトリの run loop に即座に反映させたい場合、template 編集と同時に自リポジトリの live copy も同期する必要がある**。
- 影響:
  - この変更自体が `implementation-review-loop` 自身を使った dogfooding（自リポジトリ内で loop を回して効果を検証する）で評価されるケースでは、live copy を同期しないと効果ゼロに見える。
  - 新規 repo には効くが既存 repo には効かない、という非対称性が計画に明示されていない。
- 対応案:
  - §7 実装手順または §10 受け入れ条件に「自リポジトリの `.agent-loop/prompts/code-reviewer.md` を template と同じ内容に同期する」ステップを追加する。
  - もしくは「既存リポジトリは本計画のスコープ外。必要に応じて手動同期する」と明示する。

### [P3] §7 step 8「既存テストの最小限更新」は現状 no-op

- 対象:
  - `docs/implementation-plans/20260412-code-reviewer-high-signal-filter.md` §7 step 8
- 内容:
  - 計画は「tests/ に prompt 内容を直接 assert しているテストがあれば、追加したセクション見出しを含めるよう最小限に更新する」と書いているが、`tests/` 配下で `code-reviewer.md` の本文に assert する箇所は **0 件**。テストはすべて `# Code Reviewer\n` のプレースホルダで上書きしてから使う設計。
- 影響:
  - step 7「既存テストがテンプレート文字列の prefix や特定語句に依存していないか確認」は妥当な safety net として残して問題ない。
  - ただし step 8 は実際には何もしないので、実装者が「どのテストを更新するのか」を探し回る無駄が生じる可能性がある。
- 対応案:
  - step 8 を削除、または「現状該当テスト無し。step 7 の確認で問題が出た場合のみ対応する」と注記する。

### [P3] style 参照 `plan-reviewer.md` の所在ディレクトリが異なる

- 対象:
  - `docs/implementation-plans/20260412-code-reviewer-high-signal-filter.md` §12 L157
- 内容:
  - 計画は「既存の `implementer.md` / `plan-reviewer.md` と揃える」と書いているが:
    - `implementer.md` → `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/`
    - `plan-reviewer.md` → `skills/implementation-review-loop/src/agent_loop/assets/prompts/`（**テンプレートではなく agent-loop 本体が直接使う prompt**）
  - 別ディレクトリにあることは実害ではない（style 参考として読めば十分）が、実装者が `templates/prompts/` 配下だけを見て `plan-reviewer.md` が無いと混乱する可能性がある。
- 対応案:
  - §12 に `plan-reviewer.md` の実際のパスを添える（1 行の脚注で十分）。

## 確認したこと

- `uv run --project skills/implementation-review-loop pytest tests/ -x` → 78 passed
- `code-review-output.schema.json` の severity enum = `["low", "medium", "high"]` で変更不要
- `loop.py:214-222` で reviewer invocation が `implementer_output_path` を受け取って環境変数化している
- `init_cmd.py:86-88` の既存ファイルスキップ挙動
- `.agent-loop/prompts/code-reviewer.md` と template の内容は末尾改行以外同一
- `tests/` 配下で `code-reviewer.md` の本文文字列に依存するテストは 0 件

## 総評

スコープ制御は非常に良い:

- 触らないもの（schema, `loop.py`, `findings.py`, `state.py`, severity enum, `plan-reviewer.md`）を §4 / §5 で明示
- §11 でエスカレーション条件を具体化
- 2 段階バリデーション層、agent 分割、CLAUDE.md path scoping、pre-flight skip など **大きな変更は別計画に切り離している**
- 公式プラグインの思想（allow-list 3 カテゴリ / deny-list 6 項目）が §2 と §6 で具体的に引用されている

したがって、この計画の方向性自体は十分採用可能。ただし [P1] の §6 と §12 の矛盾、および [P2] の 2 件（env 変数の不正確な parenthetical、自リポジトリの live copy への反映漏れ）は、**実装に入る前に計画本文に反映しておくことを推奨する**。[P1] は実装者が判断を誤ると本計画の肝である「prompt を runtime 詳細から切り離す」原則が崩れる可能性があるため、放置しない方がよい。

## 指摘一覧

| # | 種別 | 箇所 | 内容 |
|---|---|---|---|
| 1 | P1 | §6 L64-66 / §12 L159 | §6 draft が env 変数名を hard-code、§12 が hard-code を禁止しており矛盾 |
| 2 | P2 | §6 L53 | `WORKFLOW_IMPLEMENTER_OUTPUT_PATH` / `WORKFLOW_PREV_*` の関係性の説明が事実と異なる |
| 3 | P2 | §7 / §10 | 自リポジトリの `.agent-loop/prompts/code-reviewer.md` への反映ステップが無い |
| 4 | P3 | §7 step 8 | 対象テストが 0 件のため step 8 は no-op |
| 5 | P3 | §12 L157 | `plan-reviewer.md` の所在ディレクトリが `implementer.md` と異なることが書かれていない |
