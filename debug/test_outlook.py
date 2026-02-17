# /// script
# requires-python = ">=3.10"
# dependencies = ["pywin32"]
# ///

import win32com.client

def test_outlook_connection():
    print("アウトルックに接続してタスクを読み込みます...\n" + "-"*40)
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        task_folder = outlook.GetDefaultFolder(13)

        raw_tasks = []
        for item in task_folder.Items:
            if not item.Complete:
                raw_tasks.append({
                    "subject": item.Subject,
                    "importance": item.Importance
                })

        # 重要度順（2=高, 1=通常, 0=低）に並び替え
        raw_tasks.sort(key=lambda x: x["importance"], reverse=True)

        print(f"合計 {len(raw_tasks)} 件の未完了タスクが見つかりました。\n")
        for t in raw_tasks[:5]: # 最初の5件だけ表示
            priority_mark = "🔴高" if t["importance"]==2 else "🟡通常" if t["importance"]==1 else "🔵低"
            print(f"[{priority_mark}] {t['subject']}")

        print("-" * 40 + "\nテスト成功！アウトルック連携は完璧です。")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}\nアウトルックが起動しているか確認してください。")

if __name__ == "__main__":
    test_outlook_connection()