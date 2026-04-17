import re, time, random
import requests, streamlit as st, pandas as pd
from bs4 import BeautifulSoup

# ── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Job Scanner Pro", page_icon="⚡", layout="wide")

# ── CSS (ПОВЕРНУТО ПОПЕРЕДНІЙ СТИЛЬ) ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; background-color: #f8fafc !important; }

/* Метрики */
.metric-box { background: white; padding: 1.2rem; border-radius: 14px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
.metric-val { font-family: 'DM Mono', monospace; font-size: 1.7rem; font-weight: 700; color: #2563eb; line-height: 1; }
.metric-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; font-weight: 700; margin-top: 8px; letter-spacing: 0.05em; }

/* Картки */
.stExpander { background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 12px !important; margin-bottom: 0.8rem !important; }
.desc-text { line-height: 1.6; color: #334155; font-size: 0.95rem; }

#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── LOGIC ───────────────────────────────────────────────────────────────────

def is_strictly_remote(title, desc):
    """Жорстка перевірка на віддалену роботу через усі аліаси"""
    remote_aliases = [
        r"віддален", r"дистанційн", r"remote", r"home-office", 
        r"вдома", r"дом[ау]", r"online", r"онлайн", r"work from anywhere"
    ]
    full_text = (str(title) + " " + str(desc)).lower()
    return any(re.search(alias, full_text) for alias in remote_aliases)

def format_description(text):
    if not text or len(text) < 50: return text
    sections = {
        "🎯 Вимоги:": [r"вимог", r"очікуєм", r"вміння", r"досвід"],
        "🛠 Обов'язки:": [r"обов'язк", r"що робити", r"завдання"],
        "🎁 Умови:": [r"умов", r"пропонуєм", r"ми гарант", r"графік"]
    }
    formatted = text
    for label, keys in sections.items():
        pattern = re.compile(f"({'|'.join(keys)})", re.IGNORECASE)
        formatted = pattern.sub(f"<br><br><b>{label}</b><br>", formatted)
    return formatted

def get_job_description(url):
    try:
        time.sleep(random.uniform(0.4, 0.8))
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, timeout=7, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        desc_div = soup.find("div", id="job-description") or soup.find("div", class_="job-description-content")
        return desc_div.get_text("\n", strip=True) if desc_div else ""
    except: return ""

def calc_score(title, desc, filters):
    score = 0
    text = (str(title) + " " + str(desc)).lower()
    for word, weight in filters.items():
        if str(word).lower() in text: score += weight
    return score

# ── PARSER ──────────────────────────────────────────────────────────────────

def run_scanner(pages, filters):
    jobs = []
    STOP_WORDS = ["водій", "кур'єр", "експедитор", "зсу", "охоронець", "кухар", "вантажник"]
    bar = st.progress(0); status = st.empty()
    
    for p in range(1, pages + 1):
        status.caption(f"Аналіз сторінки {p}...")
        try:
            r = requests.get(f"https://www.work.ua/jobs-remote/?page={p}", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"job-link|card-hover"))
            
            for c in cards:
                t_tag = c.find("h2").find("a")
                title = t_tag.get_text(strip=True)
                if any(sw in title.lower() for sw in STOP_WORDS): continue
                
                link = "https://www.work.ua" + t_tag["href"]
                desc = get_job_description(link)
                
                # ЖОРСТКИЙ ФІЛЬТР: Тільки якщо підтверджено Remote
                if not is_strictly_remote(title, desc): continue
                
                sal = c.find("b", string=re.compile(r'\d')).get_text(strip=True) if c.find("b", string=re.compile(r'\d')) else "Не вказана"
                jobs.append({"title": title, "salary": sal, "link": link, "desc": desc})
        except: continue
        bar.progress(p / pages)
    
    status.empty(); bar.empty()
    if not jobs: return pd.DataFrame()
    df = pd.DataFrame(jobs)
    df["score"] = df.apply(lambda r: calc_score(r["title"], r["desc"], filters), axis=1)
    df["match"] = df["score"].apply(lambda s: min(100, max(0, int((float(s) + 20) * 2))))
    return df

# ── INTERFACE ───────────────────────────────────────────────────────────────

if "filters" not in st.session_state:
    st.session_state["filters"] = {"crm": 8, "автоматиза": 9, "excel": 5, "дашборд": 7, "Python": 6}

with st.sidebar:
    st.title("⚙️ Налаштування")
    updated_filters = {}
    for word, weight in st.session_state["filters"].items():
        c1, c2 = st.columns([3, 2])
        w = c1.text_input("Слово", word, key=f"k_{word}", label_visibility="collapsed")
        v = c2.number_input("Вага", value=weight, key=f"v_{word}", label_visibility="collapsed")
        updated_filters[w] = v
    
    if st.button("➕ Додати критерій"):
        st.session_state["filters"]["new_word"] = 5
        st.rerun()
    
    if st.button("💾 Застосувати", use_container_width=True):
        st.session_state["filters"] = updated_filters
        st.rerun()

    st.divider()
    pages = st.number_input("Кількість сторінок", 1, 15, 3)
    if st.button("🚀 Почати сканування", use_container_width=True):
        st.session_state["df"] = run_scanner(pages, st.session_state["filters"])

# Main Area
st.title("Job Intelligence Dashboard")

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Знайдено</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df[df["match"] >= 75])}</div><div class="metric-lbl">Топ Match</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-box"><div class="metric-val">{int(df["match"].mean())}%</div><div class="metric-lbl">Сер. Релевантність</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-box"><div class="metric-val">100%</div><div class="metric-lbl">Remote Only</div></div>', unsafe_allow_html=True)
    with m5: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df[df["salary"] != "Не вказана"])}</div><div class="metric-lbl">З зарплатою</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    col_s1, col_s2 = st.columns([2, 1])
    with col_s1: search_query = st.text_input("🔍 Пошук за ключовим словом (назва/опис)", "")
    with col_s2: min_p = st.slider("Мін. % Match", 0, 100, 30)

    view = df[df["match"] >= min_p]
    if search_query:
        view = view[view["title"].str.contains(search_query, case=False) | view["desc"].str.contains(search_query, case=False)]

    for _, row in view.sort_values("match", ascending=False).iterrows():
        m_color = "#16a34a" if row["match"] >= 75 else ("#ca8a04" if row["match"] >= 45 else "#64748b")
        with st.expander(f"{row['match']}% — {row['title']}"):
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                <b style="color:{m_color}; font-size:1.2rem;">{row['match']}% Match</b>
                <b style="color:#1e293b; font-size:1rem;">💰 {row['salary']}</b>
            </div>
            <div class="desc-text">
                {format_description(row['desc'])}
            </div>
            <div style="margin-top:15px;">
                <a href="{row['link']}" target="_blank" style="color:#2563eb; font-weight:700; text-decoration:none;">🔗 Відкрити оригінал на Work.ua</a>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("👋 Налаштуйте фільтри та запустіть пошук.")