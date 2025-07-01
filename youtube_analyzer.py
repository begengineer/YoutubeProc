import os
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import sqlite3
import json

from dotenv import load_dotenv
from googleapiclient.discovery import build
from textblob import TextBlob
import requests
from urllib.parse import urlparse, parse_qs

load_dotenv()

class YouTubeAnalyzer:
    def __init__(self):
        self.api_key = os.environ.get('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YouTube API key not found. Please set YOUTUBE_API_KEY environment variable.")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.db_path = 'youtube_analysis.db'
        self.init_database()
    
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=memory')
        conn.execute('PRAGMA mmap_size=268435456')
        return conn
    
    def init_database(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    comment_count INTEGER,
                    published_at TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS view_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    comment_count INTEGER,
                    snapshot_date TEXT,
                    FOREIGN KEY (video_id) REFERENCES videos (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    video_id TEXT,
                    text TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    published_at TEXT,
                    like_count INTEGER,
                    FOREIGN KEY (video_id) REFERENCES videos (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monthly_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    month TEXT,
                    positive_comments INTEGER,
                    negative_comments INTEGER,
                    total_comments INTEGER,
                    avg_sentiment REAL,
                    FOREIGN KEY (video_id) REFERENCES videos (id)
                )
            ''')
            
            conn.commit()
    
    def extract_video_id(self, url):
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:v\/|\/u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        parsed_url = urlparse(url)
        if parsed_url.netloc in ['youtu.be']:
            return parsed_url.path[1:]
        elif parsed_url.netloc in ['youtube.com', 'www.youtube.com']:
            if 'v' in parse_qs(parsed_url.query):
                return parse_qs(parsed_url.query)['v'][0]
        
        raise ValueError("Invalid YouTube URL")
    
    def get_video_info(self, video_id):
        request = self.youtube.videos().list(
            part='snippet,statistics',
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            raise ValueError("Video not found")
        
        video = response['items'][0]
        return {
            'id': video_id,
            'title': video['snippet']['title'],
            'view_count': int(video['statistics'].get('viewCount', 0)),
            'like_count': int(video['statistics'].get('likeCount', 0)),
            'comment_count': int(video['statistics'].get('commentCount', 0)),
            'published_at': video['snippet']['publishedAt']
        }
    
    def get_video_comments(self, video_id, max_results=2000):
        comments = []
        next_page_token = None
        
        try:
            # 時系列順で取得を試行
            for order_type in ['time', 'relevance']:
                temp_comments = []
                temp_next_page_token = None
                
                while len(temp_comments) < max_results:
                    request = self.youtube.commentThreads().list(
                        part='snippet',
                        videoId=video_id,
                        maxResults=min(100, max_results - len(temp_comments)),
                        pageToken=temp_next_page_token,
                        order=order_type
                    )
                    response = request.execute()
                    
                    for item in response['items']:
                        comment = item['snippet']['topLevelComment']['snippet']
                        comment_data = {
                            'id': item['id'],
                            'text': comment['textDisplay'],
                            'published_at': comment['publishedAt'],
                            'like_count': comment.get('likeCount', 0)
                        }
                        
                        # 重複チェック
                        if not any(c['id'] == comment_data['id'] for c in temp_comments):
                            temp_comments.append(comment_data)
                    
                    temp_next_page_token = response.get('nextPageToken')
                    if not temp_next_page_token or len(temp_comments) >= max_results:
                        break
                
                # より多くのコメントが取得できた順序を採用
                if len(temp_comments) > len(comments):
                    comments = temp_comments
                
                # 十分なコメントが取得できた場合は終了
                if len(comments) >= max_results * 0.8:
                    break
        
        except Exception as e:
            print(f"Error fetching comments: {e}")
        
        # 重複除去と日付順ソート
        unique_comments = []
        seen_ids = set()
        
        for comment in comments:
            if comment['id'] not in seen_ids:
                unique_comments.append(comment)
                seen_ids.add(comment['id'])
        
        # 日付順でソート（古い順）
        unique_comments.sort(key=lambda x: x['published_at'])
        
        print(f"取得したコメント数: {len(unique_comments)}")
        if unique_comments:
            oldest = unique_comments[0]['published_at'][:10]
            newest = unique_comments[-1]['published_at'][:10]
            print(f"コメント期間: {oldest} 〜 {newest}")
        
        return unique_comments
    
    def analyze_sentiment(self, text):
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        # より慎重な感情分析（バランス重視）
        if polarity > 0.05:
            label = 'positive'
        elif polarity < -0.05:
            label = 'negative'
        else:
            label = 'neutral'
        
        # より厳密に分類された感情キーワード
        strong_positive_keywords = [
            '最高', '素晴らしい', '神', '感動', '大好き', '愛してる', 'すげー', 'すげえ', 'やばい', 'ヤバい', 
            'amazing', 'awesome', 'love', 'perfect', '完璧', '天才', 'かっこいい', 'イケメン', '美しい'
        ]
        
        positive_keywords = [
            '好き', 'いい', '良い', 'すごい', '面白い', '楽しい', 'ありがとう', '可愛い', 'かわいい', 
            '素敵', '感謝', '嬉しい', 'うれしい', '笑', 'ナイス', 'nice', 'good', 'great', 'cool'
        ]
        
        strong_negative_keywords = [
            '最悪', '死ね', 'クソ', 'くそ', 'ゴミ', 'きもい', 'うざい', 'ムカつく', 'イライラ',
            'hate', 'terrible', 'awful', 'worst', 'stupid', '大嫌い', 'ひどい', '腹立つ'
        ]
        
        negative_keywords = [
            '嫌い', '悪い', 'つまらない', '退屈', '残念', 'がっかり', 'だめ', 'ダメ', '悲しい',
            'bad', 'boring', 'disappointed'
        ]
        
        # ネガティブではない一般的な表現を除外
        neutral_expressions = [
            '思う', '思った', '感じ', '感じる', '考え', '見る', '聞く', '言う', '話', '時間', 
            '今日', '明日', '昨日', '最近', '前', '後', '中', '上', '下', '右', '左'
        ]
        
        text_clean = text.lower().replace(' ', '').replace('　', '')
        
        # 強いキーワードのチェック
        strong_positive_count = sum(1 for word in strong_positive_keywords if word in text_clean)
        strong_negative_count = sum(1 for word in strong_negative_keywords if word in text_clean)
        
        # 通常のキーワードのチェック
        positive_count = sum(1 for word in positive_keywords if word in text_clean)
        negative_count = sum(1 for word in negative_keywords if word in text_clean)
        
        # ニュートラル表現のチェック
        neutral_count = sum(1 for word in neutral_expressions if word in text_clean)
        
        # 強いキーワードが優先
        if strong_positive_count > 0 and strong_negative_count == 0:
            label = 'positive'
            polarity = max(polarity, 0.3)
        elif strong_negative_count > 0 and strong_positive_count == 0:
            label = 'negative'
            polarity = min(polarity, -0.3)
        elif strong_positive_count > 0 and strong_negative_count > 0:
            # 両方ある場合は多い方
            if strong_positive_count > strong_negative_count:
                label = 'positive'
                polarity = max(polarity, 0.2)
            else:
                label = 'negative'
                polarity = min(polarity, -0.2)
        else:
            # 通常のキーワードでの判定
            total_positive = positive_count
            total_negative = negative_count
            
            # ニュートラル表現が多い場合は感情を弱める
            if neutral_count > 2:
                total_positive *= 0.5
                total_negative *= 0.5
            
            if total_positive > total_negative and total_positive > 0:
                if polarity >= -0.1:  # あまりにネガティブでなければ
                    label = 'positive'
                    polarity = max(polarity, 0.1)
            elif total_negative > total_positive and total_negative > 0:
                if polarity <= 0.1:  # あまりにポジティブでなければ
                    label = 'negative'
                    polarity = min(polarity, -0.1)
            else:
                # キーワードが同数または無い場合、元のpolarityを尊重
                if polarity > 0.02:
                    label = 'positive'
                elif polarity < -0.02:
                    label = 'negative'
                else:
                    label = 'neutral'
        
        return polarity, label
    
    def save_video_data(self, video_info, comments_with_sentiment):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO videos 
                (id, title, view_count, like_count, comment_count, published_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                video_info['id'],
                video_info['title'],
                video_info['view_count'],
                video_info['like_count'],
                video_info['comment_count'],
                video_info['published_at']
            ))
            
            for comment in comments_with_sentiment:
                cursor.execute('''
                    INSERT OR REPLACE INTO comments
                    (id, video_id, text, sentiment_score, sentiment_label, published_at, like_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    comment['id'],
                    video_info['id'],
                    comment['text'],
                    comment['sentiment_score'],
                    comment['sentiment_label'],
                    comment['published_at'],
                    comment['like_count']
                ))
            
            conn.commit()
        
        self.save_view_snapshot(video_info)
        self.update_monthly_stats(video_info['id'])
    
    def save_view_snapshot(self, video_info):
        from datetime import datetime
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO view_snapshots
                (video_id, view_count, like_count, comment_count, snapshot_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                video_info['id'],
                video_info['view_count'],
                video_info['like_count'],
                video_info['comment_count'],
                current_date
            ))
            
            conn.commit()
    
    def update_monthly_stats(self, video_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m', published_at) as month,
                    COUNT(*) as total_comments,
                    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive_comments,
                    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative_comments,
                    AVG(sentiment_score) as avg_sentiment
                FROM comments
                WHERE video_id = ?
                GROUP BY strftime('%Y-%m', published_at)
            ''', (video_id,))
            
            monthly_data = cursor.fetchall()
            
            cursor.execute('DELETE FROM monthly_stats WHERE video_id = ?', (video_id,))
            
            for month, total, positive, negative, avg_sentiment in monthly_data:
                cursor.execute('''
                    INSERT INTO monthly_stats
                    (video_id, month, positive_comments, negative_comments, total_comments, avg_sentiment)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (video_id, month, positive, negative, total, avg_sentiment))
            
            conn.commit()
    
    def analyze_video(self, video_url):
        video_id = self.extract_video_id(video_url)
        video_info = self.get_video_info(video_id)
        comments = self.get_video_comments(video_id)
        
        comments_with_sentiment = []
        sentiment_summary = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for comment in comments:
            sentiment_score, sentiment_label = self.analyze_sentiment(comment['text'])
            comment['sentiment_score'] = sentiment_score
            comment['sentiment_label'] = sentiment_label
            comments_with_sentiment.append(comment)
            sentiment_summary[sentiment_label] += 1
        
        self.save_video_data(video_info, comments_with_sentiment)
        
        # 代表コメント取得
        representative_comments = self.get_representative_comments(video_info['id'])
        
        return {
            'video_info': video_info,
            'sentiment_summary': sentiment_summary,
            'total_comments_analyzed': len(comments_with_sentiment),
            'representative_comments': representative_comments,
            'analysis_complete': True
        }
    
    def get_monthly_rankings(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    v.title,
                    ms.month,
                    ms.negative_comments,
                    ms.positive_comments,
                    ms.total_comments
                FROM monthly_stats ms
                JOIN videos v ON ms.video_id = v.id
                ORDER BY ms.negative_comments DESC
                LIMIT 10
            ''')
            top_negative = cursor.fetchall()
            
            cursor.execute('''
                SELECT 
                    v.title,
                    ms.month,
                    ms.positive_comments,
                    ms.negative_comments,
                    ms.total_comments
                FROM monthly_stats ms
                JOIN videos v ON ms.video_id = v.id
                ORDER BY ms.positive_comments DESC
                LIMIT 10
            ''')
            top_positive = cursor.fetchall()
            
            cursor.execute('''
                SELECT 
                    v.title,
                    ms.month,
                    ms.total_comments,
                    ms.positive_comments,
                    ms.negative_comments
                FROM monthly_stats ms
                JOIN videos v ON ms.video_id = v.id
                ORDER BY ms.total_comments DESC
                LIMIT 20
            ''')
            top_comments = cursor.fetchall()
        
        return {
            'top_negative': [
                {
                    'title': row[0],
                    'month': row[1],
                    'negative_comments': row[2],
                    'positive_comments': row[3],
                    'total_comments': row[4]
                } for row in top_negative
            ],
            'top_positive': [
                {
                    'title': row[0],
                    'month': row[1],
                    'positive_comments': row[2],
                    'negative_comments': row[3],
                    'total_comments': row[4]
                } for row in top_positive
            ],
            'top_comments': [
                {
                    'title': row[0],
                    'month': row[1],
                    'total_comments': row[2],
                    'positive_comments': row[3],
                    'negative_comments': row[4]
                } for row in top_comments
            ]
        }
    
    def get_view_trends(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 各動画のスナップショット履歴を取得
            cursor.execute('''
                SELECT 
                    v.title,
                    v.id,
                    vs.view_count,
                    vs.like_count,
                    vs.comment_count,
                    strftime('%Y-%m', vs.snapshot_date) as snapshot_month,
                    vs.snapshot_date
                FROM videos v
                JOIN view_snapshots vs ON v.id = vs.video_id
                ORDER BY v.title, vs.snapshot_date DESC
            ''')
            
            trends = cursor.fetchall()
            
            # データが少ない場合は、単純な動画一覧を返す
            if not trends:
                cursor.execute('''
                    SELECT 
                        v.title,
                        strftime('%Y-%m', v.published_at) as month,
                        v.view_count,
                        v.like_count,
                        v.comment_count,
                        '初回分析時' as note
                    FROM videos v
                    ORDER BY v.published_at DESC
                ''')
                
                simple_trends = cursor.fetchall()
                return [
                    {
                        'title': row[0],
                        'month': row[1],
                        'view_count': row[2],
                        'like_count': row[3],
                        'comment_count': row[4],
                        'note': row[5]
                    } for row in simple_trends
                ]
        
        # スナップショットデータがある場合
        result = []
        for row in trends:
            result.append({
                'title': row[0],
                'video_id': row[1],
                'view_count': row[2],
                'like_count': row[3],
                'comment_count': row[4],
                'month': row[5],
                'snapshot_date': row[6],
                'note': 'スナップショット記録'
            })
        
        return result
    
    def get_representative_comments(self, video_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            representative = {
                'positive': [],
                'negative': [],
                'neutral': []
            }
            
            for sentiment in ['positive', 'negative', 'neutral']:
                cursor.execute('''
                    SELECT text, like_count, sentiment_score, published_at
                    FROM comments
                    WHERE video_id = ? AND sentiment_label = ?
                    ORDER BY like_count DESC, LENGTH(text) DESC
                    LIMIT 5
                ''', (video_id, sentiment))
                
                comments = cursor.fetchall()
                representative[sentiment] = [
                    {
                        'text': row[0],
                        'like_count': row[1],
                        'sentiment_score': row[2],
                        'published_at': row[3]
                    } for row in comments
                ]
            
            return representative
    
    def get_monthly_comments_chart_data(self):
        from datetime import datetime, timedelta
        from collections import defaultdict
        import calendar
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 各動画のコメント数を公開日からの月別に集計
            cursor.execute('''
                SELECT 
                    v.title,
                    v.id,
                    v.published_at,
                    c.published_at as comment_date,
                    COUNT(*) as comment_count
                FROM videos v
                JOIN comments c ON v.id = c.video_id
                GROUP BY v.id, v.title, v.published_at, strftime('%Y-%m', c.published_at)
                ORDER BY v.published_at, c.published_at
            ''')
            
            results = cursor.fetchall()
            
            if not results:
                return {'message': 'コメントデータがありません。動画を分析してください。', 'data': []}
            
            # 動画ごとにデータを整理
            video_data = defaultdict(lambda: {
                'title': '',
                'published_at': '',
                'monthly_comments': defaultdict(int)
            })
            
            for row in results:
                title, video_id, published_at, comment_date, comment_count = row
                video_data[video_id]['title'] = title
                video_data[video_id]['published_at'] = published_at
                
                # コメント日から年月を取得
                comment_month = comment_date[:7]  # YYYY-MM形式
                video_data[video_id]['monthly_comments'][comment_month] = comment_count
            
            # 全ての月のラベルを生成（最古の動画から最新まで）
            all_months = set()
            for data in video_data.values():
                all_months.update(data['monthly_comments'].keys())
            
            if not all_months:
                return {'message': 'コメントデータが見つかりません。', 'data': []}
            
            sorted_months = sorted(all_months)
            
            # チャート用データを準備
            chart_data = {
                'labels': [self.format_month_label(month) for month in sorted_months],
                'datasets': []
            }
            
            # 各動画ごとのデータセットを作成
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF9F9F', '#9FFF9F', '#9F9FFF']
            color_index = 0
            
            for video_id, data in video_data.items():
                dataset = {
                    'label': data['title'][:30] + ('...' if len(data['title']) > 30 else ''),
                    'data': [],
                    'borderColor': colors[color_index % len(colors)],
                    'backgroundColor': colors[color_index % len(colors)] + '20',
                    'fill': False,
                    'tension': 0.3
                }
                
                # 各月のコメント数を追加
                for month in sorted_months:
                    comment_count = data['monthly_comments'].get(month, 0)
                    dataset['data'].append(comment_count)
                
                chart_data['datasets'].append(dataset)
                color_index += 1
            
            return chart_data
    
    def format_month_label(self, month_str):
        # YYYY-MM形式をYYYY年MM月形式に変換
        try:
            year, month = month_str.split('-')
            return f"{year}年{int(month):02d}月"
        except:
            return month_str
    
    def get_monthly_views_chart_data(self):
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 各動画のスナップショット履歴を月別に整理
            cursor.execute('''
                SELECT 
                    v.title,
                    v.id,
                    vs.view_count,
                    strftime('%Y-%m', vs.snapshot_date) as snapshot_month,
                    vs.snapshot_date
                FROM videos v
                JOIN view_snapshots vs ON v.id = vs.video_id
                ORDER BY vs.snapshot_date ASC
            ''')
            
            results = cursor.fetchall()
            
            if not results:
                return {'message': 'スナップショットデータがありません。複数回分析してください。', 'data': []}
            
            # 動画ごとにデータを整理
            video_data = defaultdict(lambda: {
                'title': '',
                'monthly_views': defaultdict(int)
            })
            
            for row in results:
                title, video_id, view_count, snapshot_month, snapshot_date = row
                video_data[video_id]['title'] = title
                
                # 同じ月の場合は最新の値を使用
                if snapshot_month not in video_data[video_id]['monthly_views'] or \
                   snapshot_date > video_data[video_id]['monthly_views'][snapshot_month + '_date']:
                    video_data[video_id]['monthly_views'][snapshot_month] = view_count
                    video_data[video_id]['monthly_views'][snapshot_month + '_date'] = snapshot_date
            
            # 全ての月のラベルを生成
            all_months = set()
            for data in video_data.values():
                for key in data['monthly_views'].keys():
                    if not key.endswith('_date'):
                        all_months.add(key)
            
            if not all_months:
                return {'message': '再生数データが見つかりません。', 'data': []}
            
            sorted_months = sorted(all_months)
            
            # チャート用データを準備
            chart_data = {
                'labels': [self.format_month_label(month) for month in sorted_months],
                'datasets': []
            }
            
            # 各動画ごとのデータセットを作成
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF9F9F', '#9FFF9F', '#9F9FFF']
            color_index = 0
            
            for video_id, data in video_data.items():
                dataset = {
                    'label': data['title'][:30] + ('...' if len(data['title']) > 30 else ''),
                    'data': [],
                    'borderColor': colors[color_index % len(colors)],
                    'backgroundColor': colors[color_index % len(colors)] + '20',
                    'fill': False,
                    'tension': 0.3
                }
                
                # 各月の再生数を追加
                for month in sorted_months:
                    view_count = data['monthly_views'].get(month, None)
                    dataset['data'].append(view_count)
                
                chart_data['datasets'].append(dataset)
                color_index += 1
            
            return chart_data
    
    def analyze_csv_urls(self):
        import csv
        import os
        
        csv_path = os.path.join(os.path.dirname(__file__), '__46_1st_12th______.csv')
        
        if not os.path.exists(csv_path):
            return {'error': 'CSVファイルが見つかりません', 'success': False}
        
        urls = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                for line in file:
                    url = line.strip()
                    if url and url.startswith('https://www.youtube.com/'):
                        urls.append(url)
        except Exception as e:
            return {'error': f'CSVファイル読み込みエラー: {str(e)}', 'success': False}
        
        if not urls:
            return {'error': 'CSVファイルにYouTube URLが見つかりません', 'success': False}
        
        results = []
        failed_count = 0
        
        for i, url in enumerate(urls, 1):
            try:
                print(f"分析中 {i}/{len(urls)}: {url}")
                result = self.analyze_video(url)
                results.append({
                    'url': url,
                    'success': True,
                    'title': result['video_info']['title'],
                    'view_count': result['video_info']['view_count'],
                    'comments_analyzed': result['total_comments_analyzed']
                })
            except Exception as e:
                print(f"エラー {i}/{len(urls)}: {str(e)}")
                failed_count += 1
                results.append({
                    'url': url,
                    'success': False,
                    'error': str(e)
                })
        
        return {
            'success': True,
            'total_urls': len(urls),
            'successful': len(urls) - failed_count,
            'failed': failed_count,
            'results': results,
            'message': f'{len(urls)}個のURL中{len(urls) - failed_count}個の分析が完了しました'
        }
    
    def get_all_videos(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    v.id,
                    v.title,
                    v.view_count,
                    v.like_count,
                    v.comment_count,
                    v.published_at,
                    v.created_at,
                    COUNT(c.id) as total_comments_analyzed,
                    COUNT(vs.id) as snapshots_count
                FROM videos v
                LEFT JOIN comments c ON v.id = c.video_id
                LEFT JOIN view_snapshots vs ON v.id = vs.video_id
                GROUP BY v.id
                ORDER BY v.created_at DESC
            ''')
            
            results = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'view_count': row[2],
                    'like_count': row[3],
                    'comment_count': row[4],
                    'published_at': row[5],
                    'created_at': row[6],
                    'total_comments_analyzed': row[7],
                    'snapshots_count': row[8]
                } for row in results
            ]
    
    def delete_video_data(self, video_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 関連データを削除
            cursor.execute('DELETE FROM monthly_stats WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM view_snapshots WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM comments WHERE video_id = ?', (video_id,))
            cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
            
            conn.commit()
            
            return {'success': True, 'message': f'動画データを削除しました: {video_id}'}
    
    def clear_all_data(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 全テーブルをクリア
            cursor.execute('DELETE FROM monthly_stats')
            cursor.execute('DELETE FROM view_snapshots')
            cursor.execute('DELETE FROM comments')
            cursor.execute('DELETE FROM videos')
            
            conn.commit()
            
            return {'success': True, 'message': 'すべてのデータを削除しました'}