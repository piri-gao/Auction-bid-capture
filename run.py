import subprocess
import time
from multiprocessing import Pool
from BID.bid import run_bid
from collections import deque
import csv

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe" #chrome位置
CHROME_USER_DATA_TEMPLATE = r"C:\chrome-temp\session-%d" 
DEBUG_PORT_BASE = 9000
TASK_PATH = "tasks.csv"
MAX_CONCURRENT = 8  # 每批最多并发8个Chrome实例
PRICE_TH = 2000 # 当前最高出价超过此值就不再出价
INTERVAL_SECONDS = 60  # 每轮间隔时间（单位：秒）

# 初始任务列表（你可以加更多 URL）

def read_tasks(csv_path):
    initial_tasks = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task = {
                "url": row["url"],
                "my_code": row["my_code"]
            }
            initial_tasks.append(task)
    return initial_tasks

def process_task(task_idx_url_my_code, retry_count=0):
    idx, task = task_idx_url_my_code
    url = task["url"]
    my_code = task["my_code"]
    user_data_dir = CHROME_USER_DATA_TEMPLATE % idx
    debug_port = DEBUG_PORT_BASE + idx

    print(f"🔍[任务 {idx}] {'(重试)' if retry_count > 0 else ''}启动Chrome: {url}, my_code={my_code}")
    chrome_proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        # "--headless=new",
        url
    ])
    time.sleep(5)

    try:
        result = run_bid(my_code, debug_port, PRICE_TH, url, idx)
        if not result:
            print(f"⚠️[任务 {idx}] 未捕获到竞价信息，将加入下一批处理")
            return False, task_idx_url_my_code
    except Exception as e:
        print(f"❌[任务 {idx}] run_bid出错: {e}")
        return False, task_idx_url_my_code
    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            chrome_proc.kill()
        print(f"✅[任务 {idx}] 处理完成: {url}")

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
        
        print(f"\n🔄 批次 {batch_count}：任务数: {len(current_batch)}")
        
        with Pool(processes=len(current_batch)) as pool:
            results = pool.map(process_task, current_batch)
        
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
            print(f"⚠️ 本轮耗时 {int(elapsed)} 秒，已超过设定间隔，立即开始下一轮\n")

if __name__ == "__main__":
    main()
