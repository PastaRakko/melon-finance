import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import numpy as np

st.set_page_config(page_title="哈蜜瓜收支表儀表板", page_icon="🍈", layout="wide")
st.title("🍈 哈蜜瓜收支與季繳管理儀表板")

# ==========================================
# 1. 讀取 Excel 檔案
# ==========================================
@st.cache_data
def load_excel():
    df_trans = pd.read_excel("For Streamlit.xlsx", sheet_name='每周收支')
    df_members = pd.read_excel("For Streamlit.xlsx", sheet_name='季繳追蹤')
    
# 🌟 解決 KeyError 的關鍵：自動清除所有欄位名稱前後的隱藏空白字元
    df_trans.columns = df_trans.columns.str.strip()
    df_members.columns = df_members.columns.str.strip()
   
    return df_trans, df_members

try:
    df_trans, df_members = load_excel()
except Exception as e:
    st.error("讀取 Excel 失敗，請確認檔案與分頁是否存在。")
    st.stop()

# ==========================================
# 2. 系統初始化 (將兩份資料都放入 session_state)
# ==========================================
if 'members_df' not in st.session_state:
    df_mem = df_members.dropna(subset=['姓名']).copy()
    
    # ✨ 確保日期格式正確
    df_mem['季繳開始日期'] = pd.to_datetime(df_mem['季繳開始日期'], errors='coerce')
    today = pd.to_datetime(datetime.today().date())
    days_diff = (today - df_mem['季繳開始日期']).dt.days
    
    df_mem['剩餘次數'] = np.where(
        df_mem['季繳開始日期'].notna(),
        10 - np.ceil(days_diff / 7),
        0 # 如果沒填開始日期，預設顯示為 0
    )
    
    st.session_state.members_df = df_mem[['姓名', '繳費日期', '季繳開始日期', '剩餘次數']]
    st.session_state.play_history = []

if 'trans_df' not in st.session_state:
    df_t = df_trans.copy()
    # 清理收支明細 (去除 $ 與逗號，並將日期標準化)
    if '$' in df_t.columns:
        df_t['$'] = pd.to_numeric(df_t['$'].astype(str).replace('[\$,]', '', regex=True), errors='coerce').fillna(0)
    if '日期' in df_t.columns:
        df_t['日期'] = pd.to_datetime(df_t['日期'], errors='coerce')
    st.session_state.trans_df = df_t

current_trans = st.session_state.trans_df

# ------------------------------------------
# ✨ 動態產生下拉選單
# ------------------------------------------
# 項目選單
item_options = ["場地費", "臨打", "季繳", "羽毛球", "活動費", "其他"]
if '項目' in current_trans.columns:
    for x in current_trans['項目'].dropna().unique():
        if x not in item_options and str(x).strip() != "":
            item_options.append(x)

# 經手人選單
handler_options = ["櫃台", "妙", "齊"]
if '經手人' in current_trans.columns:
    for x in current_trans['經手人'].dropna().unique():
        if x not in handler_options and str(x).strip() != "":
            handler_options.append(x)

# ==========================================
# 3. 建立網頁分頁
# ==========================================
tab1, tab2, tab3 = st.tabs(["💰 財務與記帳", "📊 收支圖表", "🏸 季繳追蹤"])

