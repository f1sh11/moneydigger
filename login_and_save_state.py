from playwright.sync_api import sync_playwright

def login_and_save():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://buff.163.com/market/csgo")
        print("🔐 请手动登录 BUFF，完成后回终端按 Enter...")
        input("✅ 登录完成后按回车保存登录状态")
        context.storage_state(path="buff_state.json")
        browser.close()

if __name__ == "__main__":
    login_and_save()