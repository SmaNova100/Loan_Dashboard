import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="KASFO 융자 모니터링 시스템",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 2. 스타일 설정 (헤더 가운데 정렬 CSS 포함)
# ---------------------------------------------------------
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; color: #1e293b; }
        section[data-testid="stSidebar"] { background-color: #0f172a; }
        section[data-testid="stSidebar"] * { color: #f1f5f9 !important; }
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid #3b82f6;
        }
        .unit-label {
            text-align: right;
            font-size: 0.9rem;
            color: #64748b;
            margin-bottom: 5px;
            font-weight: 500;
        }
        h1, h2, h3 { font-family: 'Pretendard', sans-serif; font-weight: 700; color: #1e293b; }
        
        /* [핵심] 데이터프레임 헤더 가운데 정렬 강제 적용 */
        th {
            text-align: center !important;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. 데이터 로드 및 전처리
# ---------------------------------------------------------
def clean_header(col_name):
    """헤더 정제"""
    col_name = str(col_name)
    col_name = re.sub(r'_x000D_', '', col_name)
    col_name = col_name.replace('\n', '')
    col_name = col_name.strip().replace(' ', '')
    return col_name

def load_data(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # 1. 헤더 정제
        df.columns = [clean_header(c) for c in df.columns]
        
        # 2. 컬럼명 스마트 매핑
        for col in df.columns:
            if "대학명" in col or "교명" in col or "University" in col:
                df.rename(columns={col: '학교명'}, inplace=True)
            elif "총융자" in col or "지급액" in col or "대출액" in col:
                df.rename(columns={col: '지급금액'}, inplace=True)
            elif "상환액" in col or "납부액" in col or "회수액" in col:
                df.rename(columns={col: '상환완료액'}, inplace=True)
            elif "잔액" in col or "미상환" in col:
                df.rename(columns={col: '상환잔액'}, inplace=True)
            elif "법인" in col or "재단" in col:
                df.rename(columns={col: '법인명'}, inplace=True)
            elif "담보" in col:
                df.rename(columns={col: '담보종류'}, inplace=True)
            elif "예산" in col:
                df.rename(columns={col: '사업예산구분'}, inplace=True)
            elif "거치" in col:
                df.rename(columns={col: '거치기간'}, inplace=True)
            elif "조건변경" in col:
                df.rename(columns={col: '상환조건변경여부'}, inplace=True)
            elif "상환회계" in col:
                df.rename(columns={col: '상환회계'}, inplace=True)

        # 3. 날짜 처리
        if '지급일' in df.columns:
            df['지급일'] = pd.to_datetime(df['지급일'], errors='coerce')
            df['지급연도'] = df['지급일'].dt.year
            
        return df
    except Exception as e:
        st.error(f"파일 읽기 실패: {e}")
        return None

if 'loan_df' not in st.session_state: st.session_state['loan_df'] = None
if 'repay_df' not in st.session_state: st.session_state['repay_df'] = None

# ---------------------------------------------------------
# 4. 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.title("KASFO 융자 모니터링")
    st.markdown("---")
    menu = st.radio(
        "메뉴 선택",
        ["📊 통합 대시보드", "🏫 학교별 융자 현황", "🏢 학교별 담보 현황", "📂 데이터 업로드"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("담당자: 백종대 주무 행정관")

# ---------------------------------------------------------
# 5. 데이터 병합 및 계산
# ---------------------------------------------------------
main_df = None

if st.session_state['loan_df'] is not None:
    main_df = st.session_state['loan_df'].copy()
    
    # 숫자형 변환
    for col in ['지급금액', '상환잔액', '상환완료액']:
        if col in main_df.columns:
            main_df[col] = pd.to_numeric(main_df[col], errors='coerce').fillna(0)
    
    # 상환 데이터 병합
    if st.session_state['repay_df'] is not None:
        repay_temp = st.session_state['repay_df'].copy()
        if '상환완료액' in repay_temp.columns and '학교명' in repay_temp.columns:
            repay_temp['상환완료액'] = pd.to_numeric(repay_temp['상환완료액'], errors='coerce').fillna(0)
            repay_sum = repay_temp.groupby('학교명')['상환완료액'].sum().reset_index()
            if '상환완료액' in main_df.columns:
                main_df = main_df.drop(columns=['상환완료액'])
            main_df = pd.merge(main_df, repay_sum, on='학교명', how='left')
    
    # 상환액(완료액) 및 잔액 재계산
    if '지급금액' in main_df.columns and '상환잔액' in main_df.columns:
        main_df['상환액'] = main_df['지급금액'] - main_df['상환잔액']
        main_df['상환완료액'] = main_df['상환액']
    else:
        main_df['상환액'] = 0
        main_df['상환완료액'] = 0

    # 상환율 계산
    if '지급금액' in main_df.columns:
        main_df['상환율'] = main_df.apply(lambda x: (x['상환액'] / x['지급금액'] * 100) if x['지급금액'] > 0 else 0, axis=1)

# ---------------------------------------------------------
# [메뉴 1] 📊 통합 대시보드 (단위: 억원)
# ---------------------------------------------------------
if menu == "📊 통합 대시보드":
    st.title("📊 융자사업 통합 대시보드")
    
    if main_df is not None:
        # 1억 단위로 변환
        total_loan = (main_df['지급금액'].sum()) / 100000000
        total_repaid = (main_df['상환액'].sum()) / 100000000
        total_balance = (main_df['상환잔액'].sum()) / 100000000
        avg_rate = main_df['상환율'].mean() if '상환율' in main_df.columns else 0
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 지급 금액", f"{total_loan:,.1f} 억원")
        k2.metric("총 상환 완료액", f"{total_repaid:,.1f} 억원")
        k3.metric("현재 상환 잔액", f"{total_balance:,.1f} 억원", delta_color="inverse")
        k4.metric("평균 상환율", f"{avg_rate:.1f} %")
        
        st.divider()
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📉 연도별 융자 집행 추이 (단위: 억원)")
            if '지급연도' in main_df.columns:
                df_trend = main_df.groupby('지급연도')['지급금액'].sum().reset_index()
                df_trend['지급금액'] = df_trend['지급금액'] / 100000000 
                fig_trend = px.bar(df_trend, x='지급연도', y='지급금액', text_auto='.1f')
                fig_trend.update_layout(xaxis_type='category', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("지급일 데이터가 없습니다.")

        with c2:
            st.subheader("🍩 예산 구분별 비중")
            if '사업예산구분' in main_df.columns:
                # 차트 값은 억원 단위로 변환하여 표시
                df_pie = main_df.groupby('사업예산구분')['지급금액'].sum().reset_index()
                df_pie['지급금액'] = df_pie['지급금액'] / 100000000
                fig_pie = px.pie(df_pie, values='지급금액', names='사업예산구분', hole=0.5)
                fig_pie.update_traces(textinfo='percent+label', hovertemplate='%{label}: %{value:.1f} 억원')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("예산 구분 정보가 없습니다.")
    else:
        st.warning("데이터가 없습니다. '📂 데이터 업로드' 메뉴를 이용해주세요.")

# ---------------------------------------------------------
# [메뉴 2] 🏫 학교별 융자 현황 (수정 완료)
# ---------------------------------------------------------
elif menu == "🏫 학교별 융자 현황":
    st.title("🏫 학교별 상세 융자 현황")
    
    if main_df is not None:
        # 1. 컬럼 순서 및 '상환잔액' 포함
        target_cols_order = [
            "법인명", "학교명", "학교급", "사업명", "사업예산구분", 
            "상환회계", "지급일", "지급금액", "상환잔액", "상환액", "상환율"
        ]
        
        display_cols = [c for c in target_cols_order if c in main_df.columns]
        display_df = main_df[display_cols].copy()
        
        # 날짜 포맷
        if '지급일' in display_df.columns:
            display_df['지급일'] = display_df['지급일'].dt.strftime('%Y-%m-%d')

        # 검색
        col_search, _ = st.columns([1, 2])
        with col_search:
            search_txt = st.text_input("🔍 학교명 검색", placeholder="학교명 입력")
        
        if search_txt:
             mask = display_df.apply(lambda x: x.astype(str).str.contains(search_txt).any(), axis=1)
             display_df = display_df[mask]

        # 단위 표기
        st.markdown('<div class="unit-label">(단위 : 원)</div>', unsafe_allow_html=True)
        
        # [핵심] Pandas Styler를 사용한 정밀 포맷팅 (콤마, 정렬 해결)
        # 1. 숫자 포맷 적용 (콤마)
        styler = display_df.style.format({
            "지급금액": "{:,.0f}",
            "상환잔액": "{:,.0f}",
            "상환액": "{:,.0f}",
            "상환율": "{:,.1f}%"
        })
        
        # 2. 정렬 적용 (숫자는 오른쪽, 나머지는 왼쪽)
        # (헤더 가운데 정렬은 상단 CSS에서 th 태그로 전역 처리함)
        styler = styler.set_properties(
            subset=["지급금액", "상환잔액", "상환액", "상환율"], 
            **{'text-align': 'right'}
        )
        styler = styler.set_properties(
            subset=[c for c in display_df.columns if c not in ["지급금액", "상환잔액", "상환액", "상환율"]],
            **{'text-align': 'left'}
        )

        st.dataframe(styler, use_container_width=True, height=600)
    else:
        st.warning("데이터가 없습니다. '📂 데이터 업로드' 메뉴에서 파일을 등록해주세요.")

# ---------------------------------------------------------
# [메뉴 3] 🏢 학교별 담보 현황
# ---------------------------------------------------------
elif menu == "🏢 학교별 담보 현황":
    st.title("🏢 학교별 담보 제공 현황")
    if main_df is not None and '담보종류' in main_df.columns:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("담보 요약")
            df_col = main_df['담보종류'].value_counts().reset_index()
            df_col.columns = ['담보종류', '건수']
            st.dataframe(df_col, use_container_width=True, hide_index=True)
        with c2:
            st.subheader("상세 내역")
            # 콤마 적용
            temp_df = main_df[['학교명', '담보종류', '지급금액']].copy()
            styler_dambo = temp_df.style.format({"지급금액": "{:,.0f}"})
            st.dataframe(styler_dambo, use_container_width=True, hide_index=True)
    else:
        st.warning("담보 데이터가 없습니다.")

# ---------------------------------------------------------
# [메뉴 4] 📂 데이터 업로드
# ---------------------------------------------------------
elif menu == "📂 데이터 업로드":
    st.title("📂 데이터 업로드 센터")
    
    col_up1, col_up2 = st.columns(2)
    exp1 = True if st.session_state['loan_df'] is None else False
    exp2 = True if st.session_state['repay_df'] is None else False
    
    with col_up1:
        with st.expander("1️⃣ 지급 데이터 (Loan)", expanded=exp1):
            f1 = st.file_uploader("지급 파일", type=['xlsx', 'csv'], key="u1")
            if f1:
                st.session_state['loan_df'] = load_data(f1)
                st.rerun()
        if st.session_state['loan_df'] is not None:
            st.success(f"로드 완료: {len(st.session_state['loan_df'])}건")

    with col_up2:
        with st.expander("2️⃣ 상환 데이터 (Repay)", expanded=exp2):
            f2 = st.file_uploader("상환 파일", type=['xlsx', 'csv'], key="u2")
            if f2:
                st.session_state['repay_df'] = load_data(f2)
                st.rerun()
        if st.session_state['repay_df'] is not None:
            st.success(f"로드 완료: {len(st.session_state['repay_df'])}건")