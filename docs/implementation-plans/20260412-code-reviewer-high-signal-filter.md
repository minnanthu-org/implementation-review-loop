# 実装計画書: `code-reviewer` prompt に high-signal 基準と false-positive deny-list を追加

状態: 指摘対応済み (rev.2)
作成日: 2026-04-12
作成者: kegasawa

## 1. 目的

Anthropic 公式 `/code-review` プラグイン (`anthropics/claude-code/plugins/code-review/commands/code-review.md`) の high-signal 基準と false-positive deny-list を、本ループの reviewer prompt に取り込む。
reviewer が生成する finding の信号雑音比を、アーキテクチャ変更なしで向上させる。

## 2. 背景

- 公式プラグインは 4 並行エージェント + 2 段階バリデーションで **false positive を積極的に排除** する設計になっており、その意図は prompt 本文の **「flag する条件の allow-list」と「flag しない条件の deny-list」** として明示されている。
- 現行の `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/code-reviewer.md` は「レビュー観点」「Verdict ルール」「やってはいけないこと」の 3 ブロックで、観点は具体的だが **どの程度の確度で flag してよいか** の閾値が言語化されていない。
- 結果、reviewer が実装で反論される nit 寄りの finding（style、過剰な一般論、既存コードへの言及など）を拾ってしまう傾向がある。implementer 側は `code-reviewer.md` の指示と矛盾しない範囲で「根拠が不十分または事実誤認に基づく指摘には反論せよ」と書かれており、下流での打ち消しは効いているが、上流で減らす方が総コスト・総ターン数の両面で得。
- 本ループは計画書ベースで動くため、PR 向けプラグインの全機構をそのまま持ち込む必要はない。prompt 文言の改訂だけで **プラグインと同じ哲学を注入できる**のがこの変更のスコープ。

参考: 公式プラグインの高信号基準は 3 カテゴリのみ (compile/parse 不能、入力によらず明確に誤り、CLAUDE.md 違反で該当ルールが引用可能)。deny-list は 6 項目 (pre-existing、見かけ上のバグで実は正しいもの、pedantic nit、linter で検出可能なもの、明示されない一般的品質懸念、コード中で silence されているもの)。

## 3. 変更対象

本計画で編集するテキストファイルは **次の 2 枚のみ**（Python コード・schema・テストは変更しない）:

- `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/code-reviewer.md`（本家 template）
- `/Users/kegasawa/git/implementation-review-loop/.agent-loop/prompts/code-reviewer.md`（自リポジトリの live copy、template と同一内容にする）

`init_cmd.py:86-88` が既存の `.agent-loop/prompts/*` を上書きしないため、template 編集だけでは自リポジトリ（dogfooding 対象）には反映されない。よって live copy も本計画の明示的な変更対象に含める。

`tests/` 配下に `code-reviewer.md` 本文に依存する assert は現状 0 件（`# Code Reviewer\n` プレースホルダで上書きする設計）のため、テストファイルは変更対象に含めない。

## 4. 影響範囲

- `code-reviewer.md` は `repo_config` 経由で各リポジトリの reviewer prompt として使用される (`loop.py` の `resolve_run_loop_options` で `repo_config.prompts.reviewer` からパスが解決される)。
- prompt 本体の変更のみのため、`CodeReviewOutput` schema、`loop.py`、`findings.py`、`state.py` は変更しない。
- severity 列挙 (`low` / `medium` / `high`) も変更しない。プラグインの "Important / Nit / Pre-existing" は **severity 値の追加ではなく文中の言及**として反映する。
- 既に本リポにある他の reviewer prompt（`plan-reviewer.md`）は対象外。

## 5. 非対象範囲

以下は本計画では扱わない。必要になった時点で別計画として切る。

- **2 段階バリデーション層の追加**（`loop.py` / `findings.py` に validator stage を挿入するアーキテクチャ変更）
- **compliance reviewer / bug reviewer の 2 役並列化**（schema と loop 構造の変更が必要）
- **CLAUDE.md の path-scoped ロード**（新機能、reviewer 側で CLAUDE.md を探索する導線の追加）
- **pre-flight skip**（diff 空、前回と同一などでのスキップ。`loop.py` の attempt ループ外の制御追加）
- **severity enum の刷新**（`low/medium/high` → `important/nit/pre_existing` 相当への移行は schema 互換性の検討が必要）

## 6. 実装方針

prompt の改訂のみで 3 つのナレッジを注入する:

1. **高信号 allow-list** を新セクションとして追加。flag する条件を 3 項目に限定し、**それ以外は flag しない**ことを明記する。
2. **false-positive deny-list** を新セクションとして追加。実装時に頻出する false positive を列挙し、「これらは finding に含めない」と指示する。
3. **確度ゲート** を追加。「issue が real だと確信できないなら flag しない。false positive は信頼を損なう」旨を 1 行で記載する。

