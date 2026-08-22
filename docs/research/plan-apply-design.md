# Terraformのplan/apply/state/driftから考える同期設計

調査日: 2026-08-22

## 結論

Terraformの公式ワークフローから、Markdownを望ましい状態、Jira／Confluenceを外部の実体、同期メタデータを対応関係と実行履歴として扱う、という設計原則を類推できる。

```text
読み取り        → 現在のMarkdown・同期state・Jira/Confluenceを取得
plan            → 差分と実行予定を生成（外部へ書き込まない）
review          → 差分・削除・衝突・権限・機密情報を確認
final plan      → 最新のstateと外部状態で再計算し、承認対象を確定
apply           → 承認済みの差分だけを冪等に反映
refresh/drift   → 外部変更を検出し、受入れ・上書き・競合解決を選ぶ
```

これはTerraformのコマンドをそのままjob-utilsへ実装する提案ではない。Terraform公式資料にある「planは差分のプレビュー」「applyは実変更」「stateは設定と外部実体の対応」「driftは外部変更との不一致」という関係を、Markdown→Jira/Confluence同期に適用した推論である。

## 成功条件

- 同期前に、作成・更新・削除・無変更・競合を人が読める差分として確認できる。
- review時のplanと、apply直前の最新状態を区別し、古いplanを無条件に実行しない。
- Markdownの論理エンティティとJira issue／Confluence pageの外部IDを安定して対応付けられる。
- Jira／Confluence側で行われた変更をdriftとして検出し、黙って上書きせず方針を選べる。
- 失敗・再実行・部分適用があっても、重複作成や意図しない削除を避けられる。
- planやstateに含まれ得る本文・トークン・機密情報を、Gitやログへ不用意に出さない。

## 仮説・前提

- **前提（今回の設計上の仮置き）**: Markdownが望ましい状態の主入力で、Jira／Confluenceが同期対象の外部実体である。既存コードに正式なsource-of-truth方針がないため、これは確定事実ではない。
- **仮説**: Terraformのplan/apply分離を採用すると、同期内容をレビューしてから外部へ反映する運用を、CLIでもCIでも一貫させやすい。
- **仮説**: stateを「最後に送った内容」だけでなく、論理ID・外部ID・外部リビジョン・入力ハッシュ・最終結果の対応表として扱うと、更新対象の誤認を減らせる。
- **UNKNOWN**: Jira／Confluenceコネクタが提供するrevision、ETag、更新時刻、ページ階層の競合検知機能は、この調査範囲では確認していない。

## 事実（Terraform公式資料）

### 1. planは読み取りと差分の提示であり、通常は外部を変更しない

`terraform plan`は、既存のremote objectの状態を読み、設定とstateを比較し、設定に一致させるためのアクションを提案する。planだけでは実際の変更を行わず、期待どおりかを確認したり、チームレビューへ共有したりできる。[Terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)

