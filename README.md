# task-timer

仕事（Win）・私生活（Mac）両方で使う、個人用 時間計測 & 集中タイマー。

階層：**Project → Phase → Task** の3階層管理。タイマー計測結果はSQLiteに蓄積される。

## セットアップ

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

## ステータス

v0.1 開発中（MVP）。詳細な設計・進捗は [DESIGN.md](./DESIGN.md) を参照。
