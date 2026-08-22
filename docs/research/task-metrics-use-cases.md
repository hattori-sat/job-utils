# タスク／仕事メトリクスのユースケース調査

調査日: 2026-08-22

## 結論

個人の年度評価、上司との振り返り、成果説明でタスクメトリクスを使う場合、メトリクスは「人を一列に並べる点数」ではなく、成果・流れ・阻害要因・学習を説明するための証拠として使うべきである。

job-utilsでは、完了件数を単独の評価軸にせず、少なくとも次の層を分離して表示するのが妥当である。

```text
成果量       : 完了件数、throughput
流れ         : lead time、cycle time、WIP、work item age
投入と滞留   : active work time、waiting time、待ち理由
予測と品質   : 見積誤差、再作業、再オープン
成果／影響   : 利用者・顧客・事業・チームへの変化を記述した証拠
```

これはDORAが単一指標、目標化、異質な比較、競争を避けるよう説明していること、SPACEが個人の活動量や単一の指標だけでは開発者の生産性を測れないとしていること、Kanbanが複数のフロー指標と文脈を要求していることからの設計上の推奨である。[DORAのソフトウェアデリバリーパフォーマンス指標](https://dora.dev/guides/dora-metrics/)、[SPACE論文の公式掲載ページ（Microsoft Research）](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/)、[The Kanban Guide 2020](https://kanbanguides.org/the-kanban-guide/2020.12/pdf/kanban-guide.v2020.12.en.pdf)

## 成功条件

- 年度評価では、件数ではなく「何を届けたか」「どの程度予測可能だったか」「何が流れを止めたか」「何を改善したか」を再現可能な証拠で説明できる。
- 上司との振り返りでは、個人の責任と外部依存・レビュー待ち・優先度変更を分離して会話できる。
- 成果説明では、処理量、期間、品質・再作業、成果／影響を混ぜずに、必要な範囲で関連付けられる。
- 比較は同じ期間、仕事の種類、規模、完了条件、担当範囲などの文脈を揃えて行い、デフォルトでランキングを出さない。
- 欠測・未計測・手入力の情報を区別し、メトリクスから人の評価を自動決定しない。

## 事実（一次資料から確認できること）

### 1. 単純なタスク件数ランキングが危険な理由

SPACEの公式掲載概要は、開発者の生産性は個人の活動量だけではなく、単一の指標または単一の次元では測れないと明記している。[Microsoft Research: The SPACE of Developer Productivity](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/)

DORAの公式ガイドも、メトリクスを目標にするとゲーム化の可能性が高まる、複雑なシステムを一つの指標で測ろうとしない、異なるアプリケーションの比較は誤解を招く、チーム間で競争させるのではなく継続改善に使う、と説明している。[DORA: Common pitfalls](https://dora.dev/guides/dora-metrics/)

Kanbanの公式ガイドは、WIP、throughput、work item age、cycle timeの4つを最低限のフロー指標として定義する一方、これらはそれ自体では意味がなく、Kanbanの実践に関する意思決定へ結び付ける必要があるとしている。[The Kanban Guide 2020, Kanban Measures](https://kanbanguides.org/the-kanban-guide/2020.12/pdf/kanban-guide.v2020.12.en.pdf)

以上から、件数ランキングだけでは次の違いを潰してしまう、というのが本調査の推論である。

- 小さな定型作業と、調査・設計・障害対応などの大きな仕事。
- 自分で完結した仕事と、レビュー・承認・他チーム・顧客回答を待つ仕事。
- 初回で完了した仕事と、再オープン・修正・障害対応を伴った仕事。
- 作業を完了させたことと、利用者・顧客・事業・チームに変化を生んだこと。
- 実装だけでなく、レビュー、支援、文書化、調整、リスク低減などの見えにくい貢献。

「件数が多い人ほど高評価になる」と公式資料が直接結論づけているわけではない。この具体的な評価運用上の危険は、上記の一次資料が示す単一指標・活動量・目標化・異質比較の問題を、個人タスク管理へ適用した推論である。

### 2. DORAから借りられる考え方

DORAの現在の5指標は、ソフトウェア変更のthroughputとinstabilityに分けて整理され、change lead time、deployment frequency、failed deployment recovery time、change fail rate、deployment rework rateを扱う。[DORA metrics](https://dora.dev/guides/dora-metrics/)

これはjob-utilsがDORA指標そのものを個人タスクへ移植すべきだという意味ではない。借りられるのは、次の構造である。

1. 速度だけでなく、失敗・安定性・再作業を同時に見る。
2. 指標を一つのスコアへ早期に潰さず、緊張関係のある複数指標として提示する。
3. 指標を評価の最終目的ではなく、改善する制約やボトルネックを見つける材料にする。
4. 対象の文脈を揃え、同じ種類のシステム・仕事の中で経時変化を見る。

### 3. SPACEから借りられる考え方

SPACEは、開発者の生産性を単一指標でなく複数の次元から理解するための枠組みとして公表されている。[Microsoft Research: SPACE](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/)

DORAの2025年の公式解説も、測定前に「何の意思決定・目標のためか」を決め、ログ由来の量・時間・頻度だけでなく、満足度・ウェルビーイング・有効性のような自己申告では捉えやすい情報も考慮し、ログベースの指標も自動的に客観的とは限らないと説明している。[DORA: Choosing measurement frameworks](https://dora.dev/research/2025/measurement-frameworks/)

個人の振り返りに翻訳すると、活動ログから作れる情報と、本人・上司・関係者が説明する情報を別物として扱う必要がある。

### 4. Kanban／Jiraから確認できるフロー指標

Kanban公式ガイドの定義は次のとおりである。[The Kanban Guide 2020](https://kanbanguides.org/the-kanban-guide/2020.12/pdf/kanban-guide.v2020.12.en.pdf)

| 指標 | 公式ガイド上の意味 | 個人の振り返りで答える問い |
|---|---|---|
| WIP | 開始済みで未完了の仕事数 | 何件を同時に抱えていたか |
| Throughput | 単位時間あたりに完了した仕事数 | どれだけの仕事を届けたか |
| Work item age | 開始から現在までの経過時間 | 未完了の仕事がどれだけ滞留しているか |
| Cycle time | 開始から完了までの経過時間 | 着手後、どの程度の期間で届けたか |

Jira公式のControl Chartも、cycle timeを作業開始から完了まで、lead timeを登録から完了までとして区別し、平均・移動平均・標準偏差でばらつきや外れ値を見る。[Atlassian: Control Chart](https://support.atlassian.com/jira-software-cloud/docs/view-and-understand-the-control-chart/)

このため、job-utilsでは平均だけでなく中央値、p75、可能ならp95、個々の外れ値と原因を表示することが有用である。中央値・p値を必須とする公式標準があるわけではなく、Jiraのばらつき・外れ値の説明と、予測可能性を見たいという本プロジェクトの推論に基づく。

### 5. 見積もりと実績

Jira公式のTime Trackingは、作業前のoriginal estimateと、作業後の実績時間を比較できると説明している。[Atlassian: Log time on a work item](https://support.atlassian.com/jira-software-cloud/docs/log-time-on-an-issue/)

したがって見積誤差は、個人を罰する数値ではなく、次のような予測・学習の材料として分離する。

```text
見積誤差 = 実績 - 初期見積
相対誤差 = (実績 - 初期見積) / 初期見積
```

実績時間が厳密に記録されていない場合、この値は「実装時間」ではなく、入力された時間ログまたはactive区間の近似値である。見積単位が時間、日、ポイントで混在する場合は、単純に合算・比較してはいけない。後半はjob-utils向けの設計上の注意であり、既存データの粒度はUNKNOWNである。

## ユースケース

### 年度評価・上司との振り返り

目的は「一番多く閉じた人」を決めることではなく、期間中の成果、仕事の進め方、制約、改善を一緒に再構成することである。

推奨するレポートの構成は次のとおり。

1. **成果の一覧**: 完了タスク、種類、担当範囲、関係者、成果／影響の短い記述。
2. **流れの要約**: throughput、cycle time／lead timeの中央値とp75、WIP、未完了のage。
3. **滞留の要約**: waiting time、待ち理由、レビュー・承認・依存先ごとの滞留。
4. **品質・学習**: 再オープン、再作業、差し戻し、障害対応、そこから行った改善。
5. **文脈と本人の説明**: 優先度変更、緊急対応、難易度、他者支援、仕事の影響。

速度と安定性を分けるDORAの構造、および活動量以外も含めるSPACEの考え方から、1〜4を機械集計し、5を人が確認・補足する二層構成を推奨する。これは評価制度そのものの規則ではなく、job-utilsのレポート設計に関する推論である。

### 1on1・上司との定期的な振り返り

短い期間では、個人の順位よりも次の問いが実用的である。

- WIPが増えたのは、着手しすぎたのか、依存待ちが増えたのか。
- cycle timeが長い仕事は、active workが長いのか、waitingが長いのか。
- 再作業は要件変更、レビュー、技術的負債、品質問題のどれに偏っているか。
- 見積誤差は特定のカテゴリ、規模、依存関係、割り込みに偏っているか。
- 次の期間に変えるべき制約は何か。

Kanban公式ガイドがフロー指標を意思決定に結び付けるよう求めていること、DORAがボトルネックを見つけて改善を反復する流れを推奨していることから、job-utilsは「メトリクス→原因候補→次の実験」を一画面でつなぐとよい。[The Kanban Guide 2020](https://kanbanguides.org/the-kanban-guide/2020.12/pdf/kanban-guide.v2020.12.en.pdf)、[DORA metrics: Next steps](https://dora.dev/guides/dora-metrics/)

### 成果説明・自己評価の材料作り

成果説明では、次の順序で一つの仕事を説明できるようにする。

```text
背景／課題 → 自分の担当 → 完了した変更 → 品質・再作業 → 利用者／顧客／事業／チームへの影響 → 学び
```

タスクログだけから影響を自動推定できるという一次資料は、本調査では確認できなかった。影響は、リンク、メモ、関係者のコメント、前後の観測値などを任意の証拠として記録する欄にするのが安全である。DORAも指標を組織パフォーマンスやウェルビーイングの予測・改善材料として扱うが、個別タスクの事業価値を自動算出するとは説明していない。[DORA metrics](https://dora.dev/guides/dora-metrics/)

## 指標を分ける設計

| 層 | 定義案 | 読み方 | 画面で避けること |
|---|---|---|---|
| 量 | 期間内の完了件数、throughput | どれだけ届けたか | 件数だけの順位付け |
| Lead time | 作成／依頼から完了まで | 依頼から成果になるまでの期間 | 自分の作業時間と解釈すること |
| Cycle time | 着手から完了まで | 着手後の流れ | 待ち時間を作業時間と一体化すること |
| Active work time | active区間の合計 | 手を動かした時間の近似 | 勤怠・成果と同一視すること |
| Waiting time | waiting区間の合計 | 外部依存、レビュー、承認などの滞留 | 「遅い人」の直接証拠にすること |
| WIP | 開始済み・未完了の件数 | 同時着手の負荷 | 多いほど頑張っていると解釈すること |
| Work item age | 未完了仕事の着手から現在まで | 放置・滞留の候補 | 未完了の理由を無視すること |
| 見積誤差 | 初期見積と実績の差 | 予測の学習 | 能力の固定的な評価値にすること |
| 再作業 | 再オープン、差し戻し、修正、障害対応等 | 品質・要件・プロセスの改善材料 | 多い／少ないだけで責任を決めること |
| 成果／影響 | 利用者、顧客、事業、チームの変化の証拠 | 何が変わったか | タスクログから自動推論すること |

Lead timeとcycle timeの区別、cycle timeの分散・外れ値、original estimateとactualの比較はJira公式の定義に基づく。[Atlassian: Control Chart](https://support.atlassian.com/jira-software-cloud/docs/view-and-understand-the-control-chart/)、[Atlassian: Log time on a work item](https://support.atlassian.com/jira-software-cloud/docs/log-time-on-an-issue/)

## job-utilsに採用できる機能への分解

### 1. 記録モデル

既存レポートのイベント正本案と整合するよう、次の事実を後から再集計できる形で記録する。

- 安定したtask ID、作成時刻、完了時刻、担当・カテゴリ・仕事の種類。
- status遷移と、`started`、`waiting_started`、`waiting_ended`、`reopened`、`completed`などの時刻。
- waiting理由（レビュー、承認、依存、顧客回答、優先度変更など）。
- 初期見積の値と単位、実績またはactive区間の根拠。
- 再作業・再オープンの理由。
- 成果／影響の記述、関連リンク、関係者の補足。
- 自動取得、手入力、推定、欠測を表すデータ品質フラグ。

### 2. 派生集計

- 期間・カテゴリ・仕事種別ごとの完了数、throughput、WIP、age。
- lead time、cycle time、active work time、waiting timeの中央値・p75・外れ値。
- waiting理由別の合計と割合。
- 見積誤差の分布。ただし単位の異なる見積は分離する。
- 再作業率と再作業の理由。
- 成果／影響の記述がある仕事とない仕事を分けた一覧。

### 3. レポートと操作

- **年度レビュー出力**: 代表的な成果を選び、各成果に流れ・品質・影響の証拠を付ける。
- **1on1ビュー**: 直近期間のWIP、age、waiting理由、外れ値、次の改善候補を表示する。
- **成果説明ビュー**: 期間、仕事種別、関係者、成果リンクで絞り、Markdownへ出力する。
- **診断ビュー**: 件数ではなく、ボトルネック・再作業・見積誤差・欠測を並べる。
- **注記機能**: 自動計測では表せない難易度、割り込み、他者支援、影響を追記できるようにする。

### 4. ガードレール

- デフォルトで個人ランキング、単一の生産性スコア、自動評価ラベルを出さない。
- 小数の差を過剰に比較しないよう、サンプル数、期間、フィルタ条件、欠測を表示する。
- 平均だけでなく中央値・分位点・個別外れ値を確認できるようにする。
- task type、サイズ、完了条件、依存の有無が異なるものを同じ比較群に混ぜない。
- 影響は手入力・リンク・関係者の説明を尊重し、件数や時間から自動算出しない。
- レポートは改善の会話を始める材料と明記し、人事評価の最終判断を代替しない。

## 仮説とUNKNOWN

### 仮説

- Markdownのタスクに、成果／影響の任意メモと待ち理由を追加すると、年度レビューでの説明可能性が上がる。
- waitingとactiveを分けるだけでも、「自分の作業が長い」のか「依存先で止まった」のかを会話しやすくなる。
- 初期版は厳密な勤怠計測より、状態遷移・完了・再作業・注記を正確に保存する方が投資対効果が高い。

### UNKNOWN

- このプロジェクトでの年度評価制度、上司が実際に求める帳票、個人データの保存・共有範囲は確認できていない。
- taskのサイズ、難易度、影響、他者支援を既存Markdownがどの程度持っているかは確認できていない。
- active work timeがユーザーの操作記録からどの精度で再構成できるかは、実装・利用ログがないためUNKNOWNである。
- DORA、SPACE、Kanbanの指標が個人の人事評価に妥当だとする一次資料は確認できていない。むしろ確認できた資料は、単一指標・目標化・異質比較を避ける方向を示している。

## このプロジェクトへの短い推奨

最初に実装すべき対象は、ランキングではなく、`created/started/waiting/resumed/completed/reopened`のイベント、待ち理由、見積と実績、成果／影響メモを保存すること。その上で、年度レビューは「成果一覧＋流れ＋滞留＋品質＋本人の説明」のMarkdownを出力し、全ての自動値に期間・比較条件・欠測を添える。評価スコア化と個人ランキングは採用しない。

## 参照した一次資料・公式資料

- [DORA’s software delivery performance metrics](https://dora.dev/guides/dora-metrics/)
- [DORA: Choosing measurement frameworks to fit your organizational goals](https://dora.dev/research/2025/measurement-frameworks/)
- [Microsoft Research: The SPACE of Developer Productivity](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/)
- [The Kanban Guide 2020](https://kanbanguides.org/the-kanban-guide/2020.12/pdf/kanban-guide.v2020.12.en.pdf)
- [Atlassian: View and understand the control chart](https://support.atlassian.com/jira-software-cloud/docs/view-and-understand-the-control-chart/)
- [Atlassian: Log time on a work item](https://support.atlassian.com/jira-software-cloud/docs/log-time-on-an-issue/)
