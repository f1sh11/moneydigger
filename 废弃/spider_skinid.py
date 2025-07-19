import requests
from bs4 import BeautifulSoup
import json
import time

# ✅ BUFF 登录 Cookie（已保存）
cookies = {
    "Device-Id": "X9djkxpcRb5K4HAVW6dL",
    "Locale-Supported": "zh-Hans",
    "game": "csgo",
    "qr_code_verify_ticket": "your_ticket",
    "remember_me": "your_userinfo",
    "session": "your_session_token",
    "csrf_token": "your_csrf_token"
}

headers = {"User-Agent": "Mozilla/5.0"}

def get_all_wear_ids_by_goods_id(goods_id):
    url = f"https://buff.163.com/goods/{goods_id}?from=market"
    try:
        res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        if res.status_code != 200:
            print(f"❌ 页面请求失败: {url}")
            return {}
        soup = BeautifulSoup(res.text, "html.parser")
        result = {}

        for btn in soup.select("div.scope-btns a"):
            if "data-goodsid" in btn.attrs:
                wear = btn.get_text(strip=True).split("¥")[0].strip()
                result[wear] = int(btn["data-goodsid"])
            elif "active" in btn.get("class", []):
                next_node = btn.find_next_sibling(string=True)
                wear = next_node.strip() if next_node else "未知"
                result[wear] = int(goods_id)

        return result
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return {}

# ✅ 读取原始文件
with open("all_cases_skins.json", "r", encoding="utf-8") as f:
    cases = json.load(f)

failures = []

# ✅ 遍历所有皮肤
for case in cases:
    for skin in case.get("skins", []):
        skin_id = skin.get("id")
        name = skin.get("name")
        if not skin_id or not name:
            continue

        print(f"🔍 正在处理: {name} (ID: {skin_id})")

        max_retries = 5
        retry_delay = 1
        wear_ids = {}

        for attempt in range(1, max_retries + 1):
            wear_ids = get_all_wear_ids_by_goods_id(skin_id)
            if wear_ids:
                break
            print(f"🔁 第 {attempt} 次尝试失败，等待 {retry_delay}s 后重试...")
            time.sleep(retry_delay)

        if wear_ids:
            skin["wear_goods_ids"] = wear_ids
        else:
            skin["wear_goods_ids"] = {}
            failures.append({"name": name, "id": skin_id})

        # ✅ 每个皮肤之间加等待，防止访问过快
        time.sleep(1)

# ✅ 保存为新文件
with open("all_cases_skins_with_ids.json", "w", encoding="utf-8") as f:
    json.dump(cases, f, ensure_ascii=False, indent=2)

print("✅ 所有数据已保存至 all_cases_skins_with_ids.json")

# ✅ 显示失败列表
if failures:
    print(f"\n⚠️ 共失败 {len(failures)} 项:")
    for fail in failures:
        print(f"- {fail['name']} (ID: {fail['id']})")
else:
    print("✅ 所有皮肤抓取成功")
