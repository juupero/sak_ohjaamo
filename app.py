import streamlit as st
import pandas as pd
import uuid
from streamlit_tags import st_tags

st.set_page_config(page_title="Päiväkodin SAK-kalenteri", layout="wide")

# Vakiot
DAYS = ["Maanantai", "Tiistai", "Keskiviikko", "Torstai", "Perjantai"]
HOURS = ["08-09", "09-10", "10-11", "11-12", "12-13", "13-14", "14-15", "15-16"]

RATIO_UNDER_3 = 4
RATIO_OVER_3 = 7
SAK_TARGET = 5

def init_session_state():
    if "all_teachers" not in st.session_state:
        st.session_state.all_teachers = ["MaijaO", "LiisaV", "MattiS"]
    if "all_nurses" not in st.session_state:
        st.session_state.all_nurses = ["PekkaH", "TiinaA", "VilleM"]
        
    if "groups" not in st.session_state:
        st.session_state.groups = [
            {
                "id": str(uuid.uuid4()), 
                "name": "Esimerkkiryhmä", 
                "daily_stats": {
                    day: {
                        "under_3": 0, "over_3": 12, "preschool": 0,
                        "teachers": ["MaijaO"], "nurses": ["PekkaH", "TiinaA"]
                    } for day in DAYS
                }
            },
        ]
    else:
        # Schema migration check: clear groups if they use old schema
        if len(st.session_state.groups) > 0 and "daily_stats" not in st.session_state.groups[0]:
            st.session_state.groups = []
            st.session_state.calendars = {}
    if "events" not in st.session_state:
        # Cross-group events like "Staff meeting Tuesday 13-14"
        st.session_state.events = []
    
    if "calendars" not in st.session_state:
        st.session_state.calendars = {}
        # Format: { group_id: DataFrame }
        
    if "loans" not in st.session_state:
        # Format: {"day": "Maanantai", "hour": "10-11", "teacher": "MaijaO", "from_group": "Ryhmä A ID", "to_group": "Ryhmä B ID"}
        st.session_state.loans = []

init_session_state()

def get_ratio_multiplier(group_type):
    if group_type == "Alle 3-vuotiaat":
        return 4
    return 7

def create_group_calendar():
    # Regular 8-16 hours + a special Capacity row at the bottom
    columns = []
    for day in DAYS:
        columns.append(day)
        columns.append(f"{day} SAK")
        columns.append(f"{day} Henkilöstö")
        columns.append(f"{day} Huomiot")
        
    df = pd.DataFrame(index=HOURS + ["Kapasiteetti"], columns=columns)
    
    # Pre-fill standard program (Generic baseline)
    for day in DAYS:
        df.loc["08-09", day] = "Aamupala ja leikki"
        df.loc["09-10", day] = "Ulkoilu"
        df.loc["10-11", day] = "Musiikkituokio / Lukuhetki"
        df.loc["11-12", day] = "Lounas"
        df.loc["12-13", day] = "Lepohetki"
        df.loc["13-14", day] = "Vapaa leikki"
        df.loc["14-15", day] = "Välipala ja leikki"
        df.loc["15-16", day] = "Ulkoilu / Kotiinlähtö"
        df.loc["Kapasiteetti", day] = ""
        df.loc[:, f"{day} SAK"] = ""
        df.loc[:, f"{day} Henkilöstö"] = ""
        df.loc[:, f"{day} Huomiot"] = ""
            
    return df

def init_calendars_for_groups():
    for g in st.session_state.groups:
        gid = g["id"]
        # Schema migration check: older states had a dict here
        if gid not in st.session_state.calendars or isinstance(st.session_state.calendars[gid], dict):
            st.session_state.calendars[gid] = create_group_calendar()
        else:
            for day in DAYS:
                col_name = f"{day} Henkilöstö"
                if col_name not in st.session_state.calendars[gid].columns:
                    st.session_state.calendars[gid][col_name] = ""
                col_name2 = f"{day} Huomiot"
                if col_name2 not in st.session_state.calendars[gid].columns:
                    st.session_state.calendars[gid][col_name2] = ""

