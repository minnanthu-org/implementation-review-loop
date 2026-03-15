# 検討資料: agent-loop の Claude Agent SDK ハイブリッド移行

- 作成日: 2026-03-15
- ステータス: 検討中 (Draft)

---

## 1. 背景と目的

### 現状の課題

agent-loop は独自の制御レイヤーとして、実装→チェック→レビューのループをクロスベンダー (codex / claude / gemini) で実行する仕組みを提供している。しかし 2026年3月時点で Claude Code エコシステムが急速に成熟しており、重複する機能が増えている。

| agent-loop が自前で実装 | Claude Code / Agent SDK の対応機能 |
|---|---|
| シェルコマンド実行 (`process.ts`) | SDK 組み込みの `Bash` ツール |
| 構造化 JSON 出力 + スキーマ検証 | `--json-schema` / `outputFormat: { type: "json_schema" }` |
| プロンプト組み立て (`workflow-agent.ts`) | Skills + Sub-agents のプロンプト管理 |
| ループ制御 (`run-loop.ts`) | Agent Teams / Hooks / `maxTurns` |
| リポジトリ初期化 (`init.ts`) | なし — agent-loop 独自の価値 |
| Finding Ledger 管理 | なし — agent-loop 独自の価値 |
| クロスベンダー分岐 | なし — agent-loop 独自の価値 |

### 目的

Claude Agent SDK をランタイム基盤として採用しつつ、agent-loop の差別化要素（クロスベンダー実行、Finding Ledger、deterministic loop control、監査証跡）を維持するハイブリッドアーキテクチャを設計する。

---

## 2. Claude Agent SDK の技術概要

### SDK の位置づけ

```
┌─────────────────────────────────────────────┐
│ Claude Code (CLI / IDE 統合)                 │
├─────────────────────────────────────────────┤
│ Claude Agent SDK (TS / Python)              │
│  - query() API                              │
│  - In-process MCP servers                   │
│  - Hooks (Pre/PostToolUse, Stop, etc.)      │
│  - Sub-agents / Agent Teams                 │
│  - Structured output (json_schema)          │
│  - Session management / forking             │
├─────────────────────────────────────────────┤
│ Anthropic API (Claude Opus/Sonnet/Haiku)    │
└─────────────────────────────────────────────┘
```

### 主要 API

**TypeScript SDK** (`@anthropic-ai/claude-agent-sdk` v0.2.71+)

```typescript
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";

// 基本実行
for await (const message of query({
  prompt: "...",
  options: {
    allowedTools: ["Read", "Edit", "Bash"],
    permissionMode: "bypassPermissions",
    outputFormat: { type: "json_schema", schema: mySchema },
    maxTurns: 50,
    maxBudgetUsd: 5.0,
    hooks: { PostToolUse: [{ matcher: "Edit|Write", hooks: [myHook] }] },
  },
})) {
  // SDKMessage を処理
}
```

**カスタム MCP ツール**

```typescript
const findingLedgerTool = tool(
  "update_finding_ledger",
  "Update finding ledger with review results",
  { findingId: z.string(), status: z.enum(["open", "closed"]), ... },
  async (args) => { /* ledger 更新ロジック */ }
);

const server = createSdkMcpServer({
  name: "agent-loop-tools",
  tools: [findingLedgerTool],
});
```

### 制約事項

| 項目 | 制約 |
|---|---|
| LLM | Claude 専用。他 LLM は LiteLLM プロキシ経由のみ |
| 課金 | API キー必須 (Max サブスク不可)。Opus: $5/$25 per 1M tokens |
| Sub-agent 再帰 | Sub-agent は別の Sub-agent を起動不可 |
| Agent Teams | Experimental。deterministic 制御は不向き |
| Python SDK | Alpha。SessionStart/End hooks 未対応 |

---

## 3. 移行戦略の選択肢

### Option A: SDK 全面移行 (Claude-only)

クロスベンダーを諦め、Claude Agent SDK に全面移行する。

```
SDK query() ─→ implementer (Claude) ─→ checks ─→ reviewer (Claude)
     │                                                    │
     └──── Hooks + MCP で Finding Ledger 管理 ◄───────────┘
```

**メリット**: 最もシンプル。SDK のエコシステム (Hooks, Sub-agents, Session 管理) をフル活用。自前の process.ts, structured-prompt.ts, claude.ts を削除可能。

**デメリット**: Codex / Gemini でのレビュー不可。API 課金のみ（Max プラン不可）。SDK の Breaking Change リスク (Alpha/Beta)。

**削除可能なモジュール**: `process.ts`, `codex.ts`, `claude.ts`, `gemini.ts`, `structured-prompt.ts`, `agent-commands.ts`, `codex-agent.ts`, `claude-agent.ts`, `gemini-agent.ts`

