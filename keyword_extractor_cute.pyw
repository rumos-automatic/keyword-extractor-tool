import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import re
from typing import List, Tuple, Dict
import json
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ============================================================================
# ヘルパークラス・関数
# ============================================================================

class RateLimiter:
    """スクレイピングのレート制限を管理するクラス"""

    def __init__(self, min_delay=4.0, max_delay=9.0, penalty=30.0):
        """
        Args:
            min_delay: 最小待機時間（秒）
            max_delay: 最大待機時間（秒）
            penalty: ペナルティ時の追加待機時間（秒）
        """
        self.min = min_delay
        self.max = max_delay
        self.penalty = penalty
        self.last_request_time = 0
        self.multiplier = 1.0  # 待機時間の倍率
        self.consecutive_errors = 0

    def wait(self):
        """適切な待機時間を計算して待機"""
        target_delay = random.uniform(self.min, self.max) * self.multiplier
        elapsed = time.perf_counter() - self.last_request_time

        if elapsed < target_delay:
            wait_time = target_delay - elapsed
            print(f"[WAIT] レート制限: {wait_time:.1f}秒待機中...")
            time.sleep(wait_time)

        self.last_request_time = time.perf_counter()

    def penalize(self, hard=False):
        """エラー検出時に待機時間を延長"""
        if hard:
            # CAPTCHA検出時などの重度のペナルティ
            self.multiplier = min(4.0, self.multiplier * 2.0)
            self.consecutive_errors += 1
            print(f"[WARNING] 重度エラー検出: 待機時間を{self.multiplier:.1f}倍に延長")
            # 即座にペナルティ待機
            time.sleep(self.penalty)
        else:
            # 429エラーなどの軽度のペナルティ
            self.multiplier = min(4.0, self.multiplier * 1.5)
            self.consecutive_errors += 1
            print(f"[WARNING] エラー検出: 待機時間を{self.multiplier:.1f}倍に延長")

    def recover(self):
        """成功時に待機時間を回復"""
        if self.multiplier > 1.0:
            self.multiplier = max(1.0, self.multiplier * 0.5)
            self.consecutive_errors = 0
            print(f"[OK] 成功: 待機時間を{self.multiplier:.1f}倍に回復")


def get_random_user_agent() -> str:
    """ランダムなUser-Agentを返す"""
    user_agents = [
        # Chrome on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Chrome on Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Firefox on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        # Firefox on Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
        # Safari on Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        # Edge on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    ]
    return random.choice(user_agents)


def create_session_with_retry(max_retries=5, backoff_factor=1.2) -> requests.Session:
    """リトライ設定済みのrequests.Sessionを作成"""
    session = requests.Session()

    # リトライ戦略の設定
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False  # ステータスコードでの例外を抑制
    )

    # HTTPアダプターにリトライ戦略を適用
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# ============================================================================
# メインクラス
# ============================================================================