init_calendars_for_groups()

def apply_events_to_calendars():
    for event in st.session_state.events:
        day, hour = event["day"], event["hour"]
        for gid, cal in st.session_state.calendars.items():
            if cal.loc[hour, day] not in ["Poissa"]:
                cal.loc[hour, day] = event["name"]

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("⚙️ Asetukset")
    
    st.subheader("Päiväkodin Henkilökunta")
    st.write("Määritä koko talon työntekijät:")
    st.session_state.all_teachers = st_tags(
        label='Opettajat (SAK)',
        text='Lisää uusi',
        value=st.session_state.all_teachers,
        key="global_teachers"
    )
    st.session_state.all_nurses = st_tags(
        label='Hoitajat (Ei SAK)',
        text='Lisää uusi',
        value=st.session_state.all_nurses,
        key="global_nurses"
    )

    st.subheader("Ryhmien hallinta")
    with st.expander("Lisää ryhmä"):
        new_name = st.text_input("Ryhmän nimi")
        if st.button("Lisää ryhmä"):
            if new_name:
                new_id = str(uuid.uuid4())
                st.session_state.groups.append({
                    "id": new_id, 
                    "name": new_name, 
                    "daily_stats": {
                        day: {
                            "under_3": 0, "over_3": 0, "preschool": 0,
                            "teachers": [], "nurses": []
                        } for day in DAYS
                    }
                })
                init_calendars_for_groups()
                st.rerun()

    st.subheader("Poista ryhmiä")
    to_remove = []
    for g in st.session_state.groups:
        if st.button(f"Poista: {g['name']}", key=f"del_{g['id']}"):
            to_remove.append(g["id"])
    
    if to_remove:
        st.session_state.groups = [g for g in st.session_state.groups if g["id"] not in to_remove]
        for rid in to_remove:
            if rid in st.session_state.calendars:
                del st.session_state.calendars[rid]
        st.rerun()

    st.subheader("Yhteiset menot")
    with st.expander("Lisää yhteinen meno (Koko talo)"):
        e_name = st.text_input("Tapahtuma (esim. Palaveri)")
        e_day = st.selectbox("Päivä", DAYS)
        e_hour = st.selectbox("Tunti", HOURS)
        if st.button("Lisää meno"):
            if e_name:
                st.session_state.events.append({"name": e_name, "day": e_day, "hour": e_hour})
                apply_events_to_calendars()
                st.rerun()

# ----------------- MASTER DASHBOARD -----------------
st.title("sak_ohjaamo - Päiväkodin Resurssi- ja SAK-ohjaamo")

total_children_mon = sum(g["daily_stats"]["Maanantai"]["under_3"] + g["daily_stats"]["Maanantai"]["over_3"] + g["daily_stats"]["Maanantai"]["preschool"] for g in st.session_state.groups)
total_staff_mon = sum(len(g["daily_stats"]["Maanantai"]["teachers"]) + len(g["daily_stats"]["Maanantai"]["nurses"]) for g in st.session_state.groups)

col1, col2 = st.columns(2)
col1.metric("Lapset yhteensä (Ma)", total_children_mon)
col2.metric("Henkilökunta yhteensä (Ma)", total_staff_mon)

st.divider()

# Ratios Check and SAK calculation logic (Finnish Law)
def calculate_child_load(under_3, over_3, preschool):
    return (under_3 * 1.75) + over_3 + preschool

def check_ratio(under_3, over_3, preschool, working_staff):
    child_load = calculate_child_load(under_3, over_3, preschool)
    capacity = working_staff * 7
    return capacity >= child_load

