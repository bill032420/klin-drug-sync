
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from tqdm import tqdm
import json
import time
import os

# 初始化 Firebase
cred = credentials.Certificate("klin-76045-firebase-adminsdk-fbsvc-93aeb1d0ba.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 設定檔案路徑
csv_path = "台灣藥品許可證資料表.csv"
checkpoint_path = "upload_checkpoint.json"
error_log_path = "upload_errors.json"

# 設定批次控制
BATCH_SIZE = 100
SLEEP_SECONDS = 3

# 讀取 CSV 並篩選未註銷
df = pd.read_csv(csv_path)
df_active = df[df['註銷狀態'].isna()].reset_index(drop=True)
df_active = df_active[['中文品名', '英文品名', '主成分略述', '許可證字號']]

# checkpoint: 從哪一筆開始
start_index = 0
if os.path.exists(checkpoint_path):
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        start_index = json.load(f).get("last_index", 0)

# openFDA 查詢
def query_openfda(ingredient_or_name):
    base_url = "https://api.fda.gov/drug/label.json"
    params = {
        "search": f"openfda.generic_name:\"{ingredient_or_name}\"",
        "limit": 1
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("results", [{}])[0]
    except Exception as e:
        return {"error": str(e)}
    return {}

# 初始化錯誤紀錄
error_log = []

# 上傳至 Firestore
for i in tqdm(range(start_index, len(df_active))):
    row = df_active.iloc[i]
    license_id = str(row["許可證字號"])
    try:
        fda_data = query_openfda(row["主成分略述"] or row["英文品名"])
        doc_data = {
            "license_id": license_id,
            "chinese_name": str(row["中文品名"]),
            "english_name": str(row["英文品名"]),
            "ingredient": str(row["主成分略述"]),
            "openfda": fda_data
        }
        db.collection("drug_database").document(license_id).set(doc_data)

        # 更新 checkpoint
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump({"last_index": i + 1}, f, ensure_ascii=False)

        # 間歇休息
        if i > 0 and i % BATCH_SIZE == 0:
            print(f"✅ 已完成 {i} 筆，暫停 {SLEEP_SECONDS} 秒")
            time.sleep(SLEEP_SECONDS)

    except Exception as e:
        error_entry = {
            "index": i,
            "license_id": license_id,
            "error": str(e)
        }
        error_log.append(error_entry)
        print(f"❌ 錯誤於第 {i} 筆：{e}")

# 儲存錯誤紀錄
if error_log:
    with open(error_log_path, "w", encoding="utf-8") as f:
        json.dump(error_log, f, ensure_ascii=False, indent=2)

print("🎉 上傳完成，請確認錯誤紀錄與 checkpoint 狀態")
