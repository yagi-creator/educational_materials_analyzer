"""
🔧 商品名分類ロジック（後から調整・拡張可能）

このモジュールでは以下の分類を行います：
- 学年判別（小1-6, 中1-3, 高校）
- 科目判別（国語, 算数, 数学, 英語, 理科, 社会）
- 季節判別（春期, 夏期, 冬期）
- 入試教材判別
- 合本教材判別
"""

import re
import unicodedata
import pandas as pd

# 固定設定
UNIT_PRICE = 1500  # 売上増見込計算用単価

# 🔧 キーワード辞書（後から調整可能）
SEASON_KEYWORDS = {
    "春期": [
        "spring", "Spring", "SPRING",
        "スプリング", "ｽﾌﾟﾘﾝｸﾞ", "スプリンク", "ｽﾌﾟﾘﾝｸ",
        "春期", "春季", "春講", "新学期"
    ],
    "夏期": [
        "summer", "Summer", "SUMMER",
        "サマー", "ｻﾏｰ", "サマ", "ｻﾏ",
        "夏期", "夏季", "夏講", "夏休み"
    ],
    "冬期": [
        "winter", "Winter", "WINTER",
        "ウィンター", "ウインター", "ｳｨﾝﾀｰ", "ｳｲﾝﾀｰ",
        "ウィンタ", "ウインタ", "ｳｨﾝﾀ", "ｳｲﾝﾀ",
        "ウィンタｰ", "ウインタｰ", "ｳｨﾝﾀｰ", "ｳｲﾝﾀｰ",
        "冬期", "冬季", "冬講", "冬休み"
    ]
}

EXAM_KEYWORDS = [
    "入試", "受験", "高校入試", "入試対策", "受験対策",
    "過去問", "直前対策", "合格", "志望校"
]

COMPOSITE_KEYWORDS = [
    "合本", "総合", "セット", "パック", "まとめ",
    "全科目", "5科目", "3科目", "オールイン",
    "複合", "総復習", "総まとめ", "統合"
]

def normalize_text(text):
    """テキスト正規化"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[ーｰ−―‐]', 'ー', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def extract_grade(product_name):
    """学年抽出"""
    normalized = normalize_text(product_name)
    
    # 小学生パターン
    patterns = [
        r'小\s*([1-6１-６])',
        r'小学\s*([1-6１-６])\s*年',
        r'([1-6１-６])\s*年生'
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            num = match.group(1)
            num = num.translate(str.maketrans('１２３４５６', '123456'))
            return f'小{num}'
    
    # 中学生パターン
    patterns = [
        r'中\s*([1-3１-３])',
        r'中学\s*([1-3１-３])\s*年'
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            num = match.group(1)
            num = num.translate(str.maketrans('１２３', '123'))
            return f'中{num}'
    
    # 高校パターン
    if re.search(r'(高校|高\s*[1-3１-３]|高等学校)', normalized):
        return '高校'
    
    return None

def extract_subject(product_name, grade=None):
    """科目抽出"""
    normalized = normalize_text(product_name)
    
    subject_patterns = {
        '国語': [r'国語', r'現代文', r'古文', r'漢文', r'国'],
        '算数': [r'算数', r'算'],
        '数学': [r'数学', r'数'],
        '英語': [r'英語', r'英'],
        '理科': [r'理科', r'理', r'物理', r'化学', r'生物', r'地学'],
        '社会': [r'社会', r'社', r'歴史', r'地理', r'公民', r'政治', r'経済']
    }
    
    found_subjects = []
    for subject, patterns in subject_patterns.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                found_subjects.append(subject)
                break
    
    if not found_subjects:
        return 'その他'
    
    # 学年を考慮した調整
    if grade and grade.startswith('中'):
        if '数学' in found_subjects:
            return '数学'
        elif '算数' in found_subjects:
            return '数学'
    elif grade and grade.startswith('小'):
        if '算数' in found_subjects:
            return '算数'
        elif '数学' in found_subjects:
            return '算数'
    
    return found_subjects[0]

def extract_season_and_exam(product_name):
    """季節・入試判別"""
    normalized = normalize_text(product_name)
    
    # 入試判別（最優先）
    for keyword in EXAM_KEYWORDS:
        if keyword in normalized:
            return None, True
    
    # 季節判別
    for season, keywords in SEASON_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                return season, False
    
    return None, False

def is_composite_material(product_name):
    """合本教材判別"""
    normalized = normalize_text(product_name)
    for keyword in COMPOSITE_KEYWORDS:
        if keyword in normalized:
            return True
    return False

def classify_product_comprehensive(product_name):
    """商品名総合分類"""
    if pd.isna(product_name):
        return {
            '学年': None,
            '科目': 'その他',
            '季節': None,
            '入試フラグ': False,
            '合本フラグ': False,
            'カテゴリ': '通年'
        }
    
    grade = extract_grade(product_name)
    subject = extract_subject(product_name, grade)
    season, is_exam = extract_season_and_exam(product_name)
    is_composite = is_composite_material(product_name)
    
    # カテゴリ決定
    if is_exam:
        category = '入試'
    elif season:
        category = season
    else:
        category = '通年'
    
    return {
        '学年': grade,
        '科目': subject,
        '季節': season,
        '入試フラグ': is_exam,
        '合本フラグ': is_composite,
        'カテゴリ': category
    }