schema 互換のため、**severity は既存の `low / medium / high` を維持**し、プラグインの Important / Nit / Pre-existing は prompt 内で **`high` / `low` / `low`（かつ pre-existing は本ループでは原則 flag しない）** としてマッピング指示する。

author intent の注入については、2 つの経路がある:

- **`loop run`**: `loop.py:321-338` が reviewer 環境に現 attempt の implementer 出力を常時渡しており、`attempt >= 2` では前 attempt の出力もあわせて渡る。`summaryMd` は implementer が実際に書いた意図説明。
- **`code:review`（one-shot）**: `code_review_cmd.py:132-139` が固定文字列 `"One-shot code review request."` を implementer 出力の `summaryMd` に書き込む。つまり one-shot では `summaryMd` に意図情報が載らない。

したがって「意図の把握」セクションは **`summaryMd` を第一情報源とせず、計画書を一次情報源とし、`summaryMd` は補足とする** 方向で書く。計画書は両経路で常に reviewer に渡されており、計画の目的・手順・スコープが書かれているため、intent 源として最も堅牢。本計画ではこの扱いを prompt 文言で明示する（環境変数名は prompt に書かず、`state.py` や env の追加も行わない）。

### 改訂後の prompt 構造（案）

```markdown
# Code Reviewer

## Role
（現行を維持）

## 意図の把握（追加）
- finding を立てる前に、まず **計画書** を読み、この変更の目的・
  スコープ・非対象範囲を把握する（計画書は両経路で常に渡される）。
- 直近試行の implementer response が意味のある `summaryMd` を
  含む場合は、補足情報として参照する。one-shot review では
  `summaryMd` が placeholder のことがあるため、これ単体を意図源に
  してはならない。
- 計画書と `summaryMd` を突き合わせ、「事故」と「意図的」を
  区別してから finding を立てる。

## レビュー観点
（現行を維持）

## Flag する条件（追加: high-signal allow-list）
次の 3 条件のいずれかに該当する場合にのみ finding を立てる。

1. コードが compile / parse に失敗する
   （syntax error、type error、missing import、未解決参照など）
2. 入力によらず明確に誤った結果を生む
   （明白な logic error）
3. 承認済み計画または repo の規約に対する明確な違反で、
   該当ルールを具体的に引用できる

## Flag しない条件（追加: false-positive deny-list）
次のいずれかに該当するものは finding に含めない。

- pre-existing な問題（このループで変更されていない箇所のバグ）
- 一見バグに見えるが実際には正しい挙動のもの
- senior engineer が flag しないような pedantic nit
- linter が拾える類の指摘（検証のために linter を走らせる必要もない）
- test coverage 不足や一般的な security 懸念のような
  品質一般論（計画または規約に明示されていない限り）
- コード中で明示的に silence されている指摘
  （例: lint ignore comment がついているもの）

## 確度ゲート（追加）
issue が real であると確信できない場合は flag しない。
false positive は reviewer の信頼を損ない、総コストを増やす。

## Severity マッピング
- `high`: 上記 Flag 条件 1 または 2（compile 失敗 / 入力によらず誤り）
- `medium`: 上記 Flag 条件 3（計画・規約違反）のうち正しさに影響するもの
- `low`: 上記 Flag 条件 3 のうち軽微なもの
- pre-existing は原則 flag しない（deny-list に従う）

## Verdict ルール
（現行を維持）

## やってはいけないこと
（現行を維持）
```

## 7. 実装手順

1. `code-reviewer.md` に **「意図の把握」** セクションを `## Role` の直後に追加する。1 段落のみ。
2. 既存の **「レビュー観点」** セクションの直後に **「Flag する条件」** セクションを追加する。3 項目の箇条書き。
3. その直後に **「Flag しない条件」** セクションを追加する。6 項目の箇条書き。
4. その直後に **「確度ゲート」** セクションを追加する。2 行のみ。
5. **「Severity マッピング」** セクションを追加し、既存 enum (`low` / `medium` / `high`) と Flag 条件の対応を明示する。
6. **「Verdict ルール」** と **「やってはいけないこと」** は現行を維持する（文言変更なし）。
7. 既存テストがテンプレート文字列の prefix や特定語句に依存していないかを確認し、壊れていれば調整する。現時点では `tests/` 配下で `code-reviewer.md` の本文に assert しているテストは 0 件（`# Code Reviewer\n` プレースホルダで上書きする設計）のため、通常はこの step は no-op。
8. 自リポジトリの `.agent-loop/prompts/code-reviewer.md` を template と同一内容にする（§3 の 2 ファイル目）。`init_cmd.py:86-88` は既存ファイルをスキップするため、`agent-loop init` の再実行では上書きされない。dogfooding で本変更の効果を自リポジトリで即座に評価するために必須。
9. `code:review` と `loop run` の両経路で新しい prompt が破綻しないか、ドライランで文言を読んで確認する。特に `code_review_cmd.py:132-139` が `summaryMd` に placeholder を書き込むことを踏まえ、「意図の把握」セクションが計画書を一次情報源にしていることを確認する（実ラン無しで prompt の整合性レビューでよい）。

