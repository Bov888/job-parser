import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# Твоє посилання на Google Apps Script
GAS_PROXY_URL = "https://script.google.com/macros/s/AKfycbzVkDdbqL3wc4pGXmNCUyCZBGSZl3j9eCexPqfGSje-UuLdqbTFJH5-U2Bqwy-WlqfMUw/exec"

# --- ФУНКЦІЇ БЕЗПЕКИ ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Пароль", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Паро_ль", type="password", on_change=password_entered, key="password")
        st.error("❌ Невірний пароль")
        return False
    return True

# --- ФУНКЦІЇ ПАРСИНГУ ЧЕРЕЗ GOOGLE ---
def get_html_via_gas(url):
    """Отримує HTML сторінки через Google Apps Script проксі"""
    try:
        # Передаємо цільовий URL як параметр нашому скрипту
        response = requests.get(f"{GAS_PROXY_URL}?url={url}", timeout=30)
        if response.status_code == 200:
            return response.text
        else:
            st.warning(f"Помилка проксі: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Помилка з'єднання: {e}")
        return None

def get_job_description(url):
    """Парсить опис вакансії для розрахунку відсотка співпадіння"""
    html = get_html_via_gas(url)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    # Шукаємо блок опису (на Work.ua це зазвичай id="job-description")
    desc_div = soup.find("div", id="job-description") or soup.find("div", class_="job-description-content")
    
    if desc_div:
        # Видаляємо скрипти та стилі, якщо вони є всередині
        for s in desc_div(["script", "style"]):
            s.decompose()
        return desc_div.get_text(" ", strip=True).lower()
    return ""

def calculate_match(description, filters):
    """Рахує % співпадіння на основі твоїх ваг"""
    if not description:
        return 0
    
    score = 0
    total_possible = sum(abs(v) for v in filters.values())
    
    for word, weight in filters.items():
        if word.lower() in description:
            score += weight
            
    if total_possible == 0: return 0
    # Масштабуємо від 0 до 100
    final_score = max(0, min(100, (score / total_possible) * 100))
    return round(final_score)

# --- ОСНОВНИЙ СКАНЕР ---
def run_scanner(pages, filters):
    all_jobs = []
    progress_bar = st.progress(0)
    
    for p in range(1, pages + 1):
        status_text = st.empty()
        status_text.text(f"Скануємо сторінку {p} із {pages}...")
        
        main_url = f"https://www.work.ua/jobs-remote/?page={p}"
        html = get_html_via_gas(main_url)
        
        if not html:
            st.error("Не вдалося отримати дані. Можливо, Google заблоковано або ліміт вичерпано.")
            break
            
        soup = BeautifulSoup(html, "html.parser")
        # Знаходимо всі картки вакансій
        cards = soup.find_all("div", class_=["job-link", "card-hover"])
        
        for card in cards:
            title_tag = card.find("h2").find("a") if card.find("h2") else None
            if not title_tag: continue
            
            title = title_tag.get_text(strip=True)
            link = "https://www.work.ua" + title_tag["href"]
            company = card.find("b").get_text(strip=True) if card.find("b") else "Не вказано"
            
            # Отримуємо детальний опис для аналізу
            description = get_job_description(link)
            match_percent = calculate_match(description, filters)
            
            all_jobs.append({
                "Співпадіння %": match_percent,
                "Назва": title,
                "Компанія": company,
                "Посилання": link
            })
            
        progress_bar.progress(p / pages)
        time.sleep(1) # Невелика пауза для стабільності
        
    status_text.empty()
    return pd.DataFrame(all_jobs)

# --- ІНТЕРФЕЙС STREAMLIT ---
def main():
    st.set_page_config(page_title="Job Scanner PRO", page_icon="🔍")
    st.title("🔍 Розумний пошук вакансій")

    if not check_password():
        st.stop()

    with st.sidebar:
        st.header("Налаштування")
        pages = st.number_input("Кількість сторінок", min_value=1, max_value=10, value=1)
        
        st.subheader("Твої фільтри (слово: вага)")
        # Твої специфічні фільтри з вагами
        filter_data = {
            "Python": 20,
            "AI": 15,
            "Automation": 10,
            "English": 10,
            "Офіс": -50,   # Мінус, якщо не хочеш в офіс
            "Дзвінки": -30 # Мінус для кол-центрів
        }
        
        # Можна редагувати через JSON або просто залишити статично
        st.info("Фільтри налаштовані на: Python, AI, Автоматизацію та відсів офісів.")

    if st.button("🚀 Запустити сканування", use_container_width=True):
        df = run_scanner(pages, filter_data)
        
        if not df.empty:
            # Сортуємо за відсотком співпадіння
            df = df.sort_values(by="Співпадіння %", ascending=False)
            
            st.success(f"Знайдено {len(df)} вакансій")
            
            # Відображення таблиці з клікабельними лінками
            st.dataframe(
                df,
                column_config={
                    "Посилання": st.column_config.LinkColumn("Відкрити вакансію")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("Нічого не знайдено.")

if __name__ == "__main__":
    main()
