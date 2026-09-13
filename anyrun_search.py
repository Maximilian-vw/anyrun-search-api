#!/usr/bin/env python3

import os
import sys
import re
import json
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("ANYRUN_EMAIL")
PASSWORD = os.getenv("ANYRUN_PASSWORD")
BASE = "https://app.any.run"
SUBMISSIONS_URL = f"{BASE}/submissions/"

if not EMAIL or not PASSWORD:
    print("[-] Missing ANYRUN_EMAIL or ANYRUN_PASSWORD in .env")
    sys.exit(1)


def clean(x):
    return re.sub(r"\s+", " ", x).strip() if x else None


def extract_submission(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "os": None,
        "time": None,
        "verdict": None,
        "object": None,
        "type": None,
        "tags": [],
        "md5": None,
        "sha1": None,
        "sha256": None,
    }

    x = soup.select_one(".os-info__name")
    if x:
        result["os"] = clean(x.get_text(" "))

    x = soup.select_one(".os-info__time")
    if x:
        result["time"] = clean(x.get_text(" "))

    x = soup.select_one(".object-info__verdict")
    if x:
        result["verdict"] = clean(x.get_text(" "))

    x = soup.select_one(".object-info__info-name")
    if x:
        result["object"] = clean(x.get_text(" "))

    x = soup.select_one(".object-info__info-type")
    if x:
        result["type"] = clean(x.get_text(" "))

    result["tags"] = [
        clean(x.get_text(" "))
        for x in soup.select(".analysis-tags-list__item")
        if clean(x.get_text(" "))
    ]

    text = soup.get_text(" ", strip=True)

    patterns = {
        "md5": r"\b[a-fA-F0-9]{32}\b",
        "sha1": r"\b[a-fA-F0-9]{40}\b",
        "sha256": r"\b[a-fA-F0-9]{64}\b",
    }

    for name, pattern in patterns.items():
        matches = re.findall(pattern, text)
        for value in matches:
            value = value.lower()
            if not result[name]:
                result[name] = value

    return result


