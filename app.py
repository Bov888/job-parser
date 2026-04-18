import re, time, random
import requests, streamlit as st, pandas as pd
from bs4 import BeautifulSoup

# ── 1. АВТЕНТИФІКАЦІЯ ──────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Вхід у систему")
    pwd = st.text_input("Введіть пароль", type="password")
    if st.button("Увійти"):
        if pwd == st.secrets["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Неправильний пароль")
    return False

# ── 2. НАЛАШТУВАННЯ СТОРІНКИ ──────────────────────────────────────────
st.set_page_config(page_title="Job Scanner", page_icon="⚡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; background-color: #f8fafc !important; }
.metric-box { background: white; padding: 1.2rem; border-radius: 14px; border: 1px solid #e2e8f0; text-align: center; }
.metric-val { font-family: 'DM Mono', monospace; font-size: 1.7rem; font-weight: 700; color: #2563eb; line-height: 1; }
.metric-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; font-weight: 700; margin-top: 8px; }
.stExpander { background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 12px !important; margin-bottom: 0.8rem !important; }
#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

if not check_password():
    st.stop()

# ── 3. ФУНКЦІЇ ПАРСИНГУ (Які раніше "загубилися") ────────────────────

def is_strictly_remote(title, desc):
    remote_aliases = [r"віддален", r"дистанційн", r"remote", r"home-office", r"вдома", r"online", r"онлайн"]
    full_text = (str(title) + " " + str(desc)).lower()
    return any(re.search(alias, full_text) for alias in remote_aliases)

def format_description(text):
    if not text: return "Опис порожній"
    sections = {"🎯 Вимоги:": [r"вимог", r"очікуєм", r"вміння", r"досвід"], "🛠 Обов'язки:": [r"обов'язк", r"що робити", r"завдання"], "🎁 Умови:": [r"умов", r"пропонуєм", r"графік"]}
    formatted = text
    for label, keys in sections.items():
        pattern = re.compile(f"({'|'.join(keys)})", re.IGNORECASE)
        formatted = pattern.sub(f"<br><br><b>{label}</b><br>", formatted)
    return formatted

def get_job_description(url):
    try:
        time.sleep(random.uniform(0.5, 1.0))
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, timeout=10, headers=headers)
        if r.status_code != 200: return ""
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

def run_scanner(pages, filters):
    jobs = []
    STOP_WORDS = ["водій", "кур'єр", "експедитор", "зсу", "охоронець", "кухар", "вантажник", "прибиральн"]
    bar = st.progress(0)
    status = st.empty()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "uk,en-US;q=0.9,en;q=0.8"
    }
    
    for p in range(1, pages + 1):
        status.caption(f"Обробка сторінки {p}...")
        try:
            r = requests.get(f"https://www.work.ua/jobs-remote/?page={p}", timeout=15, headers=headers)
            
            # ДІАГНОСТИКА БЛОКУВАННЯ
            if r.status_code == 403:
                st.sidebar.error("❌ Work.ua заблокував IP-адресу хмарного сервера Streamlit. Зменшіть кількість сторінок або спробуйте пізніше.")
                break
            elif r.status_code != 200:
                st.sidebar.warning(f"⚠️ Помилка сайту (Код {r.status_code}) на сторінці {p}.")
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_=re.compile(r"job-link|card-hover"))
            
            for c in cards:
                t_tag = c.find("h2")
                if not t_tag: continue
                a_tag = t_tag.find("a")
                if not a_tag: continue
                
                title = a_tag.get_text(strip=True)
                if any(sw in title.lower() for sw in STOP_WORDS): continue
                
                link = "https://www.work.ua" + a_tag["href"]
                desc = get_job_description(link)
                
                if not is_strictly_remote(title, desc): continue
                
                sal_tag = c.find("b", string=re.compile(r'\d'))
                sal = sal_tag.get_text(strip=True) if sal_tag else "Не вказана"
                jobs.append({"title": title, "salary": sal, "link": link, "desc": desc})
        except Exception as e:
            st.sidebar.error(f"Технічна помилка на ст. {p}: {e}")
            continue
        bar.progress(p / pages)
    
    status.empty(); bar.empty()
    if not jobs: return pd.DataFrame()
    df = pd.DataFrame(jobs)
    df["score"] = df.apply(lambda r: calc_score(r["title"], r["desc"], filters), axis=1)
    df["match"] = df["score"].apply(lambda s: min(100, max(0, int((float(s) + 20) * 2))))
    return df

