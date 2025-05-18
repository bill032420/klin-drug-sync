import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
import requests
from tqdm import tqdm
import os
import json

# 初始化 Firebase Admin
cred = credentials.Certificate("credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 檢查是否有斷點記錄
checkpoint_file = "upload_checkpoint.txt"
start_index = 0
if os.path.exists(checkpoint_file):
    with open(checkpoint_file, "r") as f:
        try:
            start_index = int(f.read().strip())
        except:
            start_index = 0

# 讀取 CSV 並排除已註銷藥品
csv_path = "台灣藥品許可證資料表.csv"
df = pd.read_csv(csv_path)
df_active = df[df['註銷狀態'].isna()].reset_index(drop=True)
df_active = df_active[['中文品名', '英文品名', '主成分略述', '許可證字號']]

# 查詢 openFDA API
def query_openfda(ingredient_or_name):
    base_url = "https://api.fda.gov/drug/label.json"
    params = {
        "search": f"openfda.generic_name:{ingredient_or_name}",
        "limit": 1
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("results", [{}])[0]
    except:
        pass
    return {}

# 開始逐筆上傳
for i in tqdm(range(start_index, len(df_active))):
    row = df_active.iloc[i]
    license_id = str(row["許可證字號"])
    ingredient = str(row["主成分略述"])
    english_name = str(row["英文品名"])
    drug_name = ingredient if pd.notna(ingredient) and ingredient.strip() else english_name
    fda_data = query_openfda(drug_name)

    doc_data = {
        "license_id": license_id,
        "chinese_name": str(row["中文品名"]),
        "english_name": english_name,
        "ingredient": ingredient,
        "openfda": fda_data,
        "uploaded_at": SERVER_TIMESTAMP
    }

    try:
        db.collection("drug_database").document(license_id).set(doc_data)
    except Exception as e:
        print(f"❌ 第 {i} 筆資料上傳失敗：{e}")
        continue

    # 寫入斷點記錄
    with open(checkpoint_file, "w") as f:
        f.write(str(i + 1))

    # 每上傳 500 筆顯示一次
    if i % 500 == 0 and i > 0:
        print(f"✅ 已完成 {i} 筆資料上傳")

print("🎉 所有藥品資料已完成上傳！")
