import json

# 原始文件路径
input_file = "converted_cases_merged_updated.json"
# 输出文件路径
output_file = "converted_cases_without_commemoratives.json"

# 加载原始数据
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# 过滤掉包含“纪念包”的条目
filtered_data = [case for case in data if "纪念包" not in case["case_name"]]

# 保存结果
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(filtered_data, f, ensure_ascii=False, indent=2)

print(f"✅ 已删除所有纪念包，共保留 {len(filtered_data)} 个箱子")
