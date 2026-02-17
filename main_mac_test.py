# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "customtkinter",
#     "pyyaml"
# ]
# ///

# ---------------------------------------------------------
# 【一輝専用 予実管理＆タスク集中システム（Macテスト版）】
# ---------------------------------------------------------

import customtkinter as ctk
import yaml
import csv
import re
import time
import os
from datetime import datetime

class TaskTimerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. 設定の読み込みと画面の初期化
        self.config = self.load_config()
        self.setup_window()

        # 2. 状態を管理する変数（タイマー用）
        self.is_running = False
        self.start_timestamp = 0.0
        self.elapsed_time = 0.0

        # 3. プロジェクトとタスクのデータを格納する辞書（目次のようなもの）
        self.project_data = {}

        # 4. データの読み込みと画面作り
        self.load_dummy_outlook()
        self.build_ui()

    # ==========================================
    # 設定・データ読み込み関連
    # ==========================================
    def load_config(self):
        """config.yaml を読み込みます"""
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def setup_window(self):
        """ウィンドウのサイズや色を設定します"""
        cfg = self.config["window"]
        self.title(cfg["title"])
        self.geometry(f"{cfg['width']}x{cfg['height']}")
        if cfg.get("always_on_top"):
            self.attributes("-topmost", True)
        ctk.set_appearance_mode(cfg.get("appearance_mode", "dark"))
        ctk.set_default_color_theme(cfg.get("color_theme", "blue"))

    def load_dummy_outlook(self):
        """アウトルックの代わりにダミーCSVを読み込み、データを整理します"""
        # 固定タスクを先に追加（重要度より優先して上に表示させるため）
        for fixed in self.config.get("fixed_tasks", []):
            self.project_data[fixed] = {
                "tasks": ["（固定タスクのため選択不要）"],
                "planned_time": "",
                "planned_money": ""
            }

        # ダミーCSVの読み込み
        try:
            with open("dummy_outlook.csv", "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # 重要度で並び替えるためのルール（高=0, 通常=1, 低=2）
                priority_map = {"高": 0, "通常": 1, "低": 2}
                rows.sort(key=lambda x: priority_map.get(x["重要度"], 99))

                for row in rows:
                    subject = row["件名"]
                    body = row["本文"]

                    # ① 件名から「時間」と「金額」を自動分解する魔法（正規表現）
                    pattern = r'\[(\d+)\]\s*\[(\d+)\]'
                    match = re.search(pattern, subject)

                    if match:
                        p_time = match.group(1)
                        p_money = match.group(2)
                        # カッコの部分を消して、純粋なプロジェクト名だけを取り出す
                        proj_name = re.sub(pattern, '', subject).strip()
                    else:
                        p_time, p_money, proj_name = "", "", subject.strip()

                    # ② 本文（サブタスク）の分解と、終わったタスク（末尾9）の除外
                    task_lines = body.splitlines()
                    active_tasks = []
                    for line in task_lines:
                        clean_line = line.strip()
                        if clean_line == "": continue # 空行は無視
                        if clean_line.endswith("9"): continue # 終わったタスク(9)は無視
                        active_tasks.append(clean_line)

                    # 直近2件だけを抽出！
                    next_actions = active_tasks[:2]
                    if not next_actions:
                        next_actions = ["（次にやるべきタスクがありません）"]

                    # データを辞書に保存
                    self.project_data[proj_name] = {
                        "tasks": next_actions,
                        "planned_time": p_time,
                        "planned_money": p_money
                    }

        except Exception as e:
            print(f"ダミーデータの読み込みエラー: {e}")

    # ==========================================
    # 画面（UI）の組み立て
    # ==========================================
    def build_ui(self):
        """画面にパーツを配置します"""
        # --- 1段目：プロジェクト選択 ---
        ctk.CTkLabel(self, text="1. プロジェクトを選択", font=("Helvetica", 12)).pack(pady=(15, 0))
        project_list = list(self.project_data.keys())

        self.proj_dropdown = ctk.CTkOptionMenu(
            self, values=project_list, command=self.on_project_select
        )
        self.proj_dropdown.pack(padx=20, pady=5, fill="x")

        # --- 2段目：サブタスク選択 ---
        ctk.CTkLabel(self, text="2. 直近のタスク（次やるべき2件）", font=("Helvetica", 12)).pack(pady=(15, 0))
        self.task_dropdown = ctk.CTkOptionMenu(self, values=["（プロジェクトを選んでください）"])
        self.task_dropdown.pack(padx=20, pady=5, fill="x")

        # 初期状態のタスクリストをセット
        if project_list:
            self.on_project_select(project_list[0])

        # --- 3段目：ストップウォッチ ---
        self.lbl_time = ctk.CTkLabel(self, text="00:00:00", font=("Helvetica", 48, "bold"))
        self.lbl_time.pack(pady=30)

        # --- 4段目：ボタン群 ---
        frame_buttons = ctk.CTkFrame(self, fg_color="transparent")
        frame_buttons.pack(pady=10)

        ctk.CTkButton(frame_buttons, text="▶ 開始", fg_color="#4CAF50", hover_color="#45a049",
                      width=90, command=self.start_timer).grid(row=0, column=0, padx=5)
        ctk.CTkButton(frame_buttons, text="⏹ 終了(保存)", fg_color="#f44336", hover_color="#da190b",
                      width=90, command=self.stop_and_save).grid(row=0, column=1, padx=5)
        ctk.CTkButton(frame_buttons, text="↩ キャンセル", fg_color="gray", hover_color="#555555",
                      width=90, command=self.reset_timer).grid(row=0, column=2, padx=5)

    # ==========================================
    # 操作と動き（アクション）
    # ==========================================
    def on_project_select(self, selected_proj):
        """プロジェクトが選ばれたら、下のタスク一覧を更新します"""
        tasks = self.project_data[selected_proj]["tasks"]
        self.task_dropdown.configure(values=tasks)
        self.task_dropdown.set(tasks[0]) # 一番上のタスクを自動選択

    def update_time(self):
        """ストップウォッチの時間を0.1秒ごとに画面に描画します"""
        if self.is_running:
            current_elapsed = self.elapsed_time + (time.time() - self.start_timestamp)
            m, s = divmod(int(current_elapsed), 60)
            h, m = divmod(m, 60)
            self.lbl_time.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.after(100, self.update_time)

    def start_timer(self):
        """計測スタート"""
        if not self.is_running:
            self.is_running = True
            self.start_timestamp = time.time()
            self.start_datetime = datetime.now() # 開始した「時刻」も覚えておく
            self.update_time()

    def reset_timer(self):
        """計測をキャンセルしてリセット（CSVには保存しない）"""
        self.is_running = False
        self.elapsed_time = 0.0
        self.lbl_time.configure(text="00:00:00")

    def stop_and_save(self):
        """計測を止めて、結果をCSVに書き出します"""
        if not self.is_running and self.elapsed_time == 0:
            return # 動いていない時は何もしない

        self.is_running = False
        # 最終的な経過時間を確定させる
        self.elapsed_time += (time.time() - self.start_timestamp)
        end_datetime = datetime.now()

        # 画面に表示されている「HH:MM:SS」を取得
        duration_str = self.lbl_time.cget("text")

        # 選ばれているプロジェクトとタスクを取得
        proj_name = self.proj_dropdown.get()
        task_name = self.task_dropdown.get()

        # 予定時間と金額を取得
        p_time = self.project_data[proj_name]["planned_time"]
        p_money = self.project_data[proj_name]["planned_money"]

        # CSVに書き込む1行のデータを作成
        log_data = [
            self.start_datetime.strftime("%Y/%m/%d"), # 日付
            self.start_datetime.strftime("%H:%M:%S"), # 開始時刻
            end_datetime.strftime("%H:%M:%S"),        # 終了時刻
            duration_str,                             # 所要時間
            proj_name,                                # プロジェクト名
            task_name,                                # サブタスク名
            p_time,                                   # 予定時間
            p_money                                   # 予定金額
        ]

        # time_log.csv に追記モード('a')で保存
        file_exists = os.path.isfile("time_log.csv")
        with open("time_log.csv", "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            # ファイルが新しく作られた時だけ、一番上にヘッダー（見出し）を書く
            if not file_exists:
                writer.writerow(["日付", "開始時刻", "終了時刻", "所要時間", "プロジェクト名", "サブタスク名", "予定時間", "予定金額"])
            writer.writerow(log_data)

        print(f"記録を保存しました！: {proj_name} - {task_name} ({duration_str})")

        # 保存が終わったらタイマーをリセット
        self.reset_timer()

# ==========================================
# 起動コマンド
# ==========================================
if __name__ == "__main__":
    app = TaskTimerApp()
    app.mainloop()