import random
import time
import heapq
from collections import defaultdict
from utils import load_data, get_price, get_float_by_wear, price_cache, preload_prices

# 假设你已有这些函数可用：load_data(), get_price(), get_float_by_wear(), load_input_pool_by_case()
# 以及：price_cache 是全局缓存

TARGET_TIER = "略有磨损"
POPULATION_SIZE = 300
GENERATIONS = 40
MUTATION_RATE = 0.2
ELITE_COUNT = 10
COMBO_SIZE = 10

# 计算合成 avg_float
def compute_avg_float(combo):
    floats = []
    for item in combo:
        f = get_float_by_wear(item["wear"], item["min_float"], item["max_float"])
        if f is None:
            return None
        floats.append(f)
    return sum(floats) / len(floats)

# 计算净收益为适应度
def fitness(combo, target_avg, output_price):
    avg_f = compute_avg_float(combo)
    if avg_f is None or abs(avg_f - target_avg) > 0.002:
        return -9999  # 不命中卡线，直接淘汰
    total_cost = sum(get_price(i) or 0 for i in combo)
    return output_price - total_cost

# 交叉两个组合
def crossover(a, b):
    idx = random.randint(1, COMBO_SIZE - 2)
    child = a[:idx] + b[idx:]
    seen = set()
    unique = []
    for i in child:
        key = (i["name"], i["wear"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
        if len(unique) == COMBO_SIZE:
            break
    while len(unique) < COMBO_SIZE:
        unique.append(random.choice(a))
    return unique

# 变异：随机替换一件皮肤
def mutate(combo, pool):
    if random.random() < MUTATION_RATE:
        idx = random.randint(0, COMBO_SIZE - 1)
        replacement = random.choice(pool)
        combo[idx] = replacement
    return combo

# 主执行函数
def run_ga_optimizer(target_tier="略有磨损"):
    print(f"🧬 遗传算法优化卡线 [{target_tier}] 组合开始...")
    data = load_data()
    pool = load_input_pool_by_case()
    pool = [p for p in pool if target_tier in p.get("covered_tiers", [])]

    print(f"✅ 输入池皮肤数: {len(pool)}")

    # 找出第一个支持该卡线的输出皮肤，用来反推目标 avg_float
    output_skin = None
    for case in data:
        for s in case["skins"]:
            if target_tier in s.get("card_float_ranges", {}):
                output_skin = s
                break
        if output_skin:
            break

    if not output_skin:
        print("❌ 无法找到支持该卡线的输出皮肤")
        return

    min_f, max_f = output_skin["min_float"], output_skin["max_float"]
    tier_max = output_skin["card_float_ranges"][target_tier][1]
    target_avg_float = (tier_max - min_f) / (max_f - min_f)

    key = f"{output_skin['name']}|{output_skin['case_name']}"
    output_price = price_cache.get(key, {}).get(target_tier)
    if not output_price:
        print(f"❌ 无法找到输出皮肤价格: {key} {target_tier}")
        return

    print(f"🎯 目标 avg_float: {round(target_avg_float, 5)} | 输出售价: ¥{output_price}")

    # 初始化种群
    population = [random.sample(pool, COMBO_SIZE) for _ in range(POPULATION_SIZE)]
    best = None

    for gen in range(GENERATIONS):
        scored = [(fitness(c, target_avg_float, output_price), c) for c in population]
        scored.sort(reverse=True, key=lambda x: x[0])
        top = scored[:ELITE_COUNT]
        if not best or top[0][0] > best[0]:
            best = top[0]

        print(f"第 {gen+1} 代 🏆 最佳收益: ¥{round(top[0][0], 2)}")

        # 生成下一代
        new_pop = [c for _, c in top]  # 精英保留
        while len(new_pop) < POPULATION_SIZE:
            parents = random.sample(top, 2)
            child = crossover(parents[0][1], parents[1][1])
            child = mutate(child, pool)
            new_pop.append(child)

        population = new_pop

    print("\n🎉 最优组合:")
    for item in best[1]:
        print(f" - {item['name']} ({item['wear']})")
    print(f"🎯 合成 avg_float: {round(compute_avg_float(best[1]), 5)}")
    print(f"💰 净收益: ¥{round(best[0], 2)}")