class KeywordExtractor:
    def __init__(self):
        self.translator = None  # Google Translate APIを一時的に無効化
        self.common_brands = self.load_brands()
        self.gemini_model = None
        self.use_ai = False

        # config.jsonからスクレイピング設定を読み込み
        self.scraping_config = self.load_scraping_config()

        # スクレイピング用のセッションとレート制限
        self.session = create_session_with_retry(
            max_retries=self.scraping_config['max_retries'],
            backoff_factor=self.scraping_config['backoff_factor']
        )
        self.rate_limiter = RateLimiter(
            min_delay=self.scraping_config['min_delay'],
            max_delay=self.scraping_config['max_delay'],
            penalty=self.scraping_config['penalty_delay']
        )

        # メトリクス追跡
        self.scraping_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'captcha_count': 0,
            'http_errors': 0
        }

        self.setup_gemini()
        self.load_prompt_templates()

    def load_scraping_config(self) -> Dict:
        """config.jsonからスクレイピング設定を読み込み"""
        config_path = "config.json"
        default_config = {
            'min_delay': 4.0,
            'max_delay': 9.0,
            'penalty_delay': 30.0,
            'batch_size': 25,
            'batch_cooldown': 60,
            'max_retries': 5,
            'backoff_factor': 1.2
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    scraping_config = config.get('scraping', default_config)
                    print(f"[OK] スクレイピング設定を読み込みました: batch_size={scraping_config.get('batch_size')}, delay={scraping_config.get('min_delay')}-{scraping_config.get('max_delay')}秒")
                    return scraping_config
            else:
                print(f"[INFO] config.jsonが見つかりません。デフォルト設定を使用します。")
                return default_config
        except Exception as e:
            print(f"[WARNING] スクレイピング設定読み込みエラー: {e}。デフォルト設定を使用します。")
            return default_config

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
        """ASINからAmazonの商品タイトルとブランド名を取得（改善版）"""

        if not asin:
            print(f"ASINが空です")
            self.scraping_stats['failed'] += 1
            return "", ""

        asin = asin.strip().upper()  # ASINを大文字に正規化
        if len(asin) != 10:
            print(f"ASIN長さエラー: {asin} (長さ: {len(asin)})")
            self.scraping_stats['failed'] += 1
            return "", ""

        # メトリクス更新
        self.scraping_stats['total'] += 1

        try:
            # レート制限による待機
            self.rate_limiter.wait()

            # Amazonの商品ページURL（地域に応じて変更）
            if region == "us":
                url = f"https://www.amazon.com/dp/{asin}"
                accept_language = 'en-US,en;q=0.9'
            else:  # jp
                url = f"https://www.amazon.co.jp/dp/{asin}"
                accept_language = 'ja-JP,ja;q=0.9,en;q=0.8'

            # ランダムなUser-Agentを使用
            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept-Language': accept_language,
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }

            # セッションを使用してリクエスト（自動リトライ機能付き）
            response = self.session.get(url, headers=headers, timeout=15)

            # HTTPエラーチェック（429などの場合）
            if response.status_code == 429:
                print(f"[WARNING] レート制限エラー (429) 検出: {asin}")
                self.rate_limiter.penalize(hard=False)
                self.scraping_stats['http_errors'] += 1
                self.scraping_stats['failed'] += 1
                return "", ""

            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # CAPTCHAチェック
            if 'Robot Check' in response.text or 'captcha' in response.text.lower():
                print(f"[WARNING] CAPTCHA検出 ({asin}): Amazonがボット対策でブロックしています")
                print(f"[INFO] 対策: しばらく待機してから再試行します...")
                self.rate_limiter.penalize(hard=True)  # 重度のペナルティ
                self.scraping_stats['captcha_count'] += 1
                self.scraping_stats['failed'] += 1
                return "", ""

            # 商品タイトルを取得（複数のセレクターを試す）
            title = ""
            title_selectors = [
                '#productTitle',
                'span#productTitle',
                'h1#title span',
                'h1.a-size-large.a-spacing-none',
                '#title',
            ]

            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    title = title_element.get_text().strip()
                    if title:
                        # タイトルの文字を安全に表示（エラー回避）
                        try:
                            print(f"[OK] タイトル取得成功 ({selector}): {title[:50]}...")
                        except UnicodeEncodeError:
                            print(f"[OK] タイトル取得成功 ({selector})")
                        break

            if not title:
                print(f"[WARNING] タイトル取得失敗: {asin} (すべてのセレクターで失敗)")

            # ブランド名を取得（複数のセレクターを順に試す）
            brand = ""
            brand_selectors = [
                # productOverview系（アメリカAmazonでよく使われる）
                '#productOverview_feature_div tr.po-brand td.a-span9 span',
                'tr.a-spacing-small.po-brand td.a-span9 span',
                # 製品仕様テーブル系
                'tr.po-brand td.a-span9 span',  # より汎用的（role属性なし）
                'tr.po-brand td.a-span9[role="presentation"] span.a-size-base.po-break-word',  # 日本Amazon（厳格版）
                # bylineInfo系
                'a#bylineInfo',  # 日本・アメリカAmazon共通
                '#brand',  # アメリカAmazonの別パターン
                '.a-row.product-by-line a',  # アメリカAmazonの代替
                'span.author.notFaded a',  # 書籍など
            ]

            for selector in brand_selectors:
                brand_element = soup.select_one(selector)
                if brand_element:
                    brand_text = brand_element.get_text().strip()
                    # 不要なテキストを除去
                    brand = brand_text.replace('にアクセス', '').replace('Visit the', '').replace('ブランド:', '').replace('Brand:', '').replace('Store', '').replace('のストアを表示', '').replace("'s Store", '').strip()
                    if brand:  # 空でない場合のみ採用
                        try:
                            print(f"[OK] ブランド取得成功 ({selector}): {brand}")
                        except UnicodeEncodeError:
                            print(f"[OK] ブランド取得成功 ({selector})")
                        break

            if not brand:
                print(f"[INFO] ブランド名なし: {asin}")

            # 成功時はレート制限を回復
            if title or brand:
                self.rate_limiter.recover()
                self.scraping_stats['success'] += 1
            else:
                self.scraping_stats['failed'] += 1

            return title, brand

        except requests.exceptions.HTTPError as e:
            print(f"HTTP エラー ({asin}): {e.response.status_code} - {e}")
            self.scraping_stats['http_errors'] += 1
            self.scraping_stats['failed'] += 1
            self.rate_limiter.penalize(hard=False)
            return "", ""
        except requests.exceptions.Timeout as e:
            print(f"タイムアウト エラー ({asin}): {e}")
            self.scraping_stats['failed'] += 1
            return "", ""
        except requests.exceptions.RequestException as e:
            print(f"リクエスト エラー ({asin}): {e}")
            self.scraping_stats['failed'] += 1
            return "", ""
        except Exception as e:
            print(f"予期しないエラー ({asin}): {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            self.scraping_stats['failed'] += 1
            return "", ""

    def fetch_product_title_from_asin(self, asin: str) -> str:
        """後方互換性のためのメソッド"""
        title, _ = self.fetch_product_info_from_asin(asin)
        return title

    # ============================================================================
    # 進捗管理関数
    # ============================================================================

    def save_progress(self, processed_asins: List[str], filepath: str = ".progress.json"):
        """処理済みASINをJSONファイルに保存"""
        try:
            progress_data = {
                'processed_asins': processed_asins,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'stats': self.scraping_stats.copy()
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            print(f"[OK] 進捗保存: {len(processed_asins)}件 ({filepath})")
        except Exception as e:
            print(f"[WARNING] 進捗保存エラー: {e}")

    def load_progress(self, filepath: str = ".progress.json") -> Dict:
        """保存された進捗をJSONファイルから読み込み"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                print(f"[OK] 進捗読み込み: {len(progress_data.get('processed_asins', []))}件 ({filepath})")
                return progress_data
            else:
                print(f"[INFO] 進捗ファイルが存在しません: {filepath}")
                return {'processed_asins': [], 'stats': None}
        except Exception as e:
            print(f"[WARNING] 進捗読み込みエラー: {e}")
            return {'processed_asins': [], 'stats': None}

    def get_unprocessed_asins(self, all_asins: List[str], processed_asins: List[str]) -> List[str]:
        """未処理のASINリストを返す"""
        unprocessed = [asin for asin in all_asins if asin not in processed_asins]
        print(f"[INFO] 未処理ASIN: {len(unprocessed)}件 / 全体: {len(all_asins)}件")
        return unprocessed

    def clear_progress(self, filepath: str = ".progress.json"):
        """進捗ファイルを削除"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[OK] 進捗ファイルを削除しました: {filepath}")
        except Exception as e:
            print(f"[WARNING] 進捗ファイル削除エラー: {e}")

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
        current = self.prompt_data.get('current_template', 'デフォルト')
        # デフォルトのフォールバック（古いキーとの互換性も考慮）
        if current not in self.prompt_data['templates']:
            current = 'デフォルト' if 'デフォルト' in self.prompt_data['templates'] else list(self.prompt_data['templates'].keys())[0]
        return self.prompt_data['templates'][current]

    def validate_ai_keywords(self, keywords: List[str], title: str) -> List[str]:
        """AIが生成したキーワード（フレーズ）がタイトルに実際に存在するかを検証"""
        # タイトルを小文字化（検証用）
        title_lower = title.lower()

        # タイトルから実際の単語を抽出
        title_words = self._extract_words_from_title(title)
        title_words_lower = [word.lower() for word in title_words]

        validated_keywords = []

        for keyword in keywords:
            keyword_lower = keyword.lower().strip()

            # 空のキーワードをスキップ
            if not keyword_lower:
                continue

            # 明らかに説明文や文章を除外
            if any(phrase in keyword for phrase in ['です', 'ます', 'について', 'キーワード', '制造', '製造', 'された', '→', '例:', '例）']):
                print(f"説明文として除外: {keyword}")
                continue

            # 長すぎるキーワード（100文字以上）を除外
            if len(keyword) > 100:
                print(f"長すぎるキーワードを除外: {keyword}")
                continue

            # フレーズの検証
            is_valid = False

            # 1. フレーズ全体がタイトルに含まれているかチェック
            if keyword_lower in title_lower:
                is_valid = True
            else:
                # 2. フレーズを単語に分割して、すべての単語がタイトルに存在するかチェック
                keyword_words = keyword.split()
                if keyword_words:
                    # すべての単語がタイトルに存在するか確認
                    all_words_exist = True
                    for kw_word in keyword_words:
                        kw_word_lower = kw_word.lower()
                        word_exists = False

                        # タイトルの単語と照合
                        for title_word in title_words_lower:
                            if kw_word_lower == title_word or kw_word_lower in title_word or title_word in kw_word_lower:
                                word_exists = True
                                break

                        if not word_exists:
                            all_words_exist = False
                            break

                    if all_words_exist:
                        is_valid = True

            if is_valid:
                validated_keywords.append(keyword)
            else:
                print(f"タイトルに存在しないキーワードを除外: {keyword}")

        return validated_keywords

    def cleanse_keywords(self, keywords: List[str], mode: str) -> List[str]:
        """
        生成後のキーワードクレンジング
        1) 各フレーズをトークン化 → 連続/非連続の重複単語を削除
        2) 各フレーズの語数をモードに応じた上限に丸め（超過分は右側から削除）
        3) 全フレーズ結合後の総語数が上限を超えたら、末尾フレーズから短縮/削除
        """
        # モード別の制約
        mode_limits = {
            'loose': {'max_words_per_phrase': 3, 'max_total_words': 8},
            'moderate': {'max_words_per_phrase': 5, 'max_total_words': 12},
            'strict': {'max_words_per_phrase': 6, 'max_total_words': 14}
        }

        limits = mode_limits.get(mode, mode_limits['moderate'])
        max_words_per_phrase = limits['max_words_per_phrase']
        max_total_words = limits['max_total_words']

        cleansed_phrases = []

        # 1) 各フレーズの処理
        for phrase in keywords:
            # フレーズをトークン化（スペース区切り）
            words = phrase.split()

            # 重複単語を削除（順序を保ちながら）
            seen = set()
            unique_words = []
            for word in words:
                word_lower = word.lower()
                if word_lower not in seen:
                    seen.add(word_lower)
                    unique_words.append(word)

            # 2) 語数制限（右側から削除）
            if len(unique_words) > max_words_per_phrase:
                unique_words = unique_words[:max_words_per_phrase]

            # 再構成
            cleansed_phrase = ' '.join(unique_words)
            if cleansed_phrase:
                cleansed_phrases.append(cleansed_phrase)

        # 3) 総語数チェック
        total_words = sum(len(phrase.split()) for phrase in cleansed_phrases)

        # 総語数が上限を超えている場合、末尾のフレーズから削除/短縮
        while total_words > max_total_words and cleansed_phrases:
            # 最後のフレーズを削除
            removed_phrase = cleansed_phrases.pop()
            total_words -= len(removed_phrase.split())
            print(f"総語数制限のためフレーズを削除: {removed_phrase}")

        return cleansed_phrases

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
            if include_brand:
                brand_instruction = """【ブランド名の扱い】
できるだけブランド偏重を避ける。カテゴリ/商品ジャンルを最優先し、ブランドは検索で明確な差が出る場合のみ含める。

・アパレル・グッズ・コラボ系で、ブランド/チーム/コラボ名を入れると検索精度が上がる場合（例: "New Era", "レッドブルレーシング"）は標準/厳しめでのみ採用可（緩めでは原則不採用）
・フットウェアや学用品など汎用品では、ブランドよりジャンル（例: "スクールシューズ"）やコレクション名（例: "LOWMEL"）を優先
・電子機器は、商品ジャンル＋主要仕様/シリーズ名を優先し、メーカー名は原則不要。ただしシリーズ名がブランドと不可分（例: "KRAKEN"がNZXTの固有シリーズ）の場合、シリーズ名は可・メーカー名は不要"""
            else:
                brand_instruction = """【ブランド名の扱い】
ブランド名・メーカー名は一切含めないでください。カテゴリ/商品ジャンル/コレクション名/主要特徴のみを抽出してください。"""

            # プロンプトをフォーマット
            prompt = template['base_prompt'].format(
                title=title,
                instruction=instruction,
                brand_instruction=brand_instruction
            )

            # デバッグ: プロンプトの最初の200文字を出力
            print(f"\n使用中のプロンプト（最初の200文字）:\n{prompt[:200]}...\n")

            # Gemini APIを呼び出し
            response = self.gemini_model.generate_content(prompt)

            # レスポンスをパース
            keywords_text = response.text.strip()

            # AIの応答が空の場合
            if not keywords_text:
                print(f"AIの応答が空でした。タイトル: {title[:50]}...")
                # フォールバック処理
                if mode == 'strict':
                    return self.extract_keywords_strict(title, include_brand, brand)
                elif mode == 'moderate':
                    return self.extract_keywords_moderate(title, include_brand, brand)
                else:
                    return self.extract_keywords_loose(title, include_brand, brand)

            print(f"AIレスポンス: {keywords_text}")
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

            # 検証後もキーワードが空の場合はフォールバック
            if not validated_keywords:
                print(f"検証後にキーワードが0個になりました。フォールバックします。")
                if mode == 'strict':
                    return self.extract_keywords_strict(title, include_brand, brand)
                elif mode == 'moderate':
                    return self.extract_keywords_moderate(title, include_brand, brand)
                else:
                    return self.extract_keywords_loose(title, include_brand, brand)

            # キーワードのクレンジング（重複削除・語数制限）
            cleansed_keywords = self.cleanse_keywords(validated_keywords, mode)
            if len(cleansed_keywords) < len(validated_keywords):
                print(f"キーワードクレンジング: {len(validated_keywords)}個中{len(cleansed_keywords)}個に整理しました")

            # クレンジング後もキーワードが空の場合はフォールバック
            if not cleansed_keywords:
                print(f"クレンジング後にキーワードが0個になりました。フォールバックします。")
                if mode == 'strict':
                    return self.extract_keywords_strict(title, include_brand, brand)
                elif mode == 'moderate':
                    return self.extract_keywords_moderate(title, include_brand, brand)
                else:
                    return self.extract_keywords_loose(title, include_brand, brand)

            return cleansed_keywords

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
                     include_brand: bool, region: str = "jp", use_ai: bool = None,
                     batch_size: int = 25, batch_cooldown: int = 60,
                     enable_progress_save: bool = True,
                     progress_callback=None,
                     should_stop_callback=None) -> List[Dict]:
        """複数のASINを処理してタイトルとブランド名を取得後、キーワード抽出（改善版）"""
        results = []
        processed_asins = []

        # 進捗再開モードの確認
        if enable_progress_save:
            progress_data = self.load_progress()
            already_processed = progress_data.get('processed_asins', [])
            if already_processed:
                print(f"[RESUME] 進捗再開モード: {len(already_processed)}件スキップ")
                # すでに処理済みのASINはスキップ
                asins_to_process = self.get_unprocessed_asins(asins, already_processed)
            else:
                asins_to_process = asins
        else:
            asins_to_process = asins

        total_asins = len(asins_to_process)
        if total_asins == 0:
            print("[OK] すべてのASINが処理済みです")
            return results

        print(f"[START] 処理開始: {total_asins}件のASIN（バッチサイズ: {batch_size}）")

        # バッチ処理
        for batch_idx, i in enumerate(range(0, total_asins, batch_size), 1):
            batch_asins = asins_to_process[i:i+batch_size]
            total_batches = (total_asins + batch_size - 1) // batch_size

            print(f"\n[BATCH] バッチ {batch_idx}/{total_batches} 処理中... ({len(batch_asins)}件)")

            for idx, asin in enumerate(batch_asins, 1):
                # 停止チェック
                if should_stop_callback and should_stop_callback():
                    print("\n[STOP] ユーザーによる処理中断")
                    return results

                if not asin.strip():
                    continue

                asin = asin.strip()
                current_index = i + idx
                print(f"\n[{current_index}/{total_asins}] 処理中: {asin}")

                # 進捗コールバック（処理開始）
                if progress_callback:
                    progress_callback('processing', current_index, total_asins, asin, None)

                # ASINから商品タイトルとブランド名を取得
                title, brand_from_asin = self.fetch_product_info_from_asin(asin, region)
                if not title:
                    print(f"[WARNING] タイトル取得失敗: {asin}")
                    # 失敗してもprocessed_asinsに追加（無限ループ防止）
                    processed_asins.append(asin)

                    # 進捗コールバック（失敗）
                    if progress_callback:
                        failed_result = {
                            'asin': asin,
                            'original_title': f"取得失敗: {asin}",
                            'brand': '',
                            'keywords': [],
                            'translated_keywords': []
                        }
                        progress_callback('failed', current_index, total_asins, asin, failed_result)
                    continue

                # 通常のタイトル処理と同じ処理を実行
                result = self.process_single_title(title, mode, translate_mode, include_brand, use_ai)

                # ASINから取得したブランド名がある場合はそれを優先
                if brand_from_asin:
                    result['brand'] = brand_from_asin

                result['asin'] = asin  # ASINも結果に保存
                results.append(result)
                processed_asins.append(asin)

                # 進捗保存（各ASIN処理後）
                if enable_progress_save:
                    all_processed = already_processed + processed_asins if enable_progress_save else processed_asins
                    self.save_progress(all_processed)

                # メトリクス表示
                success_rate = (self.scraping_stats['success'] / self.scraping_stats['total'] * 100) if self.scraping_stats['total'] > 0 else 0
                print(f"[PROGRESS] 進捗: {len(processed_asins)}/{total_asins} | 成功率: {success_rate:.1f}% | CAPTCHA: {self.scraping_stats['captcha_count']}回")

                # 進捗コールバック（完了）
                if progress_callback:
                    progress_callback('completed', current_index, total_asins, asin, result)

            # バッチ間のクールダウン（最後のバッチ以外）
            if batch_idx < total_batches and batch_cooldown > 0:
                print(f"\n[COOLDOWN] バッチ間クールダウン: {batch_cooldown}秒待機中...")
                time.sleep(batch_cooldown)

        print(f"\n[COMPLETE] 処理完了: {len(results)}件成功 / {total_asins}件")
        print(f"[STATS] 最終メトリクス: 成功={self.scraping_stats['success']}, 失敗={self.scraping_stats['failed']}, CAPTCHA={self.scraping_stats['captcha_count']}")

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

    def on_process_mode_change(self):
        """処理モード切り替え時の処理"""
        mode = self.process_mode.get()

        if mode == 'brand':
            # ブランド名取得モード: キーワード抽出関連の設定を無効化
            self._disable_frame(self.trans_frame)
            self._disable_frame(self.extract_frame)
            self._disable_frame(self.brand_frame)
            self._disable_frame(self.ai_frame)
        else:
            # キーワード抽出モード: すべての設定を有効化
            self._enable_frame(self.trans_frame)
            self._enable_frame(self.extract_frame)
            self._enable_frame(self.brand_frame)
            self._enable_frame(self.ai_frame)

    def _disable_frame(self, frame):
        """フレーム内のすべてのウィジェットを無効化"""
        for child in frame.winfo_children():
            if isinstance(child, (tk.Radiobutton, tk.Checkbutton, ttk.Combobox)):
                child.configure(state='disabled')
            elif hasattr(child, 'winfo_children'):
                self._disable_frame(child)

    def _enable_frame(self, frame):
        """フレーム内のすべてのウィジェットを有効化"""
        for child in frame.winfo_children():
            if isinstance(child, (tk.Radiobutton, tk.Checkbutton)):
                child.configure(state='normal')
            elif isinstance(child, ttk.Combobox):
                child.configure(state='readonly')
            elif hasattr(child, 'winfo_children'):
                self._enable_frame(child)

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

        # 処理モード選択
        process_mode_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        process_mode_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(process_mode_frame,
                text="処理モード",
                font=self.get_scaled_font('label'),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(anchor='w')

        self.process_mode = tk.StringVar(value='keyword')

        # キーワード抽出モード
        keyword_rb = tk.Radiobutton(process_mode_frame,
                                   text="キーワード抽出",
                                   variable=self.process_mode,
                                   value='keyword',
                                   bg=self.colors['bg_secondary'],
                                   fg=self.colors['text_primary'],
                                   selectcolor=self.colors['bg_main'],
                                   activebackground=self.colors['bg_secondary'],
                                   activeforeground=self.colors['text_primary'],
                                   font=self.get_scaled_font('label'),
                                   command=self.on_process_mode_change)
        keyword_rb.pack(anchor='w', pady=2)

        # ブランド名取得モード
        brand_rb = tk.Radiobutton(process_mode_frame,
                                 text="ブランド名取得",
                                 variable=self.process_mode,
                                 value='brand',
                                 bg=self.colors['bg_secondary'],
                                 fg=self.colors['text_primary'],
                                 selectcolor=self.colors['bg_main'],
                                 activebackground=self.colors['bg_secondary'],
                                 activeforeground=self.colors['text_primary'],
                                 font=self.get_scaled_font('label'),
                                 command=self.on_process_mode_change)
        brand_rb.pack(anchor='w', pady=2)

        # 翻訳モード
        trans_frame = tk.Frame(left_panel, bg=self.colors['bg_secondary'])
        trans_frame.pack(fill='x', padx=20, pady=10)
        self.trans_frame = trans_frame  # 後で有効/無効化するために保存

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
        self.extract_frame = extract_frame  # 後で有効/無効化するために保存

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
        self.brand_frame = brand_frame  # 後で有効/無効化するために保存

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
        self.ai_frame = ai_frame  # 後で有効/無効化するために保存

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

        # カスタムプログレスバー（細く、角丸）
        self.progress_canvas = tk.Canvas(progress_frame,
                                        height=12,
                                        bg=self.colors['bg_tertiary'],
                                        highlightthickness=0)
        self.progress_canvas.pack(fill='x', pady=2)

        # 角丸の四角形を描画する関数
        def create_rounded_rect_for_progress(canvas, x1, y1, x2, y2, radius=4, **kwargs):
            points = [
                x1 + radius, y1,
                x2 - radius, y1,
                x2, y1,
                x2, y1 + radius,
                x2, y2 - radius,
                x2, y2,
                x2 - radius, y2,
                x1 + radius, y2,
                x1, y2,
                x1, y2 - radius,
                x1, y1 + radius,
                x1, y1
            ]
            return canvas.create_polygon(points, smooth=True, **kwargs)

        # 左右のパディング
        padding = 5

        # 背景バー（角丸）
        self.progress_bg_rect = create_rounded_rect_for_progress(
            self.progress_canvas,
            padding, 2, 250 - padding, 10,
            radius=4,
            fill=self.colors['bg_main'],
            outline=''
        )

        # 進捗バー（角丸）- 初期状態では非表示
        self.progress_fill_rect = None
        self.progress_padding = padding  # 保存しておく

        self.progress_text = tk.Label(progress_frame,
                                    text="0 / 0 (0%)",
                                    font=self.get_scaled_font('small'),
                                    bg=self.colors['bg_tertiary'],
                                    fg=self.colors['text_primary'])
        self.progress_text.pack(anchor='w')

        # 残り時間表示
        self.time_remaining_label = tk.Label(progress_frame,
                                            text="",
                                            font=self.get_scaled_font('small'),
                                            bg=self.colors['bg_tertiary'],
                                            fg=self.colors['text_secondary'])
        self.time_remaining_label.pack(anchor='w')

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
        # ウィジェットの存在確認
        if not hasattr(self, 'result_tree'):
            return

        try:
            # ウィジェットが有効かチェック
            self.result_tree.winfo_exists()
        except:
            return

        keywords_str = ' '.join(result['keywords'])
        translated_keywords_str = ' '.join(result['translated_keywords'])

        # 交互に背景色を変える
        try:
            row_index = len(self.result_tree.get_children())
        except:
            return
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

    def update_progress(self, current, total, start_time=None):
        """プログレスバーを更新（角丸、細いバー）"""
        # キャンバスの幅を取得
        canvas_width = self.progress_canvas.winfo_width()
        if canvas_width <= 1:  # まだ描画されていない場合
            canvas_width = 250

        # 進捗率を計算
        if total > 0:
            progress = current / total
        else:
            progress = 0

        # パディングを考慮した幅を計算
        padding = self.progress_padding
        usable_width = canvas_width - (padding * 2)
        fill_width = int(usable_width * progress)

        # 角丸の四角形を描画する関数
        def create_rounded_rect_coords(x1, y1, x2, y2, radius=4):
            points = [
                x1 + radius, y1,
                x2 - radius, y1,
                x2, y1,
                x2, y1 + radius,
                x2, y2 - radius,
                x2, y2,
                x2 - radius, y2,
                x1 + radius, y2,
                x1, y2,
                x1, y2 - radius,
                x1, y1 + radius,
                x1, y1
            ]
            return points

        # 背景バーを更新（角丸）
        bg_coords = create_rounded_rect_coords(padding, 2, canvas_width - padding, 10, radius=4)
        self.progress_canvas.coords(self.progress_bg_rect, *bg_coords)

        # 進捗バーを削除して再描画（角丸）
        if self.progress_fill_rect:
            self.progress_canvas.delete(self.progress_fill_rect)
            self.progress_fill_rect = None

        if fill_width > 8:  # 最小幅8px以上の場合のみ描画
            fill_coords = create_rounded_rect_coords(
                padding, 2,
                padding + fill_width, 10,
                radius=4
            )
            self.progress_fill_rect = self.progress_canvas.create_polygon(
                fill_coords,
                fill=self.colors['accent'],
                outline='',
                smooth=True
            )

        # テキスト更新
        percentage = int(progress * 100)
        self.progress_text.config(text=f"{current} / {total} ({percentage}%)")

        # 残り時間を計算
        if start_time and current > 0:
            elapsed_time = time.time() - start_time
            avg_time_per_item = elapsed_time / current
            remaining_items = total - current
            remaining_seconds = avg_time_per_item * remaining_items

            if remaining_seconds > 60:
                remaining_minutes = int(remaining_seconds / 60)
                self.time_remaining_label.config(text=f"残り時間: 約 {remaining_minutes} 分")
            elif remaining_seconds > 0:
                self.time_remaining_label.config(text=f"残り時間: 約 {int(remaining_seconds)} 秒")
            else:
                self.time_remaining_label.config(text="")
        else:
            self.time_remaining_label.config(text="")

        self.root.update()

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
        self.update_progress(0, 0)
        self.root.update()

        # 入力取得（ASINを大文字に正規化）
        input_text = self.input_text.get('1.0', 'end-1c')
        inputs = [line.strip().upper() for line in input_text.split('\n') if line.strip()]

        if not inputs:
            self.result_status.config(text="入力なし", fg=self.colors['text_primary'])
            messagebox.showwarning("警告", "ASINを入力してください")
            return

        # ASINの長さをチェック
        valid_inputs = []
        for asin in inputs:
            if len(asin) == 10:
                valid_inputs.append(asin)
            else:
                print(f"警告: 無効なASIN長さ: {asin} (長さ: {len(asin)})")

        if not valid_inputs:
            self.result_status.config(text="有効なASINがありません", fg=self.colors['text_primary'])
            messagebox.showwarning("警告", "有効なASINがありません（ASINは10文字である必要があります）")
            return

        inputs = valid_inputs

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

            # 処理開始時刻を記録
            start_time = time.time()

            # プログレスバーの初期化
            self.update_progress(0, total_count, start_time)
            self.root.update()

            # 処理モードで分岐
            process_mode = self.process_mode.get()
            region = self.amazon_region.get()

            # コールバック関数を定義
            def progress_callback(status, current_index, total, asin, result):
                """進捗コールバック"""
                nonlocal processed_count, brand_count

                if status == 'processing':
                    # 処理開始時
                    self.result_status.config(
                        text=f"処理中... {current_index}/{total} (ASIN: {asin})",
                        fg=self.colors['text_primary']
                    )
                    self.root.update()

                elif status in ('completed', 'failed'):
                    # 処理完了または失敗時
                    if result:
                        results.append(result)
                        processed_count += 1

                        # ブランド数カウント
                        if result.get('brand'):
                            brand_count += 1

                        # リアルタイム表示
                        self.display_result(result)

                        # プログレスバーと統計情報を更新
                        self.update_progress(processed_count, total_count, start_time)
                        self.stats_label.config(
                            text=f"件数: {processed_count}/{total_count}\nブランド数: {brand_count}\n処理状況: 処理中..."
                        )
                        self.result_status.config(
                            text=f"処理中... {processed_count}/{total_count}",
                            fg=self.colors['text_primary']
                        )
                        self.root.update()

            def should_stop_callback():
                """停止判定コールバック"""
                # 一時停止チェック
                while self.is_paused and self.processing:
                    self.root.update()
                    time.sleep(0.1)

                return not self.processing

            # キーワード抽出モードの場合は新しいprocess_asins()を使用
            if process_mode == 'keyword':
                print(f"\n[GUI] 新しいバッチ処理モードで実行します")
                results = self.extractor.process_asins(
                    asins=inputs,
                    mode=self.extract_mode.get(),
                    translate_mode=translate_mode,
                    include_brand=self.include_brand.get(),
                    region=region,
                    use_ai=None,  # AIはextractor内で自動判定
                    batch_size=self.extractor.scraping_config['batch_size'],
                    batch_cooldown=self.extractor.scraping_config['batch_cooldown'],
                    enable_progress_save=True,
                    progress_callback=progress_callback,
                    should_stop_callback=should_stop_callback
                )
                processed_count = len(results)
                for result in results:
                    if result.get('brand'):
                        brand_count += 1

            # ブランド名取得モードの場合は従来の処理（特別な待機時間が必要）
            else:
                print(f"\n[GUI] ブランド名取得モードで実行します")
                for i, asin in enumerate(inputs, 1):
                    if not self.processing:
                        break

                    # 一時停止チェック
                    while self.is_paused and self.processing:
                        self.root.update()
                        time.sleep(0.1)

                    if not self.processing:
                        break

                    # ステータス表示
                    self.result_status.config(
                        text=f"処理中... {i}/{total_count} (ASIN: {asin})",
                        fg=self.colors['text_primary']
                    )
                    self.root.update()

                    # ASINから商品タイトルとブランド名を取得
                    title, brand_from_asin = self.extractor.fetch_product_info_from_asin(asin, region)

                    # ブランド名取得モード: ASINとブランド名だけを表示
                    result = {
                        'asin': asin,
                        'original_title': '',  # 商品タイトルは表示しない
                        'brand': brand_from_asin if brand_from_asin else '',
                        'keywords': [],
                        'translated_keywords': []
                    }

                    # 結果を追加
                    results.append(result)
                    processed_count += 1

                    # ブランド数カウント
                    if result.get('brand'):
                        brand_count += 1

                    # リアルタイム表示
                    self.display_result(result)

                    # プログレスバーと統計情報を更新
                    self.update_progress(processed_count, total_count, start_time)
                    self.stats_label.config(
                        text=f"件数: {processed_count}/{total_count}\nブランド数: {brand_count}\n処理状況: 処理中..."
                    )
                    self.result_status.config(
                        text=f"処理中... {processed_count}/{total_count}",
                        fg=self.colors['text_primary']
                    )

                    # ブランド名取得モードは処理が速いため、追加の待機時間を設ける
                    import random
                    wait_time = random.uniform(10, 15)
                    print(f"次のリクエストまで {wait_time:.1f}秒待機中...")
                    time.sleep(wait_time)

            # 統計更新（最終）
            self.stats_label.config(
                text=f"件数: {processed_count}\nブランド数: {brand_count}\n処理状況: 完了"
            )

            # プログレスバーを完了状態に
            self.update_progress(processed_count, total_count, start_time)
            self.time_remaining_label.config(text="")  # 残り時間をクリア

            # ステータス更新
            self.result_status.config(text=f"✓ {processed_count}件処理完了", fg=self.colors['text_primary'])

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

        template_var = tk.StringVar(value=self.extractor.prompt_data.get('current_template', 'デフォルト'))
        template_combo = ttk.Combobox(template_frame,
                                      textvariable=template_var,
                                      values=list(self.extractor.prompt_data['templates'].keys()),
                                      state='readonly',
                                      width=25)
        template_combo.pack(side='left', padx=(0, 10))

        # テンプレート管理ボタン
        def add_template():
            """新しいテンプレートを追加"""
            # 名前入力ダイアログ
            from tkinter import simpledialog
            name = simpledialog.askstring("新規テンプレート", "テンプレート名を入力してください:")
            if name and name.strip():
                name = name.strip()
                if name in self.extractor.prompt_data['templates']:
                    messagebox.showwarning("警告", "同じ名前のテンプレートが既に存在します")
                    return
                if name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル']):
                    messagebox.showwarning("警告", "デフォルトテンプレートと同じ名前は使用できません")
                    return

                # デフォルトテンプレートをコピーして新規作成
                default_template = self.extractor.prompt_data['templates']['デフォルト']
                self.extractor.prompt_data['templates'][name] = {
                    'name': name,
                    'base_prompt': default_template['base_prompt'],
                    'instructions': default_template['instructions'].copy()
                }
                # コンボボックスを更新
                template_combo['values'] = list(self.extractor.prompt_data['templates'].keys())
                template_var.set(name)
                load_template()
                messagebox.showinfo("成功", f"テンプレート '{name}' を作成しました")

        def rename_template():
            """テンプレート名を変更"""
            current_name = template_var.get()
            if current_name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル']):
                messagebox.showwarning("警告", "デフォルトテンプレートの名前は変更できません")
                return

            from tkinter import simpledialog
            new_name = simpledialog.askstring("名前変更", f"'{current_name}' の新しい名前を入力してください:", initialvalue=current_name)
            if new_name and new_name.strip():
                new_name = new_name.strip()
                if new_name == current_name:
                    return
                if new_name in self.extractor.prompt_data['templates']:
                    messagebox.showwarning("警告", "同じ名前のテンプレートが既に存在します")
                    return
                if new_name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル']):
                    messagebox.showwarning("警告", "デフォルトテンプレートと同じ名前は使用できません")
                    return

                # 名前を変更
                self.extractor.prompt_data['templates'][new_name] = self.extractor.prompt_data['templates'][current_name]
                self.extractor.prompt_data['templates'][new_name]['name'] = new_name
                del self.extractor.prompt_data['templates'][current_name]

                # current_templateも更新
                if self.extractor.prompt_data.get('current_template') == current_name:
                    self.extractor.prompt_data['current_template'] = new_name

                # コンボボックスを更新
                template_combo['values'] = list(self.extractor.prompt_data['templates'].keys())
                template_var.set(new_name)
                messagebox.showinfo("成功", f"テンプレート名を '{new_name}' に変更しました")

        def delete_template():
            """テンプレートを削除"""
            current_name = template_var.get()
            if current_name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル']):
                messagebox.showwarning("警告", "デフォルトテンプレートは削除できません")
                return

            if messagebox.askyesno("確認", f"テンプレート '{current_name}' を削除しますか？"):
                del self.extractor.prompt_data['templates'][current_name]

                # current_templateをデフォルトに戻す
                if self.extractor.prompt_data.get('current_template') == current_name:
                    self.extractor.prompt_data['current_template'] = 'デフォルト'

                # コンボボックスを更新
                template_combo['values'] = list(self.extractor.prompt_data['templates'].keys())
                template_var.set('デフォルト')
                load_template()
                messagebox.showinfo("成功", f"テンプレート '{current_name}' を削除しました")

        # ボタンを追加
        tk.Button(template_frame, text="➕ 追加", command=add_template,
                 bg=self.colors['accent'], fg='white',
                 font=self.get_scaled_font('small'),
                 relief='flat', padx=10, pady=3).pack(side='left', padx=2)

        tk.Button(template_frame, text="✏️ 名前変更", command=rename_template,
                 bg=self.colors['accent_hover'], fg='white',
                 font=self.get_scaled_font('small'),
                 relief='flat', padx=10, pady=3).pack(side='left', padx=2)

        tk.Button(template_frame, text="🗑️ 削除", command=delete_template,
                 bg='#e74c3c', fg='white',
                 font=self.get_scaled_font('small'),
                 relief='flat', padx=10, pady=3).pack(side='left', padx=2)

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
            is_default = template_name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル'])

            if template_name in self.extractor.prompt_data['templates']:
                template = self.extractor.prompt_data['templates'][template_name]
                base_text.delete('1.0', tk.END)
                base_text.insert('1.0', template['base_prompt'])

                for mode_key, text_widget in instruction_texts.items():
                    text_widget.delete('1.0', tk.END)
                    text_widget.insert('1.0', template['instructions'].get(mode_key, ''))

                # デフォルトテンプレートの場合は編集を無効化
                if is_default:
                    base_text.config(state='disabled', bg='#f0f0f0')
                    for text_widget in instruction_texts.values():
                        text_widget.config(state='disabled', bg='#f0f0f0')
                    base_label.config(text="ベースプロンプト（デフォルトテンプレートは編集できません）:")
                else:
                    base_text.config(state='normal', bg=self.colors['input_bg'])
                    for text_widget in instruction_texts.values():
                        text_widget.config(state='normal', bg=self.colors['input_bg'])
                    base_label.config(text="ベースプロンプト（{title}, {instruction}, {brand_instruction}が置換されます）:")

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

            # デフォルトテンプレートは保存できない
            if template_name in self.extractor.prompt_data.get('default_templates', ['デフォルト', 'シンプル']):
                messagebox.showwarning("警告", "デフォルトテンプレートは保存できません。\n編集したい場合は、新しいテンプレートを作成してください。")
                return

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