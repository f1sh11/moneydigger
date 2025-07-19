import json, requests, itertools, time
from collections import Counter, defaultdict
from bs4 import BeautifulSoup, NavigableString
from itertools import combinations, islice
from math import comb

STANDARD_TIERS = {
    "崭新出厂": (0.00, 0.07),
    "略有磨损": (0.07, 0.15),
    "久经沙场": (0.15, 0.38),
    "破损不堪": (0.38, 0.45),
    "战痕累累": (0.45, 1.00),
}

RARITY_ORDER = ["消费级", "工业级", "军规级", "受限", "保密", "隐秘"]
price_cache = {}
request_counter = {"count": 0}
loaded_goods_ids = set()

ALLOWED_CASES = {"反冲武器箱"} 

def get_float_tier(value):
    for tier, (min_f, max_f) in STANDARD_TIERS.items():
        if min_f <= value < max_f:
            return tier
    return None

def load_input_pool_by_case():
    data = load_data()
    pool = []
    for case in data:
        if case["case_name"] not in ALLOWED_CASES:
            continue
        for skin in case["skins"]:
            next_rarity = get_next_rarity(skin.get("rarity"))
            if not next_rarity or not skin.get("name") or not skin.get("wear_goods_ids"):
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
                    "float": (skin.get("min_float", 0) + skin.get("max_float", 1)) / 2
                })
    return pool

