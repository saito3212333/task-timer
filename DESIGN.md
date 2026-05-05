# task-timer 設計メモ

このドキュメントは、これまでのClaudeとの設計議論で確定した内容をまとめたもの。
**次回セッションで Claude が読めば、要件定義からやり直さずに開発を再開できる**ことを目的とする。

最終更新：2026-05-05（カンバンボード実装完了）

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
tasks   (id, phase_id→,   name, status, order_index, priority, deadline?, planned_hours, ...)
time_logs(id, task_id→,   started_at, ended_at, duration_sec, note, created_at)
```

- **status**：`active / done / archived`（CHECK制約あり）
- **priority**：`high / normal / low`（taskのみ）
- **deadline**：phase は必須、project と task は任意
- **planned_hours**：Tシャツサイズで入力 → 実際の時間値（0.25=15min, 0.5=30min, 1.0=1h, 2.0=2h, 4.0=4h, 8.0=1日）として保存
- **FK**：ON DELETE CASCADE（プロジェクト削除で連鎖）
- **時刻形式**：すべてISO-8601文字列（TEXT列）

スキーマDDLは `src/task_timer/db/schema.py`。`schema_meta` テーブルでバージョン管理（現在 v1）。

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
    │   └── repository.py      # Database クラス（CRUD + load_project_tree）
    ├── ui/
    │   ├── __init__.py
    │   ├── (timer_window.py)  # 未実装
    │   ├── (manager_window.py)# 未実装
    │   └── widgets/
    │       └── __init__.py
    └── services/
        └── __init__.py        # 未実装
```

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
- [ ] **ステップ5**：残機能（後述）
- [ ] **ステップ6**：両OS動作確認 + README整備

### 動作確認済み（2026-05-05）

- DBファイル自動作成 (`data/task_timer.db`)
- Project / Phase / Task / TimeLog 全CRUD
- タイマー画面：プロジェクト→フェーズ→タスクのドロップダウン連動
- タイマー画面：▶スタート / ⏹ストップ → time_logs保存
- カンバンボード：プロジェクト切替・フェーズ列・タスクカード（チェックで完了）
- カンバンボード：フェーズ追加・タスク追加（Enterキー）・削除
- 色テーマ：ダークネイビー上部バー + ライトグレー列 + 白カード

### テストデータ

`data/task_timer.db` に「PEARLサイト リダイレクト」プロジェクトのデータが入っている。
リセット：`rm -f data/task_timer.db data/task_timer.db-wal data/task_timer.db-shm`

---

## 11. 残実装リスト（ステップ5）

優先度順。次回セッションで「〇〇を実装して」と言えばすぐ着手できる。

### 🔴 必須（v0.1完成に必要）

| # | 機能 | 対象ファイル | 概要 |
|---|---|---|---|
| 1 | **カンバン↔タイマー連携** | timer_window.py | タイマー停止後にカンバンのチェック状態を自動更新 |
| 2 | **プロジェクト削除** | kanban_window.py | 上部バーにプロジェクト削除ボタン（確認ダイアログあり） |
| 3 | **タスク名インライン編集** | kanban_window.py | カード上でダブルクリック → QLineEditに切替 → Enterで保存 |

### 🟡 あると嬉しい（v0.1+）

| # | 機能 | 対象ファイル | 概要 |
|---|---|---|---|
| 4 | **フェーズ名編集** | kanban_window.py | ヘッダーをダブルクリックで名前変更 |
| 5 | **タスク並び替え** | kanban_window.py | ↑↓ボタン or ドラッグ（↑↓ボタンのほうが実装簡単） |
| 6 | **優先度表示** | kanban_window.py | カードに🔴🟡⚪ アイコン。クリックで循環 |
| 7 | **ボトムアップ集計** | kanban_window.py | フェーズヘッダーに「完了n/全n件」バッジ表示 |
| 8 | **完了タスクの折りたたみ** | kanban_window.py | 「完了済みを隠す」トグルボタン |

### ⚪ v0.2以降

| # | 機能 | 概要 |
|---|---|---|
| 9 | テンプレート機能 | YAMLでプロジェクト雛形を読み込み |
| 10 | 週次レポート | time_logsを集計してプロジェクト別時間を表示 |
| 11 | Windows動作確認 | uv sync + 起動テスト |

---

## 12. 開発を再開するときの読み順

1. このDESIGN.md（まず残実装リストを確認）
2. `src/task_timer/ui/kanban_window.py`
3. `src/task_timer/ui/timer_window.py`
4. `src/task_timer/db/repository.py`（使えるCRUD一覧）