**推定工数**: 中 (2–3 週間)

---

### Option B: ハイブリッド — SDK + クロスベンダー CLI (推奨)

SDK をオーケストレーション基盤として使い、implementer / reviewer は引き続きプロバイダー別 CLI を呼び出す。

```
SDK query() ─→ MCP Tool: run_implementer(provider) ─→ codex/claude/gemini CLI
     │                                                        │
     │         MCP Tool: run_checks() ◄──────────────────────┘
     │                    │
     │         MCP Tool: run_reviewer(provider) ─→ codex/claude/gemini CLI
     │                                                        │
     │         MCP Tool: update_ledger() ◄────────────────────┘
     │                    │
     └──── Loop control via maxTurns + Stop hook ◄────────────┘
```

**アーキテクチャ詳細**:

```
packages/
  agent-loop-core/          # ビジネスロジック (維持)
    src/
      contracts.ts          # Zod スキーマ (維持)
      run-loop.ts           # ループ制御 (維持、SDK 連携追加)
      finding-ledger.ts     # Ledger ロジック (run-loop.ts から抽出)
      checks.ts             # チェック実行 (維持)
      providers/             # プロバイダー抽象 (リファクタ)
        codex.ts
        claude.ts
        gemini.ts
        types.ts
      repo-config.ts        # 設定 (維持)
      doctor.ts             # ヘルスチェック (維持)

  agent-loop-sdk/           # 新パッケージ: SDK 統合レイヤー
    src/
      mcp-server.ts         # In-process MCP server (agent-loop ツール群)
      orchestrator.ts       # SDK query() ベースのオーケストレーター
      hooks.ts              # PostToolUse hooks (自動チェック等)
      session.ts            # セッション管理

  agent-loop-cli/           # CLI エントリポイント (簡素化)
    src/
      run-loop.ts           # SDK orchestrator 経由に変更
      init.ts               # 維持
      doctor.ts             # 維持
      ...
```

**MCP ツール定義**:

```typescript
// mcp-server.ts
import { tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";

const runImplementer = tool(
  "run_implementer",
  "指定プロバイダーで implementer を実行し、構造化出力を返す",
  {
    provider: z.enum(["codex", "claude", "gemini"]),
    planPath: z.string(),
    attempt: z.number(),
    openFindingsPath: z.string(),
  },
  async (args) => {
    // 既存の structured-prompt + provider 分岐を呼び出し
    const result = await runStructuredPrompt({ provider: args.provider, ... });
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  }
);

const runReviewer = tool("run_reviewer", ...);
const runChecks = tool("run_checks", ...);
const updateFindingLedger = tool("update_finding_ledger", ...);
const getRunState = tool("get_run_state", ...);

export const agentLoopMcpServer = createSdkMcpServer({
  name: "agent-loop",
  version: "0.2.0",
  tools: [runImplementer, runReviewer, runChecks, updateFindingLedger, getRunState],
});
```

**オーケストレーター**:

```typescript
// orchestrator.ts
import { query } from "@anthropic-ai/claude-agent-sdk";
import { agentLoopMcpServer } from "./mcp-server.js";

export async function runSdkLoop(options: RunLoopOptions): Promise<CompletedRun> {
  const systemPrompt = buildOrchestratorPrompt(options);

  for await (const message of query({
    prompt: systemPrompt,
    options: {
      mcpServers: { "agent-loop": agentLoopMcpServer },
      allowedTools: [
        "mcp__agent-loop__run_implementer",
        "mcp__agent-loop__run_reviewer",
        "mcp__agent-loop__run_checks",
        "mcp__agent-loop__update_finding_ledger",
        "mcp__agent-loop__get_run_state",
      ],
      permissionMode: "bypassPermissions",
      maxTurns: options.maxAttempts * 4,  // 余裕を持たせる
      maxBudgetUsd: 2.0,  // オーケストレーション自体のコスト上限
      model: "claude-haiku-4-5-20251001",  // オーケストレーターは軽量モデルで十分
      hooks: {
        Stop: [{
          matcher: ".*",
          hooks: [async (input) => {
            // ループ終了時に summary を書き込み
            await writeRunSummary(runDir, currentState);
            return {};
          }],
        }],
      },
    },
  })) {
    // メッセージ処理・状態更新
  }
}
```

**メリット**:
- クロスベンダー実行を維持
- SDK の Hooks / Session / MCP を活用
- オーケストレーターは Haiku で安価に実行可能
- Finding Ledger, 監査証跡は既存ロジックを MCP ツールとして公開するだけ
- 将来 Agent Teams が安定したら、implementer/reviewer を teammate として分離可能