# ------------------------------------------
# 分頁 1：財務與記帳 (加入新增帳目表單)
# ------------------------------------------
with tab1:
    st.subheader("💰 總財務概況")
    
    if '類別' in current_trans.columns and '$' in current_trans.columns:
        total_income = current_trans[current_trans['類別'] == '收入']['$'].sum()
        total_expense = current_trans[current_trans['類別'] == '支出']['$'].sum()
        net_balance = total_income - total_expense

        # 安全挪用款
        if '項目' in current_trans.columns:
            venue_expenses = current_trans[(current_trans['類別'] == '支出') & (current_trans['項目'] == '場地費')]['$']
            weekly_venue_fee = venue_expenses.mode()[0] if not venue_expenses.empty else 760
        else:
            weekly_venue_fee = 760
        safe_buffer = weekly_venue_fee * 2 

        # 季繳預留金
        total_remaining = st.session_state.members_df['剩餘次數'].sum()
        cost_per_time = 220
        quarterly_reserve = total_remaining * cost_per_time

        col1, col2, col3 = st.columns(3)
        with col2:
            st.metric("💵 總結餘金額", f"${net_balance:,.0f}")
        with col1:
            st.success(f"### 🛡️ 可挪用金額: **${safe_buffer:,.0f}**")
        with col3:
            st.metric("💳 季繳預留金", f"${quarterly_reserve:,.0f}")
            
    st.divider()
    
    # 手動輸入流水帳表單
    st.subheader("✍️ 新增收支紀錄")
    with st.form("add_transaction_form", clear_on_submit=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            t_date = st.date_input("📅 日期", datetime.today())
            t_type = st.selectbox("類別", ["收入", "支出"])
        with col_f2:
            t_item = st.selectbox("項目", item_options)
            t_amount = st.number_input("金額 ($)", min_value=0, step=1)
        with col_f3:
            t_handler = st.selectbox("經手人", handler_options)
            t_note = st.text_input("備註")
            
        submitted = st.form_submit_button("➕ 確認新增這筆帳目", use_container_width=True)
        if submitted:
            if not t_item:
                st.warning("⚠️ 請填寫「項目」欄位！")
            else:
                # 建立新資料列並附加到現有的 session_state
                new_record = pd.DataFrame([{
                    "日期": pd.to_datetime(t_date),
                    "類別": t_type,
                    "項目": t_item,
                    "$": t_amount,
                    "經手人": t_handler,
                    "備註": t_note
                }])
                st.session_state.trans_df = pd.concat([st.session_state.trans_df, new_record], ignore_index=True)
                st.success(f"✅ 已成功記帳：{t_type} - {t_item} ${t_amount}")
                st.rerun() # 自動重新整理畫面，讓上方財務概況瞬間更新

    st.subheader("📝 每週收支總表")
    if "日期" in st.session_state.trans_df.columns:
        display_df = st.session_state.trans_df.sort_values(by="日期", ascending=False)
    else:
        display_df = st.session_state.trans_df
        st.warning(f"⚠️ 找不到『日期』欄位，目前的欄位有：{list(display_df.columns)}。請確認 Excel 的標題列位置。")
    # ✨ 使用 st.data_editor 讓表格可以直接雙擊修改
    edited_trans = st.data_editor(
        display_df, 
        use_container_width=True, 
        num_rows="dynamic", # 開啟此設定，您甚至可以直接在表格最下方新增一列，或選取整列按 Delete 刪除！
        key="trans_editor"
    )
    
    # 若您在表格上做了任何修改，將新資料存回系統並重新整理重算總結餘
    if not edited_trans.equals(display_df):
        st.session_state.trans_df = edited_trans
        st.rerun()

    # ✨ 新增：刪除收支紀錄功能
    with st.expander("🗑️ 刪除錯誤的收支紀錄"):
        del_opts = []
        for idx, row in st.session_state.trans_df.iterrows():
            d_str = row['日期'].strftime('%Y-%m-%d') if pd.notnull(row['日期']) else ''
            del_opts.append(f"{idx} | {d_str} - {row.get('類別','')} : {row.get('項目','')} (${row.get('$','')})")
        
        sel_del = st.selectbox("請選擇要刪除的紀錄：", ["請選擇..."] + del_opts)
        if st.button("🚨 確認刪除這筆收支"):
            if sel_del != "請選擇...":
                del_idx = int(sel_del.split(" | ")[0])
                st.session_state.trans_df = st.session_state.trans_df.drop(del_idx).reset_index(drop=True)
                st.success("✅ 已成功刪除該筆紀錄！")
                st.rerun()

# ------------------------------------------
# 分頁 2：視覺化圖表
# ------------------------------------------
with tab2:
    st.subheader("📊 收支圖表分析")
    if '類別' in current_trans.columns and '$' in current_trans.columns and '日期' in current_trans.columns:
        col1, col2 = st.columns(2)
        with col1:
            summary = current_trans.groupby('類別')['$'].sum().reset_index()
            fig_pie = px.pie(summary, values='$', names='類別', title="總收入 vs 總支出",
                             color='類別', color_discrete_map={'收入':'#28a745', '支出':'#dc3545'})
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            daily_summary = current_trans.groupby(['日期', '類別'])['$'].sum().reset_index()
            fig_bar = px.bar(daily_summary, x='日期', y='$', color='類別', barmode='group', title="每日收支變化",
                             color_discrete_map={'收入':'#28a745', '支出':'#dc3545'})
            st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------
# 分頁 3：季繳剩餘次數追蹤
# ------------------------------------------
with tab3:
    st.subheader("➕ 新增季繳人員")
    
    with st.form("add_member_form"):
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            new_name = st.text_input("👤 姓名", placeholder="必填")
        with col_m2:
            new_date = st.date_input("📅 繳費日期", datetime.today())
        with col_m3:
            new_start_date = st.date_input("📅 季繳開始日期", datetime.today(), help="⚠️ 系統限制僅能選擇禮拜二")
            
        submit_new_member = st.form_submit_button("確認新增名單", use_container_width=True)
        
        if submit_new_member:
            if not new_name.strip():
                st.warning("⚠️ 請填寫「姓名」欄位！")
            elif new_start_date.weekday() != 1:
                weekdays_zh = ["一", "二", "三", "四", "五", "六", "日"]
                wrong_day = weekdays_zh[new_start_date.weekday()]
                st.error(f"⚠ 【日期錯誤】「季繳開始日期」必須為星期二！您選擇的 {new_start_date.strftime('%Y-%m-%d')} 是星期{wrong_day}。")
            else:
                # 針對新名單套用公式
                today_dt = pd.to_datetime(datetime.today().date())
                start_dt = pd.to_datetime(new_start_date)
                days_diff_new = (today_dt - start_dt).days
                calculated_times = 10 - np.ceil(days_diff_new / 7)
                
                new_member_data = pd.DataFrame([{
                    "姓名": new_name,
                    "繳費日期": pd.to_datetime(new_date),
                    "季繳開始日期": start_dt,
                    "剩餘次數": calculated_times
                }])
                st.session_state.members_df = pd.concat(
                    [st.session_state.members_df, new_member_data], 
                    ignore_index=True
                )
                st.success(f"✅ 已成功新增球友：{new_name} (開始日: {new_start_date}, 系統自動計算剩餘 {calculated_times} 次)")
                st.rerun() 
    st.divider()

    st.subheader("📋 季繳追蹤清單")
    
    def update_status(times):
        if times <= 0: return "🛑 已結束"
        elif times <= 3: return "⚠️ 提醒繳費"
        else: return "✅ 進行中"

    display_df = st.session_state.members_df.copy()
    display_df['狀態提醒'] = display_df['剩餘次數'].apply(update_status)

    def highlight_zero(row):
        if row['剩餘次數'] <= 0:
            return ['text-decoration: line-through; color: #888888;'] * len(row)
        return [''] * len(row)

# ✨ 使用 st.data_editor 讓名單可以直接修改
    edited_members = st.data_editor(
        display_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="members_editor"
    )

    # 若有修改，把新資料覆蓋回去 (排除掉自動產生的'狀態提醒'欄位)
    if not edited_members.equals(display_df):
        st.session_state.members_df = edited_members[['姓名', '繳費日期', '季繳開始日期', '剩餘次數']]
        st.rerun()

# ✨ 新增：刪除季繳球友功能
    with st.expander("🗑️️ 名單編輯"):
        del_mem_opts = []
        for idx, row in st.session_state.members_df.iterrows():
            d_str = row['季繳開始日期'].strftime('%Y-%m-%d') if pd.notnull(row['季繳開始日期']) else '無日期'
            del_mem_opts.append(f"{idx} | {row.get('姓名','')} (開始日: {d_str})")
            
        sel_mem_del = st.selectbox("請選擇欲刪除項目：", ["請選擇..."] + del_mem_opts)
        if st.button("🚨 確認刪除"):
            if sel_mem_del != "請選擇...":
                mem_del_idx = int(sel_mem_del.split(" | ")[0])
                st.session_state.members_df = st.session_state.members_df.drop(mem_del_idx).reset_index(drop=True)
                st.success("✅ 已成功刪除！")
                st.rerun()

