# 出价监测

采用selenium避开某拍卖网站的反爬，监测出价情况

## 步骤1 配置chrome driver

首先需要有chrome浏览器，在chrome浏览器地址栏输入`chrome://version/`获得浏览器版本。

然后根据版本在[ChromeDriver Download](https://developer.chrome.com/docs/chromedriver/downloads?hl=zh-cn)下载`chromedriver.exe`放置到当前目录下。

## 步骤2 配置运行环境

创建conda环境

```
conda create -n bid python=3.10

conda activate bid
```
安装selenium

```
pip install selenium=4.11.2
```

## 步骤3 编写tasks.csv

tasks.csv有三列：

| url     | my_code  | price_th   |
|---------|----------|------------|
| 网址    | 你的编号  | 出价阈值   |

出价阈值指当前出价高于此值就不考虑继续出价。

## 步骤4 编写脚本内配置 

在run.py中修改配置，参考其中注释，一般只需要修改CHROME_PATH、MAX_CONCURRENT、INTERVAL_SECONDS。



## 步骤5 运行程序



多进程版本。当进程多时存在首次打开网页不跳转的问题。

```
python run_mp.py
```

多进程手动打开网页版本。根据命令行提示手动跳转页面，最稳妥。

```
python run_mp_hand.py
```


多线程版本。内存消耗少，但运行不稳定，速度慢，不推荐。

```
python run_mt.py
```

## 步骤6 查看监测结果

程序会在命令行输出运行结果，并且会在当前目录输出一个`bids.csv`文件，包含以下内容：

| url     | bid_code     | price_value| bid_time      | need_bid      |
|---------|--------------|------------| --------------|---------------|
| 网址    | 最高出价编号  | 最高出价    | 最高出价时间   | 你是否需要出价  |