**デメリット**:
- SDK への依存が増える (Alpha/Beta リスク)
- オーケストレーション層が LLM 依存になる（現在は deterministic）
- API キー課金が追加で発生（オーケストレーター分）

**推定工数**: 中–大 (3–4 週間)

---

### Option C: SDK 部分採用 — MCP ツールのみ

SDK をオーケストレーターとしては使わず、agent-loop のツール群を MCP server として公開するだけに留める。ループ制御は既存の deterministic ロジックを維持。

```
run-loop.ts (既存) ─→ implementer CLI ─→ checks ─→ reviewer CLI
       │
       └─── MCP server としても公開 (Claude Code から直接呼べる)
```

**メリット**: 最小限の変更。既存の堅い制御ロジックを維持。Claude Code ユーザーが MCP 経由で agent-loop を利用可能に。

**デメリット**: SDK のエコシステム (Hooks, Sub-agents, Session) を活用しない。二重管理が残る。

**推定工数**: 小 (1–2 週間)

---

### Option D: 現状維持 + Claude Code 機能の選択的取り込み

SDK 移行は行わず、Claude Code の個別機能を agent-loop に取り込む。

- Worktree 分離を implementer 実行時に適用
- Agent Skills 標準に合わせた SKILL.md の拡充
- Claude Code の `--json-schema` 改善を追従

**メリット**: リスクゼロ。段階的に取り込み可能。

**デメリット**: 長期的に SDK エコシステムから乖離。

**推定工数**: 最小 (数日)

---

## 4. 比較マトリクス

| 評価軸 | A: SDK 全面 | B: ハイブリッド | C: MCP のみ | D: 現状維持 |
|---|---|---|---|---|
| クロスベンダー維持 | ✗ | ✓ | ✓ | ✓ |
| SDK エコシステム活用度 | ◎ | ○ | △ | ✗ |
| Finding Ledger 維持 | 要再実装 | MCP 化 | 維持 | 維持 |
| 監査証跡 (runs/) | SDK session に移行 | 維持 + SDK 補完 | 維持 | 維持 |
| Deterministic 制御 | ✗ (LLM 依存) | △ (Haiku 依存) | ✓ | ✓ |
| 実装コスト | 中 | 中–大 | 小 | 最小 |
| ランタイムコスト追加 | Opus API 全額 | Haiku (安価) | なし | なし |
| メンテナンス負荷 | 低 (SDK 委譲) | 中 | 中 (現状と同等) | 高 (乖離増) |
| 将来の拡張性 | ○ | ◎ | △ | ✗ |
| SDK Breaking Change リスク | 高 | 中 | 低 | なし |

---

## 5. 推奨: Option B (ハイブリッド) の段階的実行計画

全面移行ではなく、段階的に SDK 統合を進めることでリスクを制御する。

### Phase 1: MCP Server 化 (1 週間)

**目標**: agent-loop のコアロジックを MCP ツールとして公開する。既存の CLI / run-loop は変更しない。

```
新規: packages/agent-loop-mcp/
  src/
    server.ts           # createSdkMcpServer で agent-loop ツールを公開
    tools/
      run-implementer.ts
      run-reviewer.ts
      run-checks.ts
      finding-ledger.ts
      run-state.ts
```

**成果物**:
- Claude Code から `mcp__agent-loop__*` ツールとして agent-loop を直接呼べるようになる
- 既存の CLI は一切変更しないのでリグレッションリスクなし
- 既存テストスイートが全パス

**判断ポイント**: Phase 1 完了時に SDK の安定性と MCP ツール経由の使い勝手を評価。問題があれば Option C (MCP のみ) に留めて終了。

### Phase 2: SDK オーケストレーター追加 (2 週間)

**目標**: SDK の `query()` を使ったオーケストレーターを新たな実行モードとして追加する。既存の deterministic run-loop は維持。

```
新規: packages/agent-loop-sdk/
  src/
    orchestrator.ts     # SDK query() ベースのオーケストレーター
    prompts.ts          # オーケストレーター用システムプロンプト
    hooks.ts            # PostToolUse hooks

変更: packages/agent-loop-cli/
  src/
    run-loop.ts         # --execution-mode sdk フラグ追加
```

**実行モード分岐**:

```typescript
// run-loop.ts
if (options.executionMode === "sdk") {
  return runSdkLoop(options);      // 新: SDK オーケストレーター
} else {
  return runCompatLoop(options);   // 既存: deterministic ループ
}
```

**成果物**:
- `npm run loop:run -- --plan ... --execution-mode sdk` で SDK 経由実行
- 既存の `compat-loop` モードは変更なし
- 両方のモードで同じ Finding Ledger / runs/ 構造を使用