def calculate_group_buffer(g, day, hour):
    stats = g["daily_stats"][day]
    load = calculate_child_load(stats["under_3"], stats["over_3"], stats["preschool"])
    cal = st.session_state.calendars[g["id"]]
    
    sak_val = str(cal.loc[hour, f"{day} SAK"]) if hour in cal.index else ""
    if sak_val == "nan": sak_val = ""
    
    staff_val = str(cal.loc[hour, f"{day} Henkilöstö"]) if hour in cal.index and f"{day} Henkilöstö" in cal.columns else ""
    if staff_val == "nan": staff_val = ""
    
    working = len(stats["nurses"])
    for t_name in stats["teachers"]:
        if t_name not in sak_val and cal.loc[hour, day] != "Poissa":
            working += 1
    
    # Henkilöstö column is ADDITIVE: adds extra staff on top of the daily baseline
    if staff_val.strip() != "":
        extra_names = [s.strip() for s in staff_val.split(",") if s.strip()]
        for name in extra_names:
            if name not in sak_val:
                working += 1
            
    # Adjust for loans
    for loan in st.session_state.loans:
        if loan["day"] == day and loan["hour"] == hour:
            if loan["from_group"] == g["id"]:
                working -= 1
            elif loan["to_group"] == g["id"]:
                working += 1
                
    capacity = working * 7
    return capacity - load

st.subheader("Yleiskatsaus ja Hälytykset")

with st.expander("🏢 Päiväkodin tilannehuone (Tuntikohtainen resurssipuskuri)", expanded=False):
    st.markdown("Tämä taulukko näyttää jokaisen ryhmän **suhdelukupuskurin** tunneittain. Positiivinen lukema tarkoittaa, että ryhmässä on ylimääräistä kapasiteettia, ja negatiivinen tarkoittaa alimiehitystä.")
    
    th_day = st.selectbox("Valitse päivä tilannehuoneeseen", DAYS, key="th_day")
    
    th_cols = ["Ryhmä"] + HOURS
    th_data = []
    
    for g in st.session_state.groups:
        row = {"Ryhmä": g["name"]}
        for hour in HOURS:
            buf = calculate_group_buffer(g, th_day, hour)
            row[hour] = round(buf, 2)
        th_data.append(row)
        
    th_df = pd.DataFrame(th_data)
    
    def color_buffer(val):
        if isinstance(val, (int, float)):
            if val < 0:
                return "background-color: #f8d7da; color: #842029;"
            elif val >= 7:
                return "background-color: #d1e7dd; color: #0f5132;"
        return ""
        
    styled_df = th_df.style.map(color_buffer, subset=HOURS).format("{:.2f}", subset=HOURS)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    if st.session_state.loans:
        st.markdown("#### Aktiiviset henkilöstölainat")
        for loan in st.session_state.loans:
            from_name = next((g["name"] for g in st.session_state.groups if g["id"] == loan["from_group"]), "Tuntematon")
            to_name = next((g["name"] for g in st.session_state.groups if g["id"] == loan["to_group"]), "Tuntematon")
            st.write(f"- **{loan['day']} klo {loan['hour']}**: {from_name} ➡️ {to_name} (SAK: {loan['teacher']})")

alert_texts = []

for g in st.session_state.groups:
    for day in DAYS:
        stats = g["daily_stats"][day]
        total_staff = len(stats["teachers"]) + len(stats["nurses"])
        
        if not check_ratio(stats["under_3"], stats["over_3"], stats["preschool"], total_staff):
            alert_texts.append(f"⚠️ **{g['name']} ({day})**: Alimiehitetty! (Olosuhde: {stats['under_3']} alle 3v, {stats['over_3']} yli 3v, {stats['preschool']} eskarit vs {total_staff} aikuista)")
    
    # Check SAK hours
    cal = st.session_state.calendars[g["id"]]
    group_teachers = set(t for stats in g["daily_stats"].values() for t in stats["teachers"])
    for t_name in sorted(list(group_teachers)):
        sak_count = 0
        for day in DAYS:
            sak_col = f"{day} SAK"
            col_data = cal.loc[HOURS, sak_col].astype(str).tolist()
            sak_count += sum(1 for cell in col_data if t_name in cell)
            
        if sak_count < 5:
            alert_texts.append(f"🔵 **{g['name']} ({t_name})**: SAK-aikaa puuttuu {5 - sak_count} tuntia.")

