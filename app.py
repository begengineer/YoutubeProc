from flask import Flask, render_template, request, jsonify
import os
import threading
from dotenv import load_dotenv
from youtube_analyzer import YouTubeAnalyzer
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# 最終更新日時を保存する変数
last_updated = None

def run_initial_analysis():
    """アプリ起動時に一括分析を実行"""
    global last_updated
    try:
        analyzer = YouTubeAnalyzer()
        result = analyzer.analyze_csv_urls()
        last_updated = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
        print(f"初期一括分析完了: {last_updated}")
    except Exception as e:
        print(f"初期分析でエラー: {str(e)}")

# 本番環境では起動時の一括分析を無効化（タイムアウト防止）
# 代わりにスケジューラーで定期実行
# threading.Thread(target=run_initial_analysis, daemon=True).start()

@app.route('/')
def index():
    # 起動時にランキングとチャートデータを自動読み込み
    return render_template('index.html', last_updated=last_updated)

@app.route('/last_updated')
def get_last_updated():
    return jsonify({'last_updated': last_updated})

@app.route('/analyze', methods=['POST'])
def analyze_video():
    try:
        data = request.get_json()
        video_url = data.get('video_url')
        
        if not video_url:
            return jsonify({'error': 'Video URL is required'}), 400
        
        analyzer = YouTubeAnalyzer()
        result = analyzer.analyze_video(video_url)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/rankings')
def get_rankings():
    try:
        analyzer = YouTubeAnalyzer()
        rankings = analyzer.get_monthly_rankings()
        return jsonify(rankings)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view_trends')
def get_view_trends():
    try:
        analyzer = YouTubeAnalyzer()
        trends = analyzer.get_view_trends()
        return jsonify(trends)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/monthly_comments_chart')
def get_monthly_comments_chart():
    try:
        analyzer = YouTubeAnalyzer()
        chart_data = analyzer.get_monthly_comments_chart_data()
        return jsonify(chart_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/monthly_views_chart')
def get_monthly_views_chart():
    try:
        analyzer = YouTubeAnalyzer()
        chart_data = analyzer.get_monthly_views_chart_data()
        return jsonify(chart_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_csv', methods=['POST'])
def analyze_csv():
    try:
        analyzer = YouTubeAnalyzer()
        result = analyzer.analyze_csv_urls()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/database_management')
def get_database_videos():
    try:
        analyzer = YouTubeAnalyzer()
        videos = analyzer.get_all_videos()
        return jsonify(videos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_video', methods=['POST'])
def delete_video():
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({'error': 'Video ID is required'}), 400
        
        analyzer = YouTubeAnalyzer()
        result = analyzer.delete_video_data(video_id)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear_database', methods=['POST'])
def clear_database():
    try:
        analyzer = YouTubeAnalyzer()
        result = analyzer.clear_all_data()
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)