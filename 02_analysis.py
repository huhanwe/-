import pandas as pd
import jieba
import re
import os
import platform
import logging
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from gensim import corpora, models
from gensim.models.coherencemodel import CoherenceModel
import pyLDAvis
import pyLDAvis.gensim_models

# ================= 配置区 =================
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "results"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

# 字体配置
def get_font_path():
    system_name = platform.system()
    if system_name == "Windows":
        paths = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
        for p in paths:
            if os.path.exists(p): return p
    elif system_name == "Darwin":
        return "/System/Library/Fonts/PingFang.ttc"
    return None
FONT_PATH = get_font_path()

# 停用词
STOPWORDS = set([
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '我们', 
    'the', 'a', 'to', 'of', 'in', 'and', 'is', 'that', 'for', 'on', 'it', 'with', 'as', 'be', 'are', 'this', 'by', 'from',
    '记者', '编辑', '报道', '来源', '图片', 'video', 'image', 'loading', 'share', 'nan', '月', '日', '年'
])

# ================= 核心函数 =================

def preprocess_text(text, lang):
    if not isinstance(text, str): return []
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s\u4e00-\u9fa5]', '', text) 
    text = text.lower()
    
    tokens = []
    if lang == 'domestic':
        jieba.add_word("人工智能")
        jieba.add_word("自主研发")
        jieba.add_word("新质生产力")
        jieba.add_word("大模型")
        jieba.add_word("算力")
        words = jieba.lcut(text)
        tokens = [w for w in words if len(w) > 1 and w not in STOPWORDS]
    else:
        words = text.split()
        tokens = [w for w in words if len(w) > 2 and w not in STOPWORDS]
    return tokens

def compute_coherence_values(dictionary, corpus, texts, limit, start=2, step=1):
    """
    【学术级功能】遍历不同的主题数 k，计算一致性得分
    用于寻找最佳主题数 (Optimal Number of Topics)
    """
    coherence_values = []
    model_list = []
    logger.info("开始进行主题数寻优 (Optimal K Search)...")
    
    for num_topics in range(start, limit, step):
        model = models.LdaModel(corpus=corpus, num_topics=num_topics, id2word=dictionary, passes=10, random_state=42)
        model_list.append(model)
        coherencemodel = CoherenceModel(model=model, texts=texts, dictionary=dictionary, coherence='c_v', processes=1)
        score = coherencemodel.get_coherence()
        coherence_values.append(score)
        logger.info(f"  -> 主题数 k={num_topics}, Coherence Score={score:.4f}")
    
    return model_list, coherence_values

def plot_coherence(coherence_values, start, limit, step, media_type):
    """绘制一致性得分折线图"""
    x = range(start, limit, step)
    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot(x, coherence_values, marker='o')
    plt.xlabel("Num Topics (k)")
    plt.ylabel("Coherence Score")
    plt.title(f"Optimal Topic Number Analysis ({media_type})")
    plt.grid(True)
    save_path = os.path.join(OUTPUT_DIR, f"coherence_chart_{media_type}.png")
    plt.savefig(save_path)
    logger.info(f"✅ 参数寻优图已保存: {save_path}")
    # plt.show() # 如果不需要弹出窗口可注释掉

def run_thesis_level_lda(df, media_type):
    print(f"\n====== 正在分析: {media_type} 媒体 ======")
    
    subset = df[df['media_type'] == media_type]
    if len(subset) == 0: return

    docs = subset.apply(lambda x: preprocess_text(str(x['title']) + " " + str(x['text']), media_type), axis=1).tolist()
    dictionary = corpora.Dictionary(docs)
    dictionary.filter_extremes(no_below=1, no_above=1.0)
    corpus = [dictionary.doc2bow(text) for text in docs]

    if len(dictionary) == 0: return

    # --- 步骤 1: 参数寻优 (The Scientific Method) ---
    # 模拟从 2 到 9 个主题，看哪个得分最高
    limit = 9; start = 2; step = 1
    model_list, coherence_values = compute_coherence_values(dictionary, corpus, docs, limit, start, step)
    
    # 绘制寻优图
    plot_coherence(coherence_values, start, limit, step, media_type)
    
    # 自动选择得分最高的模型
    best_score_idx = coherence_values.index(max(coherence_values))
    best_k = start + best_score_idx * step
    best_model = model_list[best_score_idx]
    
    logger.info(f"🏆 最佳主题数是 k={best_k} (得分: {max(coherence_values):.4f})")
    
    # --- 步骤 2: 输出最佳模型的主题 ---
    topics = best_model.print_topics(num_words=5)
    for topic in topics:
        print(topic)

    # --- 步骤 3: 词云图 (Basic Vis) ---
    all_words = " ".join([" ".join(doc) for doc in docs])
    wc = WordCloud(font_path=FONT_PATH, width=1600, height=800, background_color='white',
                   max_words=100, colormap='flag' if media_type == 'foreign' else 'Reds').generate(all_words)
    wc.to_file(os.path.join(OUTPUT_DIR, f"wordcloud_{media_type}.png"))

    # --- 步骤 4: 交互式可视化 (Advanced Vis - pyLDAvis) ---
    # 生成 HTML 文件，答辩时可以直接打开浏览器展示
    try:
        vis = pyLDAvis.gensim_models.prepare(best_model, corpus, dictionary)
        html_path = os.path.join(OUTPUT_DIR, f"lda_vis_{media_type}.html")
        pyLDAvis.save_html(vis, html_path)
        logger.info(f"✅ 交互式可视化网页已生成: {html_path}")
    except Exception as e:
        logger.warning(f"pyLDAvis 生成失败 (可能是数据量太小): {e}")

# ================= 主程序 =================

if __name__ == "__main__":
    if os.path.exists("news_data.csv"):
        df = pd.read_csv("news_data.csv")
        run_thesis_level_lda(df, "domestic")
        run_thesis_level_lda(df, "foreign")
    else:
        print("请先运行爬虫。")