if alert_texts:
    for a in alert_texts:
        st.markdown(a)
else:
    st.success("Kaikki suhdeluvut ja SAK-tavoitteet näyttävät hyvältä!")

st.divider()

# ----------------- AUTO-SUGGEST ALGORITHM -----------------
def suggest_sak_for_group(g):
    gid = g["id"]
    cal = st.session_state.calendars[gid]
    group_teachers = sorted(list(set(t for stats in g["daily_stats"].values() for t in stats["teachers"])))
    
    for t_name in group_teachers:
        current_sak = 0
        for day in DAYS:
            sak_col = f"{day} SAK"
            current_sak += sum(1 for cell in cal.loc[HOURS, sak_col].astype(str) if t_name in cell)
            
        if current_sak >= 5:
            continue
            
        needed = 5 - current_sak
        
        # Generator for hour checks: prioritize high buffer days, then 12-14
        search_space = []
        
        # Calculate buffer per day (capacity - load)
        day_buffers = {}
        for day in DAYS:
            stats = g["daily_stats"][day]
            
            # If teacher is not assigned to this day, skip
            if t_name not in stats["teachers"]:
                day_buffers[day] = -999
                continue
                
            total_staff = len(stats["teachers"]) + len(stats["nurses"])
            load = calculate_child_load(stats["under_3"], stats["over_3"], stats["preschool"])
            capacity = total_staff * 7
            day_buffers[day] = capacity - load
            
        # Sort days by highest buffer
        sorted_days = sorted(DAYS, key=lambda d: day_buffers[d], reverse=True)
        
        for day in sorted_days:
            if day_buffers[day] < 0:
                continue # Group is already understaffed, cannot possibly take SAK
                
            stats = g["daily_stats"][day]
            has_under_3 = stats["under_3"] > 0
            has_preschool = stats["preschool"] > 0
            
            # Prioritize nap or preschool specific hours
            priority_hours = []
            if has_under_3: priority_hours += ["12-13", "13-14"]
            if has_preschool: priority_hours += ["13-14"]
            if not has_under_3 and not has_preschool: priority_hours += ["12-13", "13-14"]
            
            # Deduplicate
            priority_hours = list(dict.fromkeys(priority_hours))
                
            for p_hour in priority_hours:
                search_space.append((day, p_hour))
            for hour in HOURS:
                if hour not in priority_hours:
                    # Block preschool hours if preschoolers present
                    if has_preschool and hour in ["09-10", "10-11", "11-12", "12-13"]:
                        continue
                    search_space.append((day, hour))
                    
        for day, hour in search_space:
            if needed == 0:
                break
                
            # Skip if Poissa
            if cal.loc[hour, day] == "Poissa":
                continue
                
            sak_col = f"{day} SAK"
            current_sak_val = str(cal.loc[hour, sak_col])
            if current_sak_val == "nan": current_sak_val = ""
            
            if t_name in current_sak_val:
                continue
                
            # Check if own capacity allows it
            current_buffer = calculate_group_buffer(g, day, hour)
            
            if current_buffer >= 7:
                opts = [o.strip() for o in current_sak_val.split(",") if o.strip()]
                opts.append(t_name)
                cal.loc[hour, sak_col] = ", ".join(opts).strip(", ")
                needed -= 1
                continue
                
            # If own capacity doesn't allow, search for loans from other groups
            loan_found = False
            for other_g in st.session_state.groups:
                if other_g["id"] == g["id"]:
                    continue
                
                # If other group has at least 1 adult's worth of buffer, we can burrow their capacity
                if calculate_group_buffer(other_g, day, hour) >= 7:
                    st.session_state.loans.append({
                        "day": day,
                        "hour": hour,
                        "from_group": other_g["id"],
                        "to_group": g["id"],
                        "teacher": t_name
                    })
                    
                    opts = [o.strip() for o in current_sak_val.split(",") if o.strip()]
                    opts.append(t_name)
                    cal.loc[hour, sak_col] = ", ".join(opts).strip(", ")
                    needed -= 1
                    loan_found = True
                    break