# ── 4. ІНТЕРФЕЙС ─────────────────────────────────────────────────────────────

if "filters" not in st.session_state:
    st.session_state["filters"] = {"crm": 8, "автоматиза": 9, "excel": 5, "Python": 6}

with st.sidebar:
    st.title("⚙️ Налаштування")
    updated_filters = {}
    for word, weight in st.session_state["filters"].items():
        c1, c2 = st.columns([3, 2])
        w = c1.text_input("Критерій", word, key=f"k_{word}", label_visibility="collapsed")
        v = c2.number_input("Вага", value=weight, key=f"v_{word}", label_visibility="collapsed")
        updated_filters[w] = v
    
    if st.button("➕ Додати"):
        st.session_state["filters"]["новий"] = 5
        st.rerun()
    if st.button("💾 Оновити", use_container_width=True):
        st.session_state["filters"] = updated_filters
        st.rerun()

    st.divider()
    pages = st.number_input("Сторінок для аналізу", 1, 15, 2)
    if st.button("🚀 ПОЧАТИ СКАНУВАННЯ", use_container_width=True):
        with st.spinner("Збираю дані (не закривайте вкладку)..."):
            st.session_state["df"] = run_scanner(pages, st.session_state["filters"])

st.title("Job Intelligence Dashboard")

if "df" in st.session_state:
    df = st.session_state["df"]
    if df.empty:
        st.warning("🤷‍♂️ Жодної релевантної віддаленої вакансії не знайдено (або сервер заблоковано).")
    else:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Знайдено</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df[df["match"] >= 75])}</div><div class="metric-lbl">Топ Match</div></div>', unsafe_allow_html=True)
        with m3: st.markdown(f'<div class="metric-box"><div class="metric-val">{int(df["match"].mean())}%</div><div class="metric-lbl">Сер. Match</div></div>', unsafe_allow_html=True)
        with m4: st.markdown(f'<div class="metric-box"><div class="metric-val">100%</div><div class="metric-lbl">Remote Only</div></div>', unsafe_allow_html=True)
        with m5: st.markdown(f'<div class="metric-box"><div class="metric-val">{len(df[df["salary"] != "Не вказана"])}</div><div class="metric-lbl">З грошима</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1: search_query = st.text_input("🔍 Швидкий пошук", "")
        with col_s2: min_p = st.slider("Мін. % Match", 0, 100, 30)

        view = df[df["match"] >= min_p]
        if search_query:
            view = view[view["title"].str.contains(search_query, case=False) | view["desc"].str.contains(search_query, case=False)]

        for _, row in view.sort_values("match", ascending=False).iterrows():
            m_color = "#16a34a" if row["match"] >= 75 else ("#ca8a04" if row["match"] >= 45 else "#64748b")
            with st.expander(f"{row['match']}% — {row['title']}"):
                st.markdown(f'<div style="display:flex; justify-content:space-between; margin-bottom:15px;"><b style="color:{m_color}; font-size:1.2rem;">{row["match"]}% Match</b><b style="color:#1e293b; font-size:1rem;">💰 {row["salary"]}</b></div><div style="line-height: 1.6; color: #334155; font-size: 0.95rem;">{format_description(row["desc"])}</div><div style="margin-top:15px;"><a href="{row["link"]}" target="_blank" style="color:#2563eb; font-weight:700; text-decoration:none;">🔗 Відкрити на Work.ua</a></div>', unsafe_allow_html=True)
else:
    st.info("👈 Введіть пароль, налаштуйте фільтри та натисніть 'ПОЧАТИ СКАНУВАННЯ'.")
