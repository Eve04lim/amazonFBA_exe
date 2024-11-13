import json
import time
import re
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import simpledialog
import getpass  

def wait_for_page_load(driver, timeout=10):
    def page_has_loaded(driver):
        return driver.execute_script("return document.readyState") == "complete"
    WebDriverWait(driver, timeout).until(page_has_loaded)

def find_element_with_retry(driver, by, value, max_attempts=3, wait_time=5):
    for attempt in range(max_attempts):
        try:
            element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            if attempt == max_attempts - 1:
                raise
            time.sleep(1)

def find_element_in_shadow_dom(driver, selector):
    js_find_in_shadow = """
    function findElementInShadowDom(selector) {
        function scanShadowDom(element) {
            if (element.shadowRoot) {
                const found = element.shadowRoot.querySelector(selector);
                if (found) {
                    return found;
                }
                for (const child of element.shadowRoot.children) {
                    const result = scanShadowDom(child);
                    if (result) {
                        return result;
                    }
                }
            }
            for (const child of element.children) {
                const result = scanShadowDom(child);
                if (result) {
                    return result;
                }
            }
            return null;
        }
        return scanShadowDom(document.body);
    }
    return findElementInShadowDom(arguments[0]);
    """
    return driver.execute_script(js_find_in_shadow, selector)

def login_and_navigate_to_fee_calculator(email, password):
        # Chromeのオプションを設定
    #options = webdriver.ChromeOptions()
    #options.add_argument("--headless")  # ヘッドレスモードで実行
    #options.add_argument("--disable-gpu")  # GPUの使用を無効化
    #options.add_argument("--window-size=1920,1080")  # ウィンドウサイズを設定

    # ヘッドレスモードの設定を使用してブラウザを起動
    #driver = webdriver.Chrome(executable_path="chromedriver.exe", options=options)
    driver = webdriver.Chrome(r"C:\chromedriver\chromedriver.exe")  # ChromeDriverのパスを適切に設定してください
    driver.maximize_window()
    
    try:
        driver.get("https://sellercentral.amazon.com/revcal")
        wait_for_page_load(driver)
        print("Login page loaded")

        email_field = find_element_with_retry(driver, By.ID, "ap_email")
        email_field.send_keys(email)
        print("Email entered")

        # 「次へ進む」ボタンの存在をチェックし、存在する場合はクリック
        try:
            continue_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "continue"))
            )
            continue_button.click()
            print("Clicked 'Next' button")
        except TimeoutException:
            print("'Next' button not found, proceeding to password entry")

        password_field = find_element_with_retry(driver, By.ID, "ap_password")
        password_field.send_keys(password)
        print("Password entered")

        login_button = find_element_with_retry(driver, By.ID, "signInSubmit")
        login_button.click()
        print("Login button clicked")

        # 以下は変更なし
        handle_otp(driver)
        select_marketplace(driver)

        wait_for_page_load(driver)
        ensure_fee_calculator_loaded(driver)

        print(f"Current URL: {driver.current_url}")
        return driver

    except Exception as e:
        print(f"An error occurred during login or navigation: {e}")
        driver.quit()
        raise

def handle_otp(driver):
    try:
        otp_field = find_element_with_retry(driver, By.ID, "auth-mfa-otpcode", max_attempts=1)
        print("OTP page detected")
        
        # GUIでOTPを入力
        root = tk.Tk()
        root.withdraw()
        otp = simpledialog.askstring("Input", "ワンタイムパスワード（OTP）を入力してください:")
        root.destroy()

        otp_field.send_keys(otp)
        submit_button = find_element_with_retry(driver, By.ID, "auth-signin-button")
        submit_button.click()
        print("OTP submitted")
    except TimeoutException:
        print("OTP page not found, continuing...")

def select_marketplace(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'picker-name') and text()='アメリカ合衆国']"))
        )
        print("Marketplace selection page loaded")

        us_marketplace = driver.find_element(By.XPATH, "//div[contains(@class, 'picker-name') and text()='アメリカ合衆国']")
        us_marketplace.click()
        print("United States marketplace selected")

        account_select_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'picker-switch-accounts-button')]"))
        )
        account_select_button.click()
        print("Account selection button clicked")

    except TimeoutException:
        print("Marketplace selection page not found or elements not interactable")

