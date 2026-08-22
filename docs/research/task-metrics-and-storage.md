# Task Metrics and Git-Friendly Storage Research

調査日: 2026-08-22

## 結論

job-utils の複数PC・Git共有を前提にするなら、次の分離が最も扱いやすい。

- 正本: 不変イベントを1行1レコードで追記する UTF-8 JSONL
- SQLite: JSONLから再生成する検索・集計用の派生DB
- 時間計測: `active` と `waiting` を別の状態区間として記録する
- 基本指標: lead time、cycle time、active work time、waiting time、flow efficiency、throughput、WIP、estimate accuracy
- 同期: event IDで冪等化し、Git競合時は重複除去・正規化してから再集計する

これは、SQLiteのクエリ・トランザクション性能を利用しつつ、Gitが得意とするテキスト差分・マージをイベント正本に残す案である。SQLite単体をGit共有の正本にすると、同じDBファイルへの別PC変更を意味的にマージできない。

## 1. 何を測るべきか

### 1.1 公式ツールで一般的に使われている時間軸

Linearの公式Insightsは、issueについて次を別指標として扱っている。

- **Lead Time**: 作成から完了まで
- **Cycle Time**: 作業開始から完了まで
- **Triage Time**: Triage状態にいた時間
- **Issue Age**: 作成から現在まで
- **Effort**: 見積値の合計

