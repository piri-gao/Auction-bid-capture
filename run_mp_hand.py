import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from bid import run_bid
from collections import deque
import csv
import os
import socket
import json
import urllib.request
import signal

# 配置
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"  # chrome.exe所在目录
CHROME_USER_DATA_TEMPLATE = r"C:\chrome-temp\session-%d"
DEBUG_PORT_BASE = 9000  # 浏览器启动的port
TASK_PATH = "tasks.csv"  # 任务文件
MAX_CONCURRENT = 50  # 同时执行的进程数：一次打开的网页数量
INTERVAL_SECONDS = 60  # 监控间隔时间
WAIT_OPEN_SECONDS = 600  # 手动打开网页等待时间


chrome_proc_dict = {}  # 用于保存 Chrome 子进程


def read_tasks(csv_path):
    tasks = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task = {
                "url": row["url"],
                "my_code": row["my_code"],
                "price_th": row["price_th"]
            }
            tasks.append(task)
    return tasks



def wait_for_debug_port(port, timeout=10):
    """等待 Chrome 调试端口开放"""
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def get_chrome_tabs(debug_port):
    """获取当前 Chrome 标签页列表"""
    try:
        with urllib.request.urlopen(f"http://localhost:{debug_port}/json") as response:
            return json.loads(response.read())
    except:
        return []


def check_url_loaded(debug_port, target_url):
    """检查是否有标签页 URL 包含目标链接"""
    tabs = get_chrome_tabs(debug_port)
    for tab in tabs:
        if target_url in tab.get("url", ""):
            return True
    return False

def kill_chrome(pid):
    try:
        if pid:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            os.system(f"taskkill /F /PID {pid} >nul 2>&1")
    except Exception as e:
        print(f"⚠️ 无法终止进程 {pid}: {e}")


def start_chrome(idx, url, max_retry=1):
    user_data_dir = CHROME_USER_DATA_TEMPLATE % idx
    debug_port = DEBUG_PORT_BASE + idx

    os.makedirs(user_data_dir, exist_ok=True)

    args = [
        CHROME_PATH,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-component-update",
        "--start-maximized",
        # ⚠️ 不自动跳转网页，改为你手动跳转
        # url,
    ]

    for attempt in range(1 + max_retry):
        print(f"🚀 启动 Chrome[{idx}] 尝试 {attempt + 1}：请手动打开 {url}")
        proc = subprocess.Popen(args)
        time.sleep(3)

        if wait_for_debug_port(debug_port, timeout=10):
            print(f"🔍 等待你手动跳转到：{url}")
            wait_start = time.time()
            while time.time() - wait_start < WAIT_OPEN_SECONDS:
                if check_url_loaded(debug_port, url):
                    print(f"✅ Chrome[{idx}] 页面加载成功")
                    return proc.pid
                else:
                    print(f"⏳ 等待你在 Chrome[{idx}] 手动跳转到 {url} ...")
                    time.sleep(2)
            print(f"⚠️ Chrome[{idx}] 页面未检测到目标 URL：{url}")
            return proc.pid  # 返回PID，让后续程序继续尝试运行
        else:
            print(f"❌ Chrome[{idx}] 调试端口未开放")

        kill_chrome(proc.pid)
        time.sleep(1)

    print(f"❌ Chrome[{idx}] 启动失败")
    return None

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


def run_bid_wrapper(args):
    my_code, debug_port, price_th, url, idx = args
    return run_bid(my_code, debug_port, price_th, url, idx)


def safe_run_bid_with_timeout(my_code, debug_port, price_th, url, idx, timeout=60):
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_bid_wrapper, (my_code, debug_port, price_th, url, idx))
        return future.result(timeout=timeout)


# 改动点：process_task 只调用 run_bid，不做chrome管理
def process_task(task_idx_url_my_code):
    idx, task = task_idx_url_my_code
    url = task["url"]
    my_code = task["my_code"]
    price_th = int(task["price_th"])
    debug_port = DEBUG_PORT_BASE + idx

    try:
        result = safe_run_bid_with_timeout(my_code, debug_port, price_th, url, idx)
        return idx, result, task
    except Exception as e:
        print(f"❌[任务 {idx}] 出错: {e}")
        return idx, None, task


def run_one_round(round_id, initial_tasks):
    print(f"\n⏱️ 第 {round_id} 轮开始")
    task_queue = deque(enumerate(initial_tasks))
    processed_count = 0
    batch_count = 0

    # 先统一启动所有 Chrome 进程
    for idx, task in enumerate(initial_tasks):
        if idx not in chrome_proc_dict:
            pid = start_chrome(idx, task["url"])
            if pid:
                chrome_proc_dict[idx] = pid
            else:
                print(f"🚫 Chrome[{idx}] 启动失败，请等待后续重启")

    while task_queue:
        batch_count += 1
        current_batch = []

        while len(current_batch) < MAX_CONCURRENT and task_queue:
            current_batch.append(task_queue.popleft())

        print(f"\n🔄 批次 {batch_count}：任务数 {len(current_batch)}")
        with ProcessPoolExecutor(max_workers=len(current_batch)) as executor:
            results = list(executor.map(process_task, current_batch))

        for idx, result, task in results:
            if result:
                print(f"✅[任务 {idx}] 成功处理")
                processed_count += 1
            else:
                print(f"⚠️[任务 {idx}] 未捕获竞价信息或失败，重启Chrome...")
                restart_chrome(idx, task["url"])
                task_queue.append((idx, task))

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
