import os
import time
import random
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from newspaper import Article
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= 配置区域 =================
# 1. 强制清除系统代理 (防止 ProxyError)
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['NO_PROXY'] = '*'

# 2. 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 3. 目标 URL (选取更容易抓取的列表页)
URLS = {
    # TechCrunch 人工智能版块
    "foreign": "https://techcrunch.com/category/artificial-intelligence/",
    # 中新网 IT 频道 (国内源)
    "domestic": "http://www.chinanews.com.cn/it/"
}

# 伪装头 (模拟最新的 Chrome)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

data_list = []

# ================= 核心工具函数 =================

def get_robust_session():
    """创建带有重试机制的 Session"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.trust_env = False
    return session

def fetch_links_universal(session, media_type, url):
    """
    【核心改进】：不再依赖具体的 class 名，而是通过 URL 特征进行广谱扫描
    """
    links = []
    logger.info(f"正在广谱扫描 [{media_type}] 站点: {url} ...")
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8' # 强制 UTF-8，中新网有时候会乱码
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 提取页面上所有的 <a> 标签
        all_anchors = soup.find_all('a', href=True)
        
        for a in all_anchors:
            href = a['href']
            title = a.get_text().strip()
            
            # --- 国内中新网筛选规则 ---
            if media_type == "domestic":
                # 规则1: 必须包含 .shtml (中新网新闻页特征)
                # 规则2: 必须包含 /202 (只抓近几年的，去掉老链接)
                # 规则3: 排除 video 视频链接
                if '.shtml' in href and '/202' in href and 'video' not in href:
                    if href.startswith('//'): href = 'http:' + href
                    if not href.startswith('http'): href = 'http://www.chinanews.com.cn' + href
                    links.append(href)

            # --- 国外 TechCrunch 筛选规则 ---
            elif media_type == "foreign":
                # 规则1: 必须包含 /202 (年份)
                # 规则2: 链接长度通常较长 (排除 tag 页)
                if '/202' in href and len(href) > 40:
                    links.append(href)
        
        # 去重并取前 5 条 (为了演示速度)
        links = list(set(links))[:5]
        logger.info(f"  -> 成功匹配到 {len(links)} 条有效文章链接")
        return links
        
    except Exception as e:
        logger.error(f"  -> 扫描失败: {e}")
        return []

def parse_article(url, media_type):
    """解析文章内容"""
    try:
        # 使用 newspaper 解析
        article = Article(url, language='zh' if media_type == 'domestic' else 'en', request_timeout=20)
        article.download()
        article.parse()
        
        # 简单清洗
        if len(article.text) < 50:
            return False

        logger.info(f"    [成功] {article.title[:20]}...")
        data_list.append({
            "title": article.title,
            "text": article.text,
            "date": str(article.publish_date) if article.publish_date else "2025-01-01",
            "media_type": media_type,
            "url": url
        })
        return True
    except Exception as e:
        logger.warning(f"    [跳过] 解析出错: {e}")
        return False

# ================= 主程序 =================

def main():
    session = get_robust_session()
    
    for m_type, url in URLS.items():
        links = fetch_links_universal(session, m_type, url)
        
        for link in links:
            parse_article(link, m_type)
            time.sleep(1) # 礼貌等待
    
    # 保存
    if data_list:
        df = pd.DataFrame(data_list)
        df.to_csv("news_data.csv", index=False, encoding='utf-8-sig')
        logger.info(f"🎉 任务完成！共抓取 {len(df)} 条真实数据。")
    else:
        logger.error("❌ 依然未抓取到数据。建议直接运行 01_fix_data.py 使用补全数据。")

if __name__ == "__main__":
    main()