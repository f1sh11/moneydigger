import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# === 稀有度排序规则 ===
rarity_order = {
    "隐秘": 1,
    "保密": 2,
    "受限": 3,
    "军规级": 4,
    "消费级": 5,
    "?": 99
}

# === Selenium 设置 ===
options = Options()
# options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--start-maximized')
service = Service()
driver = webdriver.Chrome(service=service, options=options)

# === 读取箱子列表 ===
with open("buff_cases_ids.json", "r", encoding="utf-8") as f:
    case_list = json.load(f)

all_cases_data = []
failures = []

for case in case_list:
    CASE_ID = case["id"]
    CASE_NAME = case["name_cn"]
    url = f"https://buff.163.com/goods/{CASE_ID}?from=market#tab=selling"
    print(f"\n🌐 正在处理: {CASE_NAME} ({CASE_ID})")

    try:
        driver.get(url)
        time.sleep(3)

        # 点击“包含物品”
        try:
            btn = driver.find_element(By.ID, "weapon_case_entry")
            btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"❌ 无法点击按钮: {e}")
            failures.append(CASE_ID)
            continue

        # 解析页面
        soup = BeautifulSoup(driver.page_source, "html.parser")
        result = []
        rarity_divs = soup.select("div.weapon-cate")

        for rarity_div in rarity_divs:
            rarity = rarity_div.text.strip()
            ul = rarity_div.find_next_sibling("ul")
            if not ul or "weapon-list" not in ul.get("class", []):
                continue
            for li in ul.find_all("li"):
                a = li.select_one("h3 > a[href^='/goods/']")
                h4 = li.select_one("h4")
                if not a or not h4:
                    continue
                skin_id = a["href"].split("/goods/")[-1]
                name = a.text.strip()
                price_range = h4.text.replace("\xa0", " ").strip()
                result.append({
                    "name": name,
                    "id": skin_id,
                    "price_range": price_range,
                    "rarity": rarity
                })

        # 排序并加入总列表
        result.sort(key=lambda x: rarity_order.get(x["rarity"], 99))
        all_cases_data.append({
            "case_name": CASE_NAME,
            "case_id": CASE_ID,
            "skins": result
        })

        print(f"✅ 提取 {len(result)} 个皮肤")

    except Exception as e:
        print(f"❌ 页面处理失败: {e}")
        failures.append(CASE_ID)

# 关闭浏览器
driver.quit()

# 保存为一个统一文件
with open("all_cases_skins.json", "w", encoding="utf-8") as f:
    json.dump(all_cases_data, f, ensure_ascii=False, indent=2)

# 总结
print("\n🎯 所有箱子完成。总箱子数:", len(all_cases_data))
if failures:
    print(f"❌ 失败 {len(failures)} 个箱子 ID: {failures}")
else:
    print("✅ 全部成功")
