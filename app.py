import streamlit as st
from datetime import date, timedelta
import pandas as pd
import styles
import db   # нашият слой за достъп до базата
import mailer   # сервизен слой за автоматичните заявки по имейл

# Конфигурация на страницата — широк изглед, заглавие на таба в браузъра.
st.set_page_config(page_title="Bookspace ERP", layout="wide")
styles.apply_styles()


# ----- СТРАНИЧНО МЕНЮ (Sidebar) -----
# Засега има само един раздел. С добавянето на модули списъкът ще расте.
st.sidebar.title("📚 Bookspace")
section = [
    ("Табло", "🏠"),
    ("Доставчици", "🏢"),
    ("Каталог", "📖"),
    ("Доставки", "📦"),
    ("AI Маркетинг", "🎯"),
    ("Нова продажба", "🛒"),
    ("Ваучери", "🎁"),
    ("Журнал продажби", "📊"),
    ("Автоматични заявки", "📨"),
    ("Кредитни известия", "↩️"),
    ("Склад и одит", "🔍"),
    ("Годишно приключване", "📋"),
    ("Фирмени Разходи", "💰")
]


# Помним активната секция в session_state — бутоните не пазят състояние сами.
if "active_section" not in st.session_state:
    st.session_state.active_section = section[0][0]   # първата по подразбиране

# Рисуваме по един бутон на секция. Активният е "primary" (тъмен фон).
for name, icon in section:
    is_active = (st.session_state.active_section == name)
    if st.sidebar.button(
        f"{icon}  {name}",
        key=f"nav_{name}",
        width='stretch',
        type="primary" if is_active else "secondary",
    ):
        # Клик → сменяме активната секция и презареждаме, за да се пребоядиса менюто.
        st.session_state.active_section = name
        st.rerun()

# Оттук нататък целият код чете от session_state вместо от старата променлива.
section = st.session_state.active_section

