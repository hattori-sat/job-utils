# GTDモデル調査

調査日: 2026-08-22

## Outcome

GTD（Getting Things Done）の公式資料を基準に、入力を処理するワークフローと、処理後に置くリストの意味を整理した。`job-utils` では、GTDのリスト／意味と、プロジェクト固有のToday分類を同じ状態値に押し込めず、別の軸として保存・表示することを推奨する。

この文書の表記は次のとおり。

- **事実**: David Allen Company / Getting Things Done公式資料に明記されている内容。
- **推論**: 公式資料の区別を `job-utils` のデータモデルや集計へ適用した設計判断。
- **仮説**: 現行仕様を確認できないため、採用前にプロジェクト側で検証が必要な案。
- **UNKNOWN**: この調査では確認できなかったこと。

## 成功条件

- Inboxを未処理入力の置き場として扱い、処理後の行き先をGTDの意味に沿って区別できる。
- Capture / Clarify / Organize / Reflect / Engageと、Projects / Next Actions / Waiting For / Calendar / Someday/Maybe / Referenceを混同しない。
- 「今やる」「今日表示する」をGTD標準の概念と誤認しない。
- 時間、待ち、レビューを後から分析できるだけの履歴を残せる。
- GTD公式の定義と、`job-utils` 固有の設計提案を読者が区別できる。

## 1. GTDの全体像

### 1.1 Capture / Clarify / Organize / Reflect / Engage

