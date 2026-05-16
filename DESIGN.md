# task-timer 設計メモ

このドキュメントは、これまでのClaudeとの設計議論で確定した内容をまとめたもの。
**次回セッションで Claude が読めば、要件定義からやり直さずに開発を再開できる**ことを目的とする。

最終更新：2026-05-09（メモ機能＋ルーティンフェーズ＋集中モード＋汎用プロジェクト自動セットアップ）

---

## 1. 目的

仕事（Win）・私生活（Mac）両方で、時間の使い方を計測・可視化・改善する個人ツール。

「全部入り」を最終形とする：
- **可視化**：どのプロジェクトに何時間使ったか週次で見たい
- **集中装置**：今これやる、を物理的に強制する
- **予実差分**：見積精度を上げる

ただしv0.1は段階分けで絞る（後述）。

---

## 2. 制約・前提

| 項目 | 内容 |
|---|---|
| 動作環境 | Windows（仕事）＋ Mac（私生活）両対応 |
| データ共有 | **しない**（仕事のセキュリティ厳しい）。同じコードベース・別データ |
| AI使用 | 仕事Win：**不可**。私生活Mac：**可**だがv0.1には入れない |
| ライセンス | 個人用、PySide6のLGPLv3で問題なし |
| Outlook | 依存撤廃。タスクは独自管理 |

---

## 3. 技術スタック

| 層 | 採用 | 理由 |
|---|---|---|
| Python | 3.12（pin） | uv 標準 |
| 環境管理 | **uv** | 単一バイナリ、Win/Mac両対応、`uv.lock`で再現性 |
| UI | **PySide6** | ツリー・D&D・ショートカット標準装備、ネイティブ見た目 |
| データ | **SQLite** | ファイル1つ、集計クエリ可、両OS共通 |
| 設定/テンプレ | YAML（PyYAML） | Cursorで直接編集できる |

`tools/task_timer/` は **独立 git リポジトリ**（親 my-life-repo の `.gitignore` 対象、`pyproject.toml` の workspace exclude 設定済）。将来GitHub公開可能。

---

## 4. データモデル

3階層：**Project → Phase → Task**。時間ログは task に紐づき、上位に積み上がる。

```
projects(id, name, status, deadline?, planned_hours, planned_money, created_at, updated_at)
phases  (id, project_id→, name, status, order_index, deadline ★必須, planned_hours, ...)
tasks   (id, phase_id→,   name, description?, status, order_index, priority, deadline?, planned_hours, recurrence?, ...)
time_logs(id, task_id→,   started_at, ended_at, duration_sec, note, created_at)
```

- **status**：`active / done / archived`（CHECK制約あり）
- **priority**：`high / normal / low`（taskのみ）
- **deadline**：phase は必須、project と task は任意
- **planned_hours**：Tシャツサイズで入力 → 実際の時間値（0.25=15min, 0.5=30min, 1.0=1h, 2.0=2h, 4.0=4h, 8.0=1日）として保存
- **FK**：ON DELETE CASCADE（プロジェクト削除で連鎖）
- **時刻形式**：すべてISO-8601文字列（TEXT列）

スキーマDDLは `src/task_timer/db/schema.py`。`schema_meta` テーブルでバージョン管理（現在 v3）。

### 「フェーズなし」の小さい案件の扱い

→ **default フェーズ**を自動生成して透過的に扱う。コード分岐ゼロ。

### 固定タスク（雑務・休憩・ルーティン）

→ **特殊プロジェクト**として同じ階層に乗せる。テンプレートで初期投入予定。

---

## 5. UI構成

**2ウィンドウ方式**（実行モードと編集モードを物理分離）：

```
┌─ タイマー画面 380×480 ─┐    ┌─ 管理画面 800×600 ───┐
│ プロジェクト/タスク選択   │    │ ツリー全表示          │
│ ⏱  00:23:15           │ ⇄ │ 追加・編集・並び替え   │
│ [▶][⏹][✕]            │    │ 締切・優先度・見積編集 │
│ 常駐できる小さいウィンドウ │    │ 編集用に広い          │
└──────────────────┘    └──────────────────┘
```

### 編集UIの方針（全部UI上で完結）

