import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="哈蜜瓜收支表儀表板", page_icon="🍈", layout="wide")
st.title("🍈 哈蜜瓜收支與季繳管理儀表板")

# ==========================================
# 1. 讀取 Excel 檔案
# ==========================================
@st.cache_data
def load_excel():
    df_trans = pd.read_excel("For Streamlit.xlsx", sheet_name='每周收支')
    df_members = pd.read_excel("For Streamlit.xlsx", sheet_name='季繳追蹤')
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
    df_mem['剩餘次數'] = pd.to_numeric(df_mem['剩餘次數'], errors='coerce').fillna(0)
    st.session_state.members_df = df_mem[['姓名', '繳費日期', '剩餘次數']]
    st.session_state.play_history = []

if 'trans_df' not in st.session_state:
    df_t = df_trans.copy()
    # 清理收支明細 (去除 $ 與逗號，並將日期標準化)
    if '$' in df_t.columns:
        df_t['$'] = pd.to_numeric(df_t['$'].astype(str).replace('[\$,]', '', regex=True), errors='coerce').fillna(0)
    if '日期' in df_t.columns:
        df_t['日期'] = pd.to_datetime(df_t['日期'], errors='coerce')
    st.session_state.trans_df = df_t

# 取出目前的收支 DataFrame 方便後續計算
current_trans = st.session_state.trans_df

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
        st.markdown(f"*(目前季繳球友合計剩餘： **{total_remaining}** 次，資料與「季繳追蹤」分頁連動)*")
        cost_per_time = st.number_input("💲 季繳單次成本設定 (元/次)：", min_value=0, value=220, step=10)
        
        quarterly_reserve = total_remaining * cost_per_time
        available_cash = net_balance - safe_buffer - quarterly_reserve

        col1, col2, col3 = st.columns(3)
        col1.metric("💵 總結餘現金", f"${net_balance:,.0f}")
        col3.metric("🛡️ 安全挪用款", f"${safe_buffer:,.0f}", f"單週 ${weekly_venue_fee:.0f}")
        col2.metric("💳 季繳預留金", f"${quarterly_reserve:,.0f}", f"共剩 {total_remaining} 次未打")
        
        if available_cash >= 0:
            st.success(f"### 🎉 實際可動用盈餘： **${available_cash:,.0f}**")
        else:
            st.error(f"### ⚠️️ 實際可動用盈餘： **${available_cash:,.0f}**")
            
    st.divider()
    
    # ✨ 【新增功能】手動輸入流水帳表單
    st.subheader("✍️ 新增收支紀錄")
    with st.form("add_transaction_form", clear_on_submit=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            t_date = st.date_input("📅 日期", datetime.today())
            t_type = st.selectbox("類別", ["收入", "支出"])
        with col_f2:
            t_item = st.text_input("項目 (如: 臨打, 場地費, 羽毛球, 季繳, 活動費, 其他)", placeholder="必填")
            t_amount = st.number_input("金額 ($)", min_value=0, step=1)
        with col_f3:
            t_handler = st.text_input("經手人", placeholder="如: 櫃台, 妙, 齊")
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

    st.subheader("📝 每週收支流水帳")
    st.dataframe(st.session_state.trans_df.sort_values(by="日期", ascending=False), use_container_width=True)

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
# 分頁 3：季繳剩餘次數追蹤 (動態扣減)
# ------------------------------------------
with tab3:
    st.subheader("✍️ 手動扣減次數")
    
    available_members = st.session_state.members_df[st.session_state.members_df['剩餘次數'] > 0]['姓名'].tolist()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_name = st.selectbox("👤 選擇姓名：", available_members if available_members else ["無可用名單"])
    with col2:
        selected_date = st.date_input("📅 選擇打球時間：", datetime.today())
    with col3:
        st.write("")
        st.write("")
        if st.button("確認扣減 1 次", use_container_width=True) and selected_name != "無可用名單":
            idx = st.session_state.members_df[st.session_state.members_df['姓名'] == selected_name].index
            st.session_state.members_df.loc[idx, '剩餘次數'] -= 1
            st.session_state.play_history.append({"姓名": selected_name, "時間": selected_date.strftime("%Y-%m-%d")})
            st.success(f"✅ 已成功扣減 {selected_name} 1 次！")
            st.rerun()

    st.divider()
    st.subheader("📋 目前季繳狀態清單")
    
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

    styled_df = display_df.style.apply(highlight_zero, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    if st.session_state.play_history:
        st.subheader("🕒 本次新增打球紀錄 (離開網頁即清除)")
        st.table(pd.DataFrame(st.session_state.play_history))
