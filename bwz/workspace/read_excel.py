import pandas as pd

print("Starting...")
try:
    df = pd.read_excel('uploads/xlsx-e2337157c59f')
    print(f"列名: {list(df.columns)}")
    print(f"数据行数: {df.shape[0]}")
    print("\n=== 全部数据 ===")
    print(df.to_string(index=False))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