出典: [Linear Insights](https://linear.app/docs/insights)

Jiraの公式Control Chartも、cycle timeを作業開始から完了まで、lead timeを登録から完了までとして区別し、平均・移動平均・標準偏差を用いてばらつきや外れ値を確認する。JiraのFlow Metricsでは、作業中の時間に対する全cycle timeの比率を**flow efficiency**としている。

出典: [Jira Control Chart](https://support.atlassian.com/jira-software-cloud/docs/view-and-understand-the-control-chart/)、[Jira Flow Metrics](https://support.atlassian.com/analytics/docs/flow-metrics-work-items-view-dashboard-template/)

Jiraの公式Time Trackingは、original estimate、実績時間、残り時間を比較する用途を明示している。したがって、個人の振り返りでも「見積もりと実績の差」は有用な基本指標になる。

出典: [Jira: Log time on a work item](https://support.atlassian.com/jira-software-cloud/docs/log-time-on-a-work-item/)

### 1.2 GTD向けに必要なイベント

ユーザーのGTD運用では、単に `start` と `complete` だけでは待ち時間を分離できない。最低限、次のイベントを記録できるようにする。

```text
created
status_changed
started
paused
resumed
waiting_started
waiting_ended
completed
reopened
```

`waiting` は `paused` の別名にせず、外部回答待ち・レビュー待ち・依存タスク待ちなど、待ち理由を任意で記録できる状態にする。これにより「自分の作業が遅い」のか「外部待ちが長い」のかを後から分解できる。

イベントは原則として削除・上書きせず、訂正は新しいイベントで表現する。状態から時間を推測すると、別PCでの作業や離席を誤って作業時間に含めるため、明示操作と状態変更の両方を記録する。ただし自動計測は補助的に使い、ユーザーが常に厳密なタイマー操作を強制されない設計がよい。

### 1.3 推奨する派生指標と用途

| 指標 | 定義案 | 使い道 |
|---|---|---|
| Lead time | `created` から最終 `completed` まで | 依頼を受けてから成果になるまでの期間 |
| Cycle time | 最初の作業開始から最終完了まで | 作業フローの速さ、将来の見通し |
| Active work time | `active` 区間の合計 | 実際に手を動かした概算時間 |
| Waiting time | `waiting` 区間の合計 | 外部依存・レビュー・回答待ちの把握 |
| Flow efficiency | `active work time / cycle time` | 待ち・滞留が全体期間に占める割合 |
| Estimate error | `actual - estimate`、または比率 | 見積もり精度の振り返り |
| Throughput | 期間内の完了タスク数 | 月次・四半期の成果量の説明 |
| WIP | 同時に作業中のタスク数 | 着手しすぎの検知 |
| Age | 未完了タスクの経過時間 | 放置・棚上げの発見 |
| Status time | statusごとの滞在時間 | waiting、review、blocked等のボトルネック把握 |
| Percentiles | median、p75、p95 | 平均だけでは隠れる外れ値と予測幅の把握 |

Atlassianは、cycle time、lead time、throughput、WIP、flow efficiencyを同じFlow Metricsの枠で扱い、Linearもcycle/lead/triage/age/estimateを分析軸としている。個人の成果説明では、単純な完了数だけでなく、次の組合せが説明しやすい。

```text
成果量: 完了数、throughput
納期性: lead time / cycle time の中央値と p75
投入量: active work time
阻害要因: waiting time と status別滞在時間
予測力: estimate と actual の誤差
改善: flow efficiency、外れ値の原因
```

これは「完了数が多いほど優秀」と短絡しないための構成でもある。タスクの大きさ、種類、外部待ち、再オープンを一緒に表示し、成果説明や上司との評価では期間・カテゴリ・難易度を絞って比較するべきである。後半は公式製品の指標定義からの設計上の推奨であり、job-utils固有の推論である。

## 2. イベント記録の最小案

実装仕様ではなく、今回の調査から得た候補である。

```json
{"event_id":"uuid","task_id":"20260822-001","type":"waiting_started","at":"2026-08-22T10:00:00+09:00","reason":"review","source":"vim"}
{"event_id":"uuid","task_id":"20260822-001","type":"waiting_ended","at":"2026-08-22T14:30:00+09:00","source":"cli"}
```

必要な属性は、少なくとも `event_id`、安定した `task_id`、イベント種別、UTCまたはオフセット付き時刻、入力元、任意の理由である。`waiting_started` と `waiting_ended` の間をwaiting time、作業中区間の合計をactive work timeとして集計する。

イベントの時刻は、端末時刻の差異を考慮してISO 8601のオフセット付きで保存し、集計時にUTCへ正規化する。重複イベントを防ぐため、各イベントにUUID等の一意IDを持たせる。これはJSONLの性質から直接導かれる要件ではなく、複数PCで追記をマージするための設計上の推奨である。

## 3. JSON/JSONLとSQLiteの比較

### 3.1 JSONL

JSON Linesは、各行を独立したJSON値として扱い、1レコードずつ処理できるUTF-8のテキスト形式である。末尾改行を付けると生成・連結が容易で、ログにも適している。

出典: [JSON Lines specification](https://jsonlines.org/)、JSON自体の仕様は [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259)

今回のイベントログに向く理由:

- 追記型ログと自然に対応する
- 人間がレビューでき、Gitの行単位diffを使える
- `jq`、grep、Python標準ライブラリなどで調査できる
- 別PCで追加されたイベントを、イベント単位で比較しやすい
- SQLiteを再生成する入力として明確にできる

注意点:

- JSONL自体はトランザクションや一意制約を提供しない
- 同じイベントを2台で登録すると重複し得る
- 2つのブランチが同じ末尾へ追記すると、Gitの自動マージ結果の順序が意味的に保証されない
- JSONLファイルを直接編集した場合、壊れた1行がログ全体の読み込みを止め得る

最後の3点は、UUID、スキーマ検証、重複除去、時刻とevent IDによる正規化を組み合わせて扱う。Gitの既定動作だけに「追記ログだから必ず安全」と依存してはいけない。

### 3.2 SQLite

SQLiteは、テーブル・インデックス・制約・トランザクション・SQLクエリを単一のクロスプラットフォームファイルにまとめられる。公式資料も、アプリケーションファイル形式としての検索性、ACIDトランザクション、インデックス、複数テーブルを利点として挙げている。

出典: [SQLite as an Application File Format](https://www.sqlite.org/appfileformat.html)、[SQLite About](https://sqlite.org/about.html)

今回の集計DBに向く理由:

- task、event、status interval、同期状態を正規化できる
- 期間・状態・タスク種別ごとの集計がSQLで明確になる
- 再集計が速く、レポート用のビューやインデックスを持てる
- 32/64-bitやOSをまたいで利用できる

Git共有の正本にする場合の問題:

- SQLiteの主状態は通常単一のバイナリDBファイルであり、Gitの行単位merge対象にならない
- Gitはバイナリとして扱うファイルに対して、通常のテキストdiff/3-way mergeを提供しない。Git公式資料でも、binary属性では通常のdiffを抑制し、binary mergeでは片側を残して競合扱いにする説明になっている
- WALモードではDB本体の隣に `-wal` と `-shm` が関係し、これらをGitで独立に扱う設計は避ける必要がある
- SQLiteはWALモードでも同時書き込みは1 writerであり、WALはネットワークファイルシステムでは動作しない
- 2台が別々に同じDBを編集してpushした場合、SQL上の行単位ではなくファイル全体の競合になる

出典: [SQLite database file format](https://www.sqlite.org/fileformat.html)、[SQLite WAL](https://www.sqlite.org/wal.html)、[Git gitattributes: diff/merge drivers](https://git-scm.com/docs/gitattributes)、[Git merge](https://git-scm.com/docs/git-merge)

## 4. 推奨ストレージ設計

```text
.jobutils/
├── metrics/
│   ├── events.jsonl        # Gitで共有する正本
│   ├── schema.json         # イベント形式の検証用
│   └── index.sqlite        # events.jsonlから再生成する派生DB
└── ...
```

推奨方針:

1. `events.jsonl` は不変イベントのGit共有正本にする。
2. 各PCで `events.jsonl` を読み、`index.sqlite` を再生成または更新する。
3. `index.sqlite` は通常Gitの正本にせず、`.gitignore`対象にする。必要ならレポート生成時だけ成果物として出力する。
4. event IDで冪等化し、同じJSONLを何度取り込んでも同じSQLite結果になるようにする。
5. Git push拒否時はpull/rebase後にJSONLを正規化し、重複と順序を検証してから再pushする。
6. 競合解消は「単純な文字列結合」ではなく、JSONとして検証し、event IDで重複除去し、canonical orderで再出力する専用処理にする。

SQLiteをGit管理したい場合も、技術的には単一ファイルとしてcommitできる。ただし、それは「各PCが同時に変更してもGitで意味的にマージできる」ことを意味しない。SQLiteを正本にするなら、同時更新を禁止するロック・一人のpublish担当・DB export時の運用ルールが必要になる。今回の複数PC運用では、SQLiteは正規化と高速集計を担う派生read modelに限定する方が、Gitの性質と整合する。

## 5. 未確定事項

- GTDの各prefixを、`active`、`waiting`、`backlog`、`done`のどの計測カテゴリに対応付けるか
- `pause` と `waiting` の理由の語彙を固定するか、自由記述にするか
- 自動計測の開始条件と、Vim/CLIを閉じた場合の扱い
- estimateの単位を分・時間・相対ポイントのどれにするか
- 平均・中央値・p75/p95を、個人レポートでどこまで標準表示するか
- JSONLとSQLiteの再生成ルールを、既存の同期状態・外部IDインデックスとどう分離するか

現時点の設計判断としては、最初から精密な勤怠計測を目指さず、`created`、状態遷移、`started/paused/resumed`、`waiting_started/ended`、`completed`を確実に残すことが優先される。半年後の振り返りに必要な指標は、そのイベントから再計算できる形にしておくのが安全である。
