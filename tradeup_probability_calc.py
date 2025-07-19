import json, requests, itertools, time
from collections import Counter, defaultdict
from itertools import combinations, islice
from math import comb
import utils
# from ga_optimizer import run_ga_optimizer
import os

STANDARD_TIERS = {
    "崭新出厂": (0.00, 0.07),
    "略有磨损": (0.07, 0.15),
    "久经沙场": (0.15, 0.38),
    "破损不堪": (0.38, 0.45),
    "战痕累累": (0.45, 1.00),
}

TARGET_TIERS = ["略有磨损", "久经沙场"]
TOLERANCE = 0.02

RARITY_ORDER = ["消费级", "工业级", "军规级", "受限", "保密", "隐秘"]
request_counter = {"count": 0}


ALLOWED_CASES = {"反冲武器箱"} 

def is_combo_matching_target_float(
    avg_float: float,
    valid_outputs: list,
    target_tiers: list,
    tolerance: float = 0.005
) -> tuple[bool, dict | None]:
    """
    判断 avg_float 是否卡入任一输出皮肤的目标磨损等级卡线点（即 tier_max）

    参数:
    - avg_float: 当前组合的平均 float
    - valid_outputs: 可供合出的所有输出皮肤（含 min/max float 和 card_float_ranges）
    - target_tiers: 目标磨损等级（如 ["略有磨损"]）
    - tolerance: 可接受的误差范围（越小越接近卡线）

    返回:
    - (True, 命中的输出皮肤 dict) 如果命中任意卡线点
    - (False, None) 如果没有命中任何卡线
    """

    for s in valid_outputs:
        min_f = s.get("min_float")
        max_f = s.get("max_float")
        ranges = s.get("card_float_ranges", {})

        if not min_f or not max_f or max_f == min_f:
            continue

        for tier in target_tiers:
            if tier not in ranges:
                continue

            tier_min, tier_max = ranges[tier]

            # 反推命中该卡线点所需 avg_float（卡的是 tier_max）
            target_avg = (tier_max - min_f) / (max_f - min_f)

            # 判断是否命中卡线（允许一定容差）
            if 0 <= target_avg <= 1 and abs(avg_float - target_avg) <= tolerance:
                return True, {
                    "output_skin": s["name"],
                    "case": s["case_name"],
                    "tier": tier,
                    "target_avg_float": round(target_avg, 5)
                }

    return False, None

def load_input_pool_by_case():
    data = utils.load_data()
    pool = []

    for case in data:
        if case["case_name"] not in ALLOWED_CASES:
            continue
        for skin in case["skins"]:
            next_rarity = get_next_rarity(skin.get("rarity"))
            if not next_rarity or not skin.get("name") or not skin.get("wear_goods_ids"):
                continue

            supports_tiers = skin.get("covered_tiers", [])
            if not any(t in supports_tiers for t in TARGET_TIERS):
                continue

            min_f, max_f = skin.get("min_float", 0), skin.get("max_float", 1)
            if max_f == min_f:
                continue

            for wear, gid in skin["wear_goods_ids"].items():
                if "StatTrak" in wear:
                    continue
                pool.append({
                    "name": skin["name"],
                    "wear": wear,
                    "goods_id": gid,
                    "case_name": case["case_name"],
                    "next_rarity": next_rarity,
                    "min_float": min_f,
                    "max_float": max_f,
                    "covered_tiers": supports_tiers
                })
    return pool

