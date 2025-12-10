import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from textblob import TextBlob
from snownlp import SnowNLP
import os
import matplotlib

# ================= 配置区 =================
# 配置绘图风格 (Seaborn 风格，更加学术)
sns.set_theme(style="whitegrid")
# 解决中文显示问题
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = "results"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

# ================= 核心分析逻辑 =================

def analyze_sentiment(text, media_type):
    """
    计算情感得分
    国内媒体 -> SnowNLP (0-1) -> 归一化到 (-1, 1)
    国外媒体 -> TextBlob (-1, 1)
    """
    text = str(text)
    score = 0
    
    try:
        if media_type == 'foreign':
            blob = TextBlob(text)
            score = blob.sentiment.polarity # [-1, 1]
        else:
            s = SnowNLP(text)
            # SnowNLP 原始分是概率值 [0, 1]，0.5 是中性
            # 映射公式: (score - 0.5) * 2 -> 转换到 [-1, 1] 区间以便对比
            score = (s.sentiments - 0.5) * 2 
    except:
        score = 0
        
    return score

def get_stance_label(score):
    """根据分数打标签 (复现 PPT 第 66-72 页逻辑)"""
    if score < -0.1:
        return "Critical (批判)"
    elif score > 0.1:
        return "Supportive (积极)"
    else:
        return "Neutral (中立)"

# ================= 主程序 =================

if __name__ == "__main__":
    if not os.path.exists("news_data.csv"):
        print("错误: 未找到数据文件。")
        exit()
        
    df = pd.read_csv("news_data.csv")
    print(f"正在分析 {len(df)} 条数据的情感倾向...")
    
    # 1. 计算情感得分
    df['sentiment_score'] = df.apply(lambda x: analyze_sentiment(x['title'] + str(x['text']), x['media_type']), axis=1)
    df['stance'] = df['sentiment_score'].apply(get_stance_label)
    
    # 2. 绘制饼图 (总体立场对比) - PPT Slide 68, 70
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    
    # 颜色映射
    palette = {"Supportive (积极)": "#66b3ff", "Neutral (中立)": "#99ff99", "Critical (批判)": "#ff9999"}
    
    for i, m_type in enumerate(['domestic', 'foreign']):
        subset = df[df['media_type'] == m_type]
        if len(subset) > 0:
            counts = subset['stance'].value_counts()
            # 绘制饼图
            axes[i].pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=140, 
                        colors=[palette.get(x, '#cccccc') for x in counts.index],
                        wedgeprops={'alpha': 0.8})
            axes[i].set_title(f"{m_type.capitalize()} Media Stance", fontsize=14, fontweight='bold')
    
    plt.suptitle("Sentiment Analysis: Domestic vs Foreign", fontsize=16)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "sentiment_pie.png"))
    print("✅ 情感分布饼图已保存。")
    plt.show()
    
    # 3. 【高级功能】绘制时间趋势图 - PPT Slide 73-77 (变化趋势)
    # 如果数据包含不同日期，我们可以画出趋势线
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df.sort_values('date')
        
        plt.figure(figsize=(12, 6), dpi=150)
        
        # 使用 Seaborn 绘制平滑趋势线
        sns.lineplot(data=df, x='date', y='sentiment_score', hue='media_type', 
                     style='media_type', markers=True, dashes=False, linewidth=2.5)
        
        plt.axhline(0, color='gray', linestyle='--', alpha=0.5) # 0分基准线
        plt.title("Sentiment Trend Analysis (2023-2025)", fontsize=15)
        plt.ylabel("Sentiment Score (-1=Critical, 1=Supportive)")
        plt.xlabel("Date")
        plt.legend(title="Media Type")
        
        save_path = os.path.join(OUTPUT_DIR, "sentiment_trend.png")
        plt.savefig(save_path)
        print(f"✅ 情感趋势图已保存至: {save_path}")
        plt.show()
    except Exception as e:
        print(f"日期数据不足以绘制趋势图，跳过。(Error: {e})")