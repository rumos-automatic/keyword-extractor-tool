import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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


class KeywordExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("キーワード抽出ツール")
        self.root.geometry("1200x800")
        
        self.extractor = KeywordExtractor()
        
        self.setup_ui()
    
    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 設定フレーム
        settings_frame = ttk.LabelFrame(main_frame, text="設定", padding="10")
        settings_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 翻訳モード
        ttk.Label(settings_frame, text="翻訳モード:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.translate_mode = ttk.Combobox(settings_frame, width=20, state="readonly")
        self.translate_mode['values'] = [
            'ja_to_en',  # 日本語→英語
            'ja_to_ja',  # 日本語→日本語
            'en_to_ja',  # 英語→日本語
            'en_to_en'   # 英語→英語
        ]
        self.translate_mode.set('ja_to_en')
        self.translate_mode.grid(row=0, column=1, padx=5)
        
        # 抽出モード
        ttk.Label(settings_frame, text="抽出モード:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.extract_mode = ttk.Combobox(settings_frame, width=15, state="readonly")
        self.extract_mode['values'] = ['厳しめ', '標準', '緩め']
        self.extract_mode.set('標準')
        self.extract_mode.grid(row=0, column=3, padx=5)
        
        # ブランド名オプション
        self.include_brand = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="ブランド名を含める", 
                       variable=self.include_brand).grid(row=0, column=4, padx=20)
        
        # 入力エリア
        input_frame = ttk.LabelFrame(main_frame, text="商品タイトル入力（1行に1商品）", padding="10")
        input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=10, width=80, wrap=tk.WORD)
        self.input_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # サンプルテキストを追加
        self.input_text.insert(tk.END, "Nike Air Max 90 Essential Men's Shoes Black/White Size 10\n")
        self.input_text.insert(tk.END, "【資生堂】エリクシール シュペリエル リフトモイスト ローション II 170ml\n")
        self.input_text.insert(tk.END, "Apple iPhone 15 Pro Max 256GB Natural Titanium SIMフリー")
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="抽出実行", command=self.extract_keywords, 
                  width=20).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="クリア", command=self.clear_all, 
                  width=20).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="結果をコピー", command=self.copy_results, 
                  width=20).grid(row=0, column=2, padx=5)
        
        # 結果エリア
        result_frame = ttk.LabelFrame(main_frame, text="抽出結果", padding="10")
        result_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 結果表示用のTreeview
        columns = ('原文', '翻訳', 'ブランド', 'キーワード', '翻訳キーワード')
        self.result_tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=15)
        
        # カラムの設定
        self.result_tree.heading('原文', text='商品タイトル')
        self.result_tree.heading('翻訳', text='翻訳')
        self.result_tree.heading('ブランド', text='ブランド')
        self.result_tree.heading('キーワード', text='キーワード')
        self.result_tree.heading('翻訳キーワード', text='翻訳キーワード')
        
        self.result_tree.column('原文', width=250)
        self.result_tree.column('翻訳', width=250)
        self.result_tree.column('ブランド', width=100)
        self.result_tree.column('キーワード', width=200)
        self.result_tree.column('翻訳キーワード', width=200)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(result_frame, orient='vertical', command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        self.result_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # グリッドの重み設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
    
    def extract_keywords(self):
        # 既存の結果をクリア
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        # 入力テキストを取得
        input_text = self.input_text.get(1.0, tk.END)
        titles = [line.strip() for line in input_text.split('\n') if line.strip()]
        
        if not titles:
            messagebox.showwarning("警告", "商品タイトルを入力してください")
            return
        
        # モードの取得
        mode_map = {'厳しめ': 'strict', '標準': 'moderate', '緩め': 'loose'}
        mode = mode_map[self.extract_mode.get()]
        translate_mode = self.translate_mode.get()
        include_brand = self.include_brand.get()
        
        try:
            # キーワード抽出処理
            results = self.extractor.process_titles(titles, mode, translate_mode, include_brand)
            
            # 結果を表示
            for result in results:
                keywords_str = ', '.join(result['keywords'])
                translated_keywords_str = ', '.join(result['translated_keywords'])
                
                self.result_tree.insert('', 'end', values=(
                    result['original_title'][:50] + '...' if len(result['original_title']) > 50 else result['original_title'],
                    result['translated_title'][:50] + '...' if len(result['translated_title']) > 50 else result['translated_title'],
                    result['brand'],
                    keywords_str,
                    translated_keywords_str
                ))
            
            messagebox.showinfo("完了", f"{len(results)}件の商品タイトルを処理しました")
            
        except Exception as e:
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{str(e)}")
    
    def clear_all(self):
        self.input_text.delete(1.0, tk.END)
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
    
    def copy_results(self):
        results = []
        for item in self.result_tree.get_children():
            values = self.result_tree.item(item, 'values')
            results.append('\t'.join(values))
        
        if results:
            result_text = '\n'.join(results)
            self.root.clipboard_clear()
            self.root.clipboard_append(result_text)
            messagebox.showinfo("コピー完了", "結果をクリップボードにコピーしました")
        else:
            messagebox.showwarning("警告", "コピーする結果がありません")


def main():
    root = tk.Tk()
    app = KeywordExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()