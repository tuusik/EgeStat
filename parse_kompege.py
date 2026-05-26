import logging
import os
import re
import time
from typing import Any, Callable, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from tqdm import tqdm

logger = logging.getLogger(__name__)

DOWNLOAD_DIR: str = os.path.join(os.getcwd(), 'files')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PROFILE_DIR: str = os.path.join(os.getcwd(), 'C:\\selenium_profile')
os.makedirs(PROFILE_DIR, exist_ok=True)

chrome_options = Options()
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument(f'--user-data-dir={PROFILE_DIR}')
chrome_options.add_experimental_option('prefs', {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
})

driver: webdriver.Chrome = webdriver.Chrome(options=chrome_options)
wait: WebDriverWait = WebDriverWait(driver, 45)

BASE_URL: str = 'https://kompege.ru/lk'

MAX_RETRIES: int = 3


def retry_on_error(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except WebDriverException as e:
            if attempt == MAX_RETRIES:
                raise
            logger.warning("Ошибка (попытка %d/%d): %s", attempt, MAX_RETRIES, e)
            time.sleep(2)
    return None


def process_variant(idx: int) -> Optional[str]:
    idx1: int = idx + 1
    original_window: str = driver.current_window_handle

    btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         f'/html/body/div/div/div[3]/table/tbody[3]/tr[{idx1}]/td[2]')
    ))
    btn.click()

    wait.until(EC.element_to_be_clickable(
        (By.XPATH, '//p[@class="link" and contains(text(), "Скачать JSON")]')
    )).click()

    wait.until(lambda d: len(d.window_handles) > 1)
    new_window: str = [w for w in driver.window_handles if w != original_window][0]
    driver.switch_to.window(new_window)

    time.sleep(1)
    json_text: str = driver.find_element(By.TAG_NAME, 'body').text

    driver.close()
    driver.switch_to.window(original_window)
    return json_text


try:
    driver.get(BASE_URL)

    wait.until(EC.presence_of_element_located(
        (By.XPATH, '/html/body/div/div/div[3]/table')
    ))

    rows = driver.find_elements(
        By.XPATH, '/html/body/div/div/div[3]/table/tbody[3]/tr'
    )
    names: list[str] = []
    for idx in range(1, len(rows) + 1):
        try:
            name_elem = driver.find_element(
                By.XPATH, f'/html/body/div/div/div[3]/table/tbody[3]/tr[{idx}]/td[1]/span'
            )
            safe_name: str = re.sub(r'[\\/*?:"<>|]', '_', name_elem.text.strip())
            names.append(safe_name if safe_name else f'variant_{idx}')
        except Exception:
            names.append(f'variant_{idx}')

    for idx in tqdm(range(len(rows)), desc="Обработка работ", unit="файл"):
        try:
            json_text = retry_on_error(process_variant, idx)
        except Exception:
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
            continue

        filename: str = os.path.join(DOWNLOAD_DIR, f'{names[idx]}.json')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json_text)
        logger.info("Сохранён %s", filename)

        driver.back()
        wait.until(EC.presence_of_element_located(
            (By.XPATH, '/html/body/div/div/div[3]/table')
        ))
        rows = driver.find_elements(
            By.XPATH, '/html/body/div/div/div[3]/table/tbody[3]/tr'
        )

finally:
    driver.quit()