def run_cardline_mode(target_tier="略有磨损", tolerance=TOLERANCE):
    import os

    with open("buff_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    cookies = {c['name']: c['value'] for c in state['cookies'] if 'buff.163.com' in c['domain']}

    pool = []
    target_float = STANDARD_TIERS[target_tier][1]
    for item in load_input_pool_by_case():
        min_f, max_f = item["min_float"], item["max_float"]
        if min_f <= target_float <= max_f:
            item["float"] = target_float
            pool.append(item)

    print(f"🧩 输入池皮肤数量: {len(pool)}")

    data = utils.load_data()
    utils.preload_prices(pool, data, cookies)

    print(f"🎯 将使用所有支持 [{target_tier}] 的输出皮肤进行卡线匹配")

    rarity_groups = defaultdict(list)
    for item in pool:
        if target_tier not in item.get("covered_tiers", []):
            continue
        rarity_groups[item["next_rarity"]].append(item)

    # ✅ Step: 缓存每个稀有度对应的输出皮肤
    rarity_to_valid_outputs = {}
    for rarity, group in rarity_groups.items():
        group_outputs = find_possible_outputs(group, data)
        valid_outputs = [s for s in group_outputs if s.get("card_float_ranges")]
        rarity_to_valid_outputs[rarity] = valid_outputs

    total_combos = 0
    results = []
    start = time.time()

    for rarity, group in rarity_groups.items():
        valid_outputs = rarity_to_valid_outputs.get(rarity, [])
        if not valid_outputs:
            print(f"❌ 稀有度 [{rarity}] 没有可用输出皮肤，跳过")
            continue

        float_match_cache = {}

        if len(group) < 10:
            continue

        group_combos_count = comb(len(group), 10)
        print(f"\n📦 稀有度 [{rarity}] 有 {len(group)} 件支持 [{target_tier}]，组合数约: {group_combos_count}")
        total_combos += group_combos_count

        combos = combinations(group, 10)
        for idx, combo in enumerate(combos, 1):
            if idx % 200 == 0 or idx == group_combos_count:
                print_progress(idx, group_combos_count)

            try:
                prices = [utils.get_price(i) for i in combo]
                if any(p is None or p <= 0 for p in prices):
                    continue
                total_price = sum(prices)
                avg_float = target_float
            except:
                continue

            reason = should_skip(total_price, valid_outputs)
            if reason:
                continue

            output_price_map = {}
            for s in valid_outputs:
                key = f"{s['name']}|{s['case_name']}"
                price = utils.price_cache.get(key, {}).get(target_tier)
                if price:
                    output_price_map[key] = price

            key = round(avg_float, 5)  # ✅ 优化 key，避免使用 id()
            if key in float_match_cache:
                matched, info = float_match_cache[key]
            else:
                matched, info = is_combo_matching_target_float(avg_float, valid_outputs, [target_tier], tolerance)
                float_match_cache[key] = (matched, info)

            if not matched:
                continue

            expected_value = utils.calc_expected_output_value(valid_outputs, target_tier, output_price_map)
            if expected_value == 0:
                continue

            net = expected_value - total_price

            results.append({
                "组合": [f"{i['name']}({i['wear']})" for i in combo],
                "float": round(avg_float, 6),
                "成本": round(total_price, 2),
                "售价": round(expected_value, 2),
                "净收益": round(net, 2),
                "命中": info
            })

    duration = round(time.time() - start, 2)
    print(f"\n✅ 完成模拟，共组合 {total_combos:,}，耗时 {duration} 秒")

    if not results:
        print("🚫 无任何组合命中该卡线")
        return

    results.sort(key=lambda x: x["净收益"], reverse=True)
    top_n = results[:10]

    for i, combo in enumerate(top_n, 1):
        print(f"\n🏆 Top {i}（卡入 {target_tier}）:")
        for line in combo["组合"]:
            print(f" - {line}")
        print(f"🎯 float: {combo['float']}")
        print(f"💰 成本: ¥{combo['成本']} | 💵 售价: ¥{combo['售价']} | 📈 净收益: ¥{combo['净收益']}")
        print(f"🎯 命中皮肤: {combo['命中']}")

    output_path = f"cardline_results_{target_tier}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(top_n, f, indent=2, ensure_ascii=False)

    print(f"\n📁 已保存前 10 组结果到: {output_path}")


def get_next_rarity(current):
    try:
        return RARITY_ORDER[RARITY_ORDER.index(current) + 1]
    except:
        return None

def calc_float_thresholds(min_f, max_f):
    """
    计算所有磨损压线的平均 float 限制。
    返回字典形式，如 {"崭新出厂": 0.0933, ...}
    """
    thresholds = {}
    for tier, (low, high) in STANDARD_TIERS.items():
        threshold = (high - low) / (max_f - min_f)  # 从公式推反向求 avg_float 上限
        thresholds[tier] = round(threshold, 6)
    return thresholds

def find_possible_outputs(combo, all_data):
    case_counts = defaultdict(int)
    for item in combo:
        case_counts[item["case_name"]] += 1  # 输入中各箱子数量

    target_rarities = set(item["next_rarity"] for item in combo)
    outputs = []

    for case in all_data:
        case_name = case["case_name"]
        if case_name not in case_counts:
            continue

        for skin in case.get("skins", []):
            if skin.get("rarity") not in target_rarities:
                continue
            if not skin.get("name") or not skin.get("wear_goods_ids"):
                continue

            same_rarity_outputs = [
                s for s in case["skins"]
                if s.get("rarity") == skin["rarity"]
                and s.get("wear_goods_ids")
                and s.get("name")
            ]
            if not same_rarity_outputs:
                continue

            prob = case_counts[case_name] / 10.0 * (1.0 / len(same_rarity_outputs))

            outputs.append({
                "name": skin["name"],
                "wear_goods_ids": skin["wear_goods_ids"],
                "case_name": case_name,
                "min_float": skin["min_float"],
                "max_float": skin["max_float"],
                "card_float_ranges": skin.get("card_float_ranges", {}),
                "probability": round(prob, 6)
            })

    return outputs

def load_input_pool(limit):
    data = utils.load_data()
    pool = []
    count = 0
    for case in data:
        for skin in case["skins"]:
            next_rarity = get_next_rarity(skin.get("rarity"))
            if not next_rarity or not skin.get("name") or not skin.get("wear_goods_ids"):
                continue

            entries = []
            for wear, gid in skin["wear_goods_ids"].items():
                if "StatTrak" in wear:
                    continue
                entries.append({
                    "name": skin["name"],
                    "wear": wear,
                    "goods_id": gid,
                    "case_name": case["case_name"],
                    "next_rarity": next_rarity,
                    "float": (skin.get("min_float", 0) + skin.get("max_float", 1)) / 2
                })

            pool.extend(entries)
            count += 1
            if count >= limit:
                return pool
    return pool

def print_progress(current, total):
    bar_len = 30
    filled_len = int(bar_len * current // total)
    bar = '█' * filled_len + '-' * (bar_len - filled_len)
    print(f"\r⏳ 进度 [{bar}] {current}/{total}", end='')

def get_output_max_price(output_skins):
    """
    给定一组输出皮肤，返回它们在所有磨损下的最高售价
    """
    max_price = 0
    for skin in output_skins:
        key = f"{skin['name']}|{skin['case_name']}"
        price_map = utils.price_cache.get(key, {})
        for tier in STANDARD_TIERS:
            price = price_map.get(tier)
            if price and price > max_price:
                max_price = price
    return max_price

def should_skip( total_price, valid_outputs):
    if not valid_outputs:
        return "无输出皮肤"


    output_max_price = get_output_max_price(valid_outputs)
    if total_price > output_max_price:
        return "成本高于最高售价"

def test_price_preload_and_cache():
    with open("buff_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    cookies = {c['name']: c['value'] for c in state['cookies'] if 'buff.163.com' in c['domain']}

    print("✅ 开始测试: 预加载价格并打印缓存内容")
    pool = load_input_pool(limit=5)  # 只取 5 个用于测试
    data = utils.load_data()

    utils.preload_prices(pool, data, cookies)

    print("\n📦 当前 utils.price_cache 内容:")
    for skin, prices in utils.price_cache.items():
        print(f"🧪 {skin}")
        for wear, price in prices.items():
            print(f"  - {wear}: ¥{price}")
    print("\n✅ 测试完成")
    
if __name__ == "__main__":
    # run_mixed_mode()
    run_cardline_mode("略有磨损")
    # run_ga_optimizer("略有磨损")