# ----- ЕКРАН: ТАБЛО (начален преглед) -----
# ----- ЕКРАН: ГЛАВНО КОМАНДНО ТАБЛО (Модул 0) -----
if section == "Табло":
    

    st.title("Командно табло")

    # --- ФИЛТЪР ЗА ПЕРИОД ---
    # Помним избора в session_state, за да преживее презарежданията.
    if "dash_period" not in st.session_state:
        st.session_state.dash_period = "Последните 7 дни"

    st.caption("Период")
    # Бутоните за бърз избор — подредени в редица.
    p1, p2, p3, p4, p5 = st.columns(5)
    periods = [
        (p1, "Днес"), (p2, "Последните 7 дни"), (p3, "Последните 10 дни"),
        (p4, "Последните 30 дни"), (p5, "Избран период"),
    ]
    for col, label in periods:
        # Активният период се откроява като primary (тъмен).
        is_active = st.session_state.dash_period == label
        if col.button(label, width='stretch',
                      type="primary" if is_active else "secondary",
                      key=f"period_{label}"):
            st.session_state.dash_period = label
            st.rerun()

    # --- Превръщаме избора в две дати (от/до) ---
    today = date.today()
    chosen = st.session_state.dash_period

    if chosen == "Днес":
        date_from = date_to = today
    elif chosen == "Последните 7 дни":
        date_from, date_to = today - timedelta(days=6), today
    elif chosen == "Последните 10 дни":
        date_from, date_to = today - timedelta(days=9), today
    elif chosen == "Последните 30 дни":
        date_from, date_to = today - timedelta(days=29), today
    else:  # Избран период — показваме календар
        cc1, cc2 = st.columns(2)
        date_from = cc1.date_input("От", value=today - timedelta(days=7), key="dash_from")
        date_to = cc2.date_input("До", value=today, key="dash_to")

    # Филтър по начин на плащане за финансовите карти.
    pay_filter = st.selectbox("Филтър по начин на плащане (карти)", [
        "Всички", "Пощенски паричен превод (Куриер)",
        "В брой (Каса)", "Банков път / Карта",
    ])
    pay_arg = None if pay_filter == "Всички" else pay_filter

    data = db.get_dashboard_data(str(date_from), str(date_to), pay_arg)

    st.divider()

    # --- ЧЕТИРИТЕ КАРТИ ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Приходи (оборот)", f"{data['revenue']:.2f} лв.")
    c2.metric("Общо разходи", f"{data['expenses']:.2f} лв.",
              help="COGS (доставна стойност на продаденото) + оперативни разходи")

    # Чиста печалба — задължително със знак, дори при положителна стойност няма
    # значение. Streamlit метрики и без това поставят минус автоматично, но
    # използваме explicit format за яснота, че знакът е смислен.
    profit = data['profit']
    profit_str = f"{profit:.2f} лв." if profit >= 0 else f"−{abs(profit):.2f} лв."
    c3.metric("Чиста печалба", profit_str)

    c4.metric("Брой продажби", data["sales_count"])

    # Разбивка на разходите — малка справка под главните карти.
    with st.expander("Разбивка на разходите"):
        b1, b2 = st.columns(2)
        b1.metric("Доставна на продаденото (COGS)",
                  f"{data['cogs']:.2f} лв.")
        b2.metric("Оперативни разходи",
                  f"{data['operating_expenses']:.2f} лв.")
        
    # --- ПАНЕЛ: БИЗНЕС ЕФЕКТИВНОСТ (CAC / AOV / Средна цена) ---
    st.divider()
    st.subheader("Бизнес ефективност")
    st.caption("Маркетинг и продажбени KPI за избрания период")

    # Изчисляваме трите метрики. Защитаваме срещу делене на нула.
    sales_n = data["sales_count"]
    revenue = data["revenue"]
    ad_spend = data["ad_spend"]
    units_sold = data["total_units_sold"]

    cac = (ad_spend / sales_n) if sales_n > 0 else 0
    aov = (revenue / sales_n) if sales_n > 0 else 0
    avg_unit_price = (revenue / units_sold) if units_sold > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Цена за реклама на поръчка (CAC)",
              f"{cac:.2f} лв.",
              help="Разходи за реклама / брой поръчки за периода")
    k2.metric("Средна стойност на поръчка (AOV)",
              f"{aov:.2f} лв.",
              help="Общ оборот / брой поръчки за периода")
    k3.metric("Средна цена на продаден артикул",
              f"{avg_unit_price:.2f} лв.",
              help="Общ оборот / общ брой физически продадени бройки")

    # Индикатор за неефективна реклама — само ако имаме реални данни.
    if sales_n > 0 and aov > 0 and cac > 0.4 * aov:
        st.warning("⚠️ **Внимание:** Разходите за придобиване на клиент (CAC) "
                   "са твърде високи спрямо стойността на поръчките (AOV). "
                   "Оптимизирайте рекламните кампании.")
    elif sales_n == 0 and ad_spend > 0:
        # Имаме реклама, но няма продажби. Скъсаво е, но различен случай от „много CAC".
        st.info("ℹ️ Има разходи за реклама за периода, но няма продажби. "
                "Това може да е знак, че рекламата още не носи резултати, "
                "или периодът е твърде кратък.")    

    st.divider()

    # --- Разбивка на доставките по начин на плащане (за периода) ---
    st.subheader("Доставки по начин на плащане")
    st.caption("Каква част от заприходената стока е по банка, в брой или на консигнация")

    delivery_breakdown = db.get_delivery_payment_breakdown(str(date_from), str(date_to))

    consign = delivery_breakdown.get("Консигнация (отложено)", {"count": 0, "total": 0})
    bank = delivery_breakdown.get("По банка", {"count": 0, "total": 0})
    cash = delivery_breakdown.get("В брой", {"count": 0, "total": 0})

    db1, db2, db3 = st.columns(3)
    db1.metric(f"Консигнация ({consign['count']} док.)", f"{consign['total']:.2f} лв.")
    db2.metric(f"По банка ({bank['count']} док.)", f"{bank['total']:.2f} лв.")
    db3.metric(f"В брой ({cash['count']} док.)", f"{cash['total']:.2f} лв.")

    st.divider()

    # --- ДВЕ КОЛОНИ: задължения и вземания ---
    left, right = st.columns(2)

    with left:
        st.subheader("Задължения (неплатени доставки)")
        liabilities = data["liabilities"]
        if not liabilities:
            st.info("Няма неплатени доставки.")
        else:
            total_owed = sum(l["amount"] for l in liabilities)
            st.metric("Общо дължим", f"{total_owed:.2f} лв.")
            ldf = pd.DataFrame([dict(l) for l in liabilities])
            ldf = ldf.rename(columns={
                "supplier_name": "Доставчик", "doc_number": "Документ №",
                "doc_date": "Дата", "amount": "Сума",
            })
            st.dataframe(ldf[["Доставчик", "Документ №", "Дата", "Сума"]],
                         width='stretch', hide_index=True)

    with right:
        st.subheader("Вземания (чакащи поръчки)")
        receivables = data["receivables"]
        if not receivables:
            st.info("Няма чакащи плащане поръчки.")
        else:
            total_due = sum(r["amount"] for r in receivables)
            st.metric("Общо за прибиране", f"{total_due:.2f} лв.")
            rdf = pd.DataFrame([dict(r) for r in receivables])
            rdf = rdf.rename(columns={
                "order_number": "Поръчка №", "waybill_number": "Товарителница",
                "created_at": "Дата", "amount": "Сума",
            })
            st.dataframe(rdf[["Поръчка №", "Товарителница", "Дата", "Сума"]],
                         width='stretch', hide_index=True)

    st.divider()

    # --- ДОЛЕН ПАНЕЛ: последни активности ---
    st.subheader("Последни активности")
    activities = data["activities"]
    if not activities:
        st.info("Няма активности.")
    else:
        adf = pd.DataFrame([dict(a) for a in activities])
        adf = adf.rename(columns={
            "ts": "Час/Дата", "type": "Тип", "doc": "Документ", "value": "Стойност",
        })
        st.dataframe(adf, width='stretch', hide_index=True)


    # --- СЧЕТОВОДЕН ЕКСПОРТ И ДДС (Модул счетоводство) ---
    st.divider()
    st.subheader("Счетоводен експорт и ДДС")

    # Използваме същия период (date_from, date_to), избран горе на таблото.
    st.caption(f"Период за справките: {date_from} — {date_to}")

    ec1, ec2 = st.columns(2)

    # --- Месечен дневник на продажбите и покупките (Excel) ---
    with ec1:
        st.markdown("**Дневник продажби и покупки (ДДС)**")
        # Excel-ът се генерира само при заявка (бутон), не при всяко презареждане.
        # Пазим резултата в session_state с периода — ако периодът се смени,
        # бутонът се връща, за да не свалиш стар файл с грешно име.
        acc_period = (str(date_from), str(date_to))
        if st.button("Подготви Excel дневник", key="prep_acc_excel"):
            st.session_state.acc_excel = {
                "period": acc_period,
                "data": db.build_accounting_excel(*acc_period),
            }
        acc = st.session_state.get("acc_excel")
        if acc and acc["period"] == acc_period:
            st.download_button(
                "Свали Excel дневник",
                data=acc["data"],
                file_name=f"dnevnik_{date_from}_{date_to}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # --- Отчет за консигнация (CSV) ---
    with ec2:
        st.markdown("**Отчет за консигнация**")
        consignment = db.get_consignment_report(str(date_from), str(date_to))
        if consignment:
            cdf = pd.DataFrame(consignment)
            cdf = cdf.rename(columns={
                "supplier_name": "Издателство",
                "sold_qty": "Продадени бройки",
                "owed_to_publisher": "Дължимо (доставна)",
                "bookstore_margin": "Марж книжарница",
            })
            csv = cdf.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Свали CSV за издателства",
                data=csv,
                file_name=f"konsignacia_{date_from}_{date_to}.csv",
                mime="text/csv",
            )
        else:
            st.info("Няма продадена консигнация за периода.")

    # Показваме консигнацията и като таблица под бутоните, за бърз преглед.
    if consignment:
        st.dataframe(cdf, width='stretch', hide_index=True) 

    # --- МЕСЕЧЕН ОТЧЕТ ЗА СТАТУС НА ПЛАЩАНИЯТА ---
    st.divider()
    st.subheader("Месечен отчет за статус на плащанията")

    # Избор на месец и година. Генерираме последните 12 месеца като опции.
    from datetime import date
    today_d = date.today()
    month_names = ["Януари", "Февруари", "Март", "Април", "Май", "Юни",
                   "Юли", "Август", "Септември", "Октомври", "Ноември", "Декември"]
    # Строим списък {етикет: 'YYYY-MM'} за последните 12 месеца.
    month_options = {}
    for i in range(12):
        m = today_d.month - i
        y = today_d.year
        while m <= 0:
            m += 12
            y -= 1
        label = f"{month_names[m-1]} {y}"
        month_options[label] = f"{y}-{m:02d}"

    sel_month_label = st.selectbox("Избери месец", list(month_options.keys()))
    ym = month_options[sel_month_label]

    report = db.get_monthly_payment_report(ym)

    # Трите карти
    mp1, mp2, mp3 = st.columns(3)
    mp1.metric("Общ оборот за месеца", f"{report['turnover']:.2f} лв.")
    mp2.metric("Събрани приходи (платени)", f"{report['paid_total']:.2f} лв.")
    mp3.metric("Несъбрани вземания (неплатени)", f"{report['unpaid_total']:.2f} лв.")

    # Двата таба с таблиците
    t_unpaid, t_paid = st.tabs(["Чакащи плащания (неплатени)",
                                "Приключени поръчки (платени)"])

    with t_unpaid:
        if not report["unpaid"]:
            st.info("Няма неплатени поръчки за месеца.")
        else:
            udf = pd.DataFrame(report["unpaid"]).rename(columns={
                "created_at": "Дата/Час", "order_number": "Поръчка №",
                "waybill_number": "Товарителница", "payment_method": "Начин на плащане",
                "amount": "Сума",
            })
            st.dataframe(udf, width='stretch', hide_index=True)
            st.metric("Общо висящи пари", f"{report['unpaid_total']:.2f} лв.")

    with t_paid:
        if not report["paid"]:
            st.info("Няма платени поръчки за месеца.")
        else:
            pdf = pd.DataFrame(report["paid"]).rename(columns={
                "created_at": "Дата/Час", "order_number": "Поръчка №",
                "waybill_number": "Товарителница", "payment_method": "Начин на плащане",
                "amount": "Сума", "payment_date": "Дата на плащане",
            })
            st.dataframe(pdf, width='stretch', hide_index=True)
            st.metric("Общо събрани", f"{report['paid_total']:.2f} лв.")

    # Бутон за Excel експорт — генерира се само при заявка (не при всяко зареждане).
    if st.button("Подготви месечен отчет (Excel)", key="prep_monthly_excel"):
        st.session_state.monthly_excel = {"ym": ym, "data": db.build_monthly_payment_excel(ym)}
    me = st.session_state.get("monthly_excel")
    if me and me["ym"] == ym:
        st.download_button(
            "Експорт на месечен отчет за плащанията (Excel)",
            data=me["data"],
            file_name=f"otchet_plashtania_{ym}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )





# ----- ЕКРАН: ДОСТАВЧИЦИ -----
elif section == "Доставчици":
    st.title("Доставчици")

    # Три таба: списък, добавяне и редакция/изтриване.
    tab_list, tab_add, tab_edit = st.tabs(["Списък", "Добави нов",
                                           "Редактирай/Изтрий"])

    # --- ТАБ: ДОБАВИ НОВ ДОСТАВЧИК ---
    with tab_add:
        # st.form групира полета и ги праща наведнъж при натискане на бутона.
        # Без form, помниш ли — всяко въвеждане презарежда скрипта. Form-ът
        # изчаква, събира всичко и го подава при submit. Точно за това е.
        with st.form("form_add_supplier", clear_on_submit=True):
            name = st.text_input("Име на фирма/доставчик *")
            col1, col2 = st.columns(2)  # две колони един до друг
            with col1:
                bulstat = st.text_input("Булстат/ЕИК")
                mol = st.text_input("МОЛ")
                phone = st.text_input("Телефон")
            with col2:
                email = st.text_input("Имейл *",
                                      help="Задължителен — на този адрес отиват "
                                           "автоматичните заявки за зареждане.")
                address = st.text_input("Адрес")
                discount = st.number_input(
                    "Стандартен % отстъпка", min_value=0.0, max_value=100.0,
                    value=35.0, step=0.5
                )

            submitted = st.form_submit_button("Запази доставчик")

            if submitted:
                if not name.strip():
                    st.error("Името е задължително.")
                elif not mailer.is_valid_email(email):
                    st.error("Валиден имейл е задължителен — на него се "
                             "изпращат автоматичните заявки за зареждане.")
                else:
                    ok, msg = db.add_supplier(
                        name.strip(), bulstat, mol, address, phone,
                        email.strip(), discount
                    )
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    # --- ТАБ: СПИСЪК НА ДОСТАВЧИЦИТЕ ---
    with tab_list:
        suppliers = db.get_all_suppliers()
        if not suppliers:
            st.info("Все още няма въведени доставчици.")
        else:
            # Превръщаме редовете в pandas DataFrame за красива таблица.
            df = pd.DataFrame([dict(row) for row in suppliers])
            st.dataframe(df, width='stretch', hide_index=True)

    # --- ТАБ: РЕДАКЦИЯ / ИЗТРИВАНЕ ---
    with tab_edit:
        suppliers = db.get_all_suppliers()
        if not suppliers:
            st.info("Няма доставчици за редакция.")
        else:
            # Избираме доставчик; id-то отпред гарантира уникален етикет.
            sup_map = {f"#{s['id']} · {s['name']}": dict(s) for s in suppliers}
            chosen_label = st.selectbox("Избери доставчик",
                                        list(sup_map.keys()), key="edit_sup_pick")
            cur = sup_map[chosen_label]

            # Формата се пре-попълва с текущите стойности. key включва id-то,
            # за да се рефрешнат полетата при смяна на избрания доставчик.
            with st.form(f"form_edit_supplier_{cur['id']}"):
                e_name = st.text_input("Име на фирма/доставчик *", value=cur["name"])
                col1, col2 = st.columns(2)
                with col1:
                    e_bulstat = st.text_input("Булстат/ЕИК", value=cur["bulstat"] or "")
                    e_mol = st.text_input("МОЛ", value=cur["mol"] or "")
                    e_phone = st.text_input("Телефон", value=cur["phone"] or "")
                with col2:
                    e_email = st.text_input("Имейл *", value=cur["email"] or "",
                                            help="Задължителен — за автоматичните "
                                                 "заявки за зареждане.")
                    e_address = st.text_input("Адрес", value=cur["address"] or "")
                    e_discount = st.number_input(
                        "Стандартен % отстъпка", min_value=0.0, max_value=100.0,
                        value=float(cur["default_discount"]), step=0.5
                    )
                save = st.form_submit_button("Запази промените", type="primary")
                if save:
                    if not e_name.strip():
                        st.error("Името е задължително.")
                    elif not mailer.is_valid_email(e_email):
                        st.error("Валиден имейл е задължителен — на него се "
                                 "изпращат автоматичните заявки за зареждане.")
                    else:
                        ok, msg = db.update_supplier(
                            cur["id"], e_name.strip(), e_bulstat, e_mol,
                            e_address, e_phone, e_email.strip(), e_discount
                        )
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()

            # Изтриване — двустепенно потвърждение (иначе един клик трие).
            st.divider()
            st.subheader("Изтриване")
            if st.button("🗑️ Изтрий този доставчик"):
                st.session_state.pending_delete_supplier = cur["id"]
            if st.session_state.get("pending_delete_supplier") == cur["id"]:
                st.warning(f"Наистина ли да изтрия „{cur['name']}“? Необратимо е.")
                cA, cB = st.columns(2)
                with cA:
                    if st.button("Да, изтрий", type="primary", key="confirm_del_sup"):
                        ok, msg = db.delete_supplier(cur["id"])
                        (st.success if ok else st.error)(msg)
                        st.session_state.pending_delete_supplier = None
                        if ok:
                            st.rerun()
                with cB:
                    if st.button("Отказ", key="cancel_del_sup"):
                        st.session_state.pending_delete_supplier = None
                        st.rerun()

# ----- ЕКРАН: КАТАЛОГ (Модул 2) -----
elif section == "Каталог":
    st.title("Продуктов каталог")

    tab_list, tab_add, tab_edit = st.tabs(["Списък", "Добави книга",
                                           "Редактирай/Изтрий"])

    # --- ТАБ: ДОБАВИ КНИГА ---
    with tab_add:
        # Първо взимаме доставчиците — трябват ни за падащото меню.
        suppliers = db.get_all_suppliers()

        if not suppliers:
            # Не може да има книга без доставчик (релацията е задължителна).
            # Затова, ако няма доставчици, спираме потребителя с ясно съобщение.
            st.warning("Първо добавете поне един доставчик в раздел „Доставчици“.")
        else:
            # Строим речник {име: id}. Менюто показва имената (ключовете),
            # а ние пазим избраното id (стойността). Това е мостът човек->база.
            supplier_map = {s["name"]: s["id"] for s in suppliers}

            with st.form("form_add_product", clear_on_submit=True):
                # Изборът на тип определя ДДС и фискалната група автоматично.
                product_type = st.selectbox(
                    "Тип артикул", ["Книга", "Подаръчен ваучер"],
                    help="Книга = 9% ДДС, група Б. Ваучер = 0% ДДС, група Д."
                )
                # Свързваме типа с ДДС и фискалната група. Един източник на истина.
                if product_type == "Книга":
                    auto_vat = 9.0
                    auto_fiscal = "Б"
                    type_db_value = "Книга"
                else:
                    auto_vat = 0.0
                    auto_fiscal = "Д"
                    type_db_value = "Ваучер"

                col1, col2 = st.columns(2)
                with col1:
                    isbn = st.text_input("ISBN / Баркод *")
                    title = st.text_input("Заглавие *")
                    author = st.text_input("Автор (за книги)")
                    supplier_name = st.selectbox("Доставчик *", list(supplier_map.keys()))
                    genre = st.text_input("Жанр")
                with col2:
                    cover_price = st.number_input(
                        "Цена (с ДДС)" if product_type == "Книга" else "Номинал на ваучера",
                        min_value=0.0, value=0.0, step=0.5
                    )
                    # ДДС полето е ЗАКЛЮЧЕНО — стойността идва от типа, не може да се пипне.
                    st.number_input("ДДС ставка (%)", value=auto_vat, disabled=True)
                    st.text_input("Фискална група", value=auto_fiscal, disabled=True)
                    year = st.number_input("Година", min_value=0, value=2024, step=1)
                    cover_type = st.text_input("Корица (за книги)")

                description = st.text_area("Описание")

                submitted = st.form_submit_button(f"Запази {product_type.lower()}")

                if submitted:
                    if not isbn.strip() or not title.strip():
                        st.error("ISBN и Заглавие/Наименование са задължителни.")
                    else:
                        supplier_id = supplier_map[supplier_name]
                        ok, msg = db.add_product(
                            isbn.strip(), title.strip(), author, supplier_id,
                            cover_price, auto_vat, year, cover_type, genre, description,
                            product_type=type_db_value, fiscal_group=auto_fiscal
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    # --- ТАБ: СПИСЪК НА КНИГИТЕ ---
    with tab_list:
        products = db.get_all_products()
        if not products:
            st.info("Все още няма въведени книги.")
        else:
            df = pd.DataFrame([dict(row) for row in products])
            st.dataframe(df, width='stretch', hide_index=True)

    # --- ТАБ: РЕДАКЦИЯ / ИЗТРИВАНЕ НА АРТИКУЛ ---
    with tab_edit:
        full_products = db.get_all_products_full()
        suppliers = db.get_all_suppliers()
        if not full_products:
            st.info("Няма артикули за редакция.")
        elif not suppliers:
            st.warning("Няма доставчици.")
        else:
            supplier_map = {s["name"]: s["id"] for s in suppliers}
            id_to_supplier = {s["id"]: s["name"] for s in suppliers}

            prod_map = {f"#{p['id']} · {p['title']} ({p['isbn']})": p
                        for p in full_products}
            chosen_label = st.selectbox("Избери артикул",
                                        list(prod_map.keys()), key="edit_prod_pick")
            cur = prod_map[chosen_label]

            with st.form(f"form_edit_product_{cur['id']}"):
                # Типът пак определя ДДС/фискална група (един източник на истина).
                type_options = ["Книга", "Подаръчен ваучер"]
                type_index = 0 if cur["product_type"] == "Книга" else 1
                e_type = st.selectbox("Тип артикул", type_options, index=type_index,
                                      help="Книга = 9% ДДС, група Б. Ваучер = 0% ДДС, група Д.")
                if e_type == "Книга":
                    e_vat, e_fiscal, e_type_db = 9.0, "Б", "Книга"
                else:
                    e_vat, e_fiscal, e_type_db = 0.0, "Д", "Ваучер"

                col1, col2 = st.columns(2)
                with col1:
                    e_isbn = st.text_input("ISBN / Баркод *", value=cur["isbn"])
                    e_title = st.text_input("Заглавие *", value=cur["title"])
                    e_author = st.text_input("Автор", value=cur["author"] or "")
                    sup_names = list(supplier_map.keys())
                    cur_sup_name = id_to_supplier.get(cur["supplier_id"], sup_names[0])
                    e_supplier_name = st.selectbox(
                        "Доставчик *", sup_names,
                        index=sup_names.index(cur_sup_name) if cur_sup_name in sup_names else 0)
                    e_genre = st.text_input("Жанр", value=cur["genre"] or "")
                with col2:
                    e_cover_price = st.number_input(
                        "Цена (с ДДС)" if e_type == "Книга" else "Номинал",
                        min_value=0.0, value=float(cur["cover_price"]), step=0.5)
                    st.number_input("ДДС ставка (%)", value=e_vat, disabled=True)
                    st.text_input("Фискална група", value=e_fiscal, disabled=True)
                    e_year = st.number_input("Година", min_value=0,
                                             value=int(cur["year"] or 0), step=1)
                    e_cover_type = st.text_input("Корица", value=cur["cover_type"] or "")
                e_description = st.text_area("Описание", value=cur["description"] or "")

                save = st.form_submit_button("Запази промените", type="primary")
                if save:
                    if not e_isbn.strip() or not e_title.strip():
                        st.error("ISBN и Заглавие са задължителни.")
                    else:
                        ok, msg = db.update_product(
                            cur["id"], e_isbn.strip(), e_title.strip(), e_author,
                            supplier_map[e_supplier_name], e_cover_price, e_vat,
                            e_year, e_cover_type, e_genre, e_description,
                            product_type=e_type_db, fiscal_group=e_fiscal)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()

            # Изтриване — двустепенно потвърждение. DB слоят отказва, ако има история.
            st.divider()
            st.subheader("Изтриване")
            if st.button("🗑️ Изтрий този артикул"):
                st.session_state.pending_delete_product = cur["id"]
            if st.session_state.get("pending_delete_product") == cur["id"]:
                st.warning(f"Наистина ли да изтрия „{cur['title']}“? Необратимо е. "
                           "(Артикул с история не може да се изтрие.)")
                cA, cB = st.columns(2)
                with cA:
                    if st.button("Да, изтрий", type="primary", key="confirm_del_prod"):
                        ok, msg = db.delete_product(cur["id"])
                        (st.success if ok else st.error)(msg)
                        st.session_state.pending_delete_product = None
                        if ok:
                            st.rerun()
                with cB:
                    if st.button("Отказ", key="cancel_del_prod"):
                        st.session_state.pending_delete_product = None
                        st.rerun()


# ----- ЕКРАН: ДОСТАВКИ (Модул 3) -----
elif section == "Доставки":
    st.title("Доставки")
    tab_new, tab_journal = st.tabs(["Нова доставка", "Журнал на доставките"])

    # ============ ТАБ 1: НОВА ДОСТАВКА ============
    with tab_new:
        suppliers = db.get_all_suppliers()
        products_by_isbn = db.get_products_for_delivery()

        if not suppliers or not products_by_isbn:
            st.warning("Нужни са поне един доставчик и една книга в каталога.")
        else:
            # --- Кошницата живее в session_state, за да преживее презарежданията ---
            if "delivery_cart" not in st.session_state:
                st.session_state.delivery_cart = []

            # --- Данни за документа (капака) ---
            supplier_map = {s["name"]: s["id"] for s in suppliers}
            col1, col2, col3 = st.columns(3)
            with col1:
                supplier_name = st.selectbox("Доставчик", list(supplier_map.keys()))
                doc_type = st.selectbox("Тип документ",
                    ["Фактура", "Стокова разписка", "Протокол консигнация"])
            with col2:
                doc_number = st.text_input("Номер на документ")
                doc_date = st.date_input("Дата на документ")
            with col3:
                payment_type = st.selectbox("Начин на плащане", [
                    "Консигнация (отложено)", "По банка", "В брой",
                ])

            st.divider()
            st.subheader("Добавяне на книга чрез ISBN")

            # --- Добавяне на ред в кошницата ---
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                isbn_input = st.text_input("Сканирай/въведи ISBN")
            with c2:
                qty = st.number_input("Количество", min_value=1, value=1, step=1)
            with c3:
                settlement = st.selectbox("Тип", ["Купена", "Консигнация"])
            with c4:
                percent = st.number_input("% доставчик", min_value=0.0, value=35.0, step=0.5)

            del_price = st.number_input("Доставна цена (за бройка)",
                                        min_value=0.0, value=0.0, step=0.5)

            if st.button("Добави към доставката"):
                if isbn_input.strip() in products_by_isbn:
                    book = products_by_isbn[isbn_input.strip()]
                    st.session_state.delivery_cart.append({
                        "product_id": book["id"],
                        "title": book["title"],
                        "quantity": qty,
                        "settlement_type": settlement,
                        "supplier_percent": percent,
                        "delivery_price": del_price,
                    })
                    st.success(f"Добавена: {book['title']}")
                else:
                    st.error(f"Няма книга с ISBN „{isbn_input}“ в каталога.")
 
            # --- Показваме текущата кошница ---
            if st.session_state.delivery_cart:
                st.subheader("Книги в доставката")
                cart_df = pd.DataFrame(st.session_state.delivery_cart)
                cart_df["ред_сума"] = cart_df["quantity"] * cart_df["delivery_price"]
                st.dataframe(cart_df[["title", "quantity", "settlement_type",
                                      "supplier_percent", "delivery_price", "ред_сума"]],
                             width='stretch', hide_index=True)

                total = cart_df["ред_сума"].sum()
                st.metric("Обща доставна сума", f"{total:.2f} лв.")

                colA, colB = st.columns(2)
                with colA:
                    if st.button("Запиши доставката", type="primary"):
                        ok, msg = db.create_delivery(
                            supplier_map[supplier_name], doc_type, doc_number,
                            str(doc_date), st.session_state.delivery_cart, payment_type
                        )
                        if ok:
                            st.success(msg)
                            st.session_state.delivery_cart = []
                            st.rerun()
                        else:
                            st.error(msg)

                            
                with colB:
                    if st.button("Изчисти кошницата"):
                        st.session_state.delivery_cart = []
                        st.rerun()

    # ============ ТАБ 2: ЖУРНАЛ НА ДОСТАВКИТЕ ============
    with tab_journal:
        st.subheader("Филтри")
        f1, f2, f3, f4, f5 = st.columns(5)


        j_suppliers = db.get_all_suppliers()
        supplier_options = {"(всички)": None}
        supplier_options.update({s["name"]: s["id"] for s in j_suppliers})

        with f1:
            sel_supplier = st.selectbox("Доставчик", list(supplier_options.keys()),
                                        key="journal_supplier")
        with f2:
            sel_status = st.selectbox("Статус", ["(всички)", "Платена", "Неплатена"],
                                      key="journal_status")
        with f3:
            date_from = st.date_input("От дата", value=None, key="journal_from")
        with f4:
            date_to = st.date_input("До дата", value=None, key="journal_to")
        with f5:
            sel_payment_type = st.selectbox("Начин на плащане",
                ["(всички)", "Консигнация (отложено)", "По банка", "В брой"],
                key="journal_payment_type")
        pt_arg = None if sel_payment_type == "(всички)" else sel_payment_type

        status_arg = None if sel_status == "(всички)" else sel_status
        from_arg = str(date_from) if date_from else None
        to_arg = str(date_to) if date_to else None

        deliveries = db.get_deliveries(
            supplier_id=supplier_options[sel_supplier],
            payment_status=status_arg,
            date_from=from_arg,
            date_to=to_arg,
            payment_type=pt_arg
        )

        total_filtered = sum(d["total_amount"] for d in deliveries)
        st.metric("Обща сума (филтрирани)", f"{total_filtered:.2f} лв.")

        # --- Счетоводен брояч по начин на плащане (за периода) ---
        breakdown = db.get_delivery_payment_breakdown(from_arg, to_arg)
        st.caption("Разбивка по начин на плащане (за избрания период)")
        bc1, bc2, bc3 = st.columns(3)

        consign = breakdown.get("Консигнация (отложено)", {"count": 0, "total": 0})
        bank = breakdown.get("По банка", {"count": 0, "total": 0})
        cash = breakdown.get("В брой", {"count": 0, "total": 0})

        bc1.metric(f"Консигнация ({consign['count']} док.)",
                   f"{consign['total']:.2f} лв.")
        bc2.metric(f"По банка ({bank['count']} док.)",
                   f"{bank['total']:.2f} лв.")
        bc3.metric(f"В брой ({cash['count']} док.)",
                   f"{cash['total']:.2f} лв.")

        st.divider()

        if not deliveries:
            st.info("Няма доставки по тези критерии.")
        else:
            df = pd.DataFrame([dict(d) for d in deliveries])
            st.dataframe(df, width='stretch', hide_index=True)

            st.divider()
            st.subheader("Действия по доставка")

            delivery_labels = {
                f"№{d['doc_number']} — {d['supplier_name']} ({d['payment_status']})": d["id"]
                for d in deliveries
            }
            chosen = st.selectbox("Избери доставка", list(delivery_labels.keys()))
            chosen_id = delivery_labels[chosen]

            colA, colB = st.columns(2)
            with colA:
                if st.button("Маркирай като платена"):
                    db.mark_delivery_paid(chosen_id)
                    st.success("Маркирана като платена.")
                    st.rerun()
            with colB:
                show_details = st.checkbox("Покажи книгите в доставката")

            if show_details:
                items = db.get_delivery_items(chosen_id)
                items_df = pd.DataFrame([dict(i) for i in items])
                st.dataframe(items_df, width='stretch', hide_index=True)

# ----- ЕКРАН: НОВА ПРОДАЖБА / ПОС (Модул 4) -----
elif section == "Нова продажба":
    st.title("Нова продажба")

    # Кошница за продажбата — пак в session_state.
    if "sale_cart" not in st.session_state:
        st.session_state.sale_cart = []

     # --- Горни полета: номера + начин на плащане ---
    col1, col2, col3 = st.columns(3)
    with col1:
        order_number = st.text_input("Номер на поръчка")
    with col2:
        waybill_number = st.text_input("Номер на товарителница (Еконт/Спиди)")
    with col3:
        payment_method = st.selectbox("Начин на плащане", [
            "Пощенски паричен превод (Куриер)",
            "В брой (Каса)",
            "Банков път / Карта",
        ])
    # --- Опция: плащане с ваучер ---
    use_voucher = st.checkbox("Плащане с ваучер вместо избрания начин")
    voucher_validated = None    # ще пази валидирания ваучер, ако има

    if use_voucher:
        vc1, vc2 = st.columns([2, 1])
        with vc1:
            voucher_code = st.text_input("Код на ваучера (напр. GIFT-2026-00001)")
        with vc2:
            check_btn = st.button("Провери код")

        if check_btn and voucher_code.strip():
            ok, result = db.validate_voucher_for_use(voucher_code.strip())
            if ok:
                st.session_state.checked_voucher = result
                st.success(f"Ваучер „{result['code']}“ е активен. "
                           f"Номинал: {result['nominal']:.2f} лв. "
                           f"Валиден до: {result['valid_until']}.")
            else:
                st.session_state.checked_voucher = None
                st.error(result)

        # Активният валидиран ваучер живее в session_state (преживява клика).
        voucher_validated = st.session_state.get("checked_voucher")    

    # --- Фактура (опционално) ---
    issue_invoice = st.checkbox("Издаване на фактура при продажбата")
    invoice_data = None
    if issue_invoice:
        st.subheader("Данни за фактура")
        ic1, ic2 = st.columns(2)
        with ic1:
            inv_number = st.text_input("Номер на фактура",
                                       value=f"{order_number}" if order_number else "")
            buyer_company = st.text_input("Име на фирма")
            buyer_eik = st.text_input("ЕИК/Булстат")
        with ic2:
            buyer_mol = st.text_input("МОЛ")
            buyer_address = st.text_input("Адрес")
            buyer_email = st.text_input("Имейл")
        invoice_data = {
            "invoice_number": inv_number, "buyer_company": buyer_company,
            "buyer_eik": buyer_eik, "buyer_mol": buyer_mol,
            "buyer_address": buyer_address, "buyer_email": buyer_email,
        }

    st.divider()
    st.subheader("Добавяне на стока чрез ISBN")

    # --- Добавяне на ред ---
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        sale_isbn = st.text_input("Сканирай/въведи ISBN", key="sale_isbn")
    with sc2:
        sale_qty = st.number_input("Количество", min_value=1, value=1, step=1, key="sale_qty")

    if st.button("Добави към продажбата"):
        book = db.get_product_for_sale(sale_isbn.strip())
        if book is None:
            st.error(f"Няма книга с ISBN „{sale_isbn}“.")
        elif book["stock"] < sale_qty:
            st.error(f"Недостатъчна наличност (налични: {book['stock']}).")
        else:
            st.session_state.sale_cart.append({
                "product_id": book["id"],
                "title": book["title"],
                "supplier_name": book["supplier_name"],
                "quantity": sale_qty,
                "cost_price": book["last_cost"],
                "sale_price": book["cover_price"],
            })
            st.success(f"Добавена: {book['title']}")

    # --- Кошница ---
    if st.session_state.sale_cart:
        st.subheader("Стоки в продажбата")
        df = pd.DataFrame(st.session_state.sale_cart)
        df["ред_продажна"] = df["quantity"] * df["sale_price"]
        df["ред_доставна"] = df["quantity"] * df["cost_price"]
        st.dataframe(
            df[["title", "supplier_name", "quantity", "cost_price",
                "sale_price", "ред_продажна"]],
            width='stretch', hide_index=True
        )

        total_sale = df["ред_продажна"].sum()
        total_cost = df["ред_доставна"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Продажна сума", f"{total_sale:.2f} лв.")
        m2.metric("Доставна сума", f"{total_cost:.2f} лв.")
        m3.metric("Печалба", f"{total_sale - total_cost:.2f} лв.")

        cA, cB = st.columns(2)
        with cA:
            if st.button("Завърши продажбата", type="primary"):
                if use_voucher:
                    if not voucher_validated:
                        st.error("Първо провери ваучера с бутона „Провери код“.")
                        st.stop()

                    total_sale = sum(i["quantity"] * i["sale_price"]
                                     for i in st.session_state.sale_cart)
                    nominal = voucher_validated["nominal"]

                    if total_sale > nominal:
                        # Доплащане — ползваме начина на плащане от менюто горе.
                        diff = total_sale - nominal
                        st.info(f"Сумата ({total_sale:.2f} лв.) надвишава ваучера "
                                f"({nominal:.2f} лв.). Доплащане {diff:.2f} лв. "
                                f"с „{payment_method}“ (от полето горе).")
                        ok, msg = db.create_sale_with_voucher(
                            order_number, waybill_number,
                            st.session_state.sale_cart, voucher_validated["id"],
                            supplementary_method=payment_method,
                            invoice_data=invoice_data
                        )
                    elif total_sale < nominal:
                        # Без ресто — двойно потвърждение.
                        st.warning(f"Сумата ({total_sale:.2f} лв.) е под номинала. "
                                   f"Разликата от {nominal - total_sale:.2f} лв. "
                                   f"се губи. Натисни „Завърши“ пак за потвърждение.")
                        if not st.session_state.get("voucher_loss_acknowledged"):
                            st.session_state.voucher_loss_acknowledged = True
                            st.stop()
                        ok, msg = db.create_sale_with_voucher(
                            order_number, waybill_number,
                            st.session_state.sale_cart, voucher_validated["id"],
                            invoice_data=invoice_data
                        )
                    else:
                        # Точно — сумата = номинала.
                        ok, msg = db.create_sale_with_voucher(
                            order_number, waybill_number,
                            st.session_state.sale_cart, voucher_validated["id"],
                            invoice_data=invoice_data
                        )
                else:
                    # Стандартна продажба, без ваучер.
                    ok, msg = db.create_sale(
                        order_number, waybill_number,
                        st.session_state.sale_cart, payment_method, invoice_data
                    )

                if ok:
                    st.success(msg)
                    st.session_state.sale_cart = []
                    st.session_state.checked_voucher = None
                    st.session_state.voucher_loss_acknowledged = False
                    st.rerun()
                else:
                    st.error(msg)
        with cB:
            if st.button("Изчисти"):
                st.session_state.sale_cart = []
                st.rerun()


# ----- ЕКРАН: AI МАРКЕТИНГ -----
elif section == "AI Маркетинг":
    st.title("🎯 AI Маркетинг асистент")
    st.caption("Автоматично генериране на промоции за залежала стока")

    # Праг за залежаване (default 90 дни, потребителят може да го промени)
    days_threshold = st.number_input(
        "Праг за залежаване (дни без продажба)",
        min_value=30, max_value=365, value=90, step=10,
        help="По подразбиране: 90 дни. По-малък праг = по-агресивна промоция."
    )

    # Минимален марж след отстъпка — гарантира че не сваляме под прага.
    min_margin = st.number_input(
        "Минимален марж след отстъпка (%)",
        min_value=0, max_value=50, value=10, step=1,
        help="По подразбиране: 10%. Промоция, която би сваляла маржа под този праг, "
             "не се препоръчва за съответния продукт."
    )

    # Голям контрастен бутон — главното действие на екрана.
    if st.button("🚀 ГЕНЕРИРАЙ ПРОМОЦИЯ ЗА ЗАЛЕЖАЛА СТОКА",
                 type="primary", use_container_width=True):
        st.session_state.promo_generated = True

    # Пазим резултата в session_state — иначе при всеки клик ще се преизчислява.
    if st.session_state.get("promo_generated"):
        stale = db.get_stale_inventory(days_threshold, min_margin)

        if not stale:
            st.success("Няма залежала стока. Целият инвентар се движи активно. 🎉")
        else:
            st.divider()
            st.subheader("Препоръчителна промоционална кампания")

            df = pd.DataFrame(stale).rename(columns={
                "isbn": "ISBN", "title": "Заглавие", "supplier": "Доставчик",
                "stock": "Налични (бр.)",
                "unit_cost_no_vat": "Доставна (без ДДС)",
                "cover_price": "Оригинална цена",
                "current_margin_percent": "Текущ марж %",
                "discount_percent": "Препоръчана отстъпка %",
                "promo_price": "Нова промо цена",
                "new_margin_percent": "Марж след отстъпка %",
                "potential_revenue": "Потенциален оборот",
                "potential_profit": "Потенциална печалба",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

            # --- AI Заключение (шаблонен текст с реалните числа) ---
            total_titles = len(stale)
            total_units = sum(r["stock"] for r in stale)
            total_revenue = sum(r["potential_revenue"] for r in stale)
            total_profit = sum(r["potential_profit"] for r in stale)

            st.divider()
            st.markdown(f"""
            ### 🤖 AI Заключение

            Намерени са **{total_titles}** залежали заглавия с общо **{total_units}** бройки.
            Ако одобриш тази промоционална кампания и разпродадеш стоката с предложените
            отстъпки, **Bookspace** ще освободи складово пространство за нови заглавия
            и ще генерира **{total_revenue:.2f} лв.** свеж оборот, от които
            **{total_profit:.2f} лв.** ще бъдат чиста печалба (реализиран марж).
            """)

            # --- Excel експорт за сайта ---
            st.divider()
            excel_bytes = db.build_promotion_excel(stale)
            st.download_button(
                "📥 Експорт на промо кампанията в Excel (за сайта)",
                data=excel_bytes,
                file_name=f"promo_kampania_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )                


# ----- ЕКРАН: ВАУЧЕРИ -----
elif section == "Ваучери":
    st.title("Подаръчни ваучери")
    tab_issue, tab_list = st.tabs(["Издай ваучер", "Списък"])

    # --- ТАБ 1: ИЗДАВАНЕ ---
    with tab_issue:
        st.subheader("Издаване на нов ваучер")
        st.caption("Срок на валидност: 1 година. Кодът се генерира автоматично.")

        with st.form("form_issue_voucher", clear_on_submit=True):
            nominal = st.number_input("Номинал (лв.)", min_value=1.0,
                                      value=50.0, step=5.0)
            pay_method = st.selectbox("Как клиентът плаща ваучера", [
                "В брой (Каса)",
                "Банков път / Карта",
                "Пощенски паричен превод (Куриер)",
            ])
            submitted = st.form_submit_button("Издай ваучер", type="primary")

            if submitted:
                ok, result = db.issue_voucher(nominal, pay_method)
                if ok:
                    st.session_state.last_voucher = result
                    st.rerun()
                else:
                    st.error(result)

        # Ако в session_state има току-що издаден ваучер, показваме разписката.
        if "last_voucher" in st.session_state and st.session_state.last_voucher:
            v = st.session_state.last_voucher
            st.success("Ваучерът е издаден успешно!")
            # Подобие на разписка — лесно за прочитане/преписване на хартия.
            st.markdown(f"""
                **Код на ваучера:** `{v['code']}`
                **Номинал:** {v['nominal']:.2f} лв.
                **Валиден до:** {v['valid_until']}
            """)
            if st.button("Изчисти"):
                st.session_state.last_voucher = None
                st.rerun()

    # --- ТАБ 2: СПИСЪК ---
    with tab_list:
        st.subheader("Списък на ваучерите")

        sel_status = st.selectbox("Филтър по статус",
            ["(всички)", "Активен", "Използван", "Изтекъл"])
        status_arg = None if sel_status == "(всички)" else sel_status

        vouchers = db.get_all_vouchers(status=status_arg)

        # Обобщение
        active = [v for v in vouchers if v["status"] == "Активен"]
        used = [v for v in vouchers if v["status"] == "Използван"]
        expired = [v for v in vouchers if v["status"] == "Изтекъл"]
        total_active_value = sum(v["nominal"] for v in active)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Активни", len(active))
        m2.metric("Използвани", len(used))
        m3.metric("Изтекли", len(expired))
        m4.metric("Стойност на активните", f"{total_active_value:.2f} лв.")

        st.divider()

        if not vouchers:
            st.info("Няма ваучери по този критерий.")
        else:
            df = pd.DataFrame(vouchers)
            # Подреждаме и преименуваме колоните за четим вид.
            df = df[["code", "nominal", "status", "valid_until",
                     "issued_at", "used_at"]].rename(columns={
                "code": "Код", "nominal": "Номинал",
                "status": "Статус", "valid_until": "Валиден до",
                "issued_at": "Издаден на", "used_at": "Използван на",
            })
            st.dataframe(df, width='stretch', hide_index=True)

# ----- ЕКРАН: ЖУРНАЛ НА ПРОДАЖБИТЕ (Модул 5) -----
elif section == "Журнал продажби":
    st.title("Журнал на продажбите")

    # --- Филтри ---
    f1, f2, f3 = st.columns(3)
    with f1:
        sel_status = st.selectbox(
            "Статус", ["(всички)", "Чака плащане", "Платена", "Отказана"])
    with f2:
        date_from = st.date_input("От дата", value=None, key="sales_from")
    with f3:
        date_to = st.date_input("До дата", value=None, key="sales_to")

    status_arg = None if sel_status == "(всички)" else sel_status
    from_arg = str(date_from) if date_from else None
    to_arg = str(date_to) if date_to else None

    sales = db.get_sales(status=status_arg, date_from=from_arg, date_to=to_arg)

    # --- ФИНАНСОВ ПАНЕЛ: трите потока разделени ---
    # Групираме сумите по статус, за да видим пълната картина наведнъж.
    realized_sale = realized_cost = 0.0   # Платена — реализиран оборот
    pending_sale = 0.0                     # Чака плащане — в очакване
    cancelled_sale = 0.0                   # Отказана — сторнирано

    for s in sales:
        if s["status"] == "Платена":
            realized_sale += s["total_sale"]
            realized_cost += s["total_cost"]   # доставната ни трябва само за печалбата
        elif s["status"] == "Чака плащане":
            pending_sale += s["total_sale"]
        elif s["status"] == "Отказана":
            cancelled_sale += s["total_sale"]

    # Чистата печалба се смята САМО от реализираните (платени) продажби —
    # печалба от непродаден или сторниран товар няма.
    realized_profit = realized_sale - realized_cost

    # Първи ред: трите потока оборот
    st.subheader("Оборот по статус")
    o1, o2, o3 = st.columns(3)
    o1.metric("✅ Реализиран (платени)", f"{realized_sale:.2f} лв.")
    o2.metric("⏳ В очакване (чака плащане)", f"{pending_sale:.2f} лв.")
    o3.metric("↩️ Сторниран (отказани)", f"{cancelled_sale:.2f} лв.")

    # Втори ред: обобщаващи показатели
    st.subheader("Обобщение")
    m1, m2, m3 = st.columns(3)
    m1.metric("Брой продажби", len(sales))
    m2.metric("Доставна сума (реализ.)", f"{realized_cost:.2f} лв.")
    m3.metric("Чиста печалба (реализ.)", f"{realized_profit:.2f} лв.")

    st.divider()

    if not sales:
        st.info("Няма продажби по тези критерии.")
    else:
        df = pd.DataFrame([dict(s) for s in sales])

            # Сглобяваме читаемо описание на плащането, особено за ваучер с доплащане.
        def describe_payment(row):
                method = row["payment_method"]
                supp_method = row["supplementary_payment_method"]
                supp_amount = row["supplementary_amount"]
                if method == "Ваучер" and supp_amount > 0:
                    # Ваучер + доплащане
                    return f"Ваучер + {supp_method} ({supp_amount:.2f} лв.)"
                return method

        df["Плащане"] = df.apply(describe_payment, axis=1)

            # Подреждаме колоните за по-добра видимост — плащането близо до сумите.
        preferred_cols = ["id", "created_at", "order_number", "waybill_number",
                              "status", "payment_date", "Плащане",
                              "total_cost", "total_sale", "invoice_issued"]
        df = df[[c for c in preferred_cols if c in df.columns]]

        st.dataframe(df, width='stretch', hide_index=True)

        # --- Смяна на статус ---
        st.divider()
        st.subheader("Промяна на статус")
        sale_labels = {}
        for s in sales:
            # Ако няма номер на поръчка, показваме "(без номер)" вместо празно.
            order_part = s["order_number"] if s["order_number"] else "(без номер)"
            # ID-то отпред гарантира уникалност — две продажби никога нямат еднакво id.
            label = (f"#{s['id']} · №{order_part} · {s['status']} "
                     f"· {s['total_sale']:.2f} лв. · {s['created_at']}")
            sale_labels[label] = s["id"]

        chosen = st.selectbox("Избери продажба", list(sale_labels.keys()))
        chosen_id = sale_labels[chosen]

        new_status = st.selectbox("Нов статус",
                                  ["Чака плащане", "Платена", "Отказана"])
        if st.button("Приложи статус"):
            if new_status == "Отказана":
                # Сигнализираме, че трябва форма за касовата бележка.
                st.session_state.pending_cancel = chosen_id
            else:
                db.set_sale_status(chosen_id, new_status)
                st.success(f"Статусът е сменен на „{new_status}“.")
                st.rerun()

        # --- Форма за сторно (появява се само при отказване) ---
        if st.session_state.get("pending_cancel") == chosen_id:
            st.warning("Отказване на поръчката — необходимо е кредитно известие.")
            receipt = st.text_input("Номер на оригинална касова бележка / Е-бон")
            if st.button("Потвърди сторното", type="primary"):
                if not receipt.strip():
                    st.error("Номерът на касовата бележка е задължителен.")
                else:
                    ok, msg = db.cancel_sale(chosen_id, receipt.strip())
                    if ok:
                        st.success(msg)
                        st.session_state.pending_cancel = None
                        st.rerun()
                    else:
                        st.error(msg)        

        # --- ЕКСПОРТ ЗА ПОВТОРНА ПОРЪЧКА ---
        st.divider()
        st.subheader("Експорт за повторна поръчка")
        if from_arg and to_arg:
            reorder = db.get_sold_books_for_reorder(from_arg, to_arg)
            if reorder:
                reorder_df = pd.DataFrame([dict(r) for r in reorder])
                # to_csv връща низ; кодираме го за сваляне. utf-8-sig слага BOM,
                # за да се отвори правилно кирилицата в Excel.
                csv = reorder_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Свали CSV (групирано по доставчик)",
                    data=csv,
                    file_name=f"reorder_{from_arg}_{to_arg}.csv",
                    mime="text/csv"
                )
                st.dataframe(reorder_df, width='stretch', hide_index=True)
            else:
                st.info("Няма продадени книги в периода.")
        else:
            st.info("Задай период (от/до дата), за да генерираш експорт.")


# ----- ЕКРАН: АВТОМАТИЧНИ ЗАЯВКИ КЪМ ИЗДАТЕЛСТВА -----
elif section == "Автоматични заявки":
    st.title("📨 Автоматични заявки към издателства")
    st.caption("Заявки за зареждане до издателствата — от продажбите в системата "
               "или от експортен файл на онлайн магазина.")

    tab_internal, tab_file = st.tabs(["От продажбите в системата",
                                      "Импорт от файл (онлайн магазин)"])

    # ============ ТАБ 1: ОТ ПРОДАЖБИТЕ В СИСТЕМАТА ============
    with tab_internal:
        # Филтър за ден — по подразбиране днес.
        order_day = st.date_input("Обобщи продажбите за ден", value=date.today(),
                                  key="reorder_day")

        # Голям контрастен бутон — главното действие на екрана.
        if st.button("📨 ИЗПРАТИ АВТОМАТИЧНИ ЗАЯВКИ ЗА ЗАРЕЖДАНЕ",
                     type="primary", use_container_width=True, key="send_internal"):
            st.session_state.reorder_run_day = str(order_day)

        # Изпълняваме само ако бутонът е натиснат за този ден (пази при rerun).
        if st.session_state.get("reorder_run_day") == str(order_day):
            rows = db.get_daily_supplier_reorders(str(order_day))

            if not rows:
                st.info(f"Няма продадени книги за {order_day}. Няма какво да се заяви.")
            else:
                # --- Стъпка Б: групираме продадените книги по доставчик ---
                by_supplier = {}
                for r in rows:
                    grp = by_supplier.setdefault(r["supplier_id"], {
                        "name": r["supplier_name"],
                        "email": r["supplier_email"],
                        "items": [],
                    })
                    grp["items"].append(r)

                st.success(f"Намерени са продажби за **{len(by_supplier)}** "
                           f"издателства на {order_day}.")
                st.divider()

                # --- Стъпка В: цикъл по доставчиците и изпращане ---
                for supplier_id, grp in by_supplier.items():
                    # Всяко издателство в собствен заоблен контейнер.
                    with st.container(border=True):
                        st.subheader(f"🏢 {grp['name']}")

                        # Стъпка Г: красивата HTML таблица (Sleek Monochrome).
                        html_table = mailer.build_order_html_table(grp["items"])

                        # Преглед на самия имейл (както ще го види издателството).
                        with st.expander("Преглед на имейла"):
                            email_html = mailer.build_order_email_html(
                                grp["name"], str(order_day), html_table)
                            st.markdown(email_html, unsafe_allow_html=True)

                        total_units = sum(i["total_sold"] for i in grp["items"])
                        st.caption(f"{len(grp['items'])} заглавия · "
                                   f"{total_units} бройки за заявка")

                        # Изпращане — симулация. Ако имейлът липсва/невалиден,
                        # предупреждаваме (имейлът е задължителен по картотека).
                        if not mailer.is_valid_email(grp["email"]):
                            st.warning(f"⚠️ Издателство „{grp['name']}“ няма валиден "
                                       f"имейл в картотеката. Заявката не е изпратена. "
                                       f"Допълнете имейла в раздел „Доставчици“.")
                        else:
                            mailer.send_supplier_email(
                                grp["name"], grp["email"], html_table)

    # ============ ТАБ 2: ИМПОРТ ОТ ФАЙЛ (ОНЛАЙН МАГАЗИН) ============
    with tab_file:
        st.caption("Качи експорт от онлайн магазина. Системата разпознава "
                   "ISBN/количество, свързва ги с каталога и групира заявката "
                   "по издателство.")

        uploaded = st.file_uploader(
            "Качи експортен файл с продажби от сайта (Excel / CSV)",
            type=["xlsx", "csv"])

        if uploaded is not None:
            # --- Стъпка 1: четене на файла ---
            try:
                df = importer.read_sales_file(uploaded)
            except Exception as e:
                st.error(f"Неуспешно прочитане на файла: {e}")
                df = None

            if df is not None:
                cols = importer.detect_columns(df)
                if not cols["qty"] or (not cols["isbn"] and not cols["title"]):
                    st.error("Не открих нужните колони. Очаквам „Количество“ и "
                             "поне едно от „ISBN/Баркод“ или „Заглавие“.")
                else:
                    parsed = importer.parse_rows(df, cols)
                    if not parsed:
                        st.warning("Файлът е прочетен, но няма валидни редове "
                                   "(липсва ISBN/заглавие или количеството е 0).")
                    else:
                        # --- Стъпка 1+2: едно зареждане на каталога, после
                        # засичане в паметта (по ISBN, после по заглавие) ---
                        catalog = db.get_catalog_for_matching()
                        matched_list, unmatched = importer.resolve_rows(parsed, catalog)
                        # --- Стъпка 3: групиране по доставчик ---
                        groups = importer.group_matched(matched_list)

                        n_matched = len(matched_list)
                        by_isbn = sum(1 for m in matched_list if m["method"] == "isbn")
                        by_title = sum(1 for m in matched_list if m["method"] == "title")
                        st.success(f"Успешно обработени {n_matched} продукта от файла!")
                        if n_matched:
                            st.caption(f"Засечени: {by_isbn} по ISBN · "
                                       f"{by_title} по заглавие.")

                        # --- Стъпка 3 (визуализация): таблица по доставчик ---
                        if groups:
                            st.divider()
                            for supplier_id, g in groups.items():
                                with st.container(border=True):
                                    st.subheader(f"🏢 {g['name']}")
                                    tdf = pd.DataFrame(g["items"])
                                    tdf.insert(0, "Доставчик", g["name"])
                                    tdf = tdf.rename(columns={
                                        "isbn": "ISBN", "title": "Заглавие",
                                        "delivery_price": "Доставна цена",
                                        "cover_price": "Корична цена",
                                        "qty": "Бройка за поръчка",
                                        "line_delivery": "Обща стойност",
                                    })
                                    view_cols = ["Доставчик", "ISBN", "Заглавие",
                                                 "Доставна цена", "Корична цена",
                                                 "Бройка за поръчка", "Обща стойност"]
                                    st.dataframe(tdf[view_cols], width='stretch',
                                                 hide_index=True)
                                    st.caption(
                                        f"{len(g['items'])} заглавия · "
                                        f"{g['total_qty']} бройки · обща доставна "
                                        f"{g['total_delivery']:.2f} лв.")
                                    if not mailer.is_valid_email(g["email"]):
                                        st.warning(f"⚠️ „{g['name']}“ няма валиден "
                                                   "имейл — няма да получи заявка.")

                            st.divider()
                            # --- Стъпка 4: изпращане на данните ОТ ФАЙЛА ---
                            if st.button("📨 ИЗПРАТИ АВТОМАТИЧНИ ЗАЯВКИ ЗА ЗАРЕЖДАНЕ",
                                         type="primary", use_container_width=True,
                                         key="send_from_file"):
                                sent = 0
                                for supplier_id, g in groups.items():
                                    if not mailer.is_valid_email(g["email"]):
                                        continue
                                    # Към формата на имейл таблицата (qty->total_sold).
                                    email_items = [{
                                        "isbn": i["isbn"], "title": i["title"],
                                        "author": i["author"], "total_sold": i["qty"],
                                    } for i in g["items"]]
                                    html_table = mailer.build_order_html_table(email_items)
                                    mailer.send_supplier_email(
                                        g["name"], g["email"], html_table)
                                    sent += 1
                                if sent == 0:
                                    st.warning("Няма издателство с валиден имейл — "
                                               "нищо не е изпратено.")
                        else:
                            st.info("Все още няма съвпадащи с каталога продукти "
                                    "за заявка.")

                        # --- ЗАЩИТА: панел за НЕПОЗНАТИ продукти ---
                        # Не спираме работа — даваме възможност да се създадат на
                        # момента и да влязат в заявките към доставчиците.
                        if unmatched:
                            st.divider()
                            st.warning("⚠️ Открити са продукти от сайта, които "
                                       "липсват в базата данни на Bookspace")

                            sup_rows = db.get_all_suppliers()
                            if not sup_rows:
                                st.info("Първо добавете поне един доставчик в раздел "
                                        "„Доставчици“, за да създадете липсващите книги.")
                            else:
                                sup_names = [s["name"] for s in sup_rows]
                                sup_name_to_id = {s["name"]: s["id"] for s in sup_rows}

                                # Динамична таблица: ISBN/Заглавие/Корична от файла,
                                # плюс интерактивно падащо меню за доставчик на ред.
                                unknown_df = pd.DataFrame([{
                                    "ISBN": u["isbn"],
                                    "Заглавие": u["title"] or "",
                                    "Количество": int(u["qty"]),
                                    "Корична цена": float(u["cover_price"] or 0.0),
                                    "Доставчик/Издателство": "",
                                } for u in unmatched])

                                st.caption("Въведи продажна (корична) цена и избери "
                                           "издателство за всеки ред. Доставната цена се "
                                           "изчислява автоматично от стандартната отстъпка "
                                           "на доставчика. (За редове само със заглавие "
                                           "попълни и ISBN.)")
                                edited = st.data_editor(
                                    unknown_df, key="unknown_products_editor",
                                    width='stretch', hide_index=True,
                                    column_config={
                                        "ISBN": st.column_config.TextColumn("ISBN"),
                                        "Заглавие": st.column_config.TextColumn("Заглавие"),
                                        "Количество": st.column_config.NumberColumn(
                                            "Количество (от файла)", disabled=True),
                                        "Корична цена": st.column_config.NumberColumn(
                                            "Въведи Продажна (Корична) цена",
                                            min_value=0.0, step=0.5, format="%.2f"),
                                        "Доставчик/Издателство": st.column_config.SelectboxColumn(
                                            "Избери Доставчик/Издателство",
                                            options=sup_names),
                                    })

                                if st.button("➕ СЪЗДАЙ И ДОБАВИ ЛИПСВАЩИТЕ ПРОДУКТИ",
                                             type="primary", use_container_width=True,
                                             key="create_missing_products"):
                                    created, errors, skipped = 0, [], 0
                                    for _, row in edited.iterrows():
                                        sup_name = (row["Доставчик/Издателство"] or "").strip()
                                        if not sup_name or sup_name not in sup_name_to_id:
                                            skipped += 1
                                            continue
                                        isbn = str(row["ISBN"] or "").strip()
                                        if not isbn:
                                            # ISBN е задължителен ключ в каталога.
                                            errors.append("(ред без ISBN) — попълни ISBN")
                                            continue
                                        title = (str(row["Заглавие"]) or "").strip() or isbn
                                        try:
                                            cover = float(row["Корична цена"] or 0.0)
                                        except (ValueError, TypeError):
                                            cover = 0.0
                                        # Създаваме книгата веднага (9% ДДС, група Б).
                                        ok, msg = db.add_product(
                                            isbn, title, "", sup_name_to_id[sup_name],
                                            cover, 9.0, 0, "", "", "",
                                            product_type="Книга", fiscal_group="Б")
                                        if ok:
                                            created += 1
                                        else:
                                            errors.append(f"{isbn}: {msg}")

                                    if created:
                                        st.success(f"✅ Успешно интегрирани {created} "
                                                   "нови заглавия в каталога!")
                                    if errors:
                                        st.warning("Някои не бяха създадени:\n\n- "
                                                   + "\n- ".join(errors))
                                    if skipped and not created:
                                        st.info("Избери издателство поне за един ред.")
                                    if created:
                                        # Реобработваме файла — създадените вече се
                                        # разпознават и влизат в заявките за деня.
                                        st.rerun()


# ----- ЕКРАН: КРЕДИТНИ ИЗВЕСТИЯ (Модул 6) -----
elif section == "Кредитни известия":
    st.title("Журнал на кредитните известия")

    # Филтър по месец. Текстово поле във формат YYYY-MM, празно = всички.
    month = st.text_input("Месец (формат ГГГГ-ММ, напр. 2026-05) — празно за всички")
    month_arg = month.strip() if month.strip() else None

    notes = db.get_credit_notes(year_month=month_arg)

    # Обобщение
    total_count = len(notes)
    total_returned = sum(n["returned_amount"] for n in notes)
    m1, m2 = st.columns(2)
    m1.metric("Брой сторна", total_count)
    m2.metric("Обща върната сума", f"{total_returned:.2f} лв.")

    st.divider()

    if not notes:
        st.info("Няма кредитни известия по този критерий.")
    else:
        df = pd.DataFrame([dict(n) for n in notes])
        st.dataframe(df, width='stretch', hide_index=True)



# ----- ЕКРАН: СКЛАД И ОДИТ (Модул 7) -----
elif section == "Склад и одит":
    st.title("Склад и одит на продукт")

    # --- Бързо търсене ---
    search = st.text_input("Търси по заглавие, автор или ISBN")
    search_arg = search.strip() if search.strip() else None

    stock = db.search_stock(search_arg)

    if not stock:
        st.info("Няма намерени книги.")
    else:
        # Текущи наличности
        st.subheader("Текущи наличности")
        df = pd.DataFrame([dict(s) for s in stock])
        st.dataframe(df, width='stretch', hide_index=True)

        # --- Одит на конкретна книга ---
        st.divider()
        st.subheader("История на движенията")

        # Уникален етикет с id отпред (поуката от модул 5).
        book_labels = {
            f"#{b['id']} · {b['title']} · наличност: {b['stock']}": b["id"]
            for b in stock
        }
        chosen = st.selectbox("Избери книга за одит", list(book_labels.keys()))
        chosen_id = book_labels[chosen]

        history = db.get_product_history(chosen_id)

        if not history:
            st.info("Тази книга няма движения все още.")
        else:
            hist_df = pd.DataFrame([dict(h) for h in history])
            # Преименуваме колоните на четими български етикети за таблицата.
            hist_df = hist_df.rename(columns={
                "created_at": "Дата и час",
                "movement_type": "Тип",
                "quantity_change": "Промяна",
                "document_ref": "Документ",
                "operator": "Оператор",
            })
            st.dataframe(hist_df, width='stretch', hide_index=True)

            # Малко обобщение под историята — потвърждава, че сборът на
            # движенията дава точно текущата наличност. Това е "доказателството".
            total = sum(h["quantity_change"] for h in history)
            st.metric("Наличност (сбор от движенията)", total)

# ----- ЕКРАН: ГОДИШНО ПРИКЛЮЧВАНЕ И ИНВЕНТАРИЗАЦИЯ -----
elif section == "Годишно приключване":
    from datetime import date

    st.title("Годишно приключване и инвентаризация")
    st.caption("Опис на склада към избрана дата с разделение по тип уреждане")

    # Дата на справката. По подразбиране — 31 декември миналата година,
    # понеже инвентаризацията най-често се прави за приключилия отчетен период.
    today_d = date.today()
    default_date = date(today_d.year - 1, 12, 31)
    as_of = st.date_input("Опис към дата", value=default_date, key="inv_date")

    tab_inventory, tab_writedown = st.tabs(["Инвентаризация", "Обезценка (ЗКПО)"])

    with tab_inventory:
        snapshot = db.get_inventory_snapshot(str(as_of))

        if not snapshot:
            st.info("Няма налична стока към избраната дата.")
        
        else:
            # --- ТРИТЕ КЛЮЧОВИ СУМИ ---
            # 1) Собствен счетоводен актив: само купените бройки × доставна без ДДС.
            own_asset = sum(r["purchased_value"] for r in snapshot)
            # 2) Задбалансова стока: консигнационните бройки × доставна без ДДС.
            consigned_asset = sum(r["consigned_value"] for r in snapshot)
            # 3) Потенциален оборот: ВСИЧКА налична стока × корична цена (пазарна).
            potential = sum(r["potential_revenue"] for r in snapshot)

            st.subheader("Финансови показатели към " + str(as_of))
            m1, m2, m3 = st.columns(3)
            m1.metric("Собствен счетоводен актив",
                    f"{own_asset:.2f} лв.",
                    help="Сборът от доставните цени (без ДДС) на КУПЕНИТЕ книги. "
                        "Това са реалните активи на фирмата за баланса.")
            m2.metric("Стока на чуждо съхранение",
                    f"{consigned_asset:.2f} лв.",
                    help="Доставна стойност на консигнационните бройки. "
                        "Не са собственост на фирмата — задбалансови активи.")
            m3.metric("Потенциален оборот",
                    f"{potential:.2f} лв.",
                    help="Пазарна стойност (корична цена) на всичко налично.")

            st.divider()

            # --- ТАБЛИЦАТА С ОПИСА ---
            st.subheader("Подробен опис")

            df = pd.DataFrame(snapshot)
            # Преименуваме колоните на български етикети за справката.
            df = df.rename(columns={
                "isbn": "ISBN", "title": "Заглавие", "author": "Автор",
                "supplier": "Доставчик",
                "purchased_stock": "Купени (бр.)",
                "consigned_stock": "Консигнация (бр.)",
                "total_stock": "Общо (бр.)",
                "unit_cost_no_vat": "Ед. доставна (без ДДС)",
                "purchased_value": "Стойност купени",
                "consigned_value": "Стойност консигнация",
                "cover_price": "Корична цена",
                "potential_revenue": "Потенциал (пазарна)",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_writedown:
        st.subheader("Предложение за обезценка на залежала стока")
        st.caption("Книги без оборот в последните 12 месеца, доставени преди "
                   "поне 1 година. Според ЗКПО подлежат на обезценка, която "
                   "намалява финансовия резултат и дължимия данък печалба.")

        dead = db.get_dead_inventory()

        if not dead:
            st.success("Няма книги, отговарящи на критериите за обезценка. "
                       "Целият инвентар е активен.")
        else:
            total_writedown = sum(r["total_value"] for r in dead)
            count = len(dead)

            m1, m2 = st.columns(2)
            m1.metric("Брой заглавия за обезценка", count)
            m2.metric("Предлагана обезценка (без ДДС)",
                      f"{total_writedown:.2f} лв.",
                      help="Сборната стойност, която може да се изпише като "
                           "разход за обезценка на залежали активи.")

            st.divider()

            df = pd.DataFrame(dead).rename(columns={
                "isbn": "ISBN", "title": "Заглавие", "author": "Автор",
                "supplier": "Доставчик", "stock": "Налични (бр.)",
                "first_delivery": "Първа доставка",
                "last_sale": "Последна продажба",
                "unit_cost_no_vat": "Ед. доставна (без ДДС)",
                "total_value": "Стойност за обезценка",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.info("💡 Този списък е **предложение** за счетоводителя, не автоматично "
                    "решение. Окончателната обезценка се документира със заповед на "
                    "управителя и протокол.")
            
    # --- Excel експорт за годишен баланс ---
    st.divider()
    st.subheader("Експорт за годишен баланс")
    st.caption("Excel с два листа: собствени активи (купена стока) и "
               "задбалансови активи (консигнация). Готов за подаване към НАП.")
    # Генерира се само при заявка (бутон), не при всяко презареждане на екрана.
    if st.button("Подготви инвентаризационен опис (Excel)", key="prep_inv_excel"):
        st.session_state.inv_excel = {"as_of": str(as_of), "data": db.build_inventory_excel(str(as_of))}
    inv = st.session_state.get("inv_excel")
    if inv and inv["as_of"] == str(as_of):
        st.download_button(
            "Свали инвентаризационен опис (Excel)",
            data=inv["data"],
            file_name=f"inventarizaciq_{as_of}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ----- ЕКРАН: ФИРМЕНИ РАЗХОДИ -----
elif section == "Фирмени Разходи":
    st.title("💰 Фирмени разходи")
    st.caption("Оперативни разходи на фирмата извън доставките")

    tab_add, tab_list = st.tabs(["Добави разход", "Списък по период"])

    # --- ТАБ 1: ДОБАВЯНЕ НА РАЗХОД ---
    with tab_add:
        with st.form("form_add_expense", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                exp_date = st.date_input("Дата на разхода",
                                         value=date.today(),
                                         help="Датата, на която разходът е настъпил "
                                              "(не когато го въвеждаш в системата)")
                category = st.selectbox("Категория", [
                    "Наем",
                    "Заплати и Осигуровки",
                    "Консумативи/Опаковки",
                    "Реклама и Маркетинг",
                    "Битови сметки/Ток/Интернет",
                    "Други",
                ])
            with c2:
                amount = st.number_input("Сума (лв.)", min_value=0.0,
                                         value=0.0, step=10.0)
                document_number = st.text_input("Номер на документ "
                                                "(фактура/разписка) — по избор")

            description = st.text_area("Описание",
                                       placeholder="напр. „Ток за месец Май“")

            submitted = st.form_submit_button("Запиши разхода", type="primary")

            if submitted:
                if amount <= 0:
                    st.error("Сумата трябва да е по-голяма от 0.")
                else:
                    ok, msg = db.add_expense(
                        str(exp_date), category, description.strip() or None,
                        amount, document_number.strip() or None
                    )
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    # --- ТАБ 2: СПИСЪК НА РАЗХОДИТЕ ---
    with tab_list:
        st.subheader("Филтри")
        f1, f2, f3 = st.columns(3)

        with f1:
            list_from = st.date_input("От дата", value=None, key="exp_from")
        with f2:
            list_to = st.date_input("До дата", value=None, key="exp_to")
        with f3:
            cat_filter = st.selectbox("Категория", [
                "(всички)", "Наем", "Заплати и Осигуровки",
                "Консумативи/Опаковки", "Реклама и Маркетинг",
                "Битови сметки/Ток/Интернет", "Други",
            ])

        from_arg = str(list_from) if list_from else None
        to_arg = str(list_to) if list_to else None
        cat_arg = None if cat_filter == "(всички)" else cat_filter

        expenses = db.get_expenses_by_period(from_arg, to_arg, cat_arg)

        total = sum(e["amount"] for e in expenses)
        st.metric("Общо за периода", f"{total:.2f} лв.")

        st.divider()

        if not expenses:
            st.info("Няма разходи по тези критерии.")
        else:
            df = pd.DataFrame(expenses).rename(columns={
                "id": "ID", "date": "Дата", "category": "Категория",
                "description": "Описание", "amount": "Сума",
                "document_number": "Документ №", "created_at": "Въведен на",
            })
            # Подреждаме видимите колони, скриваме id и created_at.
            visible_cols = ["Дата", "Категория", "Описание", "Сума", "Документ №"]
            st.dataframe(df[visible_cols], width='stretch', hide_index=True)

            # --- Изтриване ---
            st.divider()
            st.subheader("Изтриване на разход")

            # Етикет с уникален id отпред, за да няма колизии.
            exp_labels = {
                f"#{e['id']} · {e['date']} · {e['category']} · {e['amount']:.2f} лв.": e["id"]
                for e in expenses
            }
            chosen_label = st.selectbox("Избери разход за изтриване",
                                        list(exp_labels.keys()))
            chosen_id = exp_labels[chosen_label]

            # Двустепенно потвърждение — иначе един клик трие.
            if st.button("🗑️ Изтрий този разход"):
                st.session_state.pending_delete_expense = chosen_id

            if st.session_state.get("pending_delete_expense") == chosen_id:
                st.warning(f"Наистина ли искаш да изтриеш разход #{chosen_id}? "
                           f"Това действие е необратимо.")
                cA, cB = st.columns(2)
                with cA:
                    if st.button("Да, изтрий", type="primary"):
                        db.delete_expense(chosen_id)
                        st.session_state.pending_delete_expense = None
                        st.success("Разходът е изтрит.")
                        st.rerun()
                with cB:
                    if st.button("Отказ"):
                        st.session_state.pending_delete_expense = None
                        st.rerun()    