| 項目 | UX |
|---|---|
| 優先度 | 行頭アイコン（🔴/🟡/⚪）クリック切替で循環 |
| 締切 | プリセット（今日/明日/今週末/来週月曜） + カレンダー |
| 状態 | 行頭チェックボックス（done ⇄ active） |
| 並び替え | ホバーで `↑↓` ボタン表示（D&Dは見送り、Treeで矢印操作） |
| 追加 | フェーズ末尾の `＋ タスクを追加…` 行 |
| 削除 | 行右端の `⋯` メニュー → 確認ダイアログ |

---

## 6. 主要な判断・採用しなかった選択肢

| 論点 | 採用 | 不採用 |
|---|---|---|
| ストレージ | SQLite | CSV / JSON（集計クエリ弱い） |
| AI分解 | Mac版のみ将来オプション | MVP組込み（Win使えない不公平） |
| 分解UI | テンプレート＋手入力 | AI必須（仕事PC問題） |
| 見積入力 | Tシャツサイズ | 直接分入力（毎回考える疲れ） |
| 集計 | ボトムアップ自動集計 | 手入力のみ |
| ウィンドウ | 2画面 | 1画面（編集と実行の混在で集中切れ） |
| UIフレーム | PySide6 | customtkinter（ツリーUI弱い） |

---

## 7. v0.1（MVP）スコープ

### 入れる ✅

- 2ウィンドウUI（タイマー / 管理）
- Project / Phase / Task の CRUD（全UI操作）
- ストップウォッチ → time_logs に保存
- 優先度（🔴🟡⚪ クリック切替）
- 締切（プリセット＋カレンダー）
- Tシャツ見積もり入力
- ボトムアップ集計表示（フェーズ合計・プロジェクト合計）
- 状態管理（active / done / archived）
- テンプレート機能（YAML読込 / 「これをテンプレに保存」）
- Win / Mac 両対応
- 設定ファイル `config.yaml`（AI機能フラグ含む）

### 入れない（v0.2以降） ❌

- 可視化（グラフ・週次レポート）→ v0.2
- 履歴ベースの見積もり提案 → v0.2
- 凝った予実差分ビュー → v0.2
- AI分解（Mac限定） → v0.3
- ポモドーロ・通知 → v0.4
- CSV/Excelエクスポート → 必要になってから

---

## 8. プロジェクト構造

```
tools/task_timer/
├── .git/                      # 独立リポ
├── .gitignore                 # data/, .venv/, *.db を除外
├── .python-version            # 3.12
├── pyproject.toml             # PySide6 + pyyaml
├── uv.lock                    # ピン留め（コミット）
├── README.md                  # 簡易セットアップ手順
├── DESIGN.md                  # ★この文書
├── data/                      # SQLite置き場（gitignore）
│   └── task_timer.db
├── templates/                 # YAMLテンプレ（未実装）
└── src/task_timer/
    ├── __init__.py            # main を re-export
    ├── __main__.py            # python -m task_timer
    ├── app.py                 # QApplication 起動 + DB初期化
    ├── models.py              # Project/Phase/Task/TimeLog dataclass
    ├── db/
    │   ├── __init__.py        # Database, connect, default_db_path を re-export
    │   ├── schema.py          # DDL
    │   ├── connection.py      # path解決 + 接続初期化（FK ON, WAL）
    │   └── repository.py      # Database クラス（CRUD + 集計 + 中央値）
    └── ui/
        ├── __init__.py
        ├── theme.py           # 色パレット＋共通スタイル文字列（唯一の真実）
        ├── format_helpers.py  # Tシャツ丸め・見積/実績フォーマット・色判定
        ├── timer_window.py    # TimerWindow（小窓・常駐）
        ├── kanban_window.py   # KanbanWindow（ボード本体）
        └── widgets/
            ├── __init__.py    # 公開クラスを re-export
            ├── deadline.py    # WeekendCalendar / DeadlinePicker / DeadlineBadge
            ├── estimate.py    # EstimateBadge（カードからは外したが見積バッジロジックは残置）
            ├── task_card.py   # TaskCard
            ├── phase_column.py # PhaseColumn
            ├── memo.py        # MemoBadge / MemoHistoryDialog
            └── totals_dialog.py # TotalsDialog（累計時間ポップアップ）
```

別配置：
- `~/Applications/TaskTimer.app/` — macOS用 .app bundle（アイコン付き、Spotlightから起動可）

