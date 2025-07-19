import json

# 输入输出路径
input_file = "converted_cases_merged_final.json"
output_file = "converted_cases_merged_no_commem.json"

# 读取原文件
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# 删除包含“纪念包”的箱子
filtered = [case for case in data if "纪念包" not in case.get("case_name", "")]

# 保存新文件
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

print(f"✅ 原始数量: {len(data)}")
print(f"🧹 删除纪念包后数量: {len(filtered)}")
print(f"📁 已保存到: {output_file}")
