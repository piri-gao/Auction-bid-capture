import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from bid import run_bid
from collections import deque
import csv
import os
import signal

# 配置
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe" # chrome.exe所在目录
CHROME_USER_DATA_TEMPLATE = r"C:\chrome-temp\session-%d" 
DEBUG_PORT_BASE = 9000  # 浏览器启动的port
TASK_PATH = "tasks.csv" # 任务文件
MAX_CONCURRENT = 8      # 同时执行的进程数：一次打开的网页数量
INTERVAL_SECONDS = 60   # 监控间隔时间



chrome_proc_dict = {}  # 用于保存 Chrome 子进程

def read_tasks(csv_path):
    tasks = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task = {
                "url": row["url"],
                "my_code": row["my_code"],
                "price_th":row["price_th"]
            }
            tasks.append(task)
    return tasks

def start_chrome(idx, url):
    user_data_dir = CHROME_USER_DATA_TEMPLATE % idx
    debug_port = DEBUG_PORT_BASE + idx
    print(f"🚀 启动Chrome[{idx}]：{url}")
    proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        url
    ])
    time.sleep(5)  # 等待页面加载
    return proc

def restart_chrome(idx, url):
    print(f"🔁 重启Chrome[{idx}]...")
    if idx in chrome_proc_dict:
        proc = chrome_proc_dict.pop(idx)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
    proc = start_chrome(idx, url)
    chrome_proc_dict[idx] = proc

def safe_run_bid_with_timeout(my_code, debug_port, price_th, url, idx, timeout=60):
    def _target():
        return run_bid(my_code, debug_port, price_th, url, idx)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_target)
        return future.result(timeout=timeout)


def process_task(task_idx_url_my_code):
    idx, task = task_idx_url_my_code
    url = task["url"]
    my_code = task["my_code"]
    price_th = int(task["price_th"])
    debug_port = DEBUG_PORT_BASE + idx

    # 启动Chrome（如果没启动）
    if idx not in chrome_proc_dict:
        chrome_proc_dict[idx] = start_chrome(idx, url)

    try:
        result = safe_run_bid_with_timeout(my_code, debug_port, price_th, url, idx)
        if not result:
            print(f"⚠️[任务 {idx}] 未捕获竞价信息，准备重试...")
            restart_chrome(idx, url)
            return False, task_idx_url_my_code
    except Exception as e:
        print(f"❌[任务 {idx}] 出错: {e}")
        restart_chrome(idx, url)
        return False, task_idx_url_my_code

    print(f"✅[任务 {idx}] 成功处理")
    return True, None

def run_one_round(round_id, initial_tasks):
    print(f"\n⏱️ 第 {round_id} 轮开始")
    task_queue = deque(enumerate(initial_tasks))
    processed_count = 0
    batch_count = 0

    while task_queue:
        batch_count += 1
        current_batch = []

        while len(current_batch) < MAX_CONCURRENT and task_queue:
            current_batch.append(task_queue.popleft())

        print(f"\n🔄 批次 {batch_count}：任务数 {len(current_batch)}")
        with ThreadPoolExecutor(max_workers=len(current_batch)) as executor:
            results = list(executor.map(process_task, current_batch))

        for success, task in results:
            if success:
                processed_count += 1
            elif task is not None:
                task_queue.append(task)

        print(f"📊 本轮已完成: {processed_count}, 剩余重试: {len(task_queue)}")

    print(f"\n✅ 第 {round_id} 轮任务完成\n")

def main():
    initial_tasks = read_tasks(TASK_PATH)
    round_id = 0
    while True:
        round_id += 1
        start_time = time.time()

        run_one_round(round_id, initial_tasks)

        elapsed = time.time() - start_time
        wait_time = INTERVAL_SECONDS - elapsed
        if wait_time > 0:
            print(f"⏸️ 等待 {int(wait_time)} 秒后开始下一轮...\n")
            time.sleep(wait_time)
        else:
            print(f"⚠️ 本轮耗时 {int(elapsed)} 秒，立即开始下一轮\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 终止程序，正在关闭所有Chrome进程...")
        for idx, proc in chrome_proc_dict.items():
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ 所有Chrome进程已关闭。")
