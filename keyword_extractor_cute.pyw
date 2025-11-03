import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import re
from typing import List, Tuple, Dict
import json
import os
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class KeywordExtractor:
    def __init__(self):
        self.translator = None  # Google Translate APIを一時的に無効化
        self.common_brands = self.load_brands()
        self.gemini_model = None
        self.use_ai = False
        self.setup_gemini()
        self.load_prompt_templates()

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

    def setup_gemini(self):
        """Gemini APIを設定"""
        if not GEMINI_AVAILABLE:
            return

        # config.jsonから読み込み
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get('gemini_api_key')
                    if api_key and api_key != "YOUR_API_KEY_HERE":
                        genai.configure(api_key=api_key)
                        # 利用可能なGeminiモデルを試す（2025年版）
                        models_to_try = [
                            'gemini-2.5-flash',
                            'gemini-2.0-flash',
                            'gemini-flash-latest',
                            'gemini-2.5-pro',
                            'gemini-pro-latest'
                        ]

                        model_found = False
                        for model_name in models_to_try:
                            try:
                                self.gemini_model = genai.GenerativeModel(model_name)
                                self.use_ai = True
                                print(f"Gemini API ({model_name}) が正常に設定されました")
                                model_found = True
                                break
                            except Exception as e:
                                print(f"モデル {model_name} の設定に失敗: {e}")
                                continue

                        if not model_found:
                            print("利用可能なGemini APIモデルが見つかりません。AIを無効にして続行します。")
                            self.use_ai = False
                    else:
                        print("Gemini APIキーが未設定です")
                        self.use_ai = False
            except Exception as e:
                print(f"Gemini設定エラー: {e}")
                self.use_ai = False
        else:
            # config.jsonが存在しない場合は作成
            default_config = {"gemini_api_key": "YOUR_API_KEY_HERE"}
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            print(f"{config_path}を作成しました。APIキーを設定してください。")
            self.use_ai = False

    def _extract_words_from_title(self, title: str) -> List[str]:
        """タイトルから実際に存在する単語を抽出する"""
        words = []

        # 基本的な区切り文字で分割
        # スペース、カンマ、スラッシュ、パイプ、括弧などで分割
        import re

        # 複数の区切り文字で分割
        # 日本語の場合は助詞なども考慮
        pattern = r'[\s,，、。・/／｜|\[\]()（）【】「」『』]+'
        parts = re.split(pattern, title)

        for part in parts:
            if not part:
                continue

            # 日本語が含まれる場合の処理
            if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', part):
                # 日本語の単語抽出
                # カタカナの連続、漢字の連続、英数字の連続を単語として抽出
                japanese_words = re.findall(r'[\u30A0-\u30FF]+|[\u4E00-\u9FAF]+|[A-Za-z0-9\-_]+', part)
                words.extend(japanese_words)
            else:
                # 英語の場合はそのまま追加
                if part and len(part) > 0:
                    words.append(part)

        # 空文字列を除去し、重複を排除（順序を保持）
        seen = set()
        result = []
        for word in words:
            if word and word not in seen:
                seen.add(word)
                result.append(word)

        return result

    def detect_language(self, text: str) -> str:
        """テキストの言語を検出"""
        # 日本語文字が含まれているかチェック
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text):
            return 'ja'
        return 'en'

    def translate_text(self, text: str, target_lang: str) -> str:
        """テキストを指定言語に翻訳"""
        if not text:
            return ""

        # ENダッシュのみを置換（最小限の対策）
        text = text.replace('\u2013', '-')

        try:
            from googletrans import Translator
            translator = Translator()

            if target_lang == 'en':
                result = translator.translate(text, src='ja', dest='en')
            elif target_lang == 'ja':
                result = translator.translate(text, src='en', dest='ja')
            else:
                return text

            return result.text if result and result.text else text
        except Exception as e:
            print(f"Translation error: {e}")
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

    def fetch_product_info_from_asin(self, asin: str, region: str = "jp") -> tuple:
        """ASINからAmazonの商品タイトルとブランド名を取得"""
        import requests
        from bs4 import BeautifulSoup
        import time
        import random

        if not asin:
            return "", ""

        asin = asin.strip()
        if len(asin) != 10:
            return "", ""

        try:
            # Amazonの商品ページURL（地域に応じて変更）
            if region == "us":
                url = f"https://www.amazon.com/dp/{asin}"
                accept_language = 'en-US,en;q=0.9'
            else:  # jp
                url = f"https://www.amazon.co.jp/dp/{asin}"
                accept_language = 'ja-JP,ja;q=0.9,en;q=0.8'

            # User-Agentを設定してリクエスト
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': accept_language,
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }

            # リクエスト間隔を設ける
            time.sleep(random.uniform(1, 3))

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 商品タイトルを取得（指定されたセレクター）
            title = ""
            title_element = soup.select_one('#productTitle')
            if title_element:
                title = title_element.get_text().strip()

            # ブランド名を取得（指定されたセレクター）
            brand = ""
            brand_element = soup.select_one('tr.po-brand td.a-span9[role="presentation"] span.a-size-base.po-break-word')
            if brand_element:
                brand = brand_element.get_text().strip()

            return title, brand

        except Exception as e:
            print(f"ASIN取得エラー ({asin}): {e}")
            return "", ""

    def fetch_product_title_from_asin(self, asin: str) -> str:
        """後方互換性のためのメソッド"""
        title, _ = self.fetch_product_info_from_asin(asin)
        return title

    def load_prompt_templates(self):
        """プロンプトテンプレートを読み込み"""
        template_path = "prompt_templates.json"
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    self.prompt_data = json.load(f)
            except Exception as e:
                print(f"プロンプトテンプレート読み込みエラー: {e}")
                self.prompt_data = self.get_default_prompt_data()
        else:
            self.prompt_data = self.get_default_prompt_data()
            self.save_prompt_templates()

    def save_prompt_templates(self):
        """プロンプトテンプレートを保存"""
        template_path = "prompt_templates.json"
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(self.prompt_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"プロンプトテンプレート保存エラー: {e}")

    def get_default_prompt_data(self):
        """デフォルトのプロンプトデータを返す"""
        return {
            "templates": {
                "default": {
                    "name": "標準テンプレート",
                    "base_prompt": "商品タイトル: {title}\n\n{instruction}{brand_instruction}\n\n重要な制約:\n- 商品タイトルに実際に含まれている単語のみを使用してください\n- 新しい単語や類義語を生成しないでください\n- タイトルを区切り文字（スペース、カンマ、スラッシュ、括弧など）で分割した結果の単語から選んでください\n\nキーワードをカンマ区切りで返してください。\n例: キーワード1, キーワード2, キーワード3",
                    "instructions": {
                        "strict": "完全一致検索用の最も重要なキーワード3-4個抽出してください。ブランド名、商品名、型番などを優先してください。",
                        "moderate": "バランスよく検索できるキーワード5-6個抽出してください。ブランド、商品タイプ、特徴、カテゴリなどを含めてください。",
                        "loose": "幅広い検索用のキーワード7-8個抽出してください。大カテゴリ、関連商品、一般的な特徴も含めてください。"
                    }
                }
            },
            "current_template": "default"
        }

    def get_current_prompt_template(self):
        """現在選択されているプロンプトテンプレートを取得"""
        current = self.prompt_data.get('current_template', 'default')
        return self.prompt_data['templates'].get(current, self.prompt_data['templates']['default'])

    def validate_ai_keywords(self, keywords: List[str], title: str) -> List[str]:
        """AIが生成したキーワードがタイトルに実際に存在するかを検証"""
        # タイトルから実際の単語を抽出
        title_words = self._extract_words_from_title(title)
        title_words_lower = [word.lower() for word in title_words]

        validated_keywords = []

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 明らかに説明文や文章を除外
            if any(phrase in keyword for phrase in ['です', 'ます', 'について', 'キーワード', '制造', '製造', 'WF4', 'された']):
                print(f"説明文として除外: {keyword}")
                continue

            # 長すぎるキーワード（20文字以上）を除外
            if len(keyword) > 20:
                print(f"長すぎるキーワードを除外: {keyword}")
                continue

            # タイトルの単語と完全一致または部分一致をチェック
            is_valid = False

            # 完全一致チェック
            if keyword_lower in title_words_lower:
                is_valid = True
            else:
                # 部分一致チェック（タイトルの単語の一部として含まれているか）
                for title_word in title_words_lower:
                    if keyword_lower in title_word or title_word in keyword_lower:
                        is_valid = True
                        break

            if is_valid:
                validated_keywords.append(keyword)
            else:
                print(f"タイトルに存在しないキーワードを除外: {keyword}")

        return validated_keywords

    def extract_keywords_strict(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """厳しめモード：ほぼ同じ商品を探すためのキーワード抽出（タイトルの単語をそのまま使う）"""
        keywords = []

        # タイトルから実際の単語を抽出
        words = self._extract_words_from_title(title)

        # ブランド名を追加
        if include_brand and brand:
            # ブランドがそのまま単語として存在する場合
            if brand in words:
                keywords.append(brand)
            # ブランドを含む単語がある場合
            else:
                for word in words:
                    if brand.lower() in word.lower():
                        keywords.append(word)
                        break

        # 型番・品番を優先的に抽出
        for word in words:
            if word not in keywords:
                # 数字を含む単語（型番の可能性が高い）
                if re.search(r'\d', word):
                    keywords.append(word)
                    if len(keywords) >= 8:
                        break

        # ハイフンやアンダースコアを含む単語（品番の可能性）
        for word in words:
            if word not in keywords:
                if '-' in word or '_' in word:
                    keywords.append(word)
                    if len(keywords) >= 8:
                        break

        # 大文字の略語（2文字以上）
        for word in words:
            if word not in keywords:
                if re.match(r'^[A-Z]{2,}$', word):
                    keywords.append(word)
                    if len(keywords) >= 8:
                        break

        # 残りは長い単語から追加
        sorted_words = sorted(words, key=len, reverse=True)
        for word in sorted_words:
            if word not in keywords and len(word) >= 2:  # 2文字以上
                keywords.append(word)
                if len(keywords) >= 8:
                    break

        return keywords[:8]  # 最大8個

    def extract_keywords_moderate(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """標準モード：バランスの良いキーワード抽出（タイトルの単語から3〜5個）"""
        keywords = []

        # タイトルから実際の単語を抽出
        words = self._extract_words_from_title(title)

        # 単語数の半分程度を目標にする（3〜5個）
        target_count = min(5, max(3, len(words) // 2))

        # ブランド名を追加
        if include_brand and brand:
            if brand in words:
                keywords.append(brand)
            else:
                for word in words:
                    if brand.lower() in word.lower():
                        keywords.append(word)
                        break

        # 数字を含む重要な単語（型番など）
        for word in words:
            if word not in keywords and re.search(r'\d', word):
                keywords.append(word)
                if len(keywords) >= target_count:
                    break

        # 大文字で始まる単語（固有名詞）
        for word in words:
            if word not in keywords and re.match(r'^[A-Z]', word) and len(word) >= 3:
                keywords.append(word)
                if len(keywords) >= target_count:
                    break

        # 長い単語を優先的に追加
        sorted_words = sorted(words, key=len, reverse=True)
        for word in sorted_words:
            if word not in keywords and len(word) >= 3:
                keywords.append(word)
                if len(keywords) >= target_count:
                    break

        return keywords[:target_count]

    def extract_keywords_loose(self, title: str, include_brand: bool, brand: str) -> List[str]:
        """緩めモード：大まかなカテゴリでの検索（タイトルの単語から2〜3個）"""
        keywords = []

        # タイトルから実際の単語を抽出
        words = self._extract_words_from_title(title)

        # ブランド名を含める場合（大手ブランドのみ）
        if include_brand and brand:
            major_brands = ['Intel', 'AMD', 'NVIDIA', 'GIGABYTE', 'ASUS', 'MSI', 'Apple', 'Samsung', 'Sony']
            for major_brand in major_brands:
                if major_brand.lower() == brand.lower():
                    if brand in words:
                        keywords.append(brand)
                        break
                    for word in words:
                        if brand.lower() in word.lower():
                            keywords.append(word)
                            break
                    break

        # カテゴリを表す長い単語（数字を含まない）
        non_numeric = [w for w in words if not re.search(r'\d', w)]
        sorted_words = sorted(non_numeric, key=len, reverse=True)

        for word in sorted_words:
            if word not in keywords and len(word) >= 4:
                keywords.append(word)
                if len(keywords) >= 3:
                    break

        # まだ足りない場合は任意の重要そうな単語を追加
        if len(keywords) < 2:
            for word in sorted_words:
                if word not in keywords and len(word) >= 3:
                    keywords.append(word)
                    if len(keywords) >= 3:
                        break

        return keywords[:3]  # 最大3個

    def extract_keywords_with_ai(self, title: str, mode: str, include_brand: bool, brand: str) -> List[str]:
        """Gemini APIを使用したキーワード抽出"""
        if not self.use_ai or not self.gemini_model:
            # AIが使用できない場合は通常の抽出にフォールバック
            if mode == 'strict':
                return self.extract_keywords_strict(title, include_brand, brand)
            elif mode == 'moderate':
                return self.extract_keywords_moderate(title, include_brand, brand)
            else:
                return self.extract_keywords_loose(title, include_brand, brand)

        try:
            # 現在のプロンプトテンプレートを取得
            template = self.get_current_prompt_template()

            # モードに応じた指示文を取得
            instruction = template['instructions'].get(mode, template['instructions']['moderate'])

            # ブランド名の扱いを指定
            brand_instruction = ""
            if not include_brand and brand:
                brand_instruction = f"\n注意: '{brand}'はキーワードに含めないでください。"

            # プロンプトをフォーマット
            prompt = template['base_prompt'].format(
                title=title,
                instruction=instruction,
                brand_instruction=brand_instruction
            )

            # Gemini APIを呼び出し
            response = self.gemini_model.generate_content(prompt)

            # レスポンスをパース
            keywords_text = response.text.strip()
            keywords = [kw.strip() for kw in keywords_text.split(',')]

            # ブランド名を含める場合は先頭に追加
            if include_brand and brand and brand not in keywords:
                keywords.insert(0, brand)

            # 空のキーワードを除去
            keywords = [kw for kw in keywords if kw]

            # AI結果の検証：タイトルに存在しない単語や説明文をフィルタリング
            validated_keywords = self.validate_ai_keywords(keywords, title)
            if len(validated_keywords) < len(keywords):
                print(f"AIキーワード検証: {len(keywords)}個中{len(validated_keywords)}個が有効でした")
                print(f"無効なキーワード: {[kw for kw in keywords if kw not in validated_keywords]}")

            return validated_keywords

        except Exception as e:
            print(f"AIキーワード抽出エラー: {e}")
            # エラー時は通常の抽出にフォールバック
            if mode == 'strict':
                return self.extract_keywords_strict(title, include_brand, brand)
            elif mode == 'moderate':
                return self.extract_keywords_moderate(title, include_brand, brand)
            else:
                return self.extract_keywords_loose(title, include_brand, brand)

    def process_asins(self, asins: List[str], mode: str, translate_mode: str,
                     include_brand: bool, region: str = "jp", use_ai: bool = None) -> List[Dict]:
        """複数のASINを処理してタイトルとブランド名を取得後、キーワード抽出"""
        results = []
        for asin in asins:
            if not asin.strip():
                continue

            # ASINから商品タイトルとブランド名を取得
            title, brand_from_asin = self.fetch_product_info_from_asin(asin.strip(), region)
            if not title:
                print(f"タイトル取得失敗: {asin}")
                continue

            # 通常のタイトル処理と同じ処理を実行
            result = self.process_single_title(title, mode, translate_mode, include_brand, use_ai)

            # ASINから取得したブランド名がある場合はそれを優先
            if brand_from_asin:
                result['brand'] = brand_from_asin

            result['asin'] = asin.strip()  # ASINも結果に保存
            results.append(result)

        return results

    def process_single_title(self, title: str, mode: str, translate_mode: str,
                           include_brand: bool, use_ai: bool = None) -> Dict:
        """単一のタイトルを処理"""
        result = {
            'original_title': title,
            'translated_title': '',
            'brand': self.extract_brand(title),
            'keywords': [],
            'translated_keywords': []
        }

        # キーワード抽出（AIを使用するかどうかを決定）
        if use_ai is None:
            use_ai = self.use_ai

        if use_ai:
            keywords = self.extract_keywords_with_ai(title, mode, include_brand, result['brand'])
        elif mode == 'strict':
            keywords = self.extract_keywords_strict(title, include_brand, result['brand'])
        elif mode == 'moderate':
            keywords = self.extract_keywords_moderate(title, include_brand, result['brand'])
        else:  # loose
            keywords = self.extract_keywords_loose(title, include_brand, result['brand'])

        # 翻訳モードに応じた処理
        if translate_mode == 'none':  # 翻訳なし
            result['keywords'] = keywords
            result['translated_keywords'] = []
        elif translate_mode == 'auto':  # 自動判定翻訳
            result['keywords'] = keywords

            # 抽出されたキーワードの言語を判定
            keywords_text = ' '.join(keywords)
            detected_lang = self.detect_language(keywords_text)

            if detected_lang == 'ja':
                # 日本語→英語に翻訳
                translated_kw = [self.translate_text(kw, 'en') for kw in keywords]
                result['translated_keywords'] = translated_kw
                print(f"日本語キーワードを英語に翻訳: {keywords} → {translated_kw}")
            else:
                # 英語→日本語に翻訳
                translated_kw = [self.translate_text(kw, 'ja') for kw in keywords]
                result['translated_keywords'] = translated_kw
                print(f"英語キーワードを日本語に翻訳: {keywords} → {translated_kw}")

        return result

    def process_titles(self, titles: List[str], mode: str, translate_mode: str,
                      include_brand: bool, use_ai: bool = None) -> List[Dict]:
        """複数の商品タイトルを処理"""
        results = []

        # 翻訳モードの解析
        if translate_mode != 'none':
            source_lang, target_lang = translate_mode.split('_to_')
        else:
            source_lang = target_lang = None

        for idx, title in enumerate(titles):
            if not title.strip():
                continue

            print(f"処理中 {idx+1}/{len(titles)}: {title[:50]}...")  # デバッグ出力

            result = {
                'original_title': title,
                'translated_title': '',
                'brand': '',
                'keywords': [],
                'translated_keywords': []
            }

            # ブランド抽出
            result['brand'] = self.extract_brand(title)

            # キーワード抽出（AIを使用するかどうかを決定）
            if use_ai is None:
                use_ai = self.use_ai

            if use_ai:
                keywords = self.extract_keywords_with_ai(title, mode, include_brand, result['brand'])
            elif mode == 'strict':
                keywords = self.extract_keywords_strict(title, include_brand, result['brand'])
            elif mode == 'moderate':
                keywords = self.extract_keywords_moderate(title, include_brand, result['brand'])
            else:  # loose
                keywords = self.extract_keywords_loose(title, include_brand, result['brand'])

            # 翻訳モードに応じた処理
            if translate_mode == 'none':  # 翻訳なし
                result['keywords'] = keywords
                result['translated_keywords'] = []
            elif translate_mode == 'auto':  # 自動判定翻訳
                result['keywords'] = keywords

                # 抽出されたキーワードの言語を判定
                keywords_text = ' '.join(keywords)
                detected_lang = self.detect_language(keywords_text)

                if detected_lang == 'ja':
                    # 日本語→英語に翻訳
                    translated_kw = [self.translate_text(kw, 'en') for kw in keywords]
                    result['translated_keywords'] = translated_kw
                else:
                    # 英語→日本語に翻訳
                    translated_kw = [self.translate_text(kw, 'ja') for kw in keywords]
                    result['translated_keywords'] = translated_kw

            results.append(result)

        return results


class CuteKeywordExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ キーワード抽出ツール ✨")
        self.root.geometry("1400x900")

        # DPI認識を有効化（高DPIディスプレイ対応）
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        # 淡い黄色系のかわいいカラースキーム
        self.colors = {
            'bg_main': '#fffef9',           # ソフトクリーム
            'bg_secondary': '#fffbf0',       # ソフトイエロー
            'bg_tertiary': '#ffe4b5',        # モカシン
            'accent': '#ffb347',             # ソフトオレンジ
            'accent_hover': '#ffa500',       # オレンジ
            'text_primary': '#4a4a4a',       # ダークグレー
            'text_secondary': '#7a7a7a',     # ミディアムグレー
            'success': '#90ee90',            # ライトグリーン
            'warning': '#ffd700',            # ゴールド
            'error': '#ff9999',              # ソフトレッド
            'input_bg': '#ffffff',           # ホワイト
            'button_bg': '#ffb347',          # ソフトオレンジ
            'button_hover': '#ffa500',       # オレンジ
            'table_bg': '#fffef5',           # ソフトクリーム
            'table_alt': '#fff5ee'           # シーシェル
        }

        self.root.configure(bg=self.colors['bg_main'])

        # 基準フォントサイズとスケール係数
        self.base_font_sizes = {
            'title': 22,
            'subtitle': 10,
            'heading': 12,
            'body': 11,
            'small': 9,
            'button': 13,  # ボタンのフォントを大きくして読みやすく
            'label': 10
        }
        self.scale_factor = 1.0
        self.min_scale = 0.8
        self.max_scale = 2.0
        self.ui_widgets = []  # 更新が必要なウィジェットを保存

        # スタイルの設定
        self.setup_styles()

        self.extractor = KeywordExtractor()

        self.setup_ui()

        # ウィンドウを中央に配置
        self.center_window()

        # リサイズイベントをバインド
        self.root.bind('<Configure>', self.on_window_resize)
        self.last_width = 1400
        self.last_height = 900
        self.ui_widgets = []  # 更新が必要なウィジェットを保存
        self.is_paused = False  # 一時停止フラグ
        self.processing = False  # 処理中フラグ

    def center_window(self):
        """ウィンドウを画面中央に配置"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def get_scaled_font(self, font_type='body', bold=False):
        """スケールされたフォントサイズを取得"""
        size = int(self.base_font_sizes[font_type] * self.scale_factor)
        weight = 'bold' if bold else 'normal'
        return font.Font(family='Segoe UI', size=size, weight=weight)

    def on_window_resize(self, event=None):
        """ウィンドウリサイズ時のフォントスケーリング"""
        if not hasattr(self, 'root'):
            return

        # ウィンドウサイズの変化を検出
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()

        # 初期サイズからの変化率を計算
        width_ratio = current_width / 1400
        height_ratio = current_height / 900

        # より小さい比率を使用（アスペクト比を維持）
        new_scale = min(width_ratio, height_ratio)
        new_scale = max(self.min_scale, min(new_scale, self.max_scale))

        # スケールが変化した場合のみ更新
        if abs(new_scale - self.scale_factor) > 0.05:  # 5%以上の変化で更新
            self.scale_factor = new_scale
            self.update_all_fonts()

    def update_all_fonts(self):
        """すべてのウィジェットのフォントを更新"""
        for widget_info in self.ui_widgets:
            widget = widget_info['widget']
            font_type = widget_info['font_type']
            bold = widget_info.get('bold', False)

            if widget and widget.winfo_exists():
                try:
                    widget.configure(font=self.get_scaled_font(font_type, bold))
                except:
                    pass  # ウィジェットがフォント属性を持たない場合

    def setup_styles(self):
        """ttkスタイルの設定"""
        style = ttk.Style()
        style.theme_use('clam')

        # かわいいコンボボックススタイル
        style.configure('Cute.TCombobox',
                       fieldbackground=self.colors['input_bg'],
                       background=self.colors['accent'],
                       bordercolor=self.colors['accent'],
                       arrowcolor=self.colors['text_primary'],
                       lightcolor=self.colors['accent_hover'],
                       darkcolor=self.colors['accent'])

        # Treeviewスタイル
        style.configure('Cute.Treeview',
                       background=self.colors['table_bg'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['table_bg'],
                       bordercolor=self.colors['accent'])

        style.configure('Cute.Treeview.Heading',
                       background=self.colors['accent'],
                       foreground='white',
                       relief='flat')

        style.map('Cute.Treeview.Heading',
                 background=[('active', self.colors['accent_hover'])])

        # プログレスバースタイル
        style.configure('Cute.Horizontal.TProgressbar',
                       background=self.colors['accent'],
                       troughcolor=self.colors['bg_main'],
                       borderwidth=1,
                       lightcolor=self.colors['accent'],
                       darkcolor=self.colors['accent'])

    def create_rounded_button(self, parent, text, bg_color, hover_color, command, width=150):
        """丸みのあるボタンを作成"""
        button_frame = tk.Frame(parent, bg=self.colors['bg_main'])
        button_frame.pack(side='left', padx=10, pady=8)

        # Canvasで角丸ボタンを作成
        canvas = tk.Canvas(button_frame,
                          width=width,
                          height=45,
                          bg=self.colors['bg_main'],
                          highlightthickness=0)
        canvas.pack()

        # 角丸四角形を描画する関数
        def create_rounded_rect(x1, y1, x2, y2, radius=15, **kwargs):
            points = []
            for x, y in [(x1, y1 + radius), (x1, y1), (x1 + radius, y1),
                        (x2 - radius, y1), (x2, y1), (x2, y1 + radius),
                        (x2, y2 - radius), (x2, y2), (x2 - radius, y2),
                        (x1 + radius, y2), (x1, y2), (x1, y2 - radius)]:
                points.extend([x, y])
            return canvas.create_polygon(points, smooth=True, **kwargs)

        # 角丸背景
        rect_id = create_rounded_rect(2, 2, width-2, 43,
                                      radius=12,
                                      fill=bg_color,
                                      outline='')

        # テキスト（読みやすい大きさ）
        text_id = canvas.create_text(width/2, 22,
                                    text=text,
                                    fill='white',
                                    font=self.get_scaled_font('button', bold=True))

        # ホバー効果
        def on_enter(e):
            canvas.itemconfig(rect_id, fill=hover_color)
            canvas.config(cursor='hand2')

        def on_leave(e):
            canvas.itemconfig(rect_id, fill=bg_color)

        # クリック効果
        clicked = False  # クリック状態を管理
        def on_click(e):
            nonlocal clicked
            if clicked:  # すでにクリックされている場合は無視
                return
            clicked = True

            # 押し込み効果
            canvas.move(rect_id, 1, 1)
            canvas.move(text_id, 1, 1)

            def reset():
                nonlocal clicked
                canvas.move(rect_id, -1, -1)
                canvas.move(text_id, -1, -1)
                clicked = False

            canvas.after(100, reset)
            command()

        canvas.bind('<Enter>', on_enter)
        canvas.bind('<Leave>', on_leave)
        canvas.bind('<Button-1>', on_click)

        # UI更新用に保存
        self.ui_widgets.append({
            'widget': canvas,
            'font_type': 'button',
            'bold': True
        })

        # 一時停止ボタンの場合は参照を返す
        if "停止" in text or "再開" in text:
            return {'canvas': canvas, 'rect_id': rect_id, 'text_id': text_id}

    def setup_ui(self):
        """UIのセットアップ"""
        # メインタイトル
        title_frame = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame,
                              text="Amazon ASIN キーワード抽出ツール",
                              font=self.get_scaled_font('title', bold=True),
                              bg=self.colors['bg_secondary'],
                              fg=self.colors['text_primary'])
        title_label.pack(expand=True)
        self.ui_widgets.append({'widget': title_label, 'font_type': 'title', 'bold': True})

        subtitle = tk.Label(title_frame,
                          text="ASINから商品情報を取得してAIによる高精度なキーワード抽出",
                          font=self.get_scaled_font('subtitle'),
                          bg=self.colors['bg_secondary'],
                          fg=self.colors['text_secondary'])
        subtitle.pack()
        self.ui_widgets.append({'widget': subtitle, 'font_type': 'subtitle'})

        # コンテンツエリア
        content_frame = tk.Frame(self.root, bg=self.colors['bg_main'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # 左側パネル（設定）
        left_panel = tk.Frame(content_frame, bg=self.colors['bg_secondary'], width=300)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)

        # 設定タイトル
        label1 = tk.Label(left_panel,
                text="設定",
                font=self.get_scaled_font('heading', bold=True),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary']).pack(pady=15)

        # 翻訳モード
        trans_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        trans_frame.pack(fill='x', padx=20, pady=10)

        labelTrans = tk.Label(trans_frame,
                text="翻訳モード",
                font=self.get_scaled_font('label'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(anchor='w')

        self.translate_mode = ttk.Combobox(trans_frame,
                                          width=25,
                                          state="readonly",
                                          font=self.get_scaled_font('label'))
        self.translate_mode['values'] = [
            'なし',
            'あり'
        ]
        self.translate_mode.set('なし')
        self.translate_mode.pack(fill='x', pady=5)

        # 抽出モード設定
        extract_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        extract_frame.pack(fill='x', padx=20, pady=10)

        label2 = tk.Label(extract_frame,
                text="抽出モード",
                font=self.get_scaled_font('label'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(anchor='w')

        # モードボタン（ラジオボタン風）
        self.extract_mode = tk.StringVar(value='moderate')

        modes = [
            ('厳しめ', 'strict', 'ほぼ同じ商品を見つける'),
            ('標準', 'moderate', 'バランスの良いキーワード抽出'),
            ('緩め', 'loose', '大まかなカテゴリで検索')
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
                               selectcolor=self.colors['bg_main'],  # ラジオボタンの背景色
                               activebackground=self.colors['bg_secondary'],  # クリック時のハイライトを無効化
                               activeforeground=self.colors['text_primary'],
                               font=self.get_scaled_font('body', bold=True),
                               indicatoron=1,  # インジケーターを確実に表示
                               relief='flat',
                               bd=0,  # ボーダーを無くす
                               highlightthickness=0,
                               padx=5)
            rb.pack(anchor='w')
            self.ui_widgets.append({'widget': rb, 'font_type': 'body', 'bold': True})

            label_desc = tk.Label(mode_frame,
                    text=f"  {desc}",
                    font=self.get_scaled_font('small'),
                    bg=self.colors['bg_secondary'],
                    fg=self.colors['text_secondary']).pack(anchor='w', padx=(20, 0))

        # ブランド名オプション
        brand_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        brand_frame.pack(fill='x', padx=20, pady=10, anchor='w')

        self.include_brand = tk.BooleanVar(value=True)

        # チェックボックスを直接作成（フレーム不要）
        cb_text = "抽出キーワードにブランド名を含める"  # アイコンなし、1行表示
        cb = tk.Checkbutton(brand_frame,
                           text=cb_text,
                           variable=self.include_brand,
                           bg=self.colors['bg_secondary'],
                           fg=self.colors['text_primary'],
                           selectcolor=self.colors['bg_main'],  # チェックボックスの背景色
                           activebackground=self.colors['bg_secondary'],  # クリック時のハイライトを無効化
                           activeforeground=self.colors['text_primary'],
                           font=self.get_scaled_font('body'),
                           relief='flat',  # 枠をフラットに
                           bd=0,  # ボーダーを無くす
                           highlightthickness=0,
                           indicatoron=1,  # インジケーターを確実に表示
                           justify='left',  # 左揃え
                           anchor='w',  # チェックボックス自体も左揃え
                           padx=0,
                           pady=2)
        cb.pack(side='left', anchor='w', pady=5)  # side='left'で左側に配置
        self.ui_widgets.append({'widget': cb, 'font_type': 'body'})

        # AI使用オプション
        ai_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        ai_frame.pack(fill='x', padx=20, pady=10, anchor='w')

        self.use_ai = tk.BooleanVar(value=self.extractor.use_ai)

        # AIチェックボックス
        ai_text = "AIを使用する"  # 短いテキストでアイコンなし
        ai_cb = tk.Checkbutton(ai_frame,
                              text=ai_text,
                              variable=self.use_ai,
                              bg=self.colors['bg_secondary'],
                              fg=self.colors['text_primary'],
                              selectcolor=self.colors['bg_main'],
                              activebackground=self.colors['bg_secondary'],
                              activeforeground=self.colors['text_primary'],
                              font=self.get_scaled_font('body'),
                              relief='flat',
                              bd=0,
                              highlightthickness=0,
                              indicatoron=1,
                              justify='left',
                              anchor='w',
                              padx=0,
                              pady=2)
        ai_cb.pack(side='left', anchor='w', pady=5)
        self.ui_widgets.append({'widget': ai_cb, 'font_type': 'body'})

        # AIステータス表示
        if not self.extractor.use_ai:
            status_text = "APIキー未設定"
            status_color = self.colors['error']
        else:
            status_text = "Gemini API有効"
            status_color = '#ff8c00'  # 濃いオレンジ色（DarkOrange）

        ai_status = tk.Label(ai_frame,
                           text=f"({status_text})",
                           font=self.get_scaled_font('small'),
                           bg=self.colors['bg_secondary'],
                           fg=status_color)
        ai_status.pack(side='left', padx=(10, 0))
        self.ui_widgets.append({'widget': ai_status, 'font_type': 'small'})

        # プロンプト編集ボタン（AIを使用する場合のみ表示）
        if self.extractor.use_ai:
            prompt_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
            prompt_frame.pack(fill='x', padx=20, pady=10)

            prompt_btn = tk.Button(prompt_frame,
                                 text="AIプロンプト編集",
                                 font=self.get_scaled_font('label'),
                                 bg=self.colors['accent'],
                                 fg='white',
                                 relief='flat',
                                 bd=0,
                                 padx=10,
                                 pady=5,
                                 cursor='hand2',
                                 command=self.open_prompt_editor)
            prompt_btn.pack(anchor='w')
            self.ui_widgets.append({'widget': prompt_btn, 'font_type': 'label'})

        # 統計情報
        stats_frame = tk.Frame(left_panel, bg=self.colors['bg_tertiary'])
        stats_frame.pack(fill='x', padx=20, pady=20)

        label3 = tk.Label(stats_frame,
                text="統計情報",
                font=self.get_scaled_font('label', bold=True),
                bg=self.colors['bg_tertiary'],
                fg=self.colors['text_primary']).pack(pady=5)

        self.stats_label = tk.Label(stats_frame,
                                   text="件数: 0\nブランド数: 0\n処理状況: 待機中",
                                   font=self.get_scaled_font('small'),
                                   bg=self.colors['bg_tertiary'],
                                   fg=self.colors['text_primary'],  # 黒色に変更
                                   justify='left')
        self.stats_label.pack(pady=5)

        # プログレスバー
        progress_frame = tk.Frame(stats_frame, bg=self.colors['bg_tertiary'])
        progress_frame.pack(fill='x', pady=(10, 5))

        self.progress_label = tk.Label(progress_frame,
                                     text="進捗",
                                     font=self.get_scaled_font('small'),
                                     bg=self.colors['bg_tertiary'],
                                     fg=self.colors['text_primary'])
        self.progress_label.pack(anchor='w')

        self.progress_bar = ttk.Progressbar(progress_frame,
                                          mode='determinate',
                                          length=250,
                                          style='Cute.Horizontal.TProgressbar')
        self.progress_bar.pack(fill='x', pady=2)

        self.progress_text = tk.Label(progress_frame,
                                    text="0 / 0 (0%)",
                                    font=self.get_scaled_font('small'),
                                    bg=self.colors['bg_tertiary'],
                                    fg=self.colors['text_primary'])
        self.progress_text.pack(anchor='w')

        # 右側パネル（メインコンテンツ）
        right_panel = tk.Frame(content_frame, bg=self.colors['bg_main'])
        right_panel.pack(side='left', fill='both', expand=True)

        # 入力エリア
        input_container = tk.Frame(right_panel, bg=self.colors['bg_secondary'])
        input_container.pack(fill='both', expand=False, pady=(0, 20))

        input_header = tk.Frame(input_container, bg=self.colors['bg_secondary'])
        input_header.pack(fill='x', padx=15, pady=(15, 5))

        # ASIN専用モード（商品タイトル機能を削除）
        self.input_mode = tk.StringVar(value="asin")  # ASINのみ

        # ASIN入力ラベル（一番左に配置）
        self.input_label = tk.Label(input_header,
                text="ASIN入力",
                font=self.get_scaled_font('heading', bold=True),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'])
        self.input_label.pack(side='left', padx=(0, 5))

        self.input_hint = tk.Label(input_header,
                text="(1行に1ASIN)",
                font=self.get_scaled_font('small'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'])
        self.input_hint.pack(side='left', padx=(0, 20))

        # Amazon地域選択（右側に配置）
        self.amazon_region = tk.StringVar(value="jp")  # "jp" or "us"
        self.region_frame = tk.Frame(input_header, bg=self.colors['bg_secondary'])
        self.region_frame.pack(side='left')

        jp_region_btn = tk.Radiobutton(self.region_frame,
                                     text="日本Amazon",
                                     variable=self.amazon_region,
                                     value="jp",
                                     font=self.get_scaled_font('small'),
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     selectcolor=self.colors['accent'])
        jp_region_btn.pack(side='left', padx=(0, 10))

        us_region_btn = tk.Radiobutton(self.region_frame,
                                     text="アメリカAmazon",
                                     variable=self.amazon_region,
                                     value="us",
                                     font=self.get_scaled_font('small'),
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     selectcolor=self.colors['accent'])
        us_region_btn.pack(side='left', padx=(0, 10))

        # テキスト入力エリアを作成
        self.create_input_area(input_container)

        # 右パネルのメイン部分を作成
        self.create_main_right_panel(right_panel)


    def display_result(self, result):
        """結果を表示に追加"""
        keywords_str = ' '.join(result['keywords'])
        translated_keywords_str = ' '.join(result['translated_keywords'])

        # 交互に背景色を変える
        row_index = len(self.result_tree.get_children())
        tags = ('oddrow',) if row_index % 2 == 0 else ('evenrow',)

        # データの各値にパディングを追加（視覚的な区切り）
        asin_val = result.get('asin', '')  # ASINを取得
        title_val = result['original_title']
        brand_val = result['brand'] or ''

        # フルデータを保存（コピー用）
        item_id = self.result_tree.insert('', 'end', values=(
            asin_val,
            title_val,
            brand_val,
            keywords_str,
            translated_keywords_str
        ), tags=tags)

        # フルデータ配列に追加
        self.full_data.append({
            'asin': asin_val,
            'title': title_val,
            'brand': brand_val,
            'keywords': keywords_str,
            'translated_keywords': translated_keywords_str
        })

        # テーブルを自動スクロール
        self.result_tree.see(item_id)

    def create_input_area(self, parent):
        """テキスト入力エリアを作成"""
        # テキスト入力エリア
        text_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        text_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self.input_text = tk.Text(text_frame,
                                 bg=self.colors['input_bg'],
                                 fg=self.colors['text_primary'],
                                 insertbackground=self.colors['accent'],
                                 selectbackground=self.colors['accent'],
                                 selectforeground='white',
                                 font=self.get_scaled_font('body'),
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

        # サンプルテキストは挿入しない（ユーザーの要望により削除）

    def create_main_right_panel(self, right_panel):
        """右パネルのメイン部分を作成"""
        # ボタンエリア - 2行に分ける
        # 1行目のボタン（メイン操作）
        button_container1 = tk.Frame(right_panel, bg=self.colors['bg_main'])
        button_container1.pack(fill='x', pady=(0, 10))

        # ボタンを作成（絵文字なし、読みやすい文字）
        self.create_rounded_button(button_container1, "キーワード抽出",
                                  '#4CAF50', '#45a049', self.extract_keywords, width=160)
        self.create_rounded_button(button_container1, "全てクリア",
                                  '#9e9e9e', '#757575', self.clear_all, width=140)
        # 一時停止ボタンへの参照を保存
        self.pause_button = self.create_rounded_button(button_container1, "一時停止",
                                  '#ff9800', '#f57c00', self.pause_processing, width=140)

        # 2行目のボタン（コピー・出力系）
        button_container2 = tk.Frame(right_panel, bg=self.colors['bg_main'])
        button_container2.pack(fill='x', pady=(0, 20))

        self.create_rounded_button(button_container2, "一括コピー",
                                  '#2196F3', '#1976D2', self.copy_results, width=120)
        self.create_rounded_button(button_container2, "ASINコピー",
                                  '#2196F3', '#1976D2', lambda: self.copy_column('asin'), width=120)
        self.create_rounded_button(button_container2, "ブランドコピー",
                                  '#2196F3', '#1976D2', lambda: self.copy_column('brand'), width=140)
        self.create_rounded_button(button_container2, "キーワードコピー",
                                  '#2196F3', '#1976D2', lambda: self.copy_column('keywords'), width=150)
        self.create_rounded_button(button_container2, "翻訳キーワードコピー",
                                  '#2196F3', '#1976D2', lambda: self.copy_column('translated_kw'), width=180)
        self.create_rounded_button(button_container2, "CSV出力",
                                  '#9c27b0', '#7b1fa2', self.export_csv, width=100)

        # 結果エリア
        result_container = tk.Frame(right_panel, bg=self.colors['bg_secondary'])
        result_container.pack(fill='both', expand=True)

        result_header = tk.Frame(result_container, bg=self.colors['bg_secondary'])
        result_header.pack(fill='x', padx=15, pady=15)

        label6 = tk.Label(result_header,
                text="抽出結果",
                font=self.get_scaled_font('heading', bold=True),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary']).pack(side='left')

        self.result_status = tk.Label(result_header,
                                     text="準備完了",
                                     font=self.get_scaled_font('small'),
                                     bg=self.colors['bg_secondary'],
                                     fg='#4CAF50')
        self.result_status.pack(side='right')
        self.ui_widgets.append({'widget': self.result_status, 'font_type': 'small'})

        # 結果テーブル
        table_frame = tk.Frame(result_container, bg=self.colors['bg_secondary'])
        table_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        # Treeviewウィジェット
        columns = ('ASIN', '商品タイトル', 'ブランド', '抽出キーワード', '翻訳キーワード')
        self.result_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                       style='Cute.Treeview', height=10, selectmode='none')

        # カラムの設定
        widths = [100, 300, 100, 300, 300]
        for col, width in zip(columns, widths):
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=width, minwidth=80)

        # セルハイライト用の変数
        self.highlighted_item = None
        self.highlighted_column = None
        self.original_values = None

        # ツリービューのスクロールバー
        tree_scrollbar_y = ttk.Scrollbar(table_frame, orient='vertical')
        tree_scrollbar_y.pack(side='right', fill='y')
        tree_scrollbar_x = ttk.Scrollbar(table_frame, orient='horizontal')
        tree_scrollbar_x.pack(side='bottom', fill='x')

        # Treeviewを配置
        self.result_tree.place(x=0, y=0, relwidth=1, relheight=1)

        self.result_tree.config(yscrollcommand=tree_scrollbar_y.set, xscrollcommand=tree_scrollbar_x.set)
        tree_scrollbar_y.config(command=self.result_tree.yview)
        tree_scrollbar_x.config(command=self.result_tree.xview)


        # キーボードショートカット
        self.result_tree.bind('<Control-c>', lambda e: self.copy_results())

        # セルクリックでコピー機能を追加

        def on_cell_click(event):
            """セルをクリックした際にその内容をコピー"""
            # 前回のハイライトを削除
            if self.highlighted_item and self.original_values:
                self.result_tree.item(self.highlighted_item, values=self.original_values)
                self.highlighted_item = None
                self.highlighted_column = None
                self.original_values = None

            # クリックした位置のアイテムと列を特定
            region = self.result_tree.identify("region", event.x, event.y)
            if region == "cell":
                item = self.result_tree.identify_row(event.y)
                column = self.result_tree.identify_column(event.x)

                if item and column:
                    # 列のインデックスを取得（#1, #2, #3, #4）
                    col_index = int(column.replace('#', '')) - 1
                    values = self.result_tree.item(item, 'values')

                    if 0 <= col_index < len(values):

                        # 新しいハイライトを設定
                        self.original_values = list(values)
                        self.highlighted_item = item
                        self.highlighted_column = col_index

                        # クリックされたセルの内容だけを青色表示に変更
                        highlighted_values = list(values)
                        highlighted_values[col_index] = f"🔵 {values[col_index]}"
                        self.result_tree.item(item, values=highlighted_values)

                        # クリップボードにコピー
                        self.root.clipboard_clear()
                        self.root.clipboard_append(values[col_index])

                        # フィードバック表示
                        column_names = ['ASIN', '商品タイトル', 'ブランド', '抽出キーワード', '翻訳キーワード']
                        self.result_status.config(
                            text=f"{column_names[col_index]}をコピーしました",
                            fg='#2196F3'  # 水色（一括コピーと同じ色）
                        )

                        # 2秒後にハイライトを削除とメッセージを戻す
                        def remove_highlight_and_message():
                            if self.highlighted_item and self.original_values:
                                self.result_tree.item(self.highlighted_item, values=self.original_values)
                                self.highlighted_item = None
                                self.highlighted_column = None
                                self.original_values = None
                            # メッセージも同時に戻す
                            self.result_status.config(
                                text=f"完了: {len(self.result_tree.get_children())}件",
                                fg=self.colors['text_primary']
                            )
                        self.root.after(2000, remove_highlight_and_message)

        # マウスクリックイベントをバインド
        self.result_tree.bind('<ButtonRelease-1>', on_cell_click)

        # 列ごとのスクロール
        def scroll_to_column(col_index):
            columns = ['asin', 'title', 'brand', 'keywords', 'translated_kw']
            if 0 <= col_index < len(columns):
                bbox = self.result_tree.bbox(self.result_tree.get_children()[0] if self.result_tree.get_children() else '', columns[col_index])
                if bbox:
                    self.result_tree.xview_moveto(0)  # 最初に左端にスクロール
                    self.result_tree.update()
                    # 対象の列が見えるようにスクロール
                    if col_index > 0:
                        self.result_tree.xview_scroll(col_index * 2, 'units')

        # Ctrl+数字で列ジャンプ
        for i in range(5):
            self.root.bind(f'<Control-Key-{i+1}>', lambda e, idx=i: scroll_to_column(idx))

        # 左右キーで列移動
        def scroll_left(event):
            # 現在の位置から左にスクロール
            self.result_tree.xview_scroll(-1, 'units')

        def scroll_right(event):
            # 現在の位置から右にスクロール
            self.result_tree.xview_scroll(1, 'units')
            col_index = 0
            columns = ['asin', 'title', 'brand', 'keywords', 'translated_kw']
            if 0 <= col_index < len(columns):
                bbox = self.result_tree.bbox(self.result_tree.get_children()[0] if self.result_tree.get_children() else '', columns[col_index])
                if bbox:
                    self.result_tree.xview_moveto(bbox[0] / self.result_tree.winfo_width())

        self.result_tree.bind('<Control-Left>', scroll_left)
        self.result_tree.bind('<Control-Right>', scroll_right)

        # 交互の行色設定
        self.result_tree.tag_configure('oddrow', background=self.colors['table_bg'])
        self.result_tree.tag_configure('evenrow', background=self.colors['table_alt'])
        # セルハイライト用の設定
        self.result_tree.tag_configure('cell_highlight', background='#BBDEFB', foreground='#1976D2')  # より目立つ青色

    def extract_keywords(self):
        """キーワード抽出処理"""
        # 結果をクリア
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # フルデータもクリア
        self.full_data = []

        # ステータス更新
        self.result_status.config(text="処理中...", fg=self.colors['text_primary'])

        # プログレスバーを初期化
        self.progress_bar['value'] = 0
        self.progress_text.config(text="0 / 0 (0%)")
        self.root.update()

        # 入力取得
        input_text = self.input_text.get('1.0', 'end-1c')
        inputs = [line.strip() for line in input_text.split('\n') if line.strip()]

        if not inputs:
            self.result_status.config(text="入力なし", fg=self.colors['text_primary'])
            messagebox.showwarning("警告", "ASINを入力してください")
            return

        # 翻訳モードの解析
        translate_map = {
            'なし': 'none',
            'あり': 'auto'
        }
        translate_mode = translate_map[self.translate_mode.get()]

        try:
            # 処理開始
            self.processing = True
            self.is_paused = False

            # ボタンテキストを「一時停止」にリセット
            if hasattr(self, 'pause_button'):
                self.pause_button['canvas'].itemconfig(
                    self.pause_button['text_id'],
                    text=f"⏸ 一時停止"
                )

            # 結果表示準備
            brand_count = 0
            total_count = len(inputs)
            results = []
            processed_count = 0  # 実際に処理された件数

            # プログレスバーの最大値を設定
            self.progress_bar['maximum'] = total_count
            self.progress_text.config(text=f"0 / {total_count} (0%)")
            self.root.update()

            # ASIN専用処理（商品タイトルモードを削除）
            for i, asin in enumerate(inputs, 1):
                if not self.processing:
                    break

                # 一時停止チェック
                while self.is_paused and self.processing:
                    self.root.update()
                    time.sleep(0.1)

                if not self.processing:
                    break

                self.result_status.config(
                    text=f"処理中... {i}/{total_count} (ASIN: {asin})",
                    fg=self.colors['text_primary']
                )
                # 統計情報も更新
                self.stats_label.config(
                    text=f"件数: {processed_count}/{total_count}\nブランド数: {brand_count}\n処理状況: {i}/{total_count} 処理中..."
                )
                # プログレスバーを更新
                self.progress_bar['value'] = i
                progress_percent = int((i / total_count) * 100)
                self.progress_text.config(text=f"{i} / {total_count} ({progress_percent}%)")
                self.root.update()

                # ASINから商品タイトルとブランド名を取得
                region = self.amazon_region.get()
                title, brand_from_asin = self.extractor.fetch_product_info_from_asin(asin, region)
                if not title:
                    print(f"タイトル取得失敗: {asin}")
                    continue

                # キーワード抽出処理
                try:
                    result = self.extractor.process_single_title(
                        title,
                        self.extract_mode.get(),
                        translate_mode,
                        self.include_brand.get()
                    )
                except Exception as e:
                    print(f"process_single_title エラー: {asin} -> {e}")
                    continue

                # ASINから取得したブランド名がある場合はそれを優先
                if brand_from_asin:
                    result['brand'] = brand_from_asin

                result['asin'] = asin  # ASINも結果に保存
                results.append(result)
                processed_count += 1

                # ブランド数カウント
                if result['brand']:
                    brand_count += 1

                # リアルタイム表示
                self.display_result(result)

            # 統計更新（最終）
            self.stats_label.config(
                text=f"件数: {len(results)}\nブランド数: {brand_count}\n処理状況: 完了"
            )

            # プログレスバーを完了状態に
            self.progress_bar['value'] = total_count
            self.progress_text.config(text=f"{total_count} / {total_count} (100%)")

            # ステータス更新
            self.result_status.config(text=f"✓ {len(results)}件処理完了", fg=self.colors['text_primary'])

        except Exception as e:
            self.result_status.config(text="エラー発生", fg=self.colors['text_primary'])
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{str(e)}")
        finally:
            # 処理終了
            self.processing = False
            self.is_paused = False

    def clear_all(self):
        """全てクリア"""
        self.input_text.delete('1.0', 'end')
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.full_data = []  # フルデータもクリア
        self.result_status.config(text="クリア済み", fg=self.colors['text_secondary'])
        self.stats_label.config(text="件数: 0\nブランド数: 0\n処理状況: 待機中")
        # プログレスバーもリセット
        self.progress_bar['value'] = 0
        self.progress_text.config(text="0 / 0 (0%)")

    def pause_processing(self):
        """処理を一時停止/再開"""
        if self.processing:
            if self.is_paused:
                # 再開
                self.is_paused = False
                self.result_status.config(text="処理を再開しました", fg=self.colors['text_primary'])
                # ボタンテキストを「一時停止」に変更
                if hasattr(self, 'pause_button') and isinstance(self.pause_button, dict):
                    self.pause_button['canvas'].itemconfig(self.pause_button['text_id'], text="一時停止")
            else:
                # 一時停止
                self.is_paused = True
                self.result_status.config(text="一時停止中...", fg=self.colors['warning'])
                # ボタンテキストを「再開」に変更
                if hasattr(self, 'pause_button') and isinstance(self.pause_button, dict):
                    self.pause_button['canvas'].itemconfig(self.pause_button['text_id'], text="再開")
        else:
            self.result_status.config(text="処理中ではありません", fg=self.colors['text_secondary'])

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
            self.result_status.config(text="✓ 一括コピーしました", fg=self.colors['text_primary'])
        else:
            self.result_status.config(text="コピーする結果がありません", fg=self.colors['text_primary'])

    def copy_column(self, column_type):
        """特定のカラムをコピー"""
        column_map = {
            'asin': 0,
            'title': 1,
            'brand': 2,
            'keywords': 3,
            'translated_kw': 4
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
                'asin': 'ASIN',
                'title': '商品タイトル',
                'brand': 'ブランド',
                'keywords': 'キーワード',
                'translated_kw': '翻訳キーワード'
            }

            self.result_status.config(
                text=f"✓ {column_names[column_type]}をコピーしました",
                fg=self.colors['text_primary']
            )
        else:
            self.result_status.config(text="コピーするデータがありません", fg=self.colors['text_primary'])

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
                    f.write("ASIN,商品タイトル,ブランド,キーワード,翻訳キーワード\n")
                    f.write('\n'.join(results))
                self.result_status.config(text=f"✓ {filename}に出力しました", fg=self.colors['text_primary'])
        else:
            self.result_status.config(text="出力する結果がありません", fg=self.colors['text_primary'])

    def open_prompt_editor(self):
        """プロンプト編集ウィンドウを開く"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title("AIプロンプト編集")
        editor_window.geometry("900x700")
        editor_window.configure(bg=self.colors['bg_main'])

        # ウィンドウを中央に配置
        editor_window.update_idletasks()
        x = (editor_window.winfo_screenwidth() // 2) - (450)
        y = (editor_window.winfo_screenheight() // 2) - (350)
        editor_window.geometry(f"+{x}+{y}")

        # タイトル
        title_frame = tk.Frame(editor_window, bg=self.colors['bg_secondary'], height=60)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)

        tk.Label(title_frame,
                text="Gemini AIプロンプトテンプレート編集",
                font=self.get_scaled_font('heading', bold=True),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary']).pack(expand=True)

        # メインコンテンツ
        main_frame = tk.Frame(editor_window, bg=self.colors['bg_main'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # テンプレート選択
        template_frame = tk.Frame(main_frame, bg=self.colors['bg_main'])
        template_frame.pack(fill='x', pady=(0, 15))

        tk.Label(template_frame,
                text="テンプレート:",
                font=self.get_scaled_font('label'),
                bg=self.colors['bg_main'],
                fg=self.colors['text_primary']).pack(side='left', padx=(0, 10))

        template_var = tk.StringVar(value=self.extractor.prompt_data.get('current_template', 'default'))
        template_combo = ttk.Combobox(template_frame,
                                      textvariable=template_var,
                                      values=list(self.extractor.prompt_data['templates'].keys()),
                                      state='readonly',
                                      width=30)
        template_combo.pack(side='left')

        # ベースプロンプト編集
        base_label = tk.Label(main_frame,
                             text="ベースプロンプト（{title}, {instruction}, {brand_instruction}が置換されます）:",
                             font=self.get_scaled_font('label'),
                             bg=self.colors['bg_main'],
                             fg=self.colors['text_primary'])
        base_label.pack(anchor='w', pady=(10, 5))

        base_text = tk.Text(main_frame,
                           height=8,
                           font=self.get_scaled_font('body'),
                           bg=self.colors['input_bg'],
                           fg=self.colors['text_primary'],
                           wrap='word')
        base_text.pack(fill='x', pady=(0, 15))

        # 各モードの指示文
        instructions_frame = tk.Frame(main_frame, bg=self.colors['bg_main'])
        instructions_frame.pack(fill='both', expand=True)

        modes = [
            ('厳しめモード', 'strict'),
            ('標準モード', 'moderate'),
            ('緩めモード', 'loose')
        ]

        instruction_texts = {}
        for mode_name, mode_key in modes:
            frame = tk.Frame(instructions_frame, bg=self.colors['bg_secondary'])
            frame.pack(fill='x', pady=5)

            tk.Label(frame,
                    text=f"{mode_name}の指示:",
                    font=self.get_scaled_font('label'),
                    bg=self.colors['bg_secondary'],
                    fg=self.colors['text_primary']).pack(anchor='w', padx=10, pady=5)

            text_widget = tk.Text(frame,
                                 height=2,
                                 font=self.get_scaled_font('small'),
                                 bg=self.colors['input_bg'],
                                 fg=self.colors['text_primary'],
                                 wrap='word')
            text_widget.pack(fill='x', padx=10, pady=(0, 10))
            instruction_texts[mode_key] = text_widget

        # 現在のテンプレートの内容をロード
        def load_template():
            template_name = template_var.get()
            if template_name in self.extractor.prompt_data['templates']:
                template = self.extractor.prompt_data['templates'][template_name]
                base_text.delete('1.0', tk.END)
                base_text.insert('1.0', template['base_prompt'])

                for mode_key, text_widget in instruction_texts.items():
                    text_widget.delete('1.0', tk.END)
                    text_widget.insert('1.0', template['instructions'].get(mode_key, ''))

        # テンプレート選択時のイベント
        template_combo.bind('<<ComboboxSelected>>', lambda e: load_template())

        # 初期ロード
        load_template()

        # ボタンエリア
        button_frame = tk.Frame(editor_window, bg=self.colors['bg_main'])
        button_frame.pack(fill='x', pady=20)

        def save_template():
            """テンプレートを保存"""
            template_name = template_var.get()

            # テンプレートデータを更新
            self.extractor.prompt_data['templates'][template_name] = {
                'name': template_name,
                'base_prompt': base_text.get('1.0', 'end-1c'),
                'instructions': {
                    'strict': instruction_texts['strict'].get('1.0', 'end-1c'),
                    'moderate': instruction_texts['moderate'].get('1.0', 'end-1c'),
                    'loose': instruction_texts['loose'].get('1.0', 'end-1c')
                }
            }

            # 現在のテンプレートとして設定
            self.extractor.prompt_data['current_template'] = template_name

            # ファイルに保存
            self.extractor.save_prompt_templates()

            messagebox.showinfo("保存完了", "プロンプトテンプレートを保存しました")
            editor_window.destroy()

        save_btn = tk.Button(button_frame,
                           text="保存",
                           font=self.get_scaled_font('button'),
                           bg=self.colors['success'],
                           fg='white',
                           relief='flat',
                           padx=20,
                           pady=10,
                           command=save_template)
        save_btn.pack(side='left', padx=10)

        cancel_btn = tk.Button(button_frame,
                             text="キャンセル",
                             font=self.get_scaled_font('button'),
                             bg=self.colors['text_secondary'],
                             fg='white',
                             relief='flat',
                             padx=20,
                             pady=10,
                             command=editor_window.destroy)
        cancel_btn.pack(side='left', padx=10)


def main():
    root = tk.Tk()
    app = CuteKeywordExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()