def load_data(path="converted_cases_with_card_ranges_strict.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_next_rarity(current):
    try:
        return RARITY_ORDER[RARITY_ORDER.index(current) + 1]
    except:
        return None

def fetch_wear_prices(goods_id, cookies):
    if goods_id in loaded_goods_ids:
        print(f"🛑 跳过重复 goods_id: {goods_id}")
        return

    loaded_goods_ids.add(goods_id)
    url = f"https://buff.163.com/goods/{goods_id}?from=market"
    print(f"🔍【fetch_wear_prices】开始请求: {url}")
    request_counter["count"] += 1
    print(f"📥 当前请求总数: {request_counter['count']}")

    headers = {"User-Agent": "Mozilla/5.0"}
    while True:
        time.sleep(1)
        try:
            res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html5lib")
                count = 0
                for btn in soup.select("div.scope-btns a"):
                    price_tag = btn.select_one("span.custom-currency")
                    if price_tag and price_tag.has_attr("data-price"):
                        price = float(price_tag["data-price"])
                        for child in btn.children:
                            if isinstance(child, NavigableString) and child.strip():
                                tier = child.strip()
                                if "StatTrak" in tier:  # ✅ 忽略 StatTrak 条目
                                    continue
                                key = f"{goods_id}_{tier}"
                                price_cache[key] = price
                                count += 1
                                print(f"✅ 价格缓存: {key} = ¥{price}")
                                break
                print(f"🎯 总计缓存磨损价格数: {count} for goods_id={goods_id}")
                return
            else:
                print(f"\n❌ 请求失败 {res.status_code}，等待重试中...")
                time.sleep(2)
        except Exception as e:
            print(f"\n⚠️ 异常: {e}，等待重试中...")
            time.sleep(2)
            
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

def get_price(goods_id, wear, cookies):
    key = f"{goods_id}_{wear}"
    if key in price_cache:
        return price_cache[key]

    # 如果缓存中没有该 goods_id 下任意磨损，说明还没加载过 → 去爬一次
    if not any(f"{goods_id}_{tier}" in price_cache for tier in STANDARD_TIERS):
        fetch_wear_prices(goods_id, cookies)

    return price_cache.get(key)

def find_possible_outputs(combo, all_data):
    target_rarities = set(item["next_rarity"] for item in combo)
    outputs = []
    for case in all_data:
        for skin in case.get("skins", []):
            if skin.get("rarity") not in target_rarities:
                continue
            if not skin.get("name") or not skin.get("wear_goods_ids"):
                continue
            outputs.append({
                "name": skin["name"],
                "wear_goods_ids": skin["wear_goods_ids"],
                "case_name": case["case_name"]  # 👈 加上这个
            })
    return outputs

def preload_prices(pool, all_data, cookies):
    goods_to_fetch = {}
    seen_skins = set()

    print("📦 [预处理] 开始构建待请求皮肤列表...")

    # 从输入池中添加皮肤（用于合成）
    for item in pool:
        unique_key = f"{item['name']}|{item['case_name']}"
        if unique_key in seen_skins:
            continue
        seen_skins.add(unique_key)
        goods_to_fetch[unique_key] = item["goods_id"]

    # 输出皮肤中也要合并（用于收益计算）
    relevant_cases = set(i["case_name"] for i in pool)
    target_rarities = set(i["next_rarity"] for i in pool)

    for case in all_data:
        if case["case_name"] not in relevant_cases:
            continue
        for skin in case.get("skins", []):
            if skin.get("rarity") not in target_rarities:
                continue
            wear_ids = skin.get("wear_goods_ids", {})
            if not wear_ids:
                continue

            unique_key = f"{skin['name']}|{case['case_name']}"
            if unique_key in seen_skins:
                continue
            seen_skins.add(unique_key)

            # 选择最优 goods_id 页面
            preferred = ["崭新出厂", "略有磨损", "久经沙场"]
            gid = None
            for tier in preferred:
                if tier in wear_ids:
                    gid = wear_ids[tier]
                    break
            if not gid:
                gid = next(iter(wear_ids.values()), None)

            if gid:
                goods_to_fetch[unique_key] = gid

    print(f"\n💾 实际需要请求页面数: {len(goods_to_fetch)}\n")

    # 请求阶段
    for i, (key, gid) in enumerate(goods_to_fetch.items(), 1):
        print(f"➡️ [第 {i}/{len(goods_to_fetch)} 项] {key} -> goods_id={gid}")
        if gid in loaded_goods_ids:
            print(f"🟡 goods_id={gid} 已在缓存中，跳过请求")
            continue
        fetch_wear_prices(gid, cookies)

def load_input_pool(limit):
    data = load_data()
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

def float_to_tier(f):
    for tier, (low, high) in STANDARD_TIERS.items():
        if low <= f < high:
            return tier
    return None

def get_output_max_price(output_skins, cookies):
    max_price = 0
    for s in output_skins:
        price_map = fetch_wear_prices(s["goods_id"], cookies)
        if price_map:
            max_price = max(max_price, *price_map.values())
    return max_price

def should_skip(combo, avg_float, total_price, valid_outputs, cookies):
    if not valid_outputs:
        return "无输出皮肤"

    if any(p is None or p <= 0 for p in [get_price(i["goods_id"], i["wear"], cookies) for i in combo]):
        return "存在价格缺失"

    float_tier_thresholds = calc_float_thresholds(0.00, 0.75)  # 默认标准区间
    target_tier = float_to_tier(avg_float)
    if target_tier and avg_float > float_tier_thresholds.get(target_tier, 1):
        return f"float 超过 {target_tier} 压线"

    output_max_price = get_output_max_price(valid_outputs, cookies)
    if total_price > output_max_price:
        return "成本高于最高售价"

    float_tier = float_to_tier(avg_float)
    if not float_tier:
        return "float 区间异常"

    for s in valid_outputs:
        wear_ids = s.get("wear_goods_ids", {})
        gid = wear_ids.get("崭新出厂") or next(iter(wear_ids.values()), None)
        if not gid:
            continue
        prices = fetch_wear_prices(gid, cookies)
        if float_tier in prices and prices[float_tier] > 0:
            return None  # ✅ 合法组合
    return "目标 float 区间无价格"

def simulate_mixed_combos(pool, cookies):
    print(f"🧪 正在构造组合（不重复 & 不考虑顺序）...")

    ONLY_PRINT_COMBO_COUNT = True  # 👈 开关控制：True = 只打印组合数量，不模拟

    rarity_groups = defaultdict(list)
    for item in pool:
        rarity_groups[item["next_rarity"]].append(item)

    total_combos = 0
    results = []
    data = load_data()
    start = time.time()
    accepted = 0
    skipped_by_cost = 0

    for rarity, group in rarity_groups.items():
        if len(group) < 10:
            continue

        group_combos_count = comb(len(group), 10)
        print(f"📦 稀有度 [{rarity}] 组包含 {len(group)} 个皮肤，理论组合数: {group_combos_count:,}")

        group_combos_count = comb(len(group), 10)
        print(f"📊 → 理论组合数: {group_combos_count:,}")
        total_combos += group_combos_count
        continue
    
        total_combos += len(combos)

        if ONLY_PRINT_COMBO_COUNT:
            continue  # ✅ 跳过模拟逻辑，只打印组合信息

        for combo in combos:
            try:
                total_price = sum(get_price(item["goods_id"], item["wear"], cookies) for item in combo)
            except:
                continue

            output_skins = find_possible_outputs(combo, data)
            valid_outputs = [s for s in output_skins if s.get("wear_goods_ids")]
            if not valid_outputs:
                continue

            max_output_price = get_output_max_price(valid_outputs, cookies)
            if total_price > max_output_price:
                skipped_by_cost += 1
                continue

            floats = [item["float"] for item in combo if "float" in item]
            avg_float = sum(floats) / 10 if floats else 0.5

            output_values = []
            for s in valid_outputs:
                gid = s["goods_id"]
                price_map = fetch_wear_prices(gid, cookies)
                if not price_map:
                    continue
                min_f, max_f = s["min_float"], s["max_float"]
                final_float = avg_float * (max_f - min_f) + min_f
                matched_tier = get_float_tier(final_float)
                price = price_map.get(matched_tier)
                if price:
                    output_values.append(price)

            if not output_values:
                continue

            expected_value = sum(output_values) / len(output_values)
            net = expected_value - total_price

            results.append({
                "组合": [f"{i['name']}({i['wear']})" for i in combo],
                "float": round(avg_float, 5),
                "成本": round(total_price, 2),
                "期望": round(expected_value, 2),
                "净收益": round(net, 2),
                "来源箱组合": list({i["case_name"] for i in combo})
            })
            accepted += 1

    duration = round(time.time() - start, 2)
    if ONLY_PRINT_COMBO_COUNT:
        print(f"\n✅ 已完成所有组合分组统计，总组合数 ≈ {total_combos:,}，耗时 {duration} 秒。")
        return None

    print(f"\n✅ 模拟完成：总组合数约 {total_combos:,}，接受 {accepted} 个，跳过（成本）{skipped_by_cost}，耗时 {duration} 秒。")
    results.sort(key=lambda x: x["净收益"], reverse=True)
    return results

def run_mixed_mode():
    with open("buff_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    cookies = {c['name']: c['value'] for c in state['cookies'] if 'buff.163.com' in c['domain']}

    pool = load_input_pool_by_case()  # ✅ 改为按箱子加载
    print(f"🧩 输入池皮肤数量: {len(pool)}")
    
    data = load_data()
    preload_prices(pool, data, cookies)
    results = simulate_mixed_combos(pool, cookies)
    if not results:
        print("🚫 当前模式未返回结果（仅打印组合数或发生中断）")
        return
    for i, r in enumerate(results[:3], 1):
        print(f"\n🏆 Top {i}")
        for line in r["组合"]:
            print(f" - {line}")
        print(f"🎯 float: {r['float']}")
        print(f"💰 成本: ¥{r['成本']} | 📦 期望: ¥{r['期望']} | 📈 净收益: ¥{r['净收益']}")
        print(f"📦 来源箱组合: {' + '.join(r['来源箱组合'])}")

if __name__ == "__main__":
    run_mixed_mode()
