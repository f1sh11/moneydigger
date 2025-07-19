import json
import requests
import time
from bs4 import BeautifulSoup, NavigableString

price_cache = {}
loaded_goods_ids = set()

STANDARD_TIERS = {
    "崭新出厂": (0.00, 0.07),
    "略有磨损": (0.07, 0.15),
    "久经沙场": (0.15, 0.38),
    "破损不堪": (0.38, 0.45),
    "战痕累累": (0.45, 1.00),
}

def get_price_by_name(skin_name_with_case, wear):
    if skin_name_with_case not in price_cache:
        print(f"❌ 未找到皮肤缓存: {skin_name_with_case}")
        return None
    price = price_cache[skin_name_with_case].get(wear)
    return price

def load_data(path="case_skin_floatrange_cardrange_covertiers.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    key = f"{item['name']}|{item['case_name']}"
    return get_price_by_name(key, item['wear'])

def get_price(item):
    key = f"{item['name']}|{item['case_name']}"
    return get_price_by_name(key, item['wear'])

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
        skin_name = key
        fetch_wear_prices(gid, skin_name, cookies)
        loaded_goods_ids.add(gid)

# 用标准磨损区间的上限（tier_max）推导出极限卡线 float
def get_cardline_float_by_wear(wear, min_f, max_f):
    tier = STANDARD_TIERS.get(wear)
    if not tier:
        return None
    tier_max = tier[1]
    target_avg = (tier_max - min_f) / (max_f - min_f)
    return target_avg


def fetch_wear_prices(base_gid, skin_name, cookies):
    """
    访问 base_gid 对应的页面，爬取所有磨损价格，存入 price_cache[skin_name][磨损等级]
    """
    url = f"https://buff.163.com/goods/{base_gid}?from=market"
    headers = {"User-Agent": "Mozilla/5.0"}

    print(f"🔍【fetch_wear_prices】开始请求: {url}")

    retry = 0
    max_retry = 5
    while retry < max_retry:
        try:
            res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if res.status_code != 200:
                print(f"❌ 请求失败 {res.status_code}，第 {retry+1} 次重试中...")
                retry += 1
                time.sleep(1)
                continue

            soup = BeautifulSoup(res.text, "html5lib")
            price_cache[skin_name] = {}
            count = 0

            for btn in soup.select("div.scope-btns a"):
                price_tag = btn.select_one("span.custom-currency")
                if not (price_tag and price_tag.has_attr("data-price")):
                    continue

                try:
                    price = float(price_tag["data-price"])
                except:
                    continue

                # 获取磨损等级名称
                for child in btn.children:
                    if isinstance(child, NavigableString) and child.strip():
                        wear = child.strip()
                        if "StatTrak" in wear:
                            continue
                        price_cache[skin_name][wear] = price
                        count += 1
                        print(f"✅ 缓存价格: {skin_name} - {wear} = ¥{price}")
                        break

            print(f"🎯 共缓存磨损价格数: {count} for {skin_name}")
            return price_cache[skin_name]

        except Exception as e:
            print(f"⚠️ 爬取异常: {e}，第 {retry+1} 次重试中...")
            retry += 1
            time.sleep(1)

    print(f"❌ 多次重试失败: {skin_name}")
    return None

def calc_expected_output_value(valid_outputs, target_tier, price_map):
    total = 0
    for s in valid_outputs:
        key = f"{s['name']}|{s['case_name']}"
        price = price_map.get(key)
        if not price:
            continue
        # ✅ 继续你已有的概率乘法逻辑
        prob = s.get("probability", 0)
        total += prob * price
    return total

