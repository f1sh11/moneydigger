import json

STANDARD_TIERS = {
    "崭新出厂": (0.00, 0.07),
    "略有磨损": (0.07, 0.15),
    "久经沙场": (0.15, 0.38),
    "破损不堪": (0.38, 0.45),
    "战痕累累": (0.45, 1.00)
}

def compute_covered_tiers(min_f, max_f, card_ranges):
    covered = {}
    for tier, (low, high) in card_ranges.items():
        # 判断 float 区间是否有交集
        if high < min_f or low > max_f:
            continue
        # 取交集部分作为覆盖范围
        cover_min = max(low, min_f)
        cover_max = min(high, max_f)
        covered[tier] = [round(cover_min, 6), round(cover_max, 6)]
    return covered

def process_json(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for case in data:
        for skin in case.get("skins", []):
            min_f = skin.get("min_float", 0)
            max_f = skin.get("max_float", 1)
            card_ranges = skin.get("card_float_ranges", {})
            covered = compute_covered_tiers(min_f, max_f, card_ranges)
            skin["covered_tiers"] = covered

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# 示例调用
process_json(
    input_path="converted_cases_with_card_ranges_strict.json",
    output_path="converted_cases_with_covered_tiers.json"
)
