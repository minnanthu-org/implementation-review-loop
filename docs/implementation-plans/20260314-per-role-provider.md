# ロール別プロバイダー指定 実装計画書

状態: 下書き
作成日: 2026-03-14
作成者: Claude

## 1. 目的

Implementer と Reviewer に異なる LLM プロバイダーを指定できるようにする。
これにより「Claude で実装して Gemini でレビュー」のようなクロスベンダー構成が可能になる。

## 2. 背景

- 現状 `--provider` フラグは 1 つだけで、Implementer/Reviewer の両方に同じプロバイダーが適用される
- クロスベンダーレビュー（異なる LLM 同士でチェックし合う）はバイアス低減・品質向上に有効
- 既に `implementerCommand` / `reviewerCommand` を個別に指定すれば回避可能だが、フルコマンドを書く必要があり UX が悪い

## 3. 変更対象

- `packages/agent-loop-core/src/repo-config.ts` — config スキーマ: `provider` → `defaultProvider` にリネーム + ロール別フィールド追加
- `packages/agent-loop-cli/src/run-loop.ts` — `--provider` を短縮形として維持しつつ `--implementer-provider` / `--reviewer-provider` を追加、config フォールバックを廃止
- `packages/agent-loop-cli/src/agent-commands.ts` — 変更なし（既にロール別にコマンドを生成可能）
- `packages/agent-loop-cli/src/code-review.ts` — `--provider` → `--reviewer-provider` に変更
- `packages/agent-loop-cli/src/plan-review.ts` — `--provider` はそのまま維持（Reviewer のみのサブコマンド）
- `packages/agent-loop-cli/src/init.ts` — config 書き込みを `defaultProvider` に対応

## 4. 影響範囲

- `run-loop` サブコマンド（Implementer/Reviewer 両方起動するメインループ）
- `code-review` サブコマンド（Reviewer のみ起動するワンショットレビュー）
- `.agent-loop/config.json` の既存設定ファイル（マイグレーション必要）
- `workflow-agent.ts` — 変更不要（provider は起動コマンド側で決定済み）

## 5. 非対象範囲

- `plan-review` サブコマンド — Reviewer しか使わないため `--provider` のままで十分
- `WorkflowProvider` 型の拡張 — 新プロバイダー追加は別タスク
- `delegatedRepoConfigSchema` への拡張 — delegated モードは `run-loop` / `code-review` で使われないため別タスク
- `--implementer-command` / `--reviewer-command` の既存フラグ — そのまま維持

## 6. 実装方針

### 6.1 CLI フラグ設計

`run-loop` では `--implementer-provider` / `--reviewer-provider` を必須とする。
`--provider`（両方を一括指定する短縮形）も残す。
スキルが文脈から判断してフラグを補完する想定のため、ユーザーが毎回手で書く負担はない。

```
# 両方 claude（短縮形）
agent-loop run-loop --plan plan.md --provider claude

# クロスベンダー（claude で実装、gemini でレビュー）
agent-loop run-loop --plan plan.md --implementer-provider claude --reviewer-provider gemini
```

`--provider` は `--implementer-provider` と `--reviewer-provider` の両方を同じ値で指定する糖衣構文として扱う。ロール別指定との併用時はロール別が優先。

いずれも未指定の場合はエラーとする（暗黙のフォールバックなし）。

### 6.2 config.json 変更

`execution.provider` を `execution.defaultProvider` にリネームする。
これはスキルが参照するヒントであり、CLI のフォールバック先ではない。

```jsonc
{
  "execution": {
    "mode": "compat-loop",
    "defaultProvider": "codex"    // リネーム: スキルが参照するデフォルト値
  }
}
```

ロール別フィールド (`implementerProvider` / `reviewerProvider`) は config には追加しない。
プロバイダーの決定は CLI フラグ（＝スキルが補完）で行い、config は「デフォルトで何を使うか」のヒントのみ持つ。

### 6.3 後方互換と破壊的変更

- `execution.provider` を持つ既存 config はスキーマで `provider` も `defaultProvider` も受け付ける移行期間を設ける
- `--provider` フラグは短縮形として残すため、既存のスクリプトやCIは動作する
- `plan-review` の `--provider` はそのまま維持
- **破壊的変更**: `run-loop` と `code-review` の直接 CLI 呼び出しでは `--provider` または `--implementer-provider` / `--reviewer-provider` の明示が必須になる（従来は config フォールバックで省略可能だった）。スキル経由の呼び出しではスキルが補完するため影響なし

## 7. 実装手順

### Step 1: `repo-config.ts` — スキーマ変更

`execution.provider` を `execution.defaultProvider` にリネーム。移行期間として両方受け付ける。