def get_driver(headless=False):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def handle_checkbox_challenge(driver, wait):
    handled = False
    
    try:
        checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox'][aria-label='Verify you are human'], input[type='checkbox'][aria-label*='human' i], .cf-turnstile input[type='checkbox'], [data-testid*='turnstile'] input[type='checkbox']")
        if checkbox.is_displayed() and checkbox.is_enabled():
            print("[!] Checkbox challenge detected - clicking...")
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            time.sleep(random.uniform(1, 2))
            checkbox.click()
            print("[+] Checkbox clicked")
            time.sleep(random.uniform(5, 8))
            handled = True
    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"[*] Checkbox check error: {e}")
    
    if not handled:
        try:
            labels = driver.find_elements(By.XPATH, "//label[contains(., 'Verify you are human') or .//input[@aria-label='Verify you are human']]")
            for label in labels:
                try:
                    checkbox = label.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                    if checkbox.is_displayed() and checkbox.is_enabled():
                        print("[!] Checkbox challenge detected in label - clicking label...")
                        driver.execute_script("arguments[0].scrollIntoView(true);", label)
                        time.sleep(random.uniform(1, 2))
                        label.click()
                        print("[+] Label (with checkbox) clicked")
                        time.sleep(random.uniform(5, 8))
                        handled = True
                        break
                    elif label.is_displayed() and label.is_enabled():
                        print("[!] Label with 'Verify you are human' found - clicking label directly...")
                        driver.execute_script("arguments[0].scrollIntoView(true);", label)
                        time.sleep(random.uniform(1, 2))
                        label.click()
                        print("[+] Label clicked directly")
                        time.sleep(random.uniform(5, 8))
                        handled = True
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[*] Label checkbox check error: {e}")
    
    if not handled:
        try:
            checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox' and @aria-label='Verify you are human']")
            for checkbox in checkboxes:
                try:
                    if checkbox.is_displayed() and checkbox.is_enabled():
                        print("[!] Checkbox with exact aria-label found - clicking...")
                        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                        time.sleep(random.uniform(1, 2))
                        checkbox.click()
                        print("[+] Checkbox (exact aria-label) clicked")
                        time.sleep(random.uniform(5, 8))
                        handled = True
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[*] Exact aria-label check error: {e}")
    
    if not handled:
        try:
            checkboxes = driver.find_elements(By.XPATH, "//*[@role='checkbox' or @aria-label='Verify you are human' or contains(@aria-label, 'human')]")
            for checkbox in checkboxes:
                try:
                    if checkbox.is_displayed() and checkbox.is_enabled():
                        print("[!] Checkbox challenge detected (role/aria) - clicking...")
                        driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                        time.sleep(random.uniform(1, 2))
                        checkbox.click()
                        print("[+] Checkbox (role/aria) clicked")
                        time.sleep(random.uniform(5, 8))
                        handled = True
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[*] Role checkbox check error: {e}")
    
    if not handled:
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    src = iframe.get_attribute("src") or ""
                    title = iframe.get_attribute("title") or ""
                    if "turnstile" in src.lower() or "challenge" in src.lower() or "cf-" in src.lower() or "verify" in title.lower() or "challenge" in title.lower():
                        print(f"[!] Found Turnstile/challenge iframe: src={src}, title={title}")
                        driver.switch_to.frame(iframe)
                        time.sleep(1)
                        
                        try:
                            checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox'], [role='checkbox'], .checkbox, div[tabindex='0']")
                            if checkbox.is_displayed() and checkbox.is_enabled():
                                print("[!] Checkbox found in iframe - clicking...")
                                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                                time.sleep(random.uniform(1, 2))
                                checkbox.click()
                                print("[+] Checkbox in iframe clicked")
                                time.sleep(random.uniform(5, 8))
                                driver.switch_to.default_content()
                                handled = True
                                break
                        except NoSuchElementException:
                            pass
                        
                        if not handled:
                            try:
                                labels = driver.find_elements(By.XPATH, "//label[contains(., 'Verify you are human') or .//input[@aria-label='Verify you are human']]")
                                for label in labels:
                                    try:
                                        checkbox = label.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                                        if checkbox.is_displayed() and checkbox.is_enabled():
                                            print("[!] Checkbox in label found in iframe - clicking label...")
                                            driver.execute_script("arguments[0].scrollIntoView(true);", label)
                                            time.sleep(random.uniform(1, 2))
                                            label.click()
                                            print("[+] Label in iframe clicked")
                                            time.sleep(random.uniform(5, 8))
                                            handled = True
                                            break
                                        elif label.is_displayed() and label.is_enabled():
                                            print("[!] Label with 'Verify you are human' in iframe - clicking label directly...")
                                            driver.execute_script("arguments[0].scrollIntoView(true);", label)
                                            time.sleep(random.uniform(1, 2))
                                            label.click()
                                            print("[+] Label in iframe clicked directly")
                                            time.sleep(random.uniform(5, 8))
                                            handled = True
                                            break
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                        
                        driver.switch_to.default_content()
                        if handled:
                            break
                except Exception as e:
                    driver.switch_to.default_content()
                    continue
        except Exception as e:
            print(f"[*] Iframe checkbox check error: {e}")
            driver.switch_to.default_content()
    
    if not handled:
        try:
            shadow_hosts = driver.find_elements(By.CSS_SELECTOR, "div.cf-turnstile, [data-testid*='turnstile'], .turnstile-widget")
            for host in shadow_hosts:
                try:
                    shadow_root = driver.execute_script("return arguments[0].shadowRoot", host)
                    if shadow_root:
                        checkbox = shadow_root.find_element(By.CSS_SELECTOR, "input[type='checkbox'], [role='checkbox']")
                        if checkbox.is_displayed() and checkbox.is_enabled():
                            print("[!] Checkbox found in shadow DOM - clicking...")
                            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                            time.sleep(random.uniform(1, 2))
                            driver.execute_script("arguments[0].click()", checkbox)
                            print("[+] Checkbox in shadow DOM clicked")
                            time.sleep(random.uniform(5, 8))
                            handled = True
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"[*] Shadow DOM check error: {e}")
    
    if not handled:
        try:
            modals = driver.find_elements(By.CSS_SELECTOR, "[role='dialog'], .modal, .ar-modal, .challenge-modal, .cf-challenge-modal")
            for modal in modals:
                try:
                    if modal.is_displayed():
                        checkbox = modal.find_element(By.CSS_SELECTOR, "input[type='checkbox'], [role='checkbox'], .checkbox")
                        if checkbox.is_displayed() and checkbox.is_enabled():
                            print("[!] Checkbox found in modal - clicking...")
                            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                            time.sleep(random.uniform(1, 2))
                            checkbox.click()
                            print("[+] Checkbox in modal clicked")
                            time.sleep(random.uniform(5, 8))
                            handled = True
                            break
                        label = modal.find_element(By.XPATH, ".//label[contains(., 'Verify you are human')]")
                        if label.is_displayed() and label.is_enabled():
                            print("[!] Label found in modal - clicking...")
                            driver.execute_script("arguments[0].scrollIntoView(true);", label)
                            time.sleep(random.uniform(1, 2))
                            label.click()
                            print("[+] Label in modal clicked")
                            time.sleep(random.uniform(5, 8))
                            handled = True
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"[*] Modal checkbox check error: {e}")
    
    return handled