---

## 9. 環境構築・起動コマンド

### Mac

```bash
brew install uv
cd tools/task_timer
uv sync
uv run task-timer
```

### Windows

```powershell
winget install astral-sh.uv
cd tools\task_timer
uv sync
uv run task-timer
```

両OSで `uv.lock` を共有する（リポジトリ経由）から、依存バージョンは完全一致。

---

## 10. 進捗チェックリスト

### v0.1 開発ステップ

- [x] **ステップ1**：プロジェクト土台（pyproject + 空PySide6ウィンドウ）
- [x] **ステップ2**：データモデル + SQLite + CRUD
- [x] **ステップ3**：管理画面（ツリーUI → カンバンボードに刷新）
- [x] **ステップ4**：タイマー画面（ドロップダウン選択 + ストップウォッチ + time_logs保存）
- [x] **ステップ5**：残機能（🔴 3件 + 追加2 D〜H + UX磨き込み一巡）
- [ ] **ステップ6**：両OS動作確認 + README整備

### 動作確認済み（2026-05-05）

- DBファイル自動作成 (`data/task_timer.db`)
- Project / Phase / Task / TimeLog 全CRUD
- タイマー画面：プロジェクト→フェーズ→タスクのドロップダウン連動
- タイマー画面：▶スタート / ⏹ストップ → time_logs保存
- カンバンボード：プロジェクト切替・フェーズ列・タスクカード（チェックで完了）
- カンバンボード：フェーズ追加・タスク追加（Enterキー）・削除
- カンバンボード：タスク名インライン編集（ダブルクリック → Enter/フォーカスアウトで保存）
- カンバンボード：プロジェクト削除（確認ダイアログあり）
- タイマー↔カンバン連携：ストップ時にカンバンが開いていれば自動リロード
- 色テーマ：ダークネイビー上部バー + ライトグレー列 + 白カード

### 既知のバグ

なし（スタートボタン不具合は解消確認済み 2026-05-06）

### テストデータ

`data/task_timer.db` にサンプルプロジェクト・タスクのデータが入っている。
リセット：`rm -f data/task_timer.db data/task_timer.db-wal data/task_timer.db-shm`

---

## 11. 残実装リスト（ステップ5）

優先度順。次回セッションで「〇〇を実装して」と言えばすぐ着手できる。

### 🔴 必須（v0.1完成に必要）→ すべて実装済み ✅

| # | 機能 | 状態 |
|---|---|---|
| 1 | **カンバン↔タイマー連携** | ✅ `_on_stop` でカンバンを `_reload_board` |
| 2 | **プロジェクト削除** | ✅ 上部バーに削除ボタン + 確認ダイアログ |
| 3 | **タスク名インライン編集** | ✅ ダブルクリック → Enter/フォーカスアウトで保存 |

### 🔴 次の実装（2026-05-06 追加）

| # | 機能 | 対象ファイル | 概要 |
|---|---|---|---|
| ~~A~~ | ~~**タイマー画面UI刷新**~~ | ✅ 2026-05-06 完了。フェーズDD廃止・プロジェクト→タスクの2段。タスクはフェーズヘッダー＋色分けで表示 |
| ~~B~~ | ~~**タイマー画面でタスク完了**~~ | ✅ 2026-05-06 完了。「✓ このタスクを完了」ボタン追加。確認ダイアログ→`done`更新→DD除外→カンバン自動リロード。計測中は無効化 |
| ~~C~~ | ~~**締切設定UI**~~ | ✅ 2026-05-06 完了。フェーズヘッダー・タスクカードにDeadlineBadge表示。クリックでDatePickerダイアログ（プリセット4種＋QCalendarWidget）。色分け：期限切れ・今日=赤／3日以内=オレンジ／それ以降=グレー |

### 🔴 次の実装（2026-05-06 追加2）→ すべて実装済み ✅

