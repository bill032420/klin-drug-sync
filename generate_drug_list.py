
import pandas as pd

# 讀取原始 TFDA CSV
df = pd.read_csv("台灣藥品許可證資料表.csv", encoding="utf-8-sig", low_memory=False)

# 篩選未註銷藥品
df_valid = df[df["註銷狀態"] != "已註銷"]

# 篩選必要欄位
df_clean = df_valid[["中文品名", "主成分略述"]].dropna()

# 去除重複與空白
df_clean = df_clean.drop_duplicates()
df_clean = df_clean[df_clean["中文品名"].str.strip() != ""]
df_clean = df_clean[df_clean["主成分略述"].str.strip() != ""]

# 儲存為 drug_list.csv
df_clean.to_csv("drug_list.csv", index=False, encoding="utf-8-sig")

print("✅ 已成功產出 drug_list.csv，共計：", len(df_clean), "筆有效藥品")
