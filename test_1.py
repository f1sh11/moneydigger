import json, requests, itertools, time
from collections import Counter
from urllib.parse import quote
from bs4 import BeautifulSoup, NavigableString

# ------------------- 用户输入 -------------------
MANUAL_INPUTS = [
    "格洛克 18 型 | 摩登时代"
] * 10

STANDARD_TIERS = {
    "崭新出厂": (0.00, 0.07),
    "略有磨损": (0.07, 0.15),
    "久经沙场": (0.15, 0.38),
    "破损不堪": (0.38, 0.45),
    "战痕累累": (0.45, 1.00),
}

RARITY_ORDER = ["消费级", "工业级", "军规级", "受限", "保密", "隐秘"]

# ------------------- 加载数据 -------------------
def load_data(path="all_cases_skins_with_ids.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_next_rarity(current):
    try:
        idx = RARITY_ORDER.index(current)
        return RARITY_ORDER[idx + 1]
    except:
        return None

def match_manual_inputs(data, manual_names):
    matched, unmatched = [], []
    for name in manual_names:
        found = False
        for case in data:
            for skin in case["skins"]:
                if skin["name"] == name:
                    matched.append({
                        "case_name": case["case_name"],
                        "skin_name": skin["name"],
                        "rarity": skin["rarity"],
                        "next_rarity": get_next_rarity(skin["rarity"]),
                        "wear_goods_ids": skin.get("wear_goods_ids", {})
                    })
                    found = True
                    break
            if found: break
        if not found: unmatched.append(name)
    return matched, unmatched

# ------------------- BUFF 页面提取函数 -------------------
def fetch_wear_prices(goods_id, cookies):
    url = f"https://buff.163.com/goods/{goods_id}?from=market"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        if res.status_code != 200:
            print(f"❌ 请求失败: goods_id={goods_id}, 状态码: {res.status_code}")
            return {}

        soup = BeautifulSoup(res.text, "html5lib")
        wear_prices = {}
        for btn in soup.select("div.scope-btns a"):
            price_tag = btn.select_one("span.custom-currency")
            if not (price_tag and price_tag.has_attr("data-price")):
                continue
            price = float(price_tag["data-price"])
            for child in btn.children:
                if isinstance(child, NavigableString) and child.strip():
                    wear_prices[child.strip()] = price
                    break
        return wear_prices

    except Exception as e:
        print(f"⚠️ 抓取错误: goods_id={goods_id}, 错误: {e}")
        return {}

def preload_output_prices(output_skin_list, cookies):
    price_table = {}
    for skin in output_skin_list:
        name = skin["name"]
        price_table[name] = {}
        wear_ids = skin.get("wear_goods_ids", {})
        gid = None
        for pref in ["崭新出厂", "略有磨损", "久经沙场", "破损不堪", "战痕累累"]:
            if pref in wear_ids:
                gid = wear_ids[pref]
                break
        if not gid and wear_ids:
            gid = list(wear_ids.values())[0]
        if not gid:
            print(f"⚠️ 无有效 goods_id：{name}")
            continue
        price_map = fetch_wear_prices(gid, cookies)
        for tier in STANDARD_TIERS:
            if tier in price_map:
                price_table[name][tier] = price_map[tier]
    return price_table

# ------------------- 组合优化计算 -------------------
def print_progress(current, total):
    bar_len = 30
    filled_len = int(bar_len * current // total)
    bar = '█' * filled_len + '-' * (bar_len - filled_len)
    print(f"\r⏳ 进度 [{bar}] {current}/{total}", end='')

def optimize_tradeup_combination(input_skin, wear_goods_ids, output_skin_list, cookies):
    if not wear_goods_ids:
        print("❌ 无 wear_goods_ids 数据")
        return None
    any_gid = list(wear_goods_ids.values())[0]
    input_prices = {}
    wear_price_map = fetch_wear_prices(any_gid, cookies)

    for tier, float_range in STANDARD_TIERS.items():
        if tier in wear_price_map:
            float_val = sum(float_range) / 2
            price = wear_price_map[tier]
            input_prices[tier] = {"float": float_val, "price": price}

    if not input_prices:
        print("❌ 所有磨损等级都没有可用价格")
        return None

    print(f"✅ 可用输入磨损等级：{list(input_prices.keys())}")
    print(f"📦 可选输出皮肤数量：{len(output_skin_list)}")

    price_table = preload_output_prices(output_skin_list, cookies)

    tiers = list(input_prices.keys())
    all_combos = []
    for counts in itertools.product(range(11), repeat=len(tiers)):
        if sum(counts) == 10:
            combo = []
            for t, c in zip(tiers, counts):
                combo.extend([t] * int(c))
            all_combos.append(combo)

    print(f"🔢 需要评估的组合总数：{len(all_combos)}")

    best_result = None
    best_profit = -9999
    total = len(all_combos)
    step = max(1, total // 50)

    for idx, combo in enumerate(all_combos):
        avg_float = sum(input_prices[t]["float"] for t in combo) / 10
        total_cost = sum(input_prices[t]["price"] for t in combo)

        total_expect = 0.0
        for out_skin in output_skin_list:
            name = out_skin["name"]
            prob = out_skin["probability"]
            price_map = price_table.get(name, {})
            for tier, (low, high) in STANDARD_TIERS.items():
                if low <= avg_float < high and tier in price_map:
                    total_expect += price_map[tier] * prob
                    break

        net_profit = total_expect - total_cost
        if net_profit > best_profit:
            best_result = {
                "combo": dict(Counter(combo)),
                "avg_float": round(avg_float, 6),
                "expected_value": round(total_expect, 2),
                "cost": round(total_cost, 2),
                "net_profit": round(net_profit, 2)
            }
            best_profit = net_profit

        if (idx + 1) % step == 0 or idx + 1 == total:
            print_progress(idx + 1, total)

    print()  # 换行
    return best_result

# ------------------- 主函数入口 -------------------
def main():
    with open("buff_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    cookies = {c['name']: c['value'] for c in state['cookies'] if 'buff.163.com' in c['domain']}

    data = load_data()
    matched, unmatched = match_manual_inputs(data, MANUAL_INPUTS)
    if unmatched:
        print("❌ 未匹配成功的皮肤：", unmatched)
        return

    skin_info = matched[0]
    skin_name = skin_info["skin_name"]
    case_name = skin_info["case_name"]
    next_rarity = skin_info["next_rarity"]
    wear_goods_ids = skin_info["wear_goods_ids"]

    outputs = []
    for case in data:
        if case["case_name"] != case_name:
            continue
        for skin in case["skins"]:
            if skin["rarity"] == next_rarity:
                outputs.append({
                    "name": skin["name"],
                    "wear_goods_ids": skin.get("wear_goods_ids", {}),
                    "probability": 1.0 / len([s for s in case["skins"] if s["rarity"] == next_rarity])
                })

    result = optimize_tradeup_combination(skin_name, wear_goods_ids, outputs, cookies)
    if not result:
        print("❌ 未找到任何有效组合（可能是无价格、无支持等级或组合不成立）")
        return

    print(f"\n✅ 最优组合：")
    for k, v in result["combo"].items():
        print(f" - {k}: {v} 件")
    print(f"\n🎯 合成 float 平均值：{result['avg_float']}")
    print(f"💰 成本：¥{result['cost']}")
    print(f"📦 期望收益：¥{result['expected_value']}")
    print(f"📈 净收益期望：¥{result['net_profit']}")

if __name__ == "__main__":
    main()