def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))


def login_and_search(driver, wait, hash_value):
    print("[*] Starting browser for login and search...")
    
    driver.get(SUBMISSIONS_URL)
    
    print("[*] Waiting for submissions page...")
    print(f"[*] Current URL: {driver.current_url}")
    print(f"[*] Page title: {driver.title}")

    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    print("[+] Page fully loaded")

    time.sleep(3)
    driver.save_screenshot("/tmp/debug_submissions.png")
    print("[*] Debug screenshot saved")

    print("[*] Looking for Sign in button in bottom corner...")
    sign_in_btn = wait.until(EC.element_to_be_clickable((By.ID, "sign-in-btn")))
    driver.execute_script("arguments[0].scrollIntoView(true);", sign_in_btn)
    time.sleep(1)
    sign_in_btn.click()
    print("[+] Sign in button clicked - modal should appear")

    time.sleep(5)
    driver.save_screenshot("/tmp/debug_modal.png")
    print("[*] Modal debug screenshot saved")

    print("[*] Checking for iframes...")
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"[*] Found {len(iframes)} iframes")

    email_input = None
    password_input = None

    print("[*] Searching for email input in iframes...")
    selectors = [
        (By.ID, "email"),
        (By.CSS_SELECTOR, "input#email"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
        (By.CSS_SELECTOR, "input[placeholder*='business' i]"),
        (By.CSS_SELECTOR, ".ar-input__field[type='email']"),
        (By.XPATH, "//input[@type='email']"),
        (By.XPATH, "//input[@id='email']"),
    ]

    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            for by, selector in selectors:
                try:
                    email_input = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
                    print(f"[+] Found email input in iframe with: {by}={selector}")
                    break
                except TimeoutException:
                    continue
            if email_input:
                break
            driver.switch_to.default_content()
        except Exception as e:
            driver.switch_to.default_content()
            continue

    if not email_input:
        print("[-] Could not find email input in iframes, trying main document...")
        driver.switch_to.default_content()
        for by, selector in selectors:
            try:
                email_input = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
                print(f"[+] Found email input in main doc with: {by}={selector}")
                break
            except TimeoutException:
                continue

    if not email_input:
        print("[-] Could not find email input anywhere")
        return None

    email_input.clear()
    human_type(email_input, EMAIL)
    print("[+] Email entered")

    print("[*] Searching for password input...")
    pwd_selectors = [
        (By.ID, "password"),
        (By.CSS_SELECTOR, "input#password"),
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.CSS_SELECTOR, "input[placeholder*='password' i]"),
        (By.CSS_SELECTOR, ".ar-input__field[type='password']"),
        (By.XPATH, "//input[@type='password']"),
        (By.XPATH, "//input[@id='password']"),
    ]

    for by, selector in pwd_selectors:
        try:
            password_input = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
            print(f"[+] Found password input with: {by}={selector}")
            break
        except TimeoutException:
            continue

    if not password_input:
        print("[-] Could not find password input in current context, trying main document...")
        driver.switch_to.default_content()
        for by, selector in pwd_selectors:
            try:
                password_input = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, selector)))
                print(f"[+] Found password input in main doc with: {by}={selector}")
                break
            except TimeoutException:
                continue

    if not password_input:
        print("[-] Could not find password input anywhere")
        return None

    password_input.clear()
    human_type(password_input, PASSWORD)
    print("[+] Password entered")

    print("[*] Clicking Sign in button...")
    submit_selectors = [
        (By.CSS_SELECTOR, "button.ar-button--primary[type='submit']"),
        (By.XPATH, "//button[@type='submit' and contains(@class, 'ar-button--primary')]"),
        (By.XPATH, "//button[.//span[text()='Sign in']]"),
    ]

    submit_btn = None
    for by, selector in submit_selectors:
        try:
            submit_btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, selector)))
            print(f"[+] Found submit button with: {by}={selector}")
            break
        except TimeoutException:
            continue

    if not submit_btn:
        print("[-] Could not find submit button in current context, trying main document...")
        driver.switch_to.default_content()
        for by, selector in submit_selectors:
            try:
                submit_btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, selector)))
                print(f"[+] Found submit button in main doc with: {by}={selector}")
                break
            except TimeoutException:
                continue

    if not submit_btn:
        print("[-] Could not find submit button anywhere")
        return None

    submit_btn.click()
    print("[+] Sign in clicked")

    driver.switch_to.default_content()
    wait.until(EC.url_contains("/submissions"))
    print("[+] Login successful - redirected to submissions")

    time.sleep(3)
    handle_checkbox_challenge(driver, wait)
    
    print("[*] Searching for hash using search input...")
    
    search_selectors = [
        (By.CSS_SELECTOR, "input.filter-field__input[placeholder*='hash' i]"),
        (By.CSS_SELECTOR, "input.filter-field__input[placeholder*='tag' i]"),
        (By.CSS_SELECTOR, "input.filter-field__input[type='text']"),
        (By.CSS_SELECTOR, ".filter-field input.filter-field__input"),
        (By.CSS_SELECTOR, "input[data-test-id*='filter']"),
        (By.XPATH, "//input[@placeholder='Type hash or tag to search']"),
        (By.XPATH, "//input[contains(@placeholder, 'hash') or contains(@placeholder, 'tag')]"),
    ]

    search_input = None
    for by, selector in search_selectors:
        try:
            search_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
            print(f"[+] Found search input with: {by}={selector}")
            break
        except TimeoutException:
            continue

    if not search_input:
        print("[-] Could not find search input")
        driver.save_screenshot("/tmp/debug_no_search.png")
        return None

    search_input.clear()
    time.sleep(0.5)
    human_type(search_input, hash_value)
    print(f"[+] Hash typed: {hash_value}")
    time.sleep(0.5)
    search_input.send_keys(Keys.RETURN)
    print("[+] Enter pressed - searching...")

    time.sleep(5)
    handle_checkbox_challenge(driver, wait)

    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(3)

    driver.save_screenshot("/tmp/debug_search_results.png")
    print("[*] Search results screenshot saved")

    page_text = driver.page_source
    hash_upper = hash_value.upper()
    hash_lower = hash_value.lower()
    
    if hash_upper in page_text or hash_lower in page_text:
        print("[+] Hash found in search results!")
        return extract_submission(page_text)
    else:
        print("[-] Hash not found in search results")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 anyrun_search.py <hash>")
        sys.exit(1)

    hash_value = sys.argv[1]

    print("=" * 70)
    print("ANY.RUN SEARCH SUBMISSION LOOKUP")
    print("=" * 70)
    print(f"[*] Hash: {hash_value}")

    driver = get_driver(headless=False)
    wait = WebDriverWait(driver, 60)

    try:
        result = login_and_search(driver, wait, hash_value)
        
        if result:
            result["task_uuid"] = "found_via_search"
            result["report_url"] = driver.current_url
            print("\n" + json.dumps([result], indent=2, ensure_ascii=False))
        else:
            print("[-] Hash not found")
            print("[]")

    except TimeoutException:
        driver.switch_to.default_content()
        print("[-] Timeout during operation")
        driver.save_screenshot("/tmp/search_error.png")
        print("[*] Screenshot saved to /tmp/search_error.png")
        print(f"[*] Current URL: {driver.current_url}")
        print(f"[*] Page title: {driver.title}")
    except Exception as e:
        driver.switch_to.default_content()
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("/tmp/search_error.png")
        print("[*] Screenshot saved to /tmp/search_error.png")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()