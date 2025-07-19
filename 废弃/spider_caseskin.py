import json
import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# ======= 配置浏览器 =======
options = Options()
# options.add_argument('--headless')  # 你可以开启此行以启用无头
options.add_argument('--disable-gpu')
options.add_argument('--disable-logging')
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_experimental_option("useAutomationExtension", False)

def start_driver():
    service = Service(log_path='nul')
    return webdriver.Chrome(service=service, options=options)

# ======= 加载箱子列表 =======
with open("case_list_for_spider.json", "r", encoding="utf-8") as f:
    case_list = json.load(f)

# ======= 稀有度排序规则 =======
rarity_order = {
    "隐秘": 1,
    "保密": 2,
    "受限": 3,
    "军规级": 4
}

# ======= 存储结果 =======
all_cases = []

for index, case in enumerate(case_list):
    case_id = case["id"]
    case_cn = case["name_cn"]
    case_en = case["name_en"]
    url = f"https://www.csgola.com/wiki/case/{case_id}"

    # 每次都重启浏览器
    if 'driver' in locals():
        driver.quit()
    driver = start_driver()
    print("🔁 已重启浏览器实例")

    # 随机延迟防反爬
    delay = round(random.uniform(5, 9), 2)
    print(f"🕒 {datetime.now().strftime('%H:%M:%S')} - 等待 {delay}s 防反爬...\n")
    time.sleep(delay)

    print(f"🔍 正在爬取 {case_cn} ({case_en}) -> {url}")

    try:
        driver.get(url)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-md-3"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("div.col-md-3")

        if not cards:
            print(f"⚠️ 页面结构无效，跳过 {case_cn} (ID: {case_id})")
            continue

        skins = []
        for card in cards:
            level = card.select_one("div.panel-body > span.label")
            name_en = card.select_one("div.panel-footer span:nth-of-type(1)")
            name_cn = card.select_one("div.panel-footer span:nth-of-type(2)")

            rarity = level.text.strip() if level else ""
            en = name_en.text.strip() if name_en else ""
            cn = name_cn.text.strip() if name_cn else ""

            if en or cn:
                skins.append({"weapon": en, "skin": cn, "rarity": rarity})

        skins.sort(key=lambda x: rarity_order.get(x["rarity"], 99))

        all_cases.append({
            "case_name": case_cn,
            "collection": case_en,
            "skins": skins
        })

        print(f"✅ 成功提取 {len(skins)} 个皮肤")

    except Exception as e:
        print(f"❌ 失败：{case_cn}（ID: {case_id}），错误信息: {str(e)}")
        continue

# ======= 保存总文件 =======
with open("all_cases_skins.json", "w", encoding="utf-8") as f:
    json.dump(all_cases, f, ensure_ascii=False, indent=2)

print("\n🎉 全部爬取完毕，结果保存在 all_cases_skins.json")
driver.quit()
