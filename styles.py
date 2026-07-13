import streamlit as st


def apply_styles():
    """Стил „Хибрид" (десктоп-ERP усет) — вика се веднъж в началото на app.py.

    Цветовете идват от .streamlit/config.toml; тук добавяме плътност, рамки на
    панелите, вид на метриките, навигационния рейл и по-компактни таблици.
    Ползваме само стабилни селектори (data-testid), за да не се чупи при ъпдейт.
    """
    st.markdown("""
        <style>
        :root{
          --paper:#f4f5f3; --surface:#ffffff; --surface-2:#fafbf9;
          --ink:#1a1c1a; --muted:#5b615c; --faint:#8a908b;
          --hair:#e3e5e1; --hair-strong:#d3d6d1;
          --accent:#12695f; --accent-soft:#e2efec; --accent-ink:#0c4a43;
          --crit:#b3261e;
          --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
        }

        /* --- По-плътно основно съдържание --- */
        .block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1500px}
        [data-testid="stHeader"]{background:transparent}

        /* --- Заглавия --- */
        h1{font-weight:700;border-bottom:2px solid var(--ink);
           padding-bottom:.35rem;margin-bottom:1rem;letter-spacing:-.01em}
        h2,h3{color:var(--ink);font-weight:650;margin-top:1.1rem;margin-bottom:.5rem;
           font-size:1.02rem;letter-spacing:.2px}
        .stCaption,[data-testid="stCaptionContainer"]{color:var(--muted)}

        /* --- Числата в метриките — моно, за подравнени колони --- */
        [data-testid="stMetric"]{background:var(--surface);border:1px solid var(--hair);
           border-radius:10px;padding:12px 14px 10px;box-shadow:0 1px 2px rgba(20,24,20,.05)}
        [data-testid="stMetricValue"]{font-family:var(--mono);font-variant-numeric:tabular-nums;
           font-weight:700;letter-spacing:-.01em}
        [data-testid="stMetricLabel"] p{color:var(--muted);font-size:.8rem;
           text-transform:uppercase;letter-spacing:.4px}

        /* --- Заоблени контейнери като „панели" --- */
        [data-testid="stVerticalBlockBorderWrapper"]{border-radius:11px}

        /* --- Бутони --- */
        .stButton > button{border-radius:9px;border:1px solid var(--hair-strong);
           font-weight:600;transition:all .15s ease;background:var(--surface);color:var(--ink)}
        .stButton > button:hover{border-color:var(--accent);color:var(--accent-ink)}
        .stButton > button[kind="primary"]{background:var(--accent);border-color:var(--accent);color:#fff}
        .stButton > button[kind="primary"]:hover{background:var(--accent-ink);border-color:var(--accent-ink);color:#fff}
        .stDownloadButton > button{border-radius:9px;font-weight:600}

        /* --- Полета за въвеждане --- */
        [data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input,.stTextArea textarea{border-radius:8px}
        [data-testid="stTextInput"] input:focus,[data-testid="stNumberInput"] input:focus{
           border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}

        /* --- Табове като ERP секции --- */
        .stTabs [data-baseweb="tab-list"]{gap:2px;border-bottom:1px solid var(--hair)}
        .stTabs [data-baseweb="tab"]{padding:8px 14px;font-weight:600;color:var(--muted)}
        .stTabs [aria-selected="true"]{color:var(--ink)}

        /* --- Таблици (нативният грид е canvas; рамка + заобляне на контейнера) --- */
        [data-testid="stDataFrame"]{border:1px solid var(--hair);border-radius:9px;overflow:hidden}

        /* --- Разделители --- */
        hr{margin:1.1rem 0;border-color:var(--hair)}

        /* ============ НАВИГАЦИОНЕН РЕЙЛ (sidebar) ============ */
        section[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--hair)}
        section[data-testid="stSidebar"] .block-container{padding-top:1rem}
        /* Заглавието „📚 Bookspace" като лого-марка */
        section[data-testid="stSidebar"] h1{border:0;font-size:1.15rem;padding:0;margin:0 0 .2rem}

        /* Навигационните бутони — като елементи от меню */
        section[data-testid="stSidebar"] .stButton > button{
           width:100%;text-align:left;background:transparent;border:1px solid transparent;
           border-radius:8px;padding:.5rem .8rem;margin-bottom:1px;font-weight:550;
           color:var(--muted);font-size:.9rem}
        section[data-testid="stSidebar"] .stButton > button:hover{
           background:var(--surface-2);color:var(--ink);border-color:var(--hair);transform:none;box-shadow:none}
        /* Активен раздел — плътен мастилен фон, бял текст */
        section[data-testid="stSidebar"] .stButton > button[kind="primary"]{
           background:var(--ink);color:#fff;border-color:var(--ink)}
        section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover{
           background:#000;color:#fff}
        /* Групови заглавия в рейла */
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{
           text-transform:uppercase;letter-spacing:.7px;font-size:.68rem;
           color:var(--faint);margin:.7rem 0 .15rem .35rem;font-weight:700}

        /* Съобщения (success/warning/error) — по-заоблени */
        [data-testid="stAlert"]{border-radius:10px}
        </style>
    """, unsafe_allow_html=True)
