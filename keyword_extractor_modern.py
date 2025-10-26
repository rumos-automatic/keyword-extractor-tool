import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import re
from typing import List, Tuple, Dict
import json

class KeywordExtractor:
    def __init__(self):
        self.translator = None  # Google Translate APIを一時的に無効化
        self.common_brands = self.load_brands()
        
    def load_brands(self) -> List[str]:
        """一般的なブランド名のリストを返す"""
        return [
            # ファッションブランド
            "Nike", "Adidas", "Puma", "Reebok", "New Balance", "ASICS",
            "Uniqlo", "Zara", "H&M", "Gap", "Levi's", "Calvin Klein",
            "Ralph Lauren", "Tommy Hilfiger", "Gucci", "Prada", "Louis Vuitton",
            "Chanel", "Dior", "Burberry", "Versace", "Armani", "Balenciaga",
            
            # 電子機器ブランド
            "Apple", "Samsung", "Sony", "Panasonic", "Sharp", "Toshiba",
            "Canon", "Nikon", "Fujitsu", "Dell", "HP", "Lenovo", "ASUS",
            "Microsoft", "Google", "Amazon", "Nintendo", "PlayStation",
            "Dyson", "Bose", "JBL", "Anker", "Xiaomi", "Huawei",
            
            # 化粧品・美容ブランド
            "Shiseido", "SK-II", "Lancome", "Estee Lauder", "Clinique",
            "MAC", "NARS", "Charlotte Tilbury", "YSL", "Maybelline",
            "L'Oreal", "Nivea", "Dove", "Olay",
            
            # 日本ブランド
            "無印良品", "ユニクロ", "資生堂", "花王", "ライオン",
            "パナソニック", "ソニー", "任天堂", "トヨタ", "ホンダ",
            "ニトリ", "ダイソー", "セリア", "カインズ"
        ]
    
    def detect_language(self, text: str) -> str:
        """テキストの言語を検出"""
        # 日本語文字が含まれているかチェック
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text):
            return 'ja'
        return 'en'
    
    def translate_text(self, text: str, target_lang: str) -> str:
        """テキストを指定言語に翻訳（簡易実装）"""
        if not text:
            return ""
        
        # 簡易的な翻訳辞書（実際の翻訳APIの代わり）
        translations = {
            'ja_to_en': {
                '靴': 'Shoes', 'バッグ': 'Bag', '時計': 'Watch', 'スマホ': 'Phone',
                'カメラ': 'Camera', 'ノートパソコン': 'Laptop', 'タブレット': 'Tablet',
                'ヘッドホン': 'Headphones', 'スピーカー': 'Speaker', 'ジャケット': 'Jacket',
                'シャツ': 'Shirt', 'パンツ': 'Pants', 'ドレス': 'Dress', 'ワンピース': 'Dress',
                '化粧品': 'Cosmetic', '香水': 'Perfume', 'おもちゃ': 'Toy', '本': 'Book',
                'ゲーム': 'Game', '黒': 'Black', '白': 'White', '赤': 'Red', '青': 'Blue',
                '緑': 'Green', '黄': 'Yellow', 'ピンク': 'Pink', '紫': 'Purple',
                'オレンジ': 'Orange', '茶': 'Brown', '灰': 'Gray', '銀': 'Silver', '金': 'Gold'
            },
            'en_to_ja': {
                'Shoes': '靴', 'Bag': 'バッグ', 'Watch': '時計', 'Phone': 'スマホ',
                'Camera': 'カメラ', 'Laptop': 'ノートパソコン', 'Tablet': 'タブレット',
                'Headphones': 'ヘッドホン', 'Speaker': 'スピーカー', 'Jacket': 'ジャケット',
                'Shirt': 'シャツ', 'Pants': 'パンツ', 'Dress': 'ドレス',
                'Cosmetic': '化粧品', 'Perfume': '香水', 'Toy': 'おもちゃ', 'Book': '本',
                'Game': 'ゲーム', 'Black': '黒', 'White': '白', 'Red': '赤', 'Blue': '青',
                'Green': '緑', 'Yellow': '黄', 'Pink': 'ピンク', 'Purple': '紫',
                'Orange': 'オレンジ', 'Brown': '茶', 'Gray': '灰', 'Silver': '銀', 'Gold': '金'
            }
        }
        
        # 現在の言語を検出
        source_lang = self.detect_language(text)
        
        # 同じ言語の場合はそのまま返す
        if (source_lang == 'ja' and target_lang == 'ja') or (source_lang == 'en' and target_lang == 'en'):
            return text
        
        # 翻訳辞書のキー
        trans_key = 'ja_to_en' if source_lang == 'ja' else 'en_to_ja'
        
        # 単語ごとに翻訳を試みる
        if trans_key in translations:
            trans_dict = translations[trans_key]
            result = text
            for original, translated in trans_dict.items():
                result = re.sub(r'\b' + re.escape(original) + r'\b', translated, result, flags=re.IGNORECASE)
            return result
        
        return text
    
    def extract_brand(self, title: str) -> str:
        """商品タイトルからブランド名を抽出"""
        title_upper = title.upper()
        
        for brand in self.common_brands:
            brand_upper = brand.upper()
            if brand_upper in title_upper:
                # 元のタイトルから正しい大文字小文字を取得
                start_index = title_upper.index(brand_upper)
                return title[start_index:start_index + len(brand)]
        
        # ブランド名の一般的なパターンを検索
        # 【ブランド名】パターン
        match = re.search(r'【([^】]+)】', title)
        if match:
            return match.group(1)
        
        # [ブランド名]パターン
        match = re.search(r'\[([^\]]+)\]', title)
        if match:
            return match.group(1)
        
        # 大文字の連続（2-10文字）をブランド名として検出
        match = re.search(r'\b[A-Z]{2,10}\b', title)
        if match:
            return match.group(0)
        
        return ""
    
    def extract_keywords_strict(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """厳しめモード：ほぼ同じ商品を探すためのキーワード抽出"""
        keywords = []
        
        # ブランド名を追加
        if include_brand and brand:
            keywords.append(brand)
        
        # 型番・モデル番号の抽出
        model_patterns = [
            r'\b[A-Z0-9]{2,}[-_][A-Z0-9]{2,}\b',  # XX-123, ABC_456
            r'\b[A-Z]{2,4}\d{3,6}\b',              # ABC1234
            r'\b\d{4,10}\b',                       # 純粋な数字の型番
        ]
        
        for pattern in model_patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            keywords.extend(matches)
        
        # サイズ情報の抽出
        size_patterns = [
            r'\b\d+(?:\.\d+)?(?:cm|mm|m|inch|in|ml|l|g|kg|GB|MB|TB)\b',
            r'\b(?:S|M|L|XL|XXL|XXXL)\b',
            r'\b\d+[×x]\d+(?:[×x]\d+)?\b',  # 10x20, 10×20×30
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            keywords.extend(matches)
        
        # 色情報の抽出
        colors = ['Black', 'White', 'Red', 'Blue', 'Green', 'Yellow', 'Pink', 'Purple', 
                  'Orange', 'Brown', 'Gray', 'Grey', 'Silver', 'Gold',
                  'ブラック', 'ホワイト', 'レッド', 'ブルー', 'グリーン', 'イエロー',
                  'ピンク', 'パープル', 'オレンジ', 'ブラウン', 'グレー', 'シルバー', 'ゴールド',
                  '黒', '白', '赤', '青', '緑', '黄', 'ピンク', '紫', 'オレンジ', '茶', '灰', '銀', '金']
        
        for color in colors:
            if color.lower() in title.lower():
                keywords.append(color)
                break
        
        # 重要な単語（名詞）を抽出
        important_words = re.findall(r'\b[A-Za-z]{4,}\b', title)
        for word in important_words[:3]:  # 最初の3つの重要な単語
            if word not in keywords and word != brand:
                keywords.append(word)
        
        return keywords[:8]  # 最大8個のキーワード
    
    def extract_keywords_moderate(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """標準モード：バランスの取れたキーワード抽出"""
        keywords = []
        
        # ブランド名を追加
        if include_brand and brand:
            keywords.append(brand)
        
        # 型番・モデル番号（主要なもののみ）
        model_match = re.search(r'\b[A-Z0-9]{2,}[-_][A-Z0-9]{2,}\b', title, re.IGNORECASE)
        if model_match:
            keywords.append(model_match.group())
        
        # カテゴリーワードの抽出
        categories = {
            'en': ['Shoes', 'Bag', 'Watch', 'Phone', 'Camera', 'Laptop', 'Tablet',
                   'Headphones', 'Speaker', 'Jacket', 'Shirt', 'Pants', 'Dress',
                   'Cosmetic', 'Perfume', 'Toy', 'Book', 'Game'],
            'ja': ['靴', 'バッグ', '時計', 'スマホ', 'カメラ', 'ノートパソコン',
                   'タブレット', 'ヘッドホン', 'スピーカー', 'ジャケット', 'シャツ',
                   'パンツ', 'ドレス', 'ワンピース', '化粧品', '香水', 'おもちゃ', '本', 'ゲーム']
        }
        
        for lang_categories in categories.values():
            for category in lang_categories:
                if category.lower() in title.lower():
                    keywords.append(category)
                    break
        
        # 特徴的な形容詞
        adjectives = re.findall(r'\b(?:New|Premium|Pro|Plus|Ultra|Max|Mini|Lite|Classic|Original|Limited|Special)\b', title, re.IGNORECASE)
        keywords.extend(adjectives[:2])
        
        # 重要な名詞（ストップワードを除く）
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were'}
        words = re.findall(r'\b[A-Za-z]{3,}\b', title)
        for word in words:
            if (word.lower() not in stop_words and 
                word not in keywords and 
                word != brand and 
                len(keywords) < 6):
                keywords.append(word)
        
        return keywords[:6]  # 最大6個のキーワード
    
    def extract_keywords_loose(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """緩めモード：大まかなカテゴリでのキーワード抽出"""
        keywords = []
        
        # ブランド名を追加（オプション）
        if include_brand and brand and len(brand) > 2:
            keywords.append(brand)
        
        # メインカテゴリーの抽出（最も重要なカテゴリワードを1つ）
        main_categories = {
            'fashion': ['Fashion', 'Clothing', 'Apparel', 'ファッション', '服', 'アパレル'],
            'electronics': ['Electronics', 'Tech', 'Digital', '電子', 'デジタル', '家電'],
            'beauty': ['Beauty', 'Cosmetic', 'Skincare', 'ビューティー', '化粧品', 'コスメ'],
            'sports': ['Sports', 'Fitness', 'Athletic', 'スポーツ', 'フィットネス', '運動'],
            'home': ['Home', 'Kitchen', 'Furniture', 'ホーム', 'キッチン', '家具'],
            'toys': ['Toy', 'Game', 'Hobby', 'おもちゃ', 'ゲーム', 'ホビー']
        }
        
        for category, terms in main_categories.items():
            for term in terms:
                if term.lower() in title.lower():
                    keywords.append(term)
                    break
            if keywords:
                break
        
        # 一般的な商品タイプの抽出
        product_types = re.findall(r'\b(?:Set|Kit|Pack|Bundle|Collection|Series|Edition)\b', title, re.IGNORECASE)
        if product_types:
            keywords.append(product_types[0])
        
        # 主要な名詞を2-3個抽出
        nouns = re.findall(r'\b[A-Za-z]{4,12}\b', title)
        stop_words = {'with', 'from', 'this', 'that', 'these', 'those', 'which', 'what', 'when', 'where'}
        
        for noun in nouns:
            if (noun.lower() not in stop_words and 
                noun not in keywords and 
                noun != brand and 
                len(keywords) < 4):
                keywords.append(noun)
        
        return keywords[:4]  # 最大4個のキーワード
    
    def process_titles(self, titles: List[str], mode: str, translate_mode: str, 
                      include_brand: bool) -> List[Dict]:
        """複数の商品タイトルを処理"""
        results = []
        
        # 翻訳モードの解析
        source_lang, target_lang = translate_mode.split('_to_')
        
        for title in titles:
            if not title.strip():
                continue
            
            result = {
                'original_title': title,
                'translated_title': '',
                'brand': '',
                'keywords': [],
                'translated_keywords': []
            }
            
            # ブランド抽出
            result['brand'] = self.extract_brand(title)
            
            # タイトルの翻訳
            if source_lang != target_lang:
                result['translated_title'] = self.translate_text(title, target_lang)
            else:
                result['translated_title'] = title
            
            # キーワード抽出
            if mode == 'strict':
                keywords = self.extract_keywords_strict(title, include_brand, result['brand'])
            elif mode == 'moderate':
                keywords = self.extract_keywords_moderate(title, include_brand, result['brand'])
            else:  # loose
                keywords = self.extract_keywords_loose(title, include_brand, result['brand'])
            
            result['keywords'] = keywords
            
            # キーワードの翻訳
            if source_lang != target_lang:
                result['translated_keywords'] = [
                    self.translate_text(kw, target_lang) for kw in keywords
                ]
            else:
                result['translated_keywords'] = keywords
            
            results.append(result)
        
        return results


class ModernKeywordExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 キーワード抽出ツール")
        self.root.geometry("1400x900")
        
        # 淡いソフトな黄色のカラースキーム
        self.colors = {
            'bg_main': '#fffef9',           # ソフトクリーム
            'bg_secondary': '#fffbf0',       # ソフトイエロー
            'bg_tertiary': '#fff4d6',        # 淡い黄色
            'accent': '#f4a460',             # サンディブラウン
            'accent_hover': '#daa520',       # ゴールデンロッド
            'text_primary': '#3c3c3c',       # ダークグレー
            'text_secondary': '#666666',     # ミディアムグレー
            'success': '#5cb85c',            # ソフトグリーン
            'warning': '#f0ad4e',            # ソフトオレンジ
            'error': '#d9534f',              # ソフトレッド
            'input_bg': '#ffffff',           # ホワイト
            'button_bg': '#f0ad4e',          # ソフトオレンジ
            'button_hover': '#ec971f',       # オレンジ
            'table_bg': '#fffef5',           # ソフトクリーム
            'table_alt': '#fffdf0'           # オフホワイト
        }
        
        self.root.configure(bg=self.colors['bg_main'])
        
        # スタイルの設定
        self.setup_styles()
        
        # ウィンドウアイコン設定（エラーを防ぐためtry-except）
        try:
            self.root.iconbitmap(default='')
        except:
            pass
        
        self.extractor = KeywordExtractor()
        
        self.setup_ui()
        
        # ウィンドウを中央に配置
        self.center_window()
    
    def center_window(self):
        """ウィンドウを画面中央に配置"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_styles(self):
        """モダンなスタイルを設定"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # メインフレームスタイル
        style.configure('Main.TFrame', 
                       background=self.colors['bg_main'],
                       borderwidth=0)
        
        # セカンダリフレームスタイル
        style.configure('Secondary.TFrame', 
                       background=self.colors['bg_secondary'],
                       relief='flat',
                       borderwidth=1)
        
        # ラベルフレームスタイル
        style.configure('Modern.TLabelframe', 
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=2,
                       relief='groove')
        style.configure('Modern.TLabelframe.Label', 
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['accent'],
                       font=('Segoe UI', 11, 'bold'))
        
        # ボタンスタイル
        style.configure('Modern.TButton',
                       background=self.colors['button_bg'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 10, 'bold'),
                       relief='flat',
                       padding=(20, 10))
        style.map('Modern.TButton',
                 background=[('active', self.colors['button_hover'])])
        
        # 特別なボタンスタイル
        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 11, 'bold'),
                       relief='flat',
                       padding=(25, 12))
        style.map('Success.TButton',
                 background=[('active', '#66bb6a')])
        
        style.configure('Warning.TButton',
                       background=self.colors['warning'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 10, 'bold'),
                       relief='flat',
                       padding=(20, 10))
        style.map('Warning.TButton',
                 background=[('active', '#ffa726')])
        
        # コンボボックススタイル
        style.configure('Modern.TCombobox',
                       fieldbackground=self.colors['input_bg'],
                       background=self.colors['input_bg'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       arrowcolor=self.colors['accent'],
                       relief='flat',
                       selectbackground=self.colors['accent'],
                       selectforeground='white')
        
        # チェックボタンスタイル
        style.configure('Modern.TCheckbutton',
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       focuscolor='none',
                       font=('Segoe UI', 10))
        style.map('Modern.TCheckbutton',
                 background=[('active', self.colors['bg_secondary'])])
        
        # Treeviewスタイル
        style.configure("Modern.Treeview",
                       background=self.colors['table_bg'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['table_bg'],
                       borderwidth=1,
                       font=('Yu Gothic UI', 11),
                       rowheight=35)  # 行の高さを少し大きく
        style.configure("Modern.Treeview.Heading",
                       background=self.colors['bg_tertiary'],
                       foreground=self.colors['bg_tertiary'],  # ヘッダーテキストを非表示
                       borderwidth=0,
                       font=('Yu Gothic UI', 0),  # フォントサイズ0で非表示
                       relief='flat')
        style.map('Modern.Treeview',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', 'white')])
    
    def create_gradient_frame(self, parent, height=50):
        """グラデーション風のヘッダーを作成"""
        header = tk.Frame(parent, bg=self.colors['bg_tertiary'], height=height)
        header.pack(fill='x', pady=(0, 10))
        
        # タイトルラベル
        title = tk.Label(header, 
                        text="🔍 キーワード抽出ツール",
                        font=('Yu Gothic UI', 22, 'bold'),
                        bg=self.colors['bg_tertiary'],
                        fg=self.colors['text_primary'])
        title.pack(pady=10)
        
        subtitle = tk.Label(header,
                           text="商品タイトルから最適なキーワードを自動抽出",
                           font=('Yu Gothic UI', 10),
                           bg=self.colors['bg_tertiary'],
                           fg=self.colors['text_secondary'])
        subtitle.pack()
        
        return header
    
    def setup_ui(self):
        # メインコンテナ
        main_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        main_container.pack(fill='both', expand=True)
        
        # ヘッダー
        self.create_gradient_frame(main_container, 80)
        
        # コンテンツエリア
        content_frame = tk.Frame(main_container, bg=self.colors['bg_main'])
        content_frame.pack(fill='both', expand=True, padx=30, pady=(0, 30))
        
        # 左側パネル（設定）
        left_panel = tk.Frame(content_frame, bg=self.colors['bg_secondary'], width=320, relief='ridge', bd=2)
        left_panel.pack(side='left', fill='y', padx=(0, 15))
        left_panel.pack_propagate(False)
        
        # 設定タイトル
        settings_title = tk.Label(left_panel,
                                 text="⚙️ 設定",
                                 font=('Yu Gothic UI', 14, 'bold'),
                                 bg=self.colors['bg_secondary'],
                                 fg=self.colors['accent'])
        settings_title.pack(pady=20)
        
        # 翻訳モード設定
        trans_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        trans_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(trans_frame,
                text="翻訳モード",
                font=('Yu Gothic UI', 10),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(anchor='w')
        
        self.translate_mode = ttk.Combobox(trans_frame, 
                                          style='Modern.TCombobox',
                                          width=25,
                                          state="readonly",
                                          font=('Segoe UI', 10))
        self.translate_mode['values'] = [
            '日本語→英語',
            '日本語→日本語',
            '英語→日本語',
            '英語→英語'
        ]
        self.translate_mode.set('日本語→英語')
        self.translate_mode.pack(fill='x', pady=5)
        
        # 抽出モード設定
        extract_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        extract_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(extract_frame,
                text="抽出モード",
                font=('Yu Gothic UI', 10),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(anchor='w')
        
        # モードボタン（ラジオボタン風）
        self.extract_mode = tk.StringVar(value='moderate')
        
        modes = [
            ('🎯 厳しめ', 'strict', 'ほぼ同じ商品を見つける'),
            ('⚖️ 標準', 'moderate', 'バランスの良いキーワード抽出'),
            ('🌊 緩め', 'loose', '大まかなカテゴリで検索')
        ]
        
        for text, value, desc in modes:
            mode_frame = tk.Frame(extract_frame, bg=self.colors['bg_secondary'])
            mode_frame.pack(fill='x', pady=5)
            
            rb = tk.Radiobutton(mode_frame,
                               text=text,
                               variable=self.extract_mode,
                               value=value,
                               bg=self.colors['bg_secondary'],
                               fg=self.colors['text_primary'],
                               selectcolor=self.colors['bg_tertiary'],
                               activebackground=self.colors['bg_secondary'],
                               activeforeground=self.colors['accent'],
                               font=('Segoe UI', 11, 'bold'))
            rb.pack(anchor='w')
            
            tk.Label(mode_frame,
                    text=f"  {desc}",
                    font=('Segoe UI', 8),
                    bg=self.colors['bg_secondary'],
                    fg=self.colors['text_secondary']).pack(anchor='w', padx=(20, 0))
        
        # ブランド名オプション
        brand_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        brand_frame.pack(fill='x', padx=20, pady=20)
        
        self.include_brand = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(brand_frame,
                           text="🏷️ ブランド名を含める",
                           variable=self.include_brand,
                           bg=self.colors['bg_secondary'],
                           fg=self.colors['text_primary'],
                           selectcolor=self.colors['bg_tertiary'],
                           activebackground=self.colors['bg_secondary'],
                           activeforeground=self.colors['accent'],
                           font=('Segoe UI', 11))
        cb.pack(anchor='w')
        
        # 統計情報
        stats_frame = tk.Frame(left_panel, bg=self.colors['bg_tertiary'])
        stats_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Label(stats_frame,
                text="📊 統計情報",
                font=('Yu Gothic UI', 10, 'bold'),
                bg=self.colors['bg_tertiary'],
                fg=self.colors['accent']).pack(pady=5)
        
        self.stats_label = tk.Label(stats_frame,
                                   text="商品数: 0\nキーワード数: 0\nブランド数: 0",
                                   font=('Segoe UI', 9),
                                   bg=self.colors['bg_tertiary'],
                                   fg=self.colors['text_secondary'],
                                   justify='left')
        self.stats_label.pack(pady=5)
        
        # 右側パネル（メインコンテンツ）
        right_panel = tk.Frame(content_frame, bg=self.colors['bg_main'])
        right_panel.pack(side='left', fill='both', expand=True)
        
        # 入力エリア
        input_container = tk.Frame(right_panel, bg=self.colors['bg_secondary'])
        input_container.pack(fill='both', expand=True, pady=(0, 20))
        
        input_header = tk.Frame(input_container, bg=self.colors['bg_secondary'])
        input_header.pack(fill='x', padx=15, pady=(15, 5))
        
        tk.Label(input_header,
                text="📝 商品タイトル入力",
                font=('Yu Gothic UI', 12, 'bold'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary']).pack(side='left')
        
        tk.Label(input_header,
                text="(1行に1商品)",
                font=('Yu Gothic UI', 9),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(side='left', padx=(10, 0))
        
        # テキスト入力エリア
        text_frame = tk.Frame(input_container, bg=self.colors['bg_secondary'])
        text_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        self.input_text = tk.Text(text_frame,
                                 bg=self.colors['input_bg'],
                                 fg=self.colors['text_primary'],
                                 insertbackground=self.colors['accent'],
                                 selectbackground=self.colors['accent'],
                                 selectforeground='white',
                                 font=('Yu Gothic UI', 10),
                                 wrap='word',
                                 relief='solid',
                                 bd=1,
                                 height=5)
        self.input_text.pack(side='left', fill='both', expand=True)
        
        # スクロールバー
        scrollbar = tk.Scrollbar(text_frame,
                                bg=self.colors['bg_secondary'],
                                activebackground=self.colors['accent'])
        scrollbar.pack(side='right', fill='y')
        self.input_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.input_text.yview)
        
        # サンプルテキスト
        sample_text = """Nike Air Max 90 Essential Men's Shoes Black/White Size 10
【資生堂】エリクシール シュペリエル リフトモイスト ローション II 170ml
Apple iPhone 15 Pro Max 256GB Natural Titanium SIMフリー
Sony WH-1000XM5 Wireless Noise Canceling Headphones - Black
[Uniqlo] Ultra Light Down Compact Jacket Women's Size M Navy"""
        
        self.input_text.insert('1.0', sample_text)
        
        # ボタンエリア
        button_container = tk.Frame(right_panel, bg=self.colors['bg_main'])
        button_container.pack(fill='x', pady=(0, 20))
        
        # 実行ボタン
        extract_btn = ttk.Button(button_container,
                                text="🚀 キーワード抽出",
                                style='Success.TButton',
                                command=self.extract_keywords)
        extract_btn.pack(side='left', padx=5)
        
        # クリアボタン
        clear_btn = ttk.Button(button_container,
                              text="🗑️ 全てクリア",
                              style='Warning.TButton',
                              command=self.clear_all)
        clear_btn.pack(side='left', padx=5)
        
        # コピーボタン（一括コピー）
        copy_btn = ttk.Button(button_container,
                             text="📋 一括コピー",
                             style='Modern.TButton',
                             command=self.copy_results)
        copy_btn.pack(side='left', padx=5)
        
        # エクスポートボタン
        export_btn = ttk.Button(button_container,
                               text="💾 CSV出力",
                               style='Modern.TButton',
                               command=self.export_csv)
        export_btn.pack(side='left', padx=5)
        
        # 結果エリア
        result_container = tk.Frame(right_panel, bg=self.colors['bg_secondary'])
        result_container.pack(fill='both', expand=True)
        
        result_header = tk.Frame(result_container, bg=self.colors['bg_secondary'])
        result_header.pack(fill='x', padx=15, pady=15)
        
        tk.Label(result_header,
                text="📊 抽出結果",
                font=('Yu Gothic UI', 12, 'bold'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary']).pack(side='left')
        
        self.result_status = tk.Label(result_header,
                                     text="準備完了",
                                     font=('Segoe UI', 9),
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['success'])
        self.result_status.pack(side='right')
        
        # 結果表示
        tree_frame = tk.Frame(result_container, bg=self.colors['bg_secondary'])
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # カラムごとのコピーボタンを含むヘッダーフレーム
        header_frame = tk.Frame(tree_frame, bg=self.colors['bg_tertiary'], height=40, relief='solid', bd=1)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # 各カラムのヘッダーとコピーボタン
        col_widths = [300, 120, 350, 350]
        col_names = ['商品タイトル', 'ブランド', '抽出キーワード', '翻訳キーワード']
        col_keys = ['title', 'brand', 'keywords', 'translated_kw']
        
        for i, (width, name, key) in enumerate(zip(col_widths, col_names, col_keys)):
            # カラムフレームに仕切り線を追加
            col_frame = tk.Frame(header_frame, bg=self.colors['bg_tertiary'], width=width, relief='ridge', bd=1)
            col_frame.pack(side='left', fill='y')
            col_frame.pack_propagate(False)
            
            # 中央揃え用の内部フレーム
            inner_frame = tk.Frame(col_frame, bg=self.colors['bg_tertiary'])
            inner_frame.place(relx=0.5, rely=0.5, anchor='center')
            
            # カラム名ラベル
            label = tk.Label(inner_frame, text=name, 
                           font=('Yu Gothic UI', 10, 'bold'),
                           bg=self.colors['bg_tertiary'],
                           fg=self.colors['text_primary'])
            label.pack(side='left', padx=5)
            
            # コピーボタン
            copy_btn = tk.Button(inner_frame, text="📋",
                               bg=self.colors['accent'],
                               fg='white',
                               font=('Yu Gothic UI', 8),
                               relief='flat',
                               bd=0,
                               padx=5,
                               pady=2,
                               cursor='hand2',
                               command=lambda k=key: self.copy_column(k))
            copy_btn.pack(side='left', padx=2)
        
        columns = ('title', 'brand', 'keywords', 'translated_kw')
        self.result_tree = ttk.Treeview(tree_frame,
                                       columns=columns,
                                       show='headings',  # ツリーカラムを非表示
                                       style='Modern.Treeview',
                                       height=20)
        
        # カラム設定（ヘッダーテキストは空に）
        self.result_tree.heading('title', text='', anchor='center')
        self.result_tree.heading('brand', text='', anchor='center')
        self.result_tree.heading('keywords', text='', anchor='center')
        self.result_tree.heading('translated_kw', text='', anchor='center')
        
        # カラムの幅と配置設定
        self.result_tree.column('title', width=300, minwidth=200, anchor='w')  # 左寄せ
        self.result_tree.column('brand', width=120, minwidth=80, anchor='center')  # 中央
        self.result_tree.column('keywords', width=350, minwidth=250, anchor='w')  # 左寄せ
        self.result_tree.column('translated_kw', width=350, minwidth=250, anchor='w')  # 左寄せ
        
        self.result_tree.pack(side='left', fill='both', expand=True)
        
        # 結果用スクロールバー
        result_scrollbar = tk.Scrollbar(tree_frame,
                                       bg=self.colors['bg_secondary'],
                                       activebackground=self.colors['accent'])
        result_scrollbar.pack(side='right', fill='y')
        self.result_tree.config(yscrollcommand=result_scrollbar.set)
        result_scrollbar.config(command=self.result_tree.yview)
        
        # 交互の行色設定
        self.result_tree.tag_configure('oddrow', background=self.colors['table_bg'])
        self.result_tree.tag_configure('evenrow', background=self.colors['table_alt'])
    
    def extract_keywords(self):
        """キーワード抽出処理"""
        # 結果をクリア
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        # ステータス更新
        self.result_status.config(text="処理中...", fg=self.colors['warning'])
        self.root.update()
        
        # 入力取得
        input_text = self.input_text.get('1.0', 'end-1c')
        titles = [line.strip() for line in input_text.split('\n') if line.strip()]
        
        if not titles:
            self.result_status.config(text="入力なし", fg=self.colors['error'])
            messagebox.showwarning("警告", "商品タイトルを入力してください")
            return
        
        # 翻訳モードの解析
        translate_map = {
            '日本語→英語': 'ja_to_en',
            '日本語→日本語': 'ja_to_ja',
            '英語→日本語': 'en_to_ja',
            '英語→英語': 'en_to_en'
        }
        translate_mode = translate_map[self.translate_mode.get()]
        
        try:
            # 処理実行
            results = self.extractor.process_titles(
                titles,
                self.extract_mode.get(),
                translate_mode,
                self.include_brand.get()
            )
            
            # 結果表示
            brand_count = 0
            keyword_count = 0
            
            for result in results:
                keywords_str = ', '.join(result['keywords'])
                translated_keywords_str = ', '.join(result['translated_keywords'])
                
                if result['brand']:
                    brand_count += 1
                keyword_count += len(result['keywords'])
                
                # 交互に背景色を変える
                tags = ('oddrow',) if len(self.result_tree.get_children()) % 2 == 0 else ('evenrow',)
                
                self.result_tree.insert('', 'end', values=(
                    result['original_title'][:50] + '...' if len(result['original_title']) > 50 else result['original_title'],
                    result['brand'] or '-',
                    keywords_str,
                    translated_keywords_str
                ), tags=tags)
            
            # 統計更新
            self.stats_label.config(
                text=f"商品数: {len(results)}\nキーワード数: {keyword_count}\nブランド数: {brand_count}"
            )
            
            # ステータス更新
            self.result_status.config(text=f"✓ {len(results)}件処理完了", fg=self.colors['success'])
            
        except Exception as e:
            self.result_status.config(text="エラー発生", fg=self.colors['error'])
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{str(e)}")
    
    def clear_all(self):
        """全てクリア"""
        self.input_text.delete('1.0', 'end')
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.result_status.config(text="クリア済み", fg=self.colors['text_secondary'])
        self.stats_label.config(text="商品数: 0\nキーワード数: 0\nブランド数: 0")
    
    def copy_results(self):
        """結果をクリップボードにコピー"""
        results = []
        for item in self.result_tree.get_children():
            values = self.result_tree.item(item, 'values')
            results.append('\t'.join(values))
        
        if results:
            result_text = '\n'.join(results)
            self.root.clipboard_clear()
            self.root.clipboard_append(result_text)
            self.result_status.config(text="✓ 一括コピーしました", fg=self.colors['success'])
        else:
            self.result_status.config(text="コピーする結果がありません", fg=self.colors['warning'])
    
    def copy_column(self, column_type):
        """特定のカラムをコピー"""
        column_map = {
            'title': 0,
            'brand': 1,
            'keywords': 2,
            'translated_kw': 3
        }
        
        column_index = column_map.get(column_type)
        if column_index is None:
            return
        
        results = []
        for item in self.result_tree.get_children():
            values = self.result_tree.item(item, 'values')
            if column_index < len(values):
                results.append(values[column_index])
        
        if results:
            result_text = '\n'.join(results)
            self.root.clipboard_clear()
            self.root.clipboard_append(result_text)
            
            column_names = {
                'title': '商品タイトル',
                'brand': 'ブランド',
                'keywords': 'キーワード',
                'translated_kw': '翻訳キーワード'
            }
            
            self.result_status.config(
                text=f"✓ {column_names[column_type]}をコピーしました", 
                fg=self.colors['success']
            )
        else:
            self.result_status.config(text="コピーするデータがありません", fg=self.colors['warning'])
    
    def export_csv(self):
        """CSV形式でエクスポート"""
        results = []
        for item in self.result_tree.get_children():
            values = self.result_tree.item(item, 'values')
            results.append(','.join([f'"{v}"' for v in values]))
        
        if results:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")]
            )
            if filename:
                with open(filename, 'w', encoding='utf-8-sig') as f:
                    f.write("商品タイトル,翻訳,ブランド,キーワード,翻訳キーワード\n")
                    f.write('\n'.join(results))
                self.result_status.config(text=f"✓ {filename}に出力しました", fg=self.colors['success'])
        else:
            self.result_status.config(text="出力する結果がありません", fg=self.colors['warning'])


def main():
    root = tk.Tk()
    app = ModernKeywordExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()