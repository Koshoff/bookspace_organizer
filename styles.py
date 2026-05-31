import streamlit as st

def apply_styles():
    """Налива монохромния фин стил. Вика се веднъж в началото на app.py."""
    st.markdown("""
        <style>
        /* Заоблени ъгли и фина рамка на бутоните + плавен hover преход */
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #d0d0d0;
            transition: all 0.2s ease;       /* плавен преход при hover */
            font-weight: 500;
        }
        .stButton > button:hover {
            border-color: #1a1a1a;           /* рамката потъмнява при задържане */
            transform: translateY(-1px);      /* фино повдигане — модерен ефект */
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        /* Заоблени полета за въвеждане */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            border-radius: 8px;
        }

        /* Таблиците — фина рамка и заобляне */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #e8e8e8;
        }

        /* Sidebar — лека дясна граница за разделяне от съдържанието */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #e8e8e8;
        }
                
        /* --- Навигационни бутони в sidebar-а --- */
        /* Правим всеки бутон в sidebar да заема цялата ширина и да е ляво-подравнен,
           за да изглежда като елемент от меню, а не като класически бутон. */
        section[data-testid="stSidebar"] .stButton > button {
            width: 100%;
            text-align: left;
            background-color: transparent;   /* без фон в нормално състояние */
            border: 1px solid transparent;   /* невидима рамка, за да няма "скачане" при hover */
            border-radius: 8px;
            padding: 0.5rem 0.9rem;
            margin-bottom: 2px;
            font-weight: 500;
            color: #333333;
            transition: all 0.15s ease;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background-color: #e4e4e4;        /* леко сиво при задържане */
            border-color: transparent;
            transform: none;                   /* без повдигането от общия стил */
            box-shadow: none;
        }
        /* Активният бутон — плътен тъмен фон, бял текст. Постига се чрез
           type="primary", който Streamlit бележи с този атрибут. */
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background-color: #1a1a1a;
            color: #ffffff;
            border-color: #1a1a1a;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background-color: #000000;
        }

                /* --- Заглавия на секциите --- */
        /* Фина долна линия под главните заглавия (st.title), за да отделят
           секцията от съдържанието ѝ. Дава "глава на страница" усещане. */
        h1 {
            border-bottom: 2px solid #1a1a1a;
            padding-bottom: 0.4rem;
            margin-bottom: 1.2rem;
            font-weight: 700;
        }

        /* Подзаглавията (st.subheader) — по-лека линия, по-малко тежест,
           за да има визуална йерархия спрямо главното заглавие. */
        h2, h3 {
            color: #1a1a1a;
            margin-top: 1.5rem;
            margin-bottom: 0.6rem;
        }

        /* --- Повече въздух около разделителите (st.divider) --- */
        hr {
            margin-top: 1.5rem;
            margin-bottom: 1.5rem;
            border-color: #e8e8e8;
        }

        /* --- Лек отстъп на основното съдържание, за да не лепне в ръба --- */
        .block-container {
            padding-top: 2.5rem;
        }        
        </style>
    """, unsafe_allow_html=True)