| # | 機能 | 状態 |
|---|---|---|
| ~~D~~ | ~~**カレンダー曜日色**~~ | ✅ 2026-05-06 完了。DeadlinePicker のカレンダーで土曜=青(#2563eb)、日曜=赤(#dc2626)。`setWeekdayTextFormat` で実装 |
| ~~E~~ | ~~**完了タスクの自動並び替え**~~ | ✅ 2026-05-06 完了。TaskCardに `status_changed` シグナル追加。done になると `order_index` をフェーズ内最大+1にしてリロード |
| ~~F~~ | ~~**タスクの並び替え**~~ | ✅ 2026-05-06 完了。TaskCard に ▲▼ ボタン追加。フェーズ内では `order_index` 入れ替え。境界では `phase_id` を変えて隣のフェーズの末尾/先頭に移す |
| ~~G~~ | ~~**タイマー画面の累計時間表示**~~ | ✅ 2026-05-06 完了。「📊 累計を表示」トグルで `_totals_panel` を開閉。プロジェクト累計・フェーズ累計を `total_seconds_for_*` で集計 |
| ~~H~~ | ~~**累計時間の表示モード切替**~~ | ✅ 2026-05-06 完了。「人工で表示」トグルで `_total_unit_hours` を切替。人工 = sec/3600/8（小数2桁） |

### 🟢 UX磨き込み（2026-05-07 完了）

| # | 機能 | 概要 |
|---|---|---|
| ~~I~~ | ~~**カレンダー先月/翌月の土日色**~~ | ✅ `WeekendCalendar.paintCell` でセル単位に着色（月外もα付き） |
| ~~J~~ | ~~**ドラッグ＆ドロップ並び替え**~~ | ✅ `TaskCard` を QDrag ソース・`PhaseColumn` をドロップターゲット化。フェーズまたぎOK。挿入位置インジケーター付き |
| ~~K~~ | ~~**タイマー累計の常設化＋整理**~~ | ✅ 「累計」トグルで `_totals_panel` 開閉、中に「人工で表示」をネスト。タスク累計も追加（`total_seconds_for_task`） |
| ~~L~~ | ~~**管理画面が前面に出る**~~ | ✅ タイマーの `WindowStaysOnTopHint` 撤去 |
| ~~M~~ | ~~**完了ボタン中央寄せ＋管理/累計を薄く小さく**~~ | ✅ `_BTN_DONE_STYLE` / `_BTN_SUBTLE_STYLE`。完了は確認なし即実行（次タスクへ自動遷移） |
| ~~N~~ | ~~**タスク名フォントの自動縮小**~~ | ✅ `_adjust_name_font` で 13→9pt の範囲で `QFontMetrics` を使い縮小 |
| ~~O~~ | ~~**フェーズ列の薄い色分け**~~ | ✅ `PHASE_COL_BGS` 6色を `index % 6` で循環。`WA_StyledBackground` で塗りを有効化 |
| ~~P~~ | ~~**タスク分解（手動）**~~ | ✅ 右クリック → 「分解…」 → 改行区切り入力 → 元タスクの位置に複数挿入し元タスクは削除 |
| ~~Q~~ | ~~**フォーカス復帰時の再読込**~~ | ✅ `event(WindowActivate)` で選択を保ったままDB再取得（計測中はスキップ） |
| ~~R~~ | ~~**フェーズ内ソート（未完了を上）**~~ | ✅ `_reload_board` と `_on_task_dropped` で `(status==done, order_index, id)` でソート |

### 🟡 v0.1+（2026-05-07 実装）

| # | 機能 | 状態 |
|---|---|---|
| ~~4~~ | ~~**フェーズ名編集**~~ | ✅ ヘッダー（QLineEdit化）をダブルクリック → 青枠で編集 → Enter/フォーカスアウトで保存 |
| 6 | ~~**優先度表示**~~ | ⛔ 見送り（シンプルさ優先 / 2026-05-07判断） |
| ~~7~~ | ~~**ボトムアップ集計**~~ | ✅ フェーズヘッダーにタイトル右へ `done/total` を薄字小さく。`_hide_done` でも全体カウント |
| ~~8~~ | ~~**完了タスクの折りたたみ**~~ | ✅ トップバー右端 `完了を隠す` QCheckBox。ON で `_reload_board` がdoneを除外 |

### 🔵 自動見積もり MVP（2026-05-08）

| # | 機能 | 概要 |
|---|---|---|
| ~~Y~~ | ~~**median自動見積もり**~~ | ✅ `Database.median_actual_seconds_for_project` 追加。タスク作成時に同プロジェクト完了タスクの実績中央値→Tシャツ丸めで `planned_hours` を自動セット。0件のときはNone |
| ~~Z~~ | ~~**EstimateBadge**~~ | ✅ 未完了は `~1h`（薄字）、完了は `1h → 1h32m`（早い=GREEN／近い=MUTED／遅い=ORANGE）。タイマー画面のタイマー下にも `見積 ~1h` |

### 🧹 リファクタリング（2026-05-08）

| 内容 | 概要 |
|---|---|
| 死コード削除 | `ui/manager_window.py`（旧Tree UI、未参照）と `services/` を削除 |
| `theme.py` 新設 | 色（5色＋背景）と共通スタイル（BTN_STYLE / BTN_DANGER / BTN_START_STYLE / BTN_STOP_STYLE / LINK_STYLE）を集約 |
| `format_helpers.py` 新設 | Tシャツ丸め・fmt_planned/fmt_actual・estimate_color を独立モジュール化 |
| `widgets/` 分割 | deadline / estimate / task_card / phase_column の4ファイルに分離 |
| `kanban_window.py` 圧縮 | 1089行 → 318行（KanbanWindowクラスのみ） |
| `timer_window.py` 整理 | ローカル色定数・ボタンスタイルを撤廃して `theme` と `format_helpers` から import |
| 機能 | **完全保持**（見た目・挙動の差分ゼロ） |

### 🟢 タイマー画面UI簡素化（2026-05-07）

| # | 機能 | 概要 |
|---|---|---|
| ~~S~~ | ~~**スタート/ストップ統合**~~ | ✅ `_btn_play` 1ボタン化。ラベル `▶ スタート`⇄`⏹ ストップ`、色 BLUE⇄RED |
| ~~T~~ | ~~**状態ラベル削除**~~ | ✅ `_lbl_status` 撤去。タイマー文字色（停止=MUTED / 計測中=GREEN）で表現 |
| ~~U~~ | ~~**完了をテキストリンク化**~~ | ✅ 枠付き`✓ 完了` → 薄字 `✓ このタスクを完了` （`_LINK_STYLE`） |
| ~~V~~ | ~~**下段リンクをドット区切りに**~~ | ✅ `管理画面 · 累計` を中央寄せフラットボタン＋ `·` QLabel |
| ~~W~~ | ~~**保存/完了フィードバックをタイマー位置で**~~ | ✅ ストップ後 `✓ 1h23m` を1.8秒、完了後 `✓ 完了` を1.2秒だけGREENで上書き → 自動でグレーに戻る |
| ~~X~~ | ~~**色パレットを5色に統一**~~ | ✅ TEXT/MUTED/BLUE/RED/GREEN のみ。kanban側の `ACCENT/DANGER` と整合 |

### 📝 メモ機能（2026-05-09）

| # | 機能 | 概要 |
|---|---|---|
| ~~AA~~ | ~~**ストップ時のメモ入力**~~ | ✅ ⏹後に `_memo_edit` を表示。Enterで `time_logs.note` に保存、Escでスキップ。次の▶でも残ってたら自動で閉じる |
| ~~AB~~ | ~~**メモ件数バッジ**~~ | ✅ TaskCardに `📝N`（noteあり件数）。0件なら非表示。クリックで履歴ダイアログ |
| ~~AC~~ | ~~**メモ履歴ダイアログ**~~ | ✅ 日時・作業時間・本文を縦に並べる。新しい順 |
| Repo | `update_time_log` / `list_notes_for_task` / `count_notes_for_task` 追加 |

### 🔁 ルーティンフェーズ（2026-05-09）— 体験は「いまいち」のため再考予定

| # | 機能 | 概要 |
|---|---|---|
| ~~BA~~ | ~~**スキーマ拡張**~~ | ✅ `phases.is_routine` ＋ `tasks.recurrence` (`daily`/`weekly`/NULL)。既存DBはALTERで自動マイグレーション。SCHEMA_VERSION 2 |
| ~~BB~~ | ~~**フェーズ追加ダイアログ**~~ | ✅ `_PhaseAddDialog`：名前 + ルーティンチェック。チェックONなら `is_routine=True` |
| ~~BC~~ | ~~**🔁バッジ**~~ | ✅ PhaseColumnヘッダーに🔁、TaskCardの名前左にも🔁（recurrence設定済み時） |
| ~~BD~~ | ~~**右クリックで繰り返し変更**~~ | ✅ ルーティンフェーズ内のみ「繰り返し ▸ なし／毎日／毎週」サブメニュー |
| ~~BE~~ | ~~**✓でクローン作成**~~ | ✅ `Database.complete_task` 共通化：done時にrecurrence設定済みなら同位置にactiveクローン作成、締切は+1日/+7日。タイマー画面の「✓ 完了」でも同じ |

### 🛠 デフォルト「汎用」プロジェクト＋スケジューリング自動計測（2026-05-09）

| # | 機能 | 概要 |
|---|---|---|
| ~~CA~~ | ~~**自動セットアップ**~~ | ✅ `Database.init_default_setup`：起動時に「汎用」プロジェクト＋「ルーティン」(is_routine)＋「スポット」フェーズ＋「スケジューリング」タスク (recurrence=None) を生成。既存ならスキップ。`system_ids` dict に各IDをキャッシュ |
| ~~CB~~ | ~~**スケジューリング時間記録**~~ | ✅ `KanbanWindow.__init__` で `_opened_at` を保存、`closeEvent` で経過時間を `time_logs` に保存（5秒未満は無視） |
| ~~CC~~ | ~~**システムエンティティ保護**~~ | ✅ `is_system_project` / `is_system_phase` / `is_system_task` で判定。汎用プロジェクトの「削除」ボタンは disable、ルーティン/スポット/スケジューリングの×ボタンは非表示、TaskCardの右クリック「分解」「削除」もシステム時はskip |

### 🎨 タイマー画面 UI 仕上げ（2026-05-09）

| # | 機能 | 概要 |
|---|---|---|
| ~~DA~~ | ~~**サイズ可変＋デフォは最小**~~ | ✅ `setFixedWidth` 撤去、`setMinimumWidth/Height` のみ。デフォ `resize(280,360)` |
| ~~DB~~ | ~~**タイマー文字 40pt**~~ | ✅ 48pt → 40pt に縮小 |
| ~~DC~~ | ~~**スタート/ストップを文字のみ**~~ | ✅ 背景なし・MUTED色で他のテキストと統一。fixed 180×34クリック領域は維持 |
| ~~DD~~ | ~~**集中モード**~~ | ✅ ▶押すと：上部DDs↔タスク名を `QStackedWidget` で同位置に切替。見積／完了リンク／下段は `QGraphicsOpacityEffect(0)` で見えないが場所は確保 → タスク名・タイマー・ストップ位置が固定 |
| ~~DE~~ | ~~**累計をポップアップ化**~~ | ✅ 旧 inline `_totals_panel` 撤去。`TotalsDialog` で タスク/フェーズ/プロジェクト × 時間/人工 の表 |
| ~~DF~~ | ~~**管理画面は現プロジェクトで開く**~~ | ✅ `KanbanWindow(initial_project_id=...)` を `_open_manager` から渡す |
| ~~DG~~ | ~~**締切バッジを「〆 」に縮小**~~ | ✅ 「+ 締切」→「〆 +」、日付には全部「〆 」prefix。font-size 11 → 10px |
| ~~DH~~ | ~~**カードからEstimateBadge撤去**~~ | ✅ 窮屈解消（時間情報はタイマー画面/累計で見る） |

### 📦 配布

- macOS用 .app bundle 自作（`~/Applications/TaskTimer.app/`）
- アイコン：`/Users/sahiyo/Downloads/icon.png` を `iconutil` で .icns 化、Resources/AppIcon.icns
- 起動：Spotlightで「TaskTimer」と打ってEnter／Dockに常駐可

### ⚪ v0.2以降

| # | 機能 | 概要 |
|---|---|---|
| 9 | テンプレート機能 | YAMLでプロジェクト雛形を読み込み |
| 10 | 週次レポート | time_logsを集計してプロジェクト別時間を表示 |
| 11 | Windows動作確認 | uv sync + 起動テスト |
| 12 | ルーティン体験の再設計 | 別画面に切り出す／「今日のルーティン」だけまとめるビュー／クローン方式の見直し |

---

## 12. 開発を再開するときの読み順

1. このDESIGN.md（まず残実装リストを確認）
2. `src/task_timer/ui/kanban_window.py`
3. `src/task_timer/ui/timer_window.py`
4. `src/task_timer/db/repository.py`（使えるCRUD一覧）