```typescript
execution: z.object({
  mode: z.literal("compat-loop"),
  defaultProvider: providerSchema.optional(),
  provider: providerSchema.optional(),        // 後方互換: 移行期間中のみ
}).refine(
  (data) => data.defaultProvider !== undefined || data.provider !== undefined,
  { message: "Either defaultProvider or provider must be specified" },
),
```

読み取り側のヘルパーを `repo-config.ts` に追加する:

```typescript
export function getEffectiveProvider(
  execution: { defaultProvider?: WorkflowProvider; provider?: WorkflowProvider },
): WorkflowProvider {
  const resolved = execution.defaultProvider ?? execution.provider;
  if (!resolved) {
    throw new Error("Either defaultProvider or provider must be specified in execution config");
  }
  return resolved;
}
```

`plan-review.ts:113` など config から provider を読む箇所はすべてこのヘルパー経由に変更する。

`delegatedRepoConfigSchema` には追加しない。delegated モードは `run-loop` / `code-review` で使われず、読み取る箇所が存在しないため別タスクとする。

### Step 2: `run-loop.ts` (CLI) — フラグ変更

1. `--provider` を「短縮形」として維持、`--implementer-provider` / `--reviewer-provider` を追加
2. `RunLoopOptions` を変更:

```typescript
export interface RunLoopOptions {
  checkCommands: readonly string[];
  checksFile?: string;
  implementerCommand?: string;
  implementerProvider?: WorkflowProvider;  // 新規
  maxAttempts?: number;
  planPath: string;
  repoPath: string;
  reviewerCommand?: string;
  reviewerProvider?: WorkflowProvider;     // 新規
  runsDir?: string;
}
```

3. `resolveAgentCommands()` を変更 — config へのフォールバックを廃止し、ロール単位でバリデーション:

```typescript
async function resolveAgentCommands(options: RunLoopOptions): Promise<{
  implementerCommand: string;
  reviewerCommand: string;
}> {
  const implementerCommand = options.implementerCommand
    ?? (options.implementerProvider
      ? defaultImplementerCommand(options.implementerProvider)
      : undefined);

  const reviewerCommand = options.reviewerCommand
    ?? (options.reviewerProvider
      ? defaultReviewerCommand(options.reviewerProvider)
      : undefined);

  if (!implementerCommand) {
    throw new Error(
      "--implementer-provider is required (or use --provider to set both, " +
      "or use --implementer-command)",
    );
  }

  if (!reviewerCommand) {
    throw new Error(
      "--reviewer-provider is required (or use --provider to set both, " +
      "or use --reviewer-command)",
    );
  }

  return { implementerCommand, reviewerCommand };
}
```

これにより `--implementer-command` + `--reviewer-provider gemini` のような混在指定も正しく動作する。

4. `parseRunLoopArgs()` で `--provider` を `implementerProvider` / `reviewerProvider` の両方に展開:

```typescript
const provider = values.get("--provider") as WorkflowProvider | undefined;
const implementerProvider =
  (values.get("--implementer-provider") as WorkflowProvider | undefined) ?? provider;
const reviewerProvider =
  (values.get("--reviewer-provider") as WorkflowProvider | undefined) ?? provider;
```

### Step 3: `code-review.ts` — `--reviewer-provider` に変更

1. `--provider` を `--reviewer-provider` にリネーム（`--provider` も後方互換で受け付ける）
2. `CodeReviewOptions` の `provider` を `reviewerProvider` にリネーム
3. `reviewerCommand` が明示されている場合は `reviewerProvider` 不要（コマンドで provider が決定済み）。両方未指定の場合のみエラー:

```typescript
const reviewerCommand = options.reviewerCommand;
if (reviewerCommand) {
  // reviewerCommand が明示されていれば provider 不要
} else if (!options.reviewerProvider) {
  throw new Error(
    "--reviewer-provider is required (or use --reviewer-command)",
  );
}
const reviewerProvider = options.reviewerProvider;
```

`formatProviderDisplayName` は `reviewerProvider` が undefined の場合（`reviewerCommand` 使用時）を考慮し、引数を optional にして未指定時はデフォルト名を返す:

```typescript
function formatProviderDisplayName(
  provider?: WorkflowProvider,
): string {
  if (provider === "claude") return "Claude";
  if (provider === "gemini") return "Gemini";
  if (provider === "codex") return "Codex";
  return "Custom Reviewer";
}
```

### Step 4: `init.ts` — `defaultProvider` 対応

`writeConfigProvider` をモード判定付きに変更。`compat-loop` では `defaultProvider` に書き込み、`delegated` では従来通り `provider` に書き込む。`delegatedRepoConfigSchema` は非対象範囲のため、delegated 側のフィールド名は変更しない。