def ensure_fee_calculator_loaded(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#katal-id-6, input[placeholder*='SKU']"))
        )
        print("Fee calculator page loaded successfully")
    except TimeoutException:
        print("Fee calculator page failed to load")

def search_product(driver, asin):
    try:
        search_field = locate_search_field(driver)
        if not search_field:
            raise Exception("Search field not found")

        original_url = driver.current_url
        original_source = driver.page_source

        enter_asin(driver, search_field, asin)
        click_search_button(driver, original_url, original_source)

        search_field.send_keys(Keys.RETURN)
        print("Enter key sent to search field")

        return wait_for_page_change(driver, original_url, original_source)

    except Exception as e:
        print(f"An error occurred during product search: {e}")
        return False

def locate_search_field(driver):
    search_field_selectors = [
        '#katal-id-6',
        'input[placeholder="SKU、商品名、ISBN、UPC、EAN、またはASINを検索"]',
        'input[part="input"]',
        'kat-input[label="Amazonの商品を検索"] input'
    ]

    for selector in search_field_selectors:
        try:
            search_field = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            print(f"Search field found with selector: {selector}")
            return search_field
        except TimeoutException:
            print(f"Selector not found in regular DOM: {selector}")
            search_field = find_element_in_shadow_dom(driver, selector)
            if search_field:
                print(f"Search field found in Shadow DOM with selector: {selector}")
                return search_field
    return None

