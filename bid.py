from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import sys
import csv
import os


def pop_win_process(driver, task_num):
    try:
        confirm_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "alert-popup-button-confirm"))
        )
        confirm_btn.click()
        print(f"✅ [任务 {task_num}] 点击了弹窗的‘我知道了’按钮")
    except Exception as e:
        print(f"⚠️ [任务 {task_num}]  没有检测到‘我知道了’按钮，可能弹窗没有出现")
        # print("错误信息：", e)

def get_highest_price(driver, task_num):
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        for row in rows:
            cols = row.find_elements(By.CSS_SELECTOR, "td > div")
            if len(cols) >= 3 and cols[0].text.strip() == "领先":
                bid_code = cols[1].text.strip()        
                price_text = cols[2].text.strip()     
                bid_time = cols[3].text.strip()    
                # 进一步去掉 ￥ 和逗号
                price_value = int(price_text.replace("￥", "").replace(",", ""))

                print(f"✅ [任务 {task_num}] 当前领先竞价编码: {bid_code}")
                print(f"✅ [任务 {task_num}] 当前最高出价: {price_value}")
                return bid_code, price_value, bid_time  # 找到后立即返回
        
        # 如果循环完成但没找到
        print(f"⚠️ [任务 {task_num}] 没有检测到出价信息")
        return False
    except Exception as e:
        print(f"⚠️ [任务 {task_num}] 获取出价信息时出错")
        # print("错误信息：", e)
        return False

def write_to_csv(url, bid_code, price_value, bid_time, need_bid, task_num=0, csv_path="bids.csv"):
    """
    将竞价信息追加写入 CSV 文件。
    若文件不存在则创建并写入表头。
    若已存在相同记录（bid_code, price_value, bid_time），则跳过写入。
    """
    record = [url, bid_code, price_value, bid_time, need_bid]
    file_exists = os.path.isfile(csv_path)

    # 检查是否已存在相同记录
    if file_exists:
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过表头
                for row in reader:
                    if row == list(map(str, record)):
                        print(f"⚠️ [任务 {task_num}] 已存在记录，跳过写入: {record}")
                        return
        except Exception as e:
            print(f"⚠️ [任务 {task_num}] 读取 CSV 失败：{e}")
            # 即使失败，仍继续尝试写入

    # 写入新记录
    try:
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["url", "bid_code", "price_value", "bid_time", "need_bid"])
            writer.writerow(record)
        print(f"✅ [任务 {task_num}] 已写入 CSV: {record}")
    except Exception as e:
        print(f"⚠️ [任务 {task_num}] 写入 CSV 失败：{e}")

def offer_price(driver, task_num):
    pass

def run_bid(my_code, debug_port, price_th, url, task_num=0):
    # 配置浏览器
    options = Options()
    options.add_argument("--headless")  # 如想看到浏览器界面可注释掉此行
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("debuggerAddress", "127.0.0.1:{}".format(debug_port))
    driver_path = "./chromedriver.exe" 
    service = Service(driver_path, log_path=os.devnull)
    # 启动浏览器
    driver  = webdriver.Chrome(service=service, options=options)
    
    pop_win_process(driver, task_num)
    result = get_highest_price(driver, task_num)
    if result is False:
        return False
    else:
        bid_code, price_value, bid_time = result
    
    if bid_code and bid_code != my_code and price_value and price_value < price_th:
        need_bid = "True"
        offer_price(driver, task_num)
    else:
        need_bid = "False"
    write_to_csv(url, bid_code, price_value, bid_time, need_bid, task_num)
    driver.quit()
    return True

if __name__ == "__main__":
    if len(sys.argv) > 5:
        my_code = int(sys.argv[1])
        debug_port = int(sys.argv[2])
        price_th = int(sys.argv[3])
        url = sys.argv[4]
        task_num = int(sys.argv[5])
    else:
        print("参数数量不足！")
        raise 
    run_bid(my_code, debug_port, price_th, url, task_num)