```typescript
async function writeConfigProvider(
  configPath: string,
  mode: ExecutionMode,
  provider: WorkflowProvider,
): Promise<void> {
  const config = JSON.parse(await readFile(configPath, "utf8"));
  if (mode === "compat-loop") {
    config.execution.defaultProvider = provider;
    delete config.execution.provider;
  } else {
    config.execution.provider = provider;
  }
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}
```

呼び出し元にも `options.mode` を渡すよう変更する。

### Step 5: config テンプレート更新

`templates/config/compat-loop.json` の `execution.provider` を `execution.defaultProvider` にリネーム。

### Step 6: 既存コードの `execution.provider` 参照を更新

`plan-review.ts` など、config から `execution.provider` を読む箇所を Step 1 で定義した `getEffectiveProvider()` ヘルパー経由に変更する。

対象箇所:
- `plan-review.ts:113` — `repoConfig.execution.provider` → `getEffectiveProvider(repoConfig.execution)`
- `code-review.ts:161` — config フォールバックを廃止するため、この参照自体を削除（Step 3 で対応済み）

### Step 7: テスト更新

1. `test/init.test.ts` — `config.execution.provider` をアサートしている箇所（L65, L87）を `config.execution.defaultProvider` に更新（compat-loop モード時）。delegated モードのテストは `provider` のまま維持。
2. `test/repo-config.test.ts` — `defaultProvider` を持つ config の読み込みテストを追加。`provider` のみの旧 config が後方互換で読めることも検証。`getEffectiveProvider()` ヘルパーのテストも追加。
3. `test/run-loop.test.ts`:
   - `parseRunLoopArgs` に `--implementer-provider` / `--reviewer-provider` フラグのパーステストを追加。`--provider` 短縮形の展開、ロール別フラグの優先、未指定時のエラーを検証。
   - 既存の統合テストが config フォールバックに依存しているため、`implementerProvider` / `reviewerProvider` を明示的に渡すよう修正する。対象: `initializeRun` テスト（L124-165, L195-212）、ネスト起動拒否テスト（L93-122）、checks 読み込みテスト（L167-193）。`writeCompatLoopConfig` で設定した provider と同じ値を各テストの `options` にも渡す。
4. `test/code-review.test.ts` — `--reviewer-provider` フラグのパーステスト、後方互換の `--provider` が `reviewerProvider` にマッピングされることを検証。既存の `runCodeReview` 統合テスト（L189, L235, L292）は `reviewerCommand` のみ渡しており `reviewerProvider` は不要なのでそのまま動作することを確認。

## 8. 必須確認項目

- `packages/agent-loop-core/src/repo-config.ts` — スキーマ定義
- `packages/agent-loop-cli/src/run-loop.ts` — フラグパース + コマンド解決
- `packages/agent-loop-cli/src/code-review.ts` — ワンショットレビューのプロバイダー解決
- `packages/agent-loop-cli/src/plan-review.ts` — `execution.provider` 参照の更新
- `packages/agent-loop-cli/src/init.ts` — config 書き込み
- `packages/agent-loop-cli/src/agent-commands.ts` — コマンド生成（変更不要だが確認）
- config テンプレート (`templates/config/compat-loop.json`)
- 既存テスト

## 9. 必須 checks

- `npm run build`
- `npm test`

## 10. 受け入れ条件

- `--implementer-provider claude --reviewer-provider gemini` で Implementer が Claude、Reviewer が Gemini で起動すること
- `--provider claude` で従来通り両方 Claude で動作すること
- `--provider claude --reviewer-provider gemini` で Implementer は Claude、Reviewer は Gemini になること
- ロール別プロバイダーも `--provider` も未指定の場合にエラーになること（暗黙のフォールバックなし）
- 既存の `--implementer-command` / `--reviewer-command` フラグが引き続き最優先で動作すること
- config の `execution.provider`（旧）と `execution.defaultProvider`（新）の両方を持つ config が読めること
- `plan-review --provider` は従来通り動作すること

## 11. エスカレーション条件

- `workflow-agent.ts` 側の変更が必要になった場合 → 設計再検討
- provider ごとにスキーマの互換性問題が発生した場合 → replan

## 12. 実装役向けメモ

- `agent-commands.ts` は変更不要。既に `defaultImplementerCommand(provider)` / `defaultReviewerCommand(provider)` でロール別にコマンド生成できる
- `workflow-agent.ts` も変更不要。provider は起動コマンド（`claude-agent.js` vs `gemini-agent.js`）で暗黙的に決定される
- config の `provider` → `defaultProvider` リネームは破壊的変更。移行期間として両方受け付けるスキーマにすること
- CLI の `--provider` は短縮形として残す。廃止ではなく意味の変更（「デフォルト」→「両方一括指定」）
- `resolveAgentCommands()` から config 参照を除去するのがこの改修の核心。プロバイダー決定を CLI フラグに一本化する
