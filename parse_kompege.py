import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

DOWNLOAD_DIR = os.path.join(os.getcwd(), 'files')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PROFILE_DIR = os.path.join(os.getcwd(), 'C:\\selenium_profile')
os.makedirs(PROFILE_DIR, exist_ok=True)

chrome_options = Options()
chrome_options.add_argument(f'--user-data-dir={PROFILE_DIR}')
chrome_options.add_experimental_option('prefs', {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
})

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 45)

BASE_URL = 'https://kompege.ru/lk'

try:
    driver.get(BASE_URL)

    wait.until(EC.presence_of_element_located(
        (By.XPATH, '/html/body/div/div/div[3]/table')
    ))

    rows = driver.find_elements(
        By.XPATH, '/html/body/div/div/div[3]/table/tbody[3]/tr'
    )
    print(f'Найдено работ: {len(rows)}')

    for idx in range(1, len(rows) + 1):
        try:
            print(f'Обрабатываю файл {idx}...')

            original_window = driver.current_window_handle

            btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 f'/html/body/div/div/div[3]/table/tbody[3]/tr[{idx}]/td[2]')
            ))
            btn.click()

            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//p[@class="link" and contains(text(), "Скачать JSON")]')
            )).click()

            wait.until(lambda d: len(d.window_handles) > 1)
            new_window = [w for w in driver.window_handles if w != original_window][0]
            driver.switch_to.window(new_window)

            time.sleep(1)
            json_text = driver.find_element(By.TAG_NAME, 'body').text

            filename = os.path.join(DOWNLOAD_DIR, f'variant_{idx}.json')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_text)
            print(f'  Сохранён {filename}')

            driver.close()
            driver.switch_to.window(original_window)

            driver.back()
            wait.until(EC.presence_of_element_located(
                (By.XPATH, '/html/body/div/div/div[3]/table')
            ))
            rows = driver.find_elements(
                By.XPATH, '/html/body/div/div/div[3]/table/tbody[3]/tr'
            )

        except Exception as e:
            print(f'Ошибка в строке {idx}: {e}')
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            driver.get(BASE_URL)
            wait.until(EC.presence_of_element_located(
                (By.XPATH, '//table')
            ))
            rows = driver.find_elements(
                By.XPATH, '/html/body/div/div/div[3]/table/tbody[3]/tr'
            )

    print(f'Готово. JSON сохранены в {DOWNLOAD_DIR}/')

finally:
    driver.quit()
