# ロール別プロバイダー指定 計画レビュー記録

状態: 承認済み
レビュー日: 2026-03-15
レビュー担当: Claude
対象計画書: `docs/implementation-plans/20260314-per-role-provider.md`

## 1. 結論

- `approve`

## 2. 総評

計画書は対象コードの現状と整合しており、スコープ・影響範囲・手順・テスト更新方針のすべてが具体的かつ正確です。`resolveAgentCommands()` から config フォールバックを除去し、CLI フラグでプロバイダー決定を一本化するという核心が明確で、既存 workflow を壊さない前提が守られています。破壊的変更は正しく識別・文書化されており、後方互換の移行パスも適切です。そのまま実装に進めて問題ありません。

## 3. 指摘一覧

なし

## 4. 影響範囲レビュー

影響範囲は正確に特定されています。

- `run-loop.ts`: `resolveAgentCommands()` の config フォールバック除去が核心であり、`loadCompatLoopRepoConfig` の import が不要になる点は自明な cleanup です
- `code-review.ts`: `reviewerProvider` が undefined になり得るケース（`reviewerCommand` 指定時）を `formatProviderDisplayName` の optional 化で正しく対処しています
- `plan-review.ts`: `loadRepoConfig` が返す union 型に対して `getEffectiveProvider()` ヘルパーが正しく動作します（delegated 側の `provider` は required のまま、compat-loop 側は `defaultProvider ?? provider` で解決）
- `init.ts`: `writeConfigProvider` のモード判定付き分岐は、delegated 側を変更しないスコープ制約と整合しています
- `agent-commands.ts`, `workflow-agent.ts`: 変更不要という判断が正しいことをコードで確認しました
- テストへの影響: `run-loop.test.ts` の `initializeRun` テスト 4 件（L93-212）が config フォールバックに依存しており、計画書はこれらすべてを正確に列挙しています。`code-review.test.ts` の `runCodeReview` 統合テスト 3 件は `reviewerCommand` のみ渡しており provider 不要のためそのまま動作することも確認しました
- Zod スキーマの `.refine()` を `z.object()` のネストプロパティに使う手法は Zod v3 で正しく動作し、`z.union()` との組み合わせも問題ありません

## 5. checks レビュー

`npm run build` と `npm test` の 2 つが必須 checks として指定されています。スキーマ変更（Zod の `.refine()` 追加）、インターフェース変更（`RunLoopOptions`, `CodeReviewOptions`）、フラグパース変更のすべてがビルドとテストで検出可能であり、十分です。受け入れ条件に記載された 7 つのシナリオもテストで網羅可能です。

## 6. 人間判断が必要な点

人間判断が必要な点はありません。破壊的変更（`run-loop`/`code-review` の直接 CLI 呼び出しで `--provider` 明示が必須になる件）は計画書で明確に文書化されており、スキル経由の呼び出しではスキルが補完するため実質的な影響は限定的です。エスカレーション条件（`workflow-agent.ts` 変更が必要になった場合、provider 互換性問題）も妥当に設定されています。

## 7. 再レビュー条件

以下のいずれかが発生した場合に再レビューが必要です:

- `delegatedRepoConfigSchema` のフィールド名変更がこのタスクのスコープに含まれることになった場合
- `workflow-agent.ts` 側でプロバイダー判定ロジックの変更が必要になった場合
- `plan-review` サブコマンドにもロール別プロバイダー指定を追加する要件が発生した場合