## 8. 必須確認項目

- `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/code-reviewer.md`
- `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/implementer.md`（反論許容ルールと整合することだけ確認、変更しない）
- `skills/implementation-review-loop/src/agent_loop/assets/schemas/code-review-output.schema.json`（severity enum の確認のみ、変更しない）
- `skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`（`build_workflow_environment` が reviewer に現 attempt の implementer 出力を渡していることの確認のみ、変更しない）
- `/Users/kegasawa/git/implementation-review-loop/.agent-loop/prompts/code-reviewer.md`（step 8 で template と同期する対象）
- prompt を `assets` からコピーする側の init / doctor コード（`init_cmd.py`, `assets.py`）に hard-coded な内容チェックがないか確認
- 既存テストで `code-reviewer.md` の文字列に依存するものの有無

## 9. 必須 checks

- `uv run --project skills/implementation-review-loop pytest tests/ -x`

## 10. 受け入れ条件

- `code-reviewer.md` に「意図の把握」「Flag する条件」「Flag しない条件」「確度ゲート」「Severity マッピング」の 5 セクションが追加されている
- 既存の「Role」「レビュー観点」「Verdict ルール」「やってはいけないこと」の文言は変更されていない
- `CodeReviewOutput` schema（severity enum 含む）に変更がない
- `loop.py` / `findings.py` / `state.py` に変更がない
- `tests/` が通る
- `init_cmd` 経由で新規リポジトリに prompt を配置した場合、追加したセクションを含む prompt が配置される
- 自リポジトリの `.agent-loop/prompts/code-reviewer.md` が template と同一内容に同期されている（dogfooding 即反映のため）
- 「意図の把握」セクションが **計画書を一次情報源とする** 文言になっており、`summaryMd` を唯一の意図源として扱っていない（`code:review` の one-shot placeholder で破綻しないこと）
- prompt の追加箇所が repo の既存表記（敬体・漢字かな配分）と揃っている

## 11. エスカレーション条件

次のような場合は `replan` または `human` に戻す。

- prompt への追記だけでは deny-list が効かない兆候が run log から見られる（例: 追記後の複数回実行で pre-existing な指摘が依然として頻出する）→ 2 段階バリデーション層の導入を別計画として検討
- severity enum の `low / medium / high` と Flag 条件のマッピングが実装者・レビュアー間で合意できない → severity enum 刷新を別計画として切る
- implementer 出力が reviewer 環境に渡っていないコードパスが見つかった → `loop.py` 側の修正が必要となり、本計画のスコープを超える

## 12. 実装役向けメモ

- **schema と Python コードは触らない**。編集するのは §3 で列挙した prompt テキストファイル **2 枚**（template + 自リポジトリの live copy）のみ。内容は両者同一にする。
- 既存セクションの **文言を書き換えない**。追加のみ。
- 追加セクションの順序は 6.「改訂後の prompt 構造（案）」のとおり。
- deny-list と allow-list の文言は、公式プラグインの原文を直訳せず、本 repo の他 prompt と同じ **敬体・簡潔体** で書く。style の参考は以下 2 ファイル（所在が異なることに注意）:
  - `skills/implementation-review-loop/src/agent_loop/assets/templates/prompts/implementer.md`（template）
  - `skills/implementation-review-loop/src/agent_loop/assets/prompts/plan-reviewer.md`（agent-loop 本体が直接使う prompt、template ではない）
- severity マッピングを書くときに、schema の enum が `low` / `medium` / `high` のままであることを必ず確認してから書く（enum を変える計画ではない）。
- implementer 出力を prompt から参照する際は、**環境変数名を hard code しない**。`WORKFLOW_IMPLEMENTER_OUTPUT_PATH` のような runtime 詳細は prompt に書かず、「直近試行の implementer response」など自然文で書く。運用側の env 名に prompt を結合させない。
- 本計画はプラグインの 7 ナレッジのうち **3 項目 (high-signal allow-list / false-positive deny-list / 意図の把握)** のみ扱う。残りの 4 項目 (2 段階バリデーション、agent 分割、CLAUDE.md path scoping、pre-flight skip) は別計画として切る想定。prompt の肥大化を避けるため、本計画のスコープから逸脱しない。