Terraformの標準ワークフローも、planはdesired state、state、実インフラを比較して変更説明を出し、実体は変更しないと説明している。[Terraform workflow for provisioning infrastructure](https://developer.hashicorp.com/terraform/cli/run)

**同期設計への推論**: `sync plan`はJira／Confluenceへ書き込まず、入力Markdown、現在の同期state、外部の現在値を読み取って、次のアクションだけを出力するべきである。

### 2. saved planは「レビューした内容をapplyする」ための実行単位

`terraform plan -out=FILE`で保存したplanは、後で`terraform apply FILE`へ渡せる。Terraform公式は、この二段階を自動化で使うワークフローとして説明している。[Terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)、[terraform apply command reference](https://developer.hashicorp.com/terraform/cli/commands/apply)

保存済みplanをapplyすると、Terraformはそのplanの操作を確認なしで実行するため、planファイルは承認の代替になる。また、planファイルは機密情報を含み得るため、公式チュートリアルはバイナリ・JSONともバージョン管理へcommitしないよう警告している。[Create a Terraform plan](https://developer.hashicorp.com/terraform/tutorials/cli/plan)、[terraform apply command reference](https://developer.hashicorp.com/terraform/cli/commands/apply)

**同期設計への推論**: job-utilsでも、review済みplanに識別子と入力ハッシュを持たせ、`sync apply <plan>`はその差分だけを反映する。ただしplanの保存場所は、内容に機密情報が含まれ得るため、Git追跡ファイルとは限らない。Markdown本文やJiraの秘密フィールドをplanへ含める場合は、redaction済み表示と実行用の安全な保管を分ける。

### 3. review用のspeculative planと、apply直前のfinal planは異なる

Terraformは、VCSのレビュー時にspeculative planを共有できるが、その後に対象システムへ別変更が入ると最終効果が変わり得るため、apply前にfinalのnon-speculative planを再確認すべきだとしている。[Terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)

チーム向けの公式ワークフローも、PRでreviewしたplanとは別に、merge後の共有ブランチと最新stateに対する最終planを確認する必要があると説明している。merge順序や最近のインフラ変更により、最初のplanから変わり得るためである。[Overview of the core Terraform workflow](https://developer.hashicorp.com/terraform/intro/core-workflow)

**同期設計への推論**: review時に出したplanをそのまま長時間後にapplyせず、apply前に外部revision・同期state・Markdown commit/hashを再検証する。変化があればplanを無効化し、差分を再生成して再承認する。

### 4. stateは設定と外部実体の対応を保持する

Terraform stateの主目的は、設定で宣言されたresource instanceとremote system上のオブジェクトのbindingを保持することにある。Terraformは通常、各remote objectが一つのresource instanceに対応することを期待する。[Purpose of Terraform State](https://developer.hashicorp.com/terraform/language/state/purpose)

Terraform公式は、stateが失われると協働が難しくなること、stateを直接編集せずCLIを使うこと、stateには機密情報が含まれ得ること、チームではremote backendを推奨することを説明している。[Terraform State](https://developer.hashicorp.com/terraform/language/state)

**同期設計への推論**: `markdown task id → Jira issue key/id`、`markdown document id → Confluence page id`の対応は、タイトルやURLの再検索に依存せず、明示的なstateとして保持する。タイトル変更、移動、同名文書があっても同じ外部実体を更新できるようにする。1対1対応を基本とし、1つのMarkdownエンティティが複数の外部オブジェクトへ誤って結び付く場合はplanをエラーまたは競合にする。

### 5. stateの同時書き込みにはロックまたは競合制御が必要

Terraformのstate lockingは、backendが対応している場合、stateを書き込む操作の前にロックして他の実行との衝突を防ぐ。ロック取得に失敗した場合は継続しない。[State Locking](https://developer.hashicorp.com/terraform/language/state/locking)

Terraform公式は、remote backendがstate保存とlocking APIを担うこと、version control systemはstate fileを一度に一つのTerraformだけが変更するためのlockingを提供しないことを説明している。[State Storage and Locking](https://developer.hashicorp.com/terraform/language/state/backends)、[Terraform configuration style](https://developer.hashicorp.com/terraform/language/style)

**同期設計への推論**: 同一の同期対象に対するapplyは、最低限、state更新と外部反映を同時に実行する同期処理の排他、または外部revisionを利用した楽観的競合検知を必要とする。Git上のMarkdownを正本にすることと、Jira／Confluenceへの同時applyを無制限に許すことは別問題である。

### 6. driftはstate／設定と外部実体の不一致であり、自動上書きの合図ではない

Terraform公式のdriftチュートリアルは、Terraform外でリソースを変更するとstateと実インフラがずれ、`terraform plan`や`terraform apply`で差分として検出されると説明している。[Manage resource drift](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)

`terraform plan -refresh-only`は、外部変更を検出し、stateへ反映する場合の差分だけを確認するモードであり、refresh-onlyのapplyは実インフラを設定へ戻さず、stateの値だけを更新する。検出後は、外部変更を採用して設定を更新するか、設定を再applyして外部変更を戻すかを判断する必要がある。[Manage resource drift](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)、[Run a refresh-only operation](https://developer.hashicorp.com/terraform/tutorials/cloud-get-started/cloud-refresh-only)

**同期設計への推論**: `sync check --refresh-only`のような読み取り専用検査を用意し、Jira／Confluence側の変更を「外部編集」「job-utilsが最後にapplyした変更」「不明な変更」に分類する。driftを検出したら、次のいずれかを明示的に選ぶ。

```text
accept   : 外部の変更をMarkdownへ取り込む
overwrite: Markdownを正として外部を更新する
conflict : 両方を残し、人の判断を要求する
ignore   : 管理対象外のフィールドとして扱う
```

この4分類はTerraformのコマンド名そのものではなく、refresh-only後に「変更を受け入れるか、設定を戻すか」を判断する公式説明からの設計上の推論である。

## 推奨ワークフロー

### Stage 1: plan

入力を固定して、次を取得する。

- Markdownのcommitまたは内容ハッシュ。
- 現在の同期state（論理ID、外部ID、最後に適用した入力ハッシュ、外部revision等）。
- Jira／Confluenceの現在値、revision、更新者、更新時刻、可能ならETag。
- 同期方針（Markdown正本、外部正本、フィールド単位、削除方針）。

出力には少なくとも次を含める。

| アクション | 意味 |
|---|---|
| no-op | 同期対象の差分なし |
| create | 対応する外部IDがなく、新規作成 |
| update | 対応済み外部実体の内容を更新 |
| move/rename | ページ階層・タイトルなどのメタデータ変更 |
| delete/archive | 削除またはアーカイブ。危険操作として明示 |
| drift | 外部側が最後のapply後に変更された |
| conflict | Markdownと外部の両方が変更された |
| blocked | 権限、必須フィールド、対応不明、機密検査などで停止 |

planは外部へ書き込まず、差分、対象ID、削除件数、権限、機密情報の有無、入力ハッシュ、stateのrevisionを表示する。Terraform planが設定・state・remote objectを比較して提案だけを出すことからの類推である。[Terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)

### Stage 2: review

人が次を確認する。

- 作成・更新・削除の対象と件数。
- 本文の差分と、タイトル・ラベル・親ページ・担当者などのメタデータ差分。
- 外部側での変更と、上書き・取り込み・競合の方針。
- 破壊的変更、権限不足、機密情報の混入。
- この変更を今反映してよいか、通知・メンテナンス・関係者確認が必要か。

Terraform公式も、review時には意図が実現されるか、変更してよいタイミングか、サービス影響や監視・通知が必要かを確認する流れを示している。[Overview of the core Terraform workflow](https://developer.hashicorp.com/terraform/intro/core-workflow)

### Stage 3: final plan

review後、apply直前に入力ハッシュと外部revisionを再確認する。変化がなければ、review済みplanの識別子を承認済みとして進める。変化があれば古いplanを失効させ、planを再生成する。

これは、Terraformのspeculative planが後続の外部変更で古くなる可能性があり、apply前にfinal planを再確認すべきだという公式説明を同期に移したものである。[Terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)

### Stage 4: apply

applyは承認済みplanのアクションだけを、対象の外部IDに対して実行する。

- createは、リトライ時に重複作成しないよう、作成前後でstateを再確認する。
- updateは、対象IDとrevisionが一致しない場合に失敗または再planする。
- delete/archiveは、明示承認を要求する。
- 部分失敗は成功済み・失敗・未実行を記録し、再開可能にする。
- 外部APIのタイムアウトは「失敗」と即断せず、再取得して適用結果を確認する。
- stateは外部反映の結果を確認してから更新し、未確認の成功を記録しない。

Terraformのsaved planが事前に決めた操作を実行すること、state lockingが同時書き込みを防ぐことからの推論である。[terraform apply command reference](https://developer.hashicorp.com/terraform/cli/commands/apply)、[State Locking](https://developer.hashicorp.com/terraform/language/state/locking)

### Stage 5: refresh／drift check

定期または同期前に、Markdownと外部の現在値を読み取って差分を報告する。drift check自体は外部へ変更せず、検出結果を人が次のplanへ回す。

Terraformのrefresh-onlyは外部変更を確認してstateだけを更新でき、実リソースを設定へ戻す操作とは分離されている。[Run a refresh-only operation](https://developer.hashicorp.com/terraform/tutorials/cloud-get-started/cloud-refresh-only)

## job-utilsに採用できる機能への分解

### Plan object

実装時には、少なくとも次の情報を持つplanを候補にする。

```yaml
plan_id: ...
source_revision: markdown commit/hash
state_revision: ...
generated_at: ...
target: jira-or-confluence
actions:
  - logical_id: ...
    remote_id: ...
    action: create|update|delete|drift|conflict|blocked
    field_diffs: ...
    expected_remote_revision: ...
    redacted_summary: ...
```

これはTerraformのplanファイル形式を再現するものではない。reviewとapplyを結び付けるための、job-utils固有の候補モデルである。

### State object

- 論理エンティティID。
- Jira issue key／idまたはConfluence page id。
- 最後に適用したMarkdownのhash。
- 最後に確認した外部revision、更新時刻、取得時刻。
- 外部へ最後に送ったフィールド別hash。
- 最終同期の状態（成功、部分成功、失敗、競合、drift）。
- 手動で受け入れた例外・管理対象外フィールド。

stateは直接編集する前提にせず、修正コマンドまたは再同期で更新する。Terraformがstateを直接編集せずCLIを使うよう案内していることからの類推である。[Terraform State](https://developer.hashicorp.com/terraform/language/state)

### フィールド単位の所有権

Markdown全体を一括上書きするか、外部の全変更を取り込むかの二択にしない。例えば、次のようにフィールド単位の所有権を定義する。

| フィールド | 初期案 | drift時の扱い |
|---|---|---|
| タイトル、本文 | Markdown | overwriteまたはconflict |
| ステータス | 明示的に決める | accept／overwriteを設定可能にする |
| Jira担当者、コメント | Jira | 原則accept、Markdownへは必要な要約だけ取り込む |
| Confluence親ページ | Markdownまたは手動管理 | moveを別アクションとしてreview |
| ラベル、リンク | 方針を明示 | フィールド単位で比較 |

ここでの表はプロジェクトの既存仕様ではなく、source-of-truthを曖昧にしないための設計案である。既存の同期対象フィールドはUNKNOWNである。

### Git・ログ・機密情報

Terraform公式はstateやsaved planに機密情報が含まれ得るため、バージョン管理へ置かないよう注意している。[Terraform State](https://developer.hashicorp.com/terraform/language/state)、[Create a Terraform plan](https://developer.hashicorp.com/terraform/tutorials/cli/plan)、[Terraform configuration style](https://developer.hashicorp.com/terraform/language/style)

job-utilsでも次を分ける。

- Gitへ保存するレビュー用Markdown: 差分の要約、対象IDの一部、機密値を除いた情報。
- ローカルまたは安全な保管場所に置く実行用plan: 必要な本文差分と正確な入力hash。
- state: tokenを保存せず、認証情報は既存の安全なcredential機構から読む。
- ログ: 本文やAPIレスポンスを無制限に出さず、redaction済みの対象・結果・エラーだけを残す。

## 公式仕様をそのまま移植してはいけない点

- Terraformのprovider、state backend、lock、plan fileは、Jira／Confluence APIのrevision・権限・レート制限と同一ではない。
- Terraformのsaved planはTerraform自身が作った実行可能な成果物だが、job-utilsのMarkdown差分は、外部APIが受け付ける最終payloadへ変換する必要がある。
- Terraformのdriftはstateとremote resourceの不一致だが、Jira／Confluenceではユーザーの正当な編集、同期対象外フィールド、表示上の正規化差分を区別する必要がある。
- HCP Terraformのremote executionやplan approval UIを、そのまま採用できるという意味ではない。ここで利用するのはplan／review／apply／state／driftの概念である。

## UNKNOWNと追加調査が必要な項目

- Jira／Confluenceの利用予定API、ページ・issueの識別子、revision／ETag、更新競合時のHTTP応答。
- Markdownの論理IDと、既存の外部ID・同期履歴の保存場所。
- 削除をdeleteとarchiveのどちらで表現するか、削除の承認者、復旧期限。
- 一つのMarkdownから複数のJira issueまたはConfluence pageを生成する要件の有無。
- 本文、コメント、添付、ラベル、担当者、ステータスのどこを同期対象にするか。
- API失敗時の部分適用、レート制限、再試行、認証更新の既存方針。

## このプロジェクトへの短い推奨

同期機能を追加する場合は、まず`plan`（外部へ書かない差分生成）と`apply`（planを明示承認して反映）を別操作にし、apply直前に最新state・外部revision・Markdown hashを検証する。`state`は論理IDと外部IDの対応および最後のhash/revisionを保持し、`refresh-only`相当のdrift検査と、accept／overwrite／conflictの選択を用意する。plan・state・ログに機密情報を含めないこと、削除と競合をデフォルト停止にすることを優先する。

## 参照したTerraform公式資料

- [terraform plan command reference](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [terraform apply command reference](https://developer.hashicorp.com/terraform/cli/commands/apply)
- [Terraform workflow for provisioning infrastructure](https://developer.hashicorp.com/terraform/cli/run)
- [Overview of the core Terraform workflow](https://developer.hashicorp.com/terraform/intro/core-workflow)
- [Purpose of Terraform State](https://developer.hashicorp.com/terraform/language/state/purpose)
- [Terraform State](https://developer.hashicorp.com/terraform/language/state)
- [State Locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [State Storage and Locking](https://developer.hashicorp.com/terraform/language/state/backends)
- [Manage resource drift](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)
- [Run a refresh-only operation](https://developer.hashicorp.com/terraform/tutorials/cloud-get-started/cloud-refresh-only)
- [Create a Terraform plan](https://developer.hashicorp.com/terraform/tutorials/cli/plan)
- [Running Terraform in automation](https://developer.hashicorp.com/terraform/tutorials/automation/automate-terraform)