def enter_asin(driver, search_field, asin):
    driver.execute_script("""
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, search_field, asin)
    print(f"ASIN {asin} entered using JavaScript")

    search_field.clear()
    search_field.send_keys(asin)
    print(f"ASIN {asin} entered using Selenium")

def click_search_button(driver, original_url, original_source):
    button_selectors = [
        'button.button[type="submit"]',
        'button.button:has(span:contains("検索"))',
        'button[type="submit"]:has(span:contains("検索"))',
        'button:contains("検索")'
    ]

    for selector in button_selectors:
        try:
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            button.click()
            print(f"Search button clicked with selector: {selector}")
            if wait_for_page_change(driver, original_url, original_source):
                return True
        except:
            print(f"Failed to click button with selector: {selector}")

def wait_for_page_change(driver, original_url, original_source, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(lambda d: d.current_url != original_url)
        print("Page URL changed")
        return True
    except TimeoutException:
        print("URL did not change, checking for content change...")

    try:
        WebDriverWait(driver, timeout).until(lambda d: d.page_source != original_source)
        print("Page source changed")
        return True
    except TimeoutException:
        print("Page source did not change, checking for new elements...")

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test-id='search-result-item'], .search-results"))
        )
        print("New elements appeared on the page")
        return True
    except TimeoutException:
        print("No new elements appeared, search might have failed")
        return False

def extract_product_data(driver):
    try:
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        # Amazon手数料を抽出
        amazon_fee_element = soup.select_one("kat-expander:-soup-contains('Amazon手数料') kat-label.expander-badge-currency")
        amazon_fee = amazon_fee_element.text.strip() if amazon_fee_element else "Amazon手数料が見つかりません"

        # FBA手数料を抽出
        fba_fee_element = soup.select_one("kat-expander:-soup-contains('出荷費用') kat-label.expander-badge-currency")
        fba_fee = fba_fee_element.text.strip() if fba_fee_element else "FBA手数料が見つかりません"

        # 商品重量を抽出
        weight = "商品重量が見つかりません"
        weight_td = soup.find("td", string=re.compile(r"ポンド"))
        if weight_td:
            weight_text = weight_td.text.strip()
            weight_match = re.search(r"([\d\.]+)\s*ポンド", weight_text)
            if weight_match:
                weight = weight_match.group(1) + " ポンド"

        # 競合者数を抽出
        competitors = "競合者数が見つかりません"
        competitors_td = soup.find("td", string=re.compile(r"出品商品"))
        if competitors_td:
            competitors_text = competitors_td.text.strip()
            competitors_match = re.search(r"(\d+)\s*出品商品", competitors_text)
            if competitors_match:
                competitors = competitors_match.group(1) + " 出品商品"

        return {
            "amazon_fee": amazon_fee,
            "fba_fee": fba_fee,
            "weight": weight,          # 商品重量を返す
            "competitors": competitors # 競合者数を返す
        }
    except Exception as e:
        print(f"データ抽出中にエラーが発生しました: {e}")
        return None

def load_json_data(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def update_product_fees(driver, products):
    updated_products = []
    fee_calculator_url = "https://sellercentral.amazon.com/revcal"  # 手数料計算ツールのリンク

    for product in products:
        asin = product['ASIN']
        print(f"Processing ASIN: {asin}")

        search_success = search_product(driver, asin)
        if search_success:
            product_data = extract_product_data(driver)
            if product_data:
                product['amazon_fee'] = product_data['amazon_fee']
                product['fba_fee'] = product_data['fba_fee']
                product['weight'] = product_data['weight']  # 商品重量を追加
                product['competitors'] = product_data['competitors']  # 競合者数を追加
                print(f"Updated fees for ASIN {asin}: Amazon Fee: {product_data['amazon_fee']}, FBA Fee: {product_data['fba_fee']}, Weight: {product_data['weight']}, Competitors: {product_data['competitors']}")
            else:
                print(f"Failed to extract data for ASIN {asin}")
        else:
            print(f"Failed to search for ASIN {asin}")

        updated_products.append(product)

        # ページをリフレッシュする代わりに、手数料計算ツールのページに戻る
        driver.get(fee_calculator_url)
        wait_for_page_load(driver)
        time.sleep(1)  # サーバーへの負荷を軽減するための遅延

    return updated_products
def get_credentials():
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示に

    email = simpledialog.askstring("Input", "Amazonセラーアカウントのメールアドレスまたは電話番号を入力してください:")
    password = simpledialog.askstring("Input", "パスワードを入力してください:", show="*")

    root.destroy()
    return email, password

def get_asin_code():
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示に
    asin_code = simpledialog.askstring("Input", "調べたい商品のASINコードを入力してください:")
    root.destroy()
    return asin_code

def main():
    email, password = get_credentials()  # GUIでログイン情報を取得
    
    driver = None
    try:
        driver = login_and_navigate_to_fee_calculator(email, password)
        if driver:
            time.sleep(5)
            
        while True:
            asin = get_asin_code()  # ASINコードをユーザーから取得

            search_success = search_product(driver, asin)
            if search_success:
                product_data = extract_product_data(driver)
                if product_data:
                    result_message = (
                        f"Amazon手数料: {product_data['amazon_fee']}\n"
                        f"FBA手数料: {product_data['fba_fee']}\n"
                        f"商品重量: {product_data['weight']}\n"
                        f"競合者数: {product_data['competitors']}"
                    )

                    # 結果表示用ウィンドウを作成
                    root = tk.Tk()
                    root.title("抽出結果")

                    # テキストウィジェットに結果を表示
                    text_widget = tk.Text(root, wrap='word')
                    text_widget.insert('1.0', result_message)
                    text_widget.config(state='normal')  # 編集可能にしてコピーを許可
                    text_widget.pack(expand=True, fill='both')

                    root.mainloop()
                else:
                    messagebox.showwarning("抽出失敗", "データの抽出に失敗しました。")

            # 次のASINを検索するか確認
            continue_search = simpledialog.askstring("Continue", "次のASINコードを検索しますか？(yes/no):")
            if continue_search.lower() == "yes":
                # ASIN検索画面に戻る
                driver.get("https://sellercentral.amazon.com/revcal")
                wait_for_page_load(driver)
                time.sleep(1)  # サーバーへの負荷を軽減するための遅延
            else:
                break
                
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        if driver:
            time.sleep(5)
            driver.quit()

if __name__ == "__main__":
    main()
