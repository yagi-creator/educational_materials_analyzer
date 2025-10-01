import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# 🔧 分類ロジック（後から調整可能）
from classifier import (
    classify_product_comprehensive,
    UNIT_PRICE
)

# ページ設定
st.set_page_config(
    page_title="📚 教材注文データ分析システム",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📚 教材注文データ分析システム")
st.markdown("**教材代理店専用** - 営業戦略支援ツール")

# セッションステート初期化
if 'bulk_threshold' not in st.session_state:
    st.session_state.bulk_threshold = 5

# サイドバー設定
st.sidebar.header("⚙️ システム設定")
st.session_state.bulk_threshold = st.sidebar.number_input(
    "大口発注基準（同日・同教材）",
    min_value=1,
    max_value=50,
    value=st.session_state.bulk_threshold,
    help="この冊数以上の同日発注を大口として緑太字表示"
)

@st.cache_data(show_spinner=False)
def load_and_process_data(file):
    """Excelファイル読み込み・前処理"""
    try:
        # 修正前：単一エンジンでの読み込み
        # df = pd.read_excel(file)
        
        # 修正後：拡張子別エンジン選択
        filename = file.name.lower()
        if filename.endswith('.xlsx'):
            df = pd.read_excel(file, engine='openpyxl')
        elif filename.endswith('.xls'):
            df = pd.read_excel(file, engine='xlrd')
        else:
            raise ValueError("対応ファイル形式: .xlsx, .xls")
        
        # 必要列の抽出・リネーム
        required_columns = ['伝票日付', '得意先名１', '商品名', '数量']
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"必要な列が見つかりません: {missing_cols}")
        
        df = df[required_columns].copy()
        df.rename(columns={
            '伝票日付': '注文日',
            '得意先名１': '塾名',
            '数量': '冊数'
        }, inplace=True)
        
        # データ型変換
        # データ型変換（YYYYMMDD形式対応）
def convert_date_robust(date_series):
    """YYYYMMDD形式（20240902等）を正しい日付に変換"""
    # まず文字列化
    str_dates = date_series.astype(str).str.strip()
    
    # 8桁数字（YYYYMMDD）を優先処理
    mask_8digit = str_dates.str.match(r'^\d{8}$')
    result = pd.Series(pd.NaT, index=date_series.index)
    
    # YYYYMMDD形式の変換
    if mask_8digit.any():
        result.loc[mask_8digit] = pd.to_datetime(
            str_dates[mask_8digit], 
            format='%Y%m%d', 
            errors='coerce'
        )
    
    # その他の形式（Excel日付等）
    remaining = result.isna()
    if remaining.any():
        result.loc[remaining] = pd.to_datetime(date_series[remaining], errors='coerce')
    
    return result