**判断ポイント**: SDK モードと compat-loop モードの出力品質・コスト・安定性を比較。

### Phase 3: オーケストレーター最適化 + compat-loop 段階的廃止 (1–2 週間)

**目標**: SDK モードが十分安定したら、compat-loop の provider 固有コードを整理する。

- `claude.ts` の `extractJson()` → SDK の `outputFormat` に置き換え
- `codex.ts` / `gemini.ts` → MCP ツール内に統合
- `workflow-agent.ts` → SDK sub-agent 定義に移行
- compat-loop モードは `deprecated` としつつ互換性を維持

---

## 6. コスト試算

### 現状 (compat-loop)

| 項目 | コスト |
|---|---|
| Claude (implementer/reviewer) | Max プラン定額 or API 従量 |
| Codex (implementer/reviewer) | Codex プラン定額 or API 従量 |
| Gemini (implementer/reviewer) | 無料枠 or API 従量 |
| オーケストレーション | 0 (deterministic) |

### SDK ハイブリッド移行後

| 項目 | コスト (概算) |
|---|---|
| Implementer / Reviewer | 現状と同じ (CLI 経由) |
| オーケストレーター (Haiku) | ~$0.01–0.05/ループ (ツール呼び出し判断のみ) |
| SDK ランタイム | ANTHROPIC_API_KEY 必須 |

オーケストレーターを Haiku で実行すれば、追加コストは 1 ループあたり数セント程度。ただし **ANTHROPIC_API_KEY が必須** になる点は、現在 Claude Code Max プランのみで運用しているユーザーへの影響がある。

---

## 7. リスクと緩和策

| リスク | 影響 | 緩和策 |
|---|---|---|
| SDK が Alpha/Beta で Breaking Change | ビルド破損 | Phase 1 で MCP のみ公開し、SDK 依存を隔離パッケージに限定。バージョンピン |
| Haiku オーケストレーターの判断ミス | ループが想定外の挙動 | Stop hook で invariant チェック。maxTurns で上限保証。fallback で compat-loop |
| API キー必須化 | Max プランユーザーが使えない | compat-loop モードを維持し、SDK モードはオプション |
| MCP ツール呼び出しのレイテンシ | ループ時間増加 | In-process MCP なのでオーバーヘッドは最小。計測して判断 |
| Codex / Gemini CLI の仕様変更 | プロバイダー実行失敗 | 既存と同じリスク。provider 別テストで検知 |

---

## 8. 成功指標

| 指標 | 目標 |
|---|---|
| 既存テスト全パス | Phase 1–3 すべてで維持 |
| compat-loop と SDK モードの出力同等性 | 同じ plan で approve される |
| オーケストレーターコスト | 1 ループ < $0.10 |
| SDK モードのループ完了率 | compat-loop と同等以上 |
| コード行数 | Phase 3 完了後に純減 |

---

## 9. 未解決の論点

1. **SDK モードでの deterministic 保証**: Haiku オーケストレーターが「次に run_reviewer を呼ぶ」判断を毎回正しく行える保証はない。MCP ツールの呼び出し順序をプロンプトで強制するか、Hooks で制御するか？

2. **Agent Teams vs MCP オーケストレーター**: Agent Teams が安定すれば、implementer/reviewer を teammate として分離する方が自然。しかし現時点では experimental。Phase 2 完了後に再評価。

3. **Python SDK 対応**: agent-loop は現在 TypeScript のみ。Python SDK も提供するか？ Claude Agent SDK は Python でも利用可能だが、Python 版の SDK は Alpha でホックイベントが不完全。

4. **delegated モードとの関係**: 現在 `delegated` モードは外部オーケストレーターに委譲する設計。SDK モードは delegated の具体的な実装とも言えるが、位置づけを整理する必要がある。

5. **ANTHROPIC_API_KEY の配布**: チーム内で SDK モードを使う場合、API キー管理をどうするか。

---

## 10. 結論

**Option B (ハイブリッド) を Phase 1 から段階的に進めることを推奨する。**

理由:

1. **クロスベンダーが核心の差別化要素** であり、これを捨てる Option A は不適
2. **Phase 1 (MCP化) は低リスク・高リターン** — 既存コードを変更せず、Claude Code ユーザーへの新しいインターフェースを提供
3. **Phase 2 以降は評価結果次第で進退を判断** できるため、コミットメントが段階的
4. SDK が安定すれば **compat-loop の provider 固有コードを大幅に削減** でき、coding-rules の「fewer lines, fewer abstractions」に合致
5. **最悪のケースでも Phase 1 の成果 (MCP server) は残る** ため、投資が無駄にならない

次のアクション: Phase 1 の実装計画書を作成し、plan:review に回す。