if st.button("🤖 Automaattinen SAK-aikojen ehdotus (Täyttää tyhjät paikat)"):
    for g in st.session_state.groups:
        suggest_sak_for_group(g)
    st.rerun()

st.divider()

# ----------------- GROUP CALENDARS --------------------
st.subheader("Ryhmien kalenterit")

if not st.session_state.groups:
    st.info("Ei ryhmiä. Lisää uusi ryhmä vasemmasta sivupalkista aloittaaksesi.")
else:
    tabs = st.tabs([g["name"] for g in st.session_state.groups])
    
    # Colors for pandas styling
    def color_cells(val):
        if val == "SAK":
            return "background-color: #d1e7dd; color: #0f5132;"
        elif "Ei SAK" in val:
            return "background-color: #f8d7da; color: #842029;"
        elif val == "Poissa":
            return "background-color: #e2e3e5; color: #41464c;"
        elif val != "Työssä":
            # Any other event like "Palaveri"
            return "background-color: #cff4fc; color: #055160;"
        return ""
    
    options = ["Työssä", "SAK", "Poissa", "Palaveri (Ei SAK)"]
    
    for i, g in enumerate(st.session_state.groups):
        with tabs[i]:
            st.markdown("### 📆 Päivittäinen miehitys ja lapsimäärät")
            
            # Render 5 columns for days
            day_cols = st.columns(5)
            
            needs_rerun = False
            
            for d_idx, day in enumerate(DAYS):
                with day_cols[d_idx]:
                    st.markdown(f"**{day}**")
                    stats = g["daily_stats"][day]
                    
                    # Children inputs
                    c1, c2 = st.columns([1, 1])
                    c1.markdown("<div style='margin-top: 5px'>Alle 3v</div>", unsafe_allow_html=True)
                    new_u3 = c2.number_input("Alle 3v", min_value=0, max_value=99, value=stats["under_3"], key=f"u3_{g['id']}_{day}", label_visibility="collapsed")
                    
                    c1, c2 = st.columns([1, 1])
                    c1.markdown("<div style='margin-top: 5px'>Yli 3v</div>", unsafe_allow_html=True)
                    new_o3 = c2.number_input("Yli 3v", min_value=0, max_value=99, value=stats["over_3"], key=f"o3_{g['id']}_{day}", label_visibility="collapsed")
                    
                    c1, c2 = st.columns([1, 1])
                    c1.markdown("<div style='margin-top: 5px'>Eskarit</div>", unsafe_allow_html=True)
                    new_pre = c2.number_input("Eskarit", min_value=0, max_value=99, value=stats["preschool"], key=f"pre_{g['id']}_{day}", label_visibility="collapsed")
                    
                    st.markdown("---")
                    
                    # Staff assignment
                    new_t = st.multiselect("Opettajat", st.session_state.all_teachers, default=stats["teachers"], key=f"t_sel_{g['id']}_{day}")
                    new_n = st.multiselect("Hoitajat", st.session_state.all_nurses, default=stats["nurses"], key=f"n_sel_{g['id']}_{day}")
                    
                    # Checks for changes
                    if (new_u3 != stats["under_3"] or new_o3 != stats["over_3"] or new_pre != stats["preschool"] or
                        new_t != stats["teachers"] or new_n != stats["nurses"]):
                        stats["under_3"] = new_u3
                        stats["over_3"] = new_o3
                        stats["preschool"] = new_pre
                        stats["teachers"] = new_t
                        stats["nurses"] = new_n
                        needs_rerun = True
                        
            st.divider()
            
            if needs_rerun:
                init_calendars_for_groups()
                st.rerun()
    
            st.markdown("### 📅 Ryhmän kalenteri ja asetetut SAK-ajat")
            cal = st.session_state.calendars[g["id"]]
            
            # Gather dynamic list of teachers mapped to this group
            group_teachers = set()
            for stats in g["daily_stats"].values():
                for t in stats["teachers"]:
                    group_teachers.add(t)
            
            # Format calendar for display and check capacity
            display_cal = cal.copy()
            group_id_to_name = {grp["id"]: grp["name"] for grp in st.session_state.groups}
            
            for day in DAYS:
                stats = g["daily_stats"][day]
                load = calculate_child_load(stats["under_3"], stats["over_3"], stats["preschool"])
                
                # Capacity at generic hour 10-11
                buf_10_11 = calculate_group_buffer(g, day, "10-11")
                capacity = buf_10_11 + load
                
                if buf_10_11 >= 0:
                    display_cal.loc["Kapasiteetti", day] = f"OK ({capacity} > {load:.2f})"
                    cal.loc["Kapasiteetti", day] = f"OK ({capacity} > {load:.2f})"
                else:
                    display_cal.loc["Kapasiteetti", day] = f"⚠️ Vajaa. ({capacity} < {load:.2f})"
                    cal.loc["Kapasiteetti", day] = f"⚠️ Vajaa. ({capacity} < {load:.2f})"
                
                cal.loc["Kapasiteetti", f"{day} SAK"] = ""
                display_cal.loc["Kapasiteetti", f"{day} SAK"] = ""
                
                cal.loc["Kapasiteetti", f"{day} Henkilöstö"] = ""
                display_cal.loc["Kapasiteetti", f"{day} Henkilöstö"] = ""
                
                cal.loc["Kapasiteetti", f"{day} Huomiot"] = ""
                display_cal.loc["Kapasiteetti", f"{day} Huomiot"] = ""
                
            # Auto-generate hourly hindrances into display_cal
            for day in DAYS:
                stats = g["daily_stats"][day]
                for hour in HOURS:
                    warnings = []
                    buf = calculate_group_buffer(g, day, hour)
                    
                    if buf < 0:
                        warnings.append(f"⚠️ Vajaa ({buf:.2f})")
                    elif buf < 7:
                        warnings.append(f"🟡 Tiukka ({buf:.2f})")
                    
                    if stats["preschool"] > 0 and hour in ["09-10", "10-11", "11-12", "12-13"]:
                        warnings.append("🎓 Eskariaikaa")
                    
                    sak_val = str(cal.loc[hour, f"{day} SAK"])
                    if sak_val != "nan" and sak_val.strip():
                        warnings.append(f"📚 SAK: {sak_val}")
                    
                    # Preserve user-written custom notes
                    existing = str(cal.loc[hour, f"{day} Huomiot"])
                    if existing == "nan": existing = ""
                    custom_parts = [p.strip() for p in existing.split("|") if p.strip() and not p.strip().startswith(("⚠️", "🟡", "🎓", "📚"))]
                    
                    all_parts = warnings + custom_parts
                    display_cal.loc[hour, f"{day} Huomiot"] = " | ".join(all_parts) if all_parts else ""
                
            # Inject loans information into the display_cal
            for loan in st.session_state.loans:
                if loan["from_group"] == g["id"]:
                    orig_val = display_cal.loc[loan["hour"], loan["day"]]
                    if orig_val != "Poissa":
                        to_name = group_id_to_name.get(loan["to_group"], "Tunt.")
                        display_cal.loc[loan["hour"], loan["day"]] = f"{orig_val} ⚠️ (Lainassa: {to_name})"
                elif loan["to_group"] == g["id"]:
                    orig_val = display_cal.loc[loan["hour"], loan["day"]]
                    if orig_val != "Poissa":
                        from_name = group_id_to_name.get(loan["from_group"], "Tunt.")
                        display_cal.loc[loan["hour"], loan["day"]] = f"{orig_val} 🤝 (Apu: {from_name})"
            
            
            # Color logic
                
            def style_group_cal(df):
                styler = df.style
                
                def highlight_sak(s):
                    return ['background-color: #d1e7dd; color: #0f5132' if pd.notna(v) and str(v).strip() != "" and str(v) != "nan" else '' for v in s]
                
                def highlight_staff(s):
                    return ['background-color: #e2e3e5; color: #41464c; font-size: 0.85em;' if pd.notna(v) and str(v).strip() != "" and str(v) != "nan" else '' for v in s]
                
                def highlight_program(s):
                    res = []
                    for v in s:
                        st_v = str(v)
                        if st_v == "Poissa":
                            res.append("background-color: #e2e3e5; color: #41464c;")
                        elif st_v.startswith("⚠️"):
                            res.append("background-color: #f8d7da; color: #842029; font-weight: bold;")
                        elif st_v.startswith("OK"):
                            res.append("background-color: #e2e3e5; color: #41464c; font-size: 0.9em;")
                        else:
                            res.append("background-color: #cff4fc; color: #055160;" if st_v != "Työssä" else "")
                    return res
    
                for day in DAYS:
                    styler = styler.apply(highlight_program, subset=[day])
                    styler = styler.apply(highlight_sak, subset=[f"{day} SAK"])
                    styler = styler.apply(highlight_staff, subset=[f"{day} Henkilöstö"])
                    styler = styler.apply(highlight_staff, subset=[f"{day} Huomiot"])
                    
                return styler
    
            col_config = {}
            for day in DAYS:
                day_teachers = g["daily_stats"][day]["teachers"]
                sak_options = [""] + sorted(day_teachers)
                
                col_config[day] = st.column_config.TextColumn(day, width="medium")
                col_config[f"{day} SAK"] = st.column_config.SelectboxColumn(
                    f"{day[:2]}. SAK",
                    help="SAK-opettajat",
                    options=sak_options,
                    width="small"
                )
                col_config[f"{day} Henkilöstö"] = st.column_config.TextColumn(
                    f"{day[:2]}. Extrat",
                    help="Tuntikohtainen henkilöstö (tyhjä = kaikki päivän työntekijät)",
                    width="small"
                )
                col_config[f"{day} Huomiot"] = st.column_config.TextColumn(
                    f"{day[:2]}. Huom.",
                    help="Automaattiset varoitukset + oma teksti (erotin: |)",
                    width="medium"
                )
                
            edited_cal = st.data_editor(
                style_group_cal(display_cal),
                column_config=col_config,
                key=f"cal_{g['id']}",
                use_container_width=True
            )
            
            if not display_cal.equals(edited_cal):
                # Sync back editable columns to the source dataframe
                for day in DAYS:
                    st.session_state.calendars[g['id']].loc[:, f"{day} SAK"] = edited_cal.loc[:, f"{day} SAK"]
                    st.session_state.calendars[g['id']].loc[:, f"{day} Henkilöstö"] = edited_cal.loc[:, f"{day} Henkilöstö"]
                    # Strip auto-warnings back so only custom parts persist
                    for hour in HOURS:
                        raw = str(edited_cal.loc[hour, f"{day} Huomiot"])
                        if raw == "nan": raw = ""
                        custom_only = [p.strip() for p in raw.split("|") if p.strip() and not p.strip().startswith(("⚠️", "🟡", "🎓", "📚"))]
                        st.session_state.calendars[g['id']].loc[hour, f"{day} Huomiot"] = " | ".join(custom_only)
                st.rerun()
    
            st.markdown("#### SAK-kertymät tässä ryhmässä")
            for t_name in sorted(list(group_teachers)):
                sak_count = 0
                for day in DAYS:
                    sak_col = f"{day} SAK"
                    col_data = cal.loc[HOURS, sak_col].astype(str).tolist()
                    sak_count += sum(1 for cell in col_data if t_name in cell)
                st.write(f"- **{t_name}**: SAK-aikaa jaettu **{sak_count}/5 tuntia**")