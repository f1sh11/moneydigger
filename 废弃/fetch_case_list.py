import requests
import json
import time

MAX_PAGE_LIMIT = 50
SLEEP_SECONDS = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

def load_cookies_from_buff_state(path="buff_state.json"):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cookies = {
        c['name']: c['value']
        for c in raw.get("cookies", [])
        if "buff.163.com" in c.get("domain", "")
    }
    return cookies

def fetch_special_cases(keywords=("纪念包", "收藏品", "收藏包"), cookies=None):
    all_cases = []
    seen_ids = set()

    for page in range(1, MAX_PAGE_LIMIT + 1):
        url = (
            "https://buff.163.com/api/market/goods"
            f"?game=csgo&page_num={page}&category=csgo_type_weaponcase&use_suggestion=0"
        )
        time.sleep(SLEEP_SECONDS)
        try:
            resp = requests.get(url, headers=HEADERS, cookies=cookies, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️ 第 {page} 页请求异常：{e}")
            break

        data = resp.json().get("data", {})
        items = data.get("items", [])
        total_page = data.get("total_page", 1)

        print(f"📦 第 {page} 页（共 {total_page} 页）：获取 {len(items)} 条记录")

        for it in items:
            name_cn = it.get("name", "").strip()
            if not any(kw in name_cn for kw in keywords):
                continue

            cid = it.get("id")
            if cid in seen_ids or cid is None:
                continue
            seen_ids.add(cid)

            all_cases.append({
                "id":      cid,
                "name_cn": name_cn,
                "name_en": it.get("market_hash_name", "").strip()
            })

        if page >= total_page:
            print(f"✅ 抓取完毕，达到最后一页：{total_page}")
            break

    return all_cases

def save_to_json(cases, filename="buff_special_cases.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"✅ 共保存 {len(cases)} 条箱子映射至 {filename}")

# 主执行逻辑
if __name__ == "__main__":
    cookies = load_cookies_from_buff_state()
    special_cases = fetch_special_cases(cookies=cookies)
    print(f"\n🎯 共找到纪念包/收藏品：{len(special_cases)} 个\n")
    save_to_json(special_cases)