df['注文日'] = convert_date_robust(df['注文日'])

        df['冊数'] = pd.to_numeric(df['冊数'], errors='coerce').fillna(0).astype(int)
        df['塾名'] = df['塾名'].astype(str).str.strip()
        df['商品名'] = df['商品名'].astype(str)
        
        # 無効データ除外
        df = df[df['冊数'] > 0]
        df = df.dropna(subset=['注文日', '塾名', '商品名'])
        
        # 🔧 商品分類適用（後から調整可能）
        classification_results = df['商品名'].apply(classify_product_comprehensive)
        df_classified = pd.json_normalize(classification_results.tolist())
        df = pd.concat([df, df_classified], axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return None

def calculate_revenue_potential(school_data, tab_name):
    """売上増見込計算（通年タブ・中学生のみ）"""
    if tab_name != "通年":
        return 0
    
    target_data = school_data[
        (school_data['カテゴリ'] == '通年') & 
        (school_data['学年'].isin(['中1', '中2', '中3']))
    ].copy()
    
    if target_data.empty:
        return 0
    
    total_potential = 0
    middle_subjects = ['国語', '数学', '英語', '理科', '社会']
    grades = ['中1', '中2', '中3']
    
    # 中3基準値の算出
    c3_data = target_data[target_data['学年'] == '中3']
    c3_eng_math_max = 0
    c3_krs_avg = 0
    
    if not c3_data.empty:
        c3_subject_totals = c3_data.groupby('科目')['冊数'].sum()
        c3_eng_math_orders = c3_subject_totals.reindex(['英語', '数学'], fill_value=0)
        c3_eng_math_max = c3_eng_math_orders.max() if not c3_eng_math_orders.empty else 0
        
        c3_krs_orders = c3_subject_totals.reindex(['国語', '理科', '社会'], fill_value=0)
        c3_krs_orders = c3_krs_orders[c3_krs_orders > 0]
        c3_krs_avg = int(np.round(c3_krs_orders.mean())) if not c3_krs_orders.empty else int(np.round(c3_eng_math_max / 2))
    
    # 各学年の売上増見込計算
    for grade in grades:
        grade_data = target_data[target_data['学年'] == grade]
        grade_subject_totals = grade_data.groupby('科目')['冊数'].sum() if not grade_data.empty else pd.Series()
        
        if not grade_data.empty:
            grade_max = grade_subject_totals.max() if not grade_subject_totals.empty else 0
            eng_math_base = grade_max
            
            krs_orders = grade_subject_totals.reindex(['国語', '理科', '社会'], fill_value=0)
            krs_orders = krs_orders[krs_orders > 0]
            krs_base = int(np.round(krs_orders.mean())) if not krs_orders.empty else int(np.round(eng_math_base / 2))
        else:
            if grade == '中1':
                eng_math_base = int(np.round(c3_eng_math_max * 2 / 4))
                krs_base = int(np.round(c3_krs_avg * 2 / 4))
            elif grade == '中2':
                eng_math_base = int(np.round(c3_eng_math_max * 3 / 4))
                krs_base = int(np.round(c3_krs_avg * 3 / 4))
            else:
                eng_math_base = c3_eng_math_max
                krs_base = c3_krs_avg
        
        for subject in middle_subjects:
            current_orders = grade_subject_totals.get(subject, 0)
            if current_orders == 0:
                if subject in ['英語', '数学']:
                    total_potential += eng_math_base * UNIT_PRICE
                else:
                    total_potential += krs_base * UNIT_PRICE
    
    return total_potential

def filter_data_by_tab(data, tab_name):
    """タブ別データフィルタリング"""
    if tab_name == "通年":
        return data[data['カテゴリ'] == '通年']
    elif tab_name == "入試":
        return data[data['カテゴリ'] == '入試']
    else:
        return data[data['カテゴリ'] == tab_name]

def display_grade_section(data, grade, tab_name, bulk_threshold):
    """学年セクション表示"""
    if grade == "高校":
        st.markdown(f"### {grade} " + "━" * 50)
        if data.empty:
            st.write("注文実績なし")
        else:
            product_summary = data.groupby('商品名')['冊数'].sum().sort_values(ascending=False)
            for product, total in product_summary.items():
                st.write(f"{product} {total}冊")
        return
    
    st.markdown(f"### {grade} " + "━" * 50)
    
    if data.empty:
        if grade.startswith('中'):
            st.markdown("⚠️ **要確認**")
        else:
            st.write(f"{grade}：要確認")
        return
    
    subjects = ['国語', '算数', '数学', '英語', '理科', '社会', 'その他']
    if tab_name in ['春期', '夏期', '冬期']:
        subjects.append('合本')
    
    subject_totals = data.groupby('科目')['冊数'].sum()
    max_subject_total = subject_totals.max() if not subject_totals.empty else 0
    
    for subject in subjects:
        if subject == '合本' and tab_name in ['春期', '夏期', '冬期']:
            composite_data = data[data['合本フラグ'] == True]
            if not composite_data.empty:
                display_subject_materials(composite_data, subject, max_subject_total, bulk_threshold, is_composite=True)
        else:
            subject_data = data[data['科目'] == subject]
            if subject_data.empty and grade.startswith('中') and subject in ['国語', '数学', '英語', '理科', '社会']:
                st.markdown(f"⚠️ **{subject}：要確認**")
            elif not subject_data.empty:
                display_subject_materials(subject_data, subject, max_subject_total, bulk_threshold)

def display_subject_materials(data, subject, max_subject_total, bulk_threshold, is_composite=False):
    """科目別教材表示"""
    daily_summary = data.groupby(['商品名', '注文日'])['冊数'].sum().reset_index()
    
    material_summary = []
    for product in daily_summary['商品名'].unique():
        product_data = daily_summary[daily_summary['商品名'] == product]
        total_books = product_data['冊数'].sum()
        max_day_idx = product_data['冊数'].idxmax()
        max_day_books = product_data.loc[max_day_idx, '冊数']
        max_day_date = product_data.loc[max_day_idx, '注文日']
        
        material_summary.append({
            'product': product,
            'total': total_books,
            'max_day_books': max_day_books,
            'max_day_date': max_day_date
        })
    
    subject_total = sum(item['total'] for item in material_summary)
    
    for item in material_summary:
        product_name = item['product']
        total_books = item['total']
        max_day_books = item['max_day_books']
        max_day_date = item['max_day_date']
        
        if is_composite:
            display_name = f"📚 {product_name}（合本）"
        else:
            display_name = f"{subject} {product_name}"
        
        books_display = f"{total_books}冊"
        if max_subject_total > 0 and subject_total <= max_subject_total // 2:
            books_display = f"**{total_books}冊**"
        
        if pd.isna(max_day_date):
    date_str = '日付不明'
else:
    date_str = max_day_date.strftime('%Y/%m/%d')

        if max_day_books >= bulk_threshold:
            date_display = f"**{date_str}**"
        else:
            date_display = date_str
        
        st.write(f"{display_name} {books_display}（{date_display} {max_day_books}冊）")

# ファイルアップロード
uploaded_file = st.file_uploader(
    "📁 年間注文データ（Excel）をアップロード",
    type=['xlsx', 'xls'],
    help="伝票日付、得意先名１、商品名、数量の列が必要です"
)

# メイン処理
if uploaded_file is not None:
    df = load_and_process_data(uploaded_file)
    
    if df is not None:
        st.success(f"✅ データ読み込み完了: {len(df):,}行")
        
        # 塾選択
        st.sidebar.header("🏫 塾選択")
        
        search_query = st.sidebar.text_input(
            "🔍 塾名検索",
            placeholder="塾名の一部を入力"
        )
        
        if search_query:
            matching_schools = df[
                df['塾名'].str.contains(search_query, case=False, na=False)
            ]['塾名'].unique()
            
            if len(matching_schools) > 0:
                selected_school = st.sidebar.selectbox(
                    "候補から選択",
                    [""] + sorted(matching_schools.tolist())
                )
            else:
                st.sidebar.warning("該当する塾が見つかりません")
                selected_school = ""
        else:
            selected_school = ""
        
        if selected_school:
            school_data = df[df['塾名'] == selected_school].copy()
            
            # タブ作成
            tab_names = ["通年", "春期", "夏期", "冬期", "入試"]
            tabs = st.tabs(tab_names)
            
            for i, (tab_name, tab) in enumerate(zip(tab_names, tabs)):
                with tab:
                    tab_data = filter_data_by_tab(school_data, tab_name)
                    total_books = school_data['冊数'].sum()
                    
                    if tab_name == "通年":
                        revenue_potential = calculate_revenue_potential(school_data, tab_name)
                        st.markdown(f"### 【{selected_school}】💰売上増見込：+¥{revenue_potential:,}　年間実績：{total_books:,}冊")
                    else:
                        st.markdown(f"### 【{selected_school}】年間実績：{total_books:,}冊")
                    
                    st.markdown(f"🔧 大口設定：同日{st.session_state.bulk_threshold}冊以上")
                    
                    if not tab_data.empty:
                        if tab_name == "通年":
                            elementary_grades = ['小1', '小2', '小3', '小4', '小5', '小6']
                            first_elem_grade = None
                            for grade in elementary_grades:
                                if not tab_data[tab_data['学年'] == grade].empty:
                                    first_elem_grade = grade
                                    break
                            
                            display_grades = []
                            if first_elem_grade:
                                start_idx = elementary_grades.index(first_elem_grade)
                                display_grades.extend(elementary_grades[start_idx:])
                            
                            display_grades.extend(['中1', '中2', '中3'])
                            
                            if not tab_data[tab_data['学年'] == '高校'].empty:
                                display_grades.append('高校')
                                
                        elif tab_name == "入試":
                            display_grades = ['中3']
                        else:
                            display_grades = ['中1', '中2', '中3']
                        
                                                for grade in display_grades:
                            grade_data = tab_data[tab_data['学年'] == grade]
                            display_grade_section(grade_data, grade, tab_name, st.session_state.bulk_threshold)
                        
                        # 学年不明データを「全体その他」として表示
                        unclassified_data = tab_data[tab_data['学年'].isna()]
                        if not unclassified_data.empty:
                            st.markdown("### 全体その他 " + "━" * 50)
                            product_summary = unclassified_data.groupby('商品名')['冊数'].sum().sort_values(ascending=False)
                            for product, total in product_summary.items():
                                # 最大注文日の取得
                                product_data = unclassified_data[unclassified_data['商品名'] == product]
                                daily_summary = product_data.groupby('注文日')['冊数'].sum()
                                max_day = daily_summary.idxmax()
                                max_day_books = daily_summary.max()
                                
                                # 日付・大口判定
                                date_str = max_day.strftime('%Y/%m/%d') if pd.notna(max_day) else '日付不明'
                                if max_day_books >= st.session_state.bulk_threshold:
                                    date_display = f"**{date_str}**"
                                else:
                                    date_display = date_str
                                
                                st.write(f"{product} {total}冊（{date_display} {max_day_books}冊）")

                    
                    else:
                        if tab_name == "入試":
                            st.markdown("⚠️ **中3入試教材：要確認**")
                        elif tab_name in ["春期", "夏期", "冬期"]:
                            st.markdown(f"⚠️ **{tab_name}教材：要確認**")
                        else:
                            st.markdown("⚠️ **注文実績なし：要確認**")
        
        else:
            st.info("💡 サイドバーで塾名を選択してください。")

else:
    st.info("📁 年間注文データのExcelファイルをアップロードしてください")
    
    with st.expander("📖 使用方法ガイド"):
        st.markdown("""
        ### 🚀 クイックスタート
        1. **ファイル準備**: 伝票日付、得意先名１、商品名、数量の列があるExcelファイル
        2. **アップロード**: 上記のファイル選択ボタンからアップロード
        3. **塾選択**: サイドバーで塾名検索・選択
        4. **タブ切り替え**: 通年・春期・夏期・冬期・入試で表示切り替え
        
        ### 📊 主な機能
        - **5タブ表示**: 通年・季節・入試別の教材採用状況
        - **売上増見込**: 通年タブで概算表示（中学生のみ）
        - **合本教材識別**: 📚マークで視覚的に区別
        - **大口発注日**: 緑太字で強調表示
        - **要確認項目**: ⚠️マークで未開拓領域を明示
        
        ### 🔧 カスタマイズ
        分類ロジックは classifier.py で調整可能です。
        """)