**事実**: GTD公式は、ワークフローを次の5段階で説明している。[GTD公式「What is GTD?」](https://gettingthingsdone.com/what-is-gtd/)、[GTD公式「Five Steps」](https://gettingthingsdone.com/five-Steps/)

| 段階 | 公式資料上の意味 | `job-utils` での読み替え |
|---|---|---|
| Capture | 注意を引いているものを、書く・記録する・集める。 | 入力を失わず、まずInboxへ置く。 |
| Clarify | それが何か、行動可能か、行動可能なら次の行動と望ましい結果は何かを決める。非行動項目はTrash / Reference / Incubate等へ分ける。 | Inbox項目を解釈し、GTDの行き先と意味を決める。 |
| Organize | 決めた内容を、必要な時と方法で取り出せる適切な場所へ置く。 | リスト種別、文脈、Projectとの関係、日時などを保存する。 |
| Reflect | システムの内容を定期的に見直し、更新する。 | Inbox、Calendar、Next Actions、Waiting For、Projects、Someday/Maybeをレビューする。 |
| Engage | 信頼できるシステムを使い、その時点で何をするか選ぶ。 | 利用可能な候補から、文脈・時間・資源・優先度を見て選ぶ。 |

**重要な区別（事実）**: これは個々の仕事が必ず一方向に遷移する「5値のステータス」ではなく、入力を処理し、信頼できるリストから行動を選ぶためのワークフローとして説明されている。[GTD公式「What is GTD?」](https://gettingthingsdone.com/what-is-gtd/)、[GTD公式「Choosing what to do」](https://gettingthingsdone.com/2023/01/choosing-what-to-do/)

**推論**: 保存モデルでは、`capture / clarify / organize / reflect / engage` をタスクの恒久的な `status` enum にしない。必要なら、処理イベントの `event_type` または操作ログとして記録する。

### 1.2 Inboxの意味

**事実**: GTD公式のInbox処理は、入力を「何か」「行動可能か」と問い、行動可能なら次の行動を決め、複数アクションなら望ましい結果をProjectとして記録する流れである。行動可能でなければ、Trash、Reference、Someday/Maybeや日付トリガーなどへ送る。[GTD公式 Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)、[GTD公式「Getting your inbox to zero」](https://gettingthingsdone.com/wp-content/uploads/2018/08/GTD_Outlook_2013-2016_sample.pdf)

**事実**: Inboxを空にするとは、項目を削除することではなく、各項目が何を意味し、何をするかを決めてInboxの外へ処理することである。[GTD公式「Getting your inbox to zero」](https://gettingthingsdone.com/wp-content/uploads/2018/08/GTD_Outlook_2013-2016_sample.pdf)

**推論**: `inbox` は「未完了タスク」という意味ではなく、「まだ意味づけ・行き先決定が済んでいない入力」という分類にする。Inboxに置かれたレコードには、少なくとも `captured_at`、`source`、原文または要約、処理済みかどうかを持たせる。

**仮説**: 処理済みInbox項目を削除せずイベント履歴として残すと、Inbox滞留時間や処理率を算出しやすい。ただし、原文保存の機密性・保持期間はプロジェクト要件が必要である。

## 2. GTDのリスト／分類

### 2.1 Next Actions

**事実**: Next Actionsは、完了へ向けて実行できる「物理的・可視的な次の行動」を保持する。Projectに関係する行動と、単独で完了する行動の両方が含まれ、文脈（Calls、Computer、Home、Errands等）で分ける方法が公式に推奨されている。[GTD公式 Next Actions sample](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf)

**事実**: Next Actionsリストは、毎日作り直す「今日の予定表」ではなく、自由時間に使える行動のリマインダーである。特定の日に必ず行う行動はCalendarへ置く。[GTD公式 Next Actions sample](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf)

**推論**: Next Actionには、曖昧な「企画を進める」ではなく、読んだ時に次の身体的・可視的な行動が分かるタイトルを要求する。`context` は必須とは限らないが、文脈で絞り込める設計にする。

### 2.2 Projects

**事実**: GTD公式は、Projectを「複数のアクションを必要とする望ましい結果」と説明し、通常は今後12か月以内に完了を見込む現在の成果のリストとして扱う。[GTD公式「Managing projects with GTD」](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/)、[GTD公式 Projects sample](https://gettingthingsdone.com/wp-content/uploads/2021/04/GTD_Outlook_Web_SAMPLE-LTR.pdf)

**事実**: CurrentなProjectには、少なくとも一つのCurrentなNext Action、Waiting For、またはCalendar上の行動があることを公式資料は示している。未来に依存していて今は行動できないものは、Next Actionsに置かず、Project supportまたはSomeday/Maybeとして扱う。[GTD公式「Managing projects with GTD」](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/)

**事実**: Next Actionsは日々の行動選択用の文脈別リストであり、Project listやProject supportを置き換えない。公式は、必要に応じてProjectとNext Actionをリンクして表示してよいとしている。[GTD公式「The GTD Approach to Linking Next Actions and Projects」](https://gettingthingsdone.com/2020/06/the-gtd-approach-to-linking-next-actions-and-projects/)

**推論**: Projectは「親タスクの状態」ではなく、望ましい結果を識別するエンティティにする。Next ActionはProjectの子リストに固定せず、`project_id` で関連付け、通常表示は文脈別Next Actionsとして投影する。

### 2.3 Waiting For

**事実**: GTDの公式Workflow Mapは、他者へ委任した行動で、完了を追跡する必要がある場合、コミュニケーションシステムとWaiting Forリスト／フォルダでリマインドすると説明している。[GTD公式 Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)

**事実**: 公式Weekly ReviewではWaiting For listを確認し、必要なフォローアップを記録し、受領済みの項目を完了扱いにする。[GTD公式 Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf)

**推論**: `waiting_for` は単なる `paused` の別名ではなく、「誰／何から、何を待っているか」を表すリマインダー種別にする。最低限、`waiting_on`、`requested_at`、`follow_up_at`（任意）、`received_at`（任意）、`project_id`（任意）を持たせる。

**仮説**: `waiting_for` を明示的な状態として保存すると、activeな作業時間と外部待ち時間を分離できる。ただし、GTD公式が時間計測の状態機械を定義しているわけではないため、これは `job-utils` 固有の計測設計である。

### 2.4 Calendar

**事実**: GTD公式は、Calendarに置くものを次の3つに分けている。[GTD公式 Calendar guidance](https://gettingthingsdone.com/wp-content/uploads/2023/12/GTD_Todoist_SAMPLE_A4.pdf)

1. **Time-specific action**: 特定の日・時刻に起きる行動。会議、予定、時間を確保した作業など。
2. **Day-specific action**: 特定の日に行うが、時刻は固定しない行動。
3. **Day-specific information**: その日に知っておきたい情報。必ずしも行動ではない。

**事実**: 公式資料は、Calendarを「その日に行うべきこと」と「特定の日までに行えばよいNext Action」を区別する、日々のhard landscapeとして説明している。[GTD公式 Calendar guidance](https://gettingthingsdone.com/wp-content/uploads/2023/12/GTD_Todoist_SAMPLE_A4.pdf)

**推論**: `due_at` と `scheduled_at` を同一視しない。Calendarに置く根拠は「その日／時刻に行う必要がある」ことであり、単に重要、早く終えたい、期限が近い、という理由だけでTodayへ移すものではない。

### 2.5 Someday/Maybe

**事実**: Someday/Maybeは、将来やりたい可能性はあるが、現時点では実行へのコミットメントがないものを置く場所である。そこに置く唯一のコミットメントは、定期的にレビューすることだと公式資料は説明している。[GTD公式 Someday/Maybe guidance](https://gettingthingsdone.com/wp-content/uploads/2021/04/GTD_Outlook_Web_SAMPLE-LTR.pdf)

**事実**: 公式Weekly ReviewではSomeday/Maybeを見直し、現在のProjectへ移すものを移し、関心がなくなったものを削除する。[GTD公式 Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf)

**推論**: Someday/Maybeは `backlog` や `低優先度` と同義にしない。実行のコミットメントが現在ない、という意味を保持する。`reviewed_at`、`promoted_at`、`discarded_at` を履歴として持たせると、レビューの結果を追跡できる。

### 2.6 Reference

**事実**: GTD公式Workflowは、行動不要だが将来価値があり得る情報をReferenceへファイルする分岐を持つ。[GTD公式 Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)

**事実**: David Allenの公式Reference資料は、Referenceを必要な時にすぐ取り出せる信頼できる仕組みとし、一般ReferenceはA-Zの単一ファイリングシステムにすること、Reminder systemとReferenceを混ぜないことを説明している。[David Allen Company「General Reference Filing」](https://gettingthingsdone.com/wp-content/uploads/2014/10/Filing.pdf)

**推論**: Referenceはタスクの未完了状態ではない。`reference_uri`、検索可能なタイトル／タグ、出典、保持方針などを持つ情報リソースとして管理し、行動リストから分離する。

## 3. 時間・状態・レビュー

### 3.1 GTDにおける時間

**事実**: Engageで何を選ぶかは、Context、Time available、Resources（エネルギー等）、Prioritiesの4基準で考えると公式は説明している。[GTD公式「Choosing what to do」](https://gettingthingsdone.com/2023/01/choosing-what-to-do/)

**事実**: GTD公式は、仕事を「既に定義した仕事」「現れてくる仕事」「仕事を定義する仕事」の三つの側面でも説明している。Inbox処理や整理は、実行そのものとは別の仕事である。[GTD公式「Choosing what to do」](https://gettingthingsdone.com/2023/01/choosing-what-to-do/)、[GTD公式 Three-fold Nature of Work](https://gettingthingsdone.com/wp-content/uploads/2021/09/Threefold-Nature-of-Work.pdf)

**推論**: `estimated_minutes` や `energy` は、GTDリストの意味を変える必須状態ではなく、Engage時の選択補助属性として扱う。Todayに選ばれた理由も、Calendar、期限、文脈、ユーザー選択などに分けて保持する。

### 3.2 GTDにおける状態

**事実**: 公式資料は、入力の処理結果をTrash、Reference、Incubate、Project、Waiting、Calendar、Next Actionsなどの異なる行き先として示している。[GTD公式 Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)

**調査上の結論（推論）**: GTDの「リスト種別」は、`open → doing → blocked → done` のような単一の標準状態機械とは異なる。特にWaiting For、Calendar、Someday/Maybeは、行動の進捗だけでなく、誰がいつ何をするか、現時点でコミットしているか、という別の意味を表す。

**推奨**: 保存時に次を分離する。

- `gtd_bucket`: `inbox` / `next_action` / `project` / `waiting_for` / `calendar` / `someday_maybe` / `reference`。
- `work_state`: `open` / `in_progress` / `completed` / `cancelled` など、アプリケーション運用上必要な値。
- `today`: 下記のプロジェクト固有分類。GTD bucketやwork stateの別名にしない。
- `events`: capture、clarify、bucket変更、waiting開始／終了、calendar追加、完了、レビューなどの履歴。

`work_state` の具体的な語彙は現行仕様がないため、UNKNOWNである。

### 3.3 GTDにおけるレビュー

**事実**: GTD公式のWeekly Reviewは、Get Clear、Get Current、Get Creativeの三部構成である。具体的には、Inboxをゼロにする、頭の中を空にする、Action Lists・過去／未来のCalendar・Waiting For・Projects・関連チェックリストを確認し、Someday/Maybeを見直す。[GTD公式 Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf)

**事実**: GTD公式の説明では、レビューはシステムを機能させ、内容を最新に保ち、信頼して選択するための反復行為である。[GTD公式「What is GTD?」](https://gettingthingsdone.com/what-is-gtd/)

**推論**: Reviewは、単一の `reviewed=true` フラグで済ませない。レビュー対象、開始・終了時刻、見た時点のスナップショット、発生した変更、未処理項目をイベントとして残すと、「レビューしたがCurrentではなかった」ことを区別できる。

**UNKNOWN**: GTD公式資料は、レビューの完了率、Inbox処理時間、Projectの滞留日数などの数値目標を標準メトリクスとして定義していない。以下のメトリクスは、公式概念から導く `job-utils` 向けの派生指標であり、GTD標準指標ではない。

## 4. GTD標準とToday分類の分離

### 4.1 分離の理由

**事実**: GTDでは、Calendarは特定の日／時刻に行うもの、Next Actionsは文脈と自由時間に応じて選ぶもの、Someday/Maybeは現在のコミットメントがないものとして区別される。[GTD公式 Calendar guidance](https://gettingthingsdone.com/wp-content/uploads/2023/12/GTD_Todoist_SAMPLE_A4.pdf)、[GTD公式 Next Actions sample](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf)、[GTD公式 Someday/Maybe guidance](https://gettingthingsdone.com/wp-content/uploads/2021/04/GTD_Outlook_Web_SAMPLE-LTR.pdf)

**推論**: `Today` は、少なくとも次の意味を混ぜる危険がある。

- Calendarにより今日必須。
- 期限が今日。
- 今日やるとユーザーが選んだ。
- Today画面に表示したい。
- GTDのEngageで今の文脈・時間・資源に合う。

これらは同じではない。Todayを `gtd_bucket=calendar` や `work_state=in_progress` として保存すると、GTDのhard landscapeと個人的な選択・表示上の都合が衝突する。

### 4.2 推奨する文書上の境界

以下のように、GTD標準とプロジェクト固有仕様を別章・別フィールドで書く。

| 層 | 内容 | 例 |
|---|---|---|
| GTD標準 | 入力を処理した結果の意味 | `inbox`, `next_action`, `project`, `waiting_for`, `calendar`, `someday_maybe`, `reference` |
| アプリ運用状態 | 実行・完了・取消などの運用状態 | `open`, `in_progress`, `completed`, `cancelled` |
| Today分類 | `job-utils` が今日の作業候補として分類・表示する独自情報 | `today=true`, `today_reason=manual|due|calendar|review` |
| 派生表示 | 保存値から作るビュー | 今日の候補、期限超過、待ちフォローアップ、未レビュー |

**推奨**: Todayをboolean一つだけで保存する場合でも、Calendar由来か、期限由来か、手動選択かを別イベントまたは `today_reason` で残す。Todayから外したことも履歴に残し、GTD bucketを変更したとは解釈しない。

**仮説**: 現行UIでTodayが「今日作業するもの」の意味なら、TodayはGTDのEngageで選んだ候補を表す投影として実装するのが最も自然である。Calendarの必須項目はToday候補へ自動表示できるが、候補に表示されたこと自体をCalendar変更とは扱わない。

**UNKNOWN**: 現在の `job-utils` にTodayのデータ形式、UI上の意味、手動選択と自動選択の優先順位、期限超過の扱いが定義されているかは、リポジトリ内の調査範囲では確認できなかった。

## 5. `job-utils` 向け推奨データモデル

これはGTD公式のデータ形式ではなく、公式概念を保ちつつ、Today分類と履歴・集計を分離するための設計推論である。

### 5.1 論理エンティティ

```yaml
item:
  id: stable-id
  title: "具体的な次の行動、または望ましい結果"
  gtd_bucket: inbox|next_action|project|waiting_for|calendar|someday_maybe|reference
  work_state: open|in_progress|completed|cancelled
  project_id: optional-stable-project-id
  context: optional-context
  captured_at: timestamp
  clarified_at: optional-timestamp
  completed_at: optional-timestamp

  # Calendar / time fields
  scheduled_at: optional-timestamp
  scheduled_date: optional-date
  due_at: optional-timestamp
  time_kind: none|time_specific|day_specific_action|day_specific_information

  # Waiting For fields
  waiting_on: optional-person-or-system
  waiting_reason: optional-review|approval|dependency|reply|other
  requested_at: optional-timestamp
  follow_up_at: optional-timestamp

  # Engage / Today projection; not a GTD bucket
  today:
    selected: false
    reason: optional-manual|calendar|due|review|other
    selected_at: optional-timestamp

  reference_uri: optional-uri
  source: optional-capture-source
  review:
    last_reviewed_at: optional-timestamp
```

### 5.2 ProjectとNext Actionの関係

**推奨**: Projectは望ましい結果、Next Actionは実行可能な次の一歩として別レコードにする。Next Actionの通常ビューは文脈別にし、Projectビューでは `project_id` で関連するNext Action、Waiting For、Calendarを集約する。[GTD公式「The GTD Approach to Linking Next Actions and Projects」](https://gettingthingsdone.com/2020/06/the-gtd-approach-to-linking-next-actions-and-projects/)

**推奨**: Projectの「進行中」を、Projectレコードだけの状態から推測しない。少なくとも、関連するCurrentなNext Action、Waiting For、Calendarがあるかを派生判定する。[GTD公式「Managing projects with GTD」](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/)

### 5.3 イベント履歴

**推論**: 時間・状態・レビューの分析には、現在値だけでなくイベントが必要である。

```yaml
event:
  event_id: stable-event-id
  item_id: stable-item-id
  event_type: capture|clarify|bucket_changed|state_changed|today_selected|today_unselected|waiting_started|waiting_ended|calendar_added|reviewed|completed
  occurred_at: timestamp-with-offset
  from_value: optional
  to_value: optional
  reason: optional
  source: vim|cli|import|manual|unknown
```

GTD公式はこのイベントスキーマを規定していない。ここでの提案は、Inbox処理、Waiting For、Calendar、Someday/Maybe、Weekly Reviewという公式上の区別を、後から検証可能な履歴へ写像したものだ。[GTD公式 Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)、[GTD公式 Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf)

## 6. GTD状態から導けるメトリクス

以下はGTD標準の公式メトリクスではなく、公式の分類・レビュー手順から導く派生指標である。評価やランキングの単一スコアにせず、システムの滞留・未整備・負荷を発見する用途に限定するのが安全である。

| メトリクス | 算出案 | 読み方 | 根拠 |
|---|---|---|---|
| Inbox件数 | `gtd_bucket=inbox` の件数 | 未処理入力の量 | Inboxは処理前の入力を受ける場所。[Workflow Map](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf) |
| Inbox滞留時間 | `clarified_at - captured_at` | 入力が意味づけされるまでの時間 | CaptureとClarifyの区別。[What is GTD?](https://gettingthingsdone.com/what-is-gtd/) |
| Inbox処理率 | 期間内にClarifyされた件数 / 期間内Capture件数 | 入口が詰まっているか | 公式Weekly ReviewのGet “IN” to zero。[Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf) |
| Next Actionの文脈別件数 | `gtd_bucket=next_action` をcontext別に集計 | 選択可能な行動の偏り・負荷 | Next Actionsは文脈別リスト。[Next Actions sample](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf) |
| 曖昧な行動率 | Next Actionのうち、具体的な動詞・対象・完了条件の検査に失敗した件数 | Clarify品質の候補 | Next Actionは物理的・可視的な行動。[Next Actions sample](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf) |
| Projectカバレッジ | Current Projectのうち、Next Action / Waiting For / Calendarのいずれかがある割合 | Projectが次に進むリマインダーを持つか | Project管理の公式基準。[Managing projects with GTD](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/) |
| Projectの未接続数 | Current Projectのうち、関連する行動・待ち・Calendarがない件数 | CurrentとSomeday/Maybeの境界が曖昧か | 同上。[Managing projects with GTD](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/) |
| Waiting For滞留時間 | `waiting_ended - waiting_started` または現在時刻との差 | 外部依存・レビュー・回答の滞留 | Waiting Forはフォローアップ用リスト。[Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf) |
| Waiting Forフォローアップ漏れ | `follow_up_at <= now` かつ未完了の件数 | 確認が必要な待ち | 公式Weekly ReviewでWaiting Forを確認し、フォローアップを記録。[Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf) |
| Calendar負荷 | 期間内のtime-specific / day-specific action件数・時間 | Hard landscapeの混雑 | Calendarの3分類。[Calendar guidance](https://gettingthingsdone.com/wp-content/uploads/2023/12/GTD_Todoist_SAMPLE_A4.pdf) |
| Someday/Maybeの鮮度 | `now - last_reviewed_at`、未レビュー件数 | Incubate項目がレビューされているか | Someday/Maybeは定期レビューが必要。[Someday/Maybe guidance](https://gettingthingsdone.com/wp-content/uploads/2021/04/GTD_Outlook_Web_SAMPLE-LTR.pdf) |
| Someday/Maybeからの転換率 | Project / Next Actionへ移った件数 / レビューした件数 | 将来候補の選別状況 | 公式Weekly Reviewの昇格・削除。[Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf) |
| レビュー鮮度 | bucket別の `now - last_reviewed_at` | システムがCurrentか | ReflectとWeekly Review。[What is GTD?](https://gettingthingsdone.com/what-is-gtd/)、[Weekly Review](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf) |
| Today選択率 | Todayに選ばれた件数 / Next Action等の候補件数 | **プロジェクト固有**の選択・表示傾向 | GTDのEngageは選択基準を示すが、Today指標は規定しない。[Choosing what to do](https://gettingthingsdone.com/2023/01/choosing-what-to-do/) |

**注意**: `active work time`、`cycle time`、`throughput` などは、GTD公式の標準語彙・標準メトリクスではない。採用する場合は、GTD bucketとは別のイベント／時間区間モデルとして定義し、Today選択やCalendarの予定時間を実作業時間とみなさない。

## 7. 仮説・UNKNOWN

### 仮説

- `job-utils` は、GTDの「意味づけ」とTodayの「当日選択」を分離すると、Calendarの必須予定、期限、手動選択、自由時間のNext Actionを同じ画面で扱いやすくなる。
- ProjectとNext Actionを親子リストとして固定せず、関連IDと複数ビューで扱うと、公式の「文脈別Next Actions」と「Project list」の両方を保ちやすい。
- 現在値の上書きだけでなくイベントを保存すると、Inbox滞留、Waiting For滞留、レビュー鮮度、Today選択の傾向を後から再計算できる。

### UNKNOWN

- `job-utils` の現行コード、データ形式、UI、CLIにToday分類が存在するか、その正確な意味は確認できていない。
- Todayの自動分類ルール（期限、Calendar、優先度、手動選択の優先順位）は未定義である。
- `work_state` の正式な語彙、完了・取消・再開・再オープンの扱いは未確認である。
- GTD公式は、Inbox処理時間、Project滞留、Waiting For時間、Today選択率などを標準KPIとして規定していない。
- GTD公式は、GTDリストをイベントソーシング形式、JSONL、SQLiteなどの保存形式で規定していない。
- どの入力をReferenceとして保存し、どの期間で削除・アーカイブするかは、機密性・保持要件の確認が必要である。
- GTD公式の「今後12か月以内」というProjectの説明を、`job-utils` の期限ルールへそのまま採用してよいかは未確認である。

## 8. 参照した公式・一次資料

- [What is GTD? — Getting Things Done](https://gettingthingsdone.com/what-is-gtd/)
- [Five Steps — Getting Things Done](https://gettingthingsdone.com/five-Steps/)
- [GTD Workflow Map — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2024/05/GTD_workflow_map.pdf)
- [Getting your inbox to zero — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2018/08/GTD_Outlook_2013-2016_sample.pdf)
- [The GTD Weekly Review — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2016/04/GTD-WeeklyReview.pdf)
- [Next Actions Lists — David Allen Company](https://store.gettingthingsdone.com/wp-content/uploads/2025/04/GTD_Paper_Organizers_SAMPLE.pdf)
- [Managing projects with GTD — Getting Things Done](https://gettingthingsdone.com/2017/05/managing-projects-with-gtd/)
- [The GTD Approach to Linking Next Actions and Projects — Getting Things Done](https://gettingthingsdone.com/2020/06/the-gtd-approach-to-linking-next-actions-and-projects/)
- [Calendar guidance — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2023/12/GTD_Todoist_SAMPLE_A4.pdf)
- [Someday/Maybe guidance — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2021/04/GTD_Outlook_Web_SAMPLE-LTR.pdf)
- [General Reference Filing — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2014/10/Filing.pdf)
- [Choosing what to do — Getting Things Done](https://gettingthingsdone.com/2023/01/choosing-what-to-do/)
- [The Three-fold Nature of Work — David Allen Company](https://gettingthingsdone.com/wp-content/uploads/2021/09/Threefold-Nature-of-Work.pdf)
