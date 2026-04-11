# implementation-review-loop レビュー記録

作成日: 2026-04-12
対象リポジトリ: `/Users/kegasawa/git/implementation-review-loop`

## 概要

`implementation-review-loop` は、GitHub Actions や PR コメントを状態機械にせず、CLI とローカル状態で implement-check-review を回す設計になっており、全体方針はかなり良い。

一方で、現時点では本番採用前に直したい P1 が 2 件ある。

## 指摘

### [P1] model 引数が shell command に未エスケープで埋め込まれる

- 対象:
  - `/Users/kegasawa/git/implementation-review-loop/skills/implementation-review-loop/src/agent_loop/cli/agent_commands.py`
  - `/Users/kegasawa/git/implementation-review-loop/skills/implementation-review-loop/src/agent_loop/core/providers/gemini.py`
  - `/Users/kegasawa/git/implementation-review-loop/skills/implementation-review-loop/src/agent_loop/core/process.py`
- 内容:
  - `default_implementer_command` / `default_reviewer_command` は `--model {model}` をそのまま文字列結合している。
  - Gemini provider も `--model {model}` を未エスケープで結合している。
  - 実行は `/bin/zsh -lc` なので、model 文字列に shell 制御文字が入るとコマンド注入や意図しない分割実行が起こりうる。
- 確認:
  - `x; echo injected` を model に与えると、生成されるコマンドにそのまま `; echo injected` が含まれた。
- 影響:
  - CLI 利用時の安全性に直結する。
  - 外部入力をそのまま流さない運用でも、将来の拡張や wrapper から呼ばれると事故りやすい。
- 対応案:
  - model を command string に埋め込まず、引数配列ベースで subprocess 実行する。
  - 少なくとも `shell_escape` 相当で model を必ず quote する。

### [P1] run ID が秒精度のため同秒起動で衝突する

- 対象:
  - `/Users/kegasawa/git/implementation-review-loop/skills/implementation-review-loop/src/agent_loop/core/run_loop/state.py`
  - `/Users/kegasawa/git/implementation-review-loop/skills/implementation-review-loop/src/agent_loop/core/run_loop/loop.py`
- 内容:
  - `build_run_id()` は plan stem と秒精度 timestamp だけで run ID を作る。
  - `initialize_run()` はその ID の directory を `exist_ok=True` で作成する。
  - 同じ plan を同じ秒に 2 回起動すると、同じ `runDir` を共有して state や review artifact が混ざる。
- 確認:
  - 固定 timestamp で `build_run_id()` を 2 回呼ぶと同じ値を返した。
- 影響:
  - 並列起動や連打時に run の独立性が壊れる。
  - 調査や再実行時の信頼性が下がる。
- 対応案:
  - run ID に millisecond / random suffix / UUID を入れる。
  - もしくは `exist_ok=False` で衝突を即エラーにする。

### [P3] mypy が green ではない

- 対象:
  - `/Users/kegasawa/git/implementation-review-loop/tests/test_repo_config.py`
  - `/Users/kegasawa/git/implementation-review-loop/tests/test_run_loop.py`
- 内容:
  - `uv run mypy skills/implementation-review-loop/src tests` が失敗する。
  - 主な内容は未使用の `type: ignore` と `AttemptTiming` への型不一致。
- 影響:
  - 実行時の blocker ではない。
  - ただし strict 運用を目指す package としては、将来の refactor 耐性を少し落とす。
- 対応案:
  - 不要な `type: ignore` を外す。
  - test の timing fixture を `AttemptTiming` に合わせて型付けする。

## 確認したこと

- `uv run pytest` は成功
  - `69 passed in 1.38s`
- `uv run mypy skills/implementation-review-loop/src tests` は失敗
  - 6 errors
- `uv run --directory skills/implementation-review-loop agent-loop doctor --repo .` は、この repo 自体が agent-loop 用に初期化されていないため失敗
  - これは実装不良というより、この repo 自体が利用側 repo ではないため

## 総評

アーキテクチャ自体は、以前の GitHub Actions ベースの review-loop よりかなり整理されている。

特に良い点:

- review / fix の状態を PR コメントではなくローカル state に寄せている
- verdict / findings / implementer responses が構造化 contract で定義されている
- `finding ledger` により再レビュー時の継続性を保ちやすい

したがって、この方式で進めること自体は十分に有望。

ただし採用前に、上記 2 件の P1 は先に潰したい。
