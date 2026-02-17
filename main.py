# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "customtkinter",
#     "pywin32",
#     "pyyaml"
# ]
# ///

# ---------------------------------------------------------
# 【一輝専用 予実管理＆タスク集中システム（Windows本番版）】
# ---------------------------------------------------------

import customtkinter as ctk
import win32com.client
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

        # 3. プロジェクトとタスクのデータを格納する辞書
        self.project_data = {}

        # 4. アウトルックからのデータ読み込みと画面作り
        self.load_outlook_data()
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

    def load_outlook_data(self):
        """アウトルックからタスクを読み込み、データを整理します"""
        # ① まず、設定ファイルの「固定タスク」を最優先で登録します
        for fixed in self.config.get("fixed_tasks", []):
            self.project_data[fixed] = {
                "tasks": ["（固定タスクのため選択不要）"],
                "planned_time": "",
                "planned_money": ""
            }

        # ② アウトルックに接続してデータを取得します
        try:
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            task_folder = outlook.GetDefaultFolder(13) # 13 = タスクフォルダ
            items = task_folder.Items

            # 完了していないタスクだけをリストに集めます
            raw_tasks = []
            for item in items:
                if not item.Complete:
                    raw_tasks.append({
                        "subject": item.Subject,
                        "body": item.Body if item.Body else "",
                        "importance": item.Importance # 2:高, 1:通常, 0:低
                    })

            # 重要度(Importance)が高い順に並び替えます
            raw_tasks.sort(key=lambda x: x["importance"], reverse=True)

            max_limit = self.config["outlook"].get("max_projects", 20)

            # ③ 読み込んだタスクを1つずつ分解・整理します
            for item in raw_tasks[:max_limit]:
                subject = item["subject"]
                body = item["body"]

                # --- 【件名の分解】時間と金額を抜き出す魔法 ---
                pattern = r'\[(\d+)\]\s*\[(\d+)\]'
                match = re.search(pattern, subject)

                if match:
                    p_time = match.group(1)
                    p_money = match.group(2)
                    proj_name = re.sub(pattern, '', subject).strip()
                else:
                    p_time, p_money, proj_name = "", "", subject.strip()

                # --- 【本文の分解】終わったタスク(9)を除外して直近2件を抽出 ---
                task_lines = body.splitlines()
                active_tasks = []
                for line in task_lines:
                    clean_line = line.strip()
                    if clean_line == "": continue # 空行は無視
                    if clean_line.endswith("9"): continue # 末尾が9（完了）は無視
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
            print(f"アウトルック連携エラー: {e}")
            self.project_data["⚠️ アウトルック連携エラー"] = {
                "tasks": ["アウトルックが起動しているか確認してください"],
                "planned_time": "", "planned_money": ""
            }

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
        tasks = self.project_data[selected_proj]["tasks"]
        self.task_dropdown.configure(values=tasks)
        self.task_dropdown.set(tasks[0])

    def update_time(self):
        if self.is_running:
            current_elapsed = self.elapsed_time + (time.time() - self.start_timestamp)
            m, s = divmod(int(current_elapsed), 60)
            h, m = divmod(m, 60)
            self.lbl_time.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.after(100, self.update_time)

    def start_timer(self):
        if not self.is_running:
            self.is_running = True
            self.start_timestamp = time.time()
            self.start_datetime = datetime.now()
            self.update_time()

    def reset_timer(self):
        self.is_running = False
        self.elapsed_time = 0.0
        self.lbl_time.configure(text="00:00:00")

    def stop_and_save(self):
        if not self.is_running and self.elapsed_time == 0:
            return

        self.is_running = False
        self.elapsed_time += (time.time() - self.start_timestamp)
        end_datetime = datetime.now()

        duration_str = self.lbl_time.cget("text")
        proj_name = self.proj_dropdown.get()
        task_name = self.task_dropdown.get()
        p_time = self.project_data[proj_name]["planned_time"]
        p_money = self.project_data[proj_name]["planned_money"]

        # CSVに書き込むデータ
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

        # time_log.csv に追記保存
        file_exists = os.path.isfile("time_log.csv")
        with open("time_log.csv", "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["日付", "開始時刻", "終了時刻", "所要時間", "プロジェクト名", "サブタスク名", "予定時間", "予定金額"])
            writer.writerow(log_data)

        print(f"記録保存: {proj_name} - {task_name} ({duration_str})")
        self.reset_timer()

if __name__ == "__main__":
    app = TaskTimerApp()
    app.mainloop()