import schedule
import time
import logging
from datetime import datetime
from youtube_analyzer import YouTubeAnalyzer

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

def run_batch_analysis():
    """5日に1回の一括分析を実行"""
    try:
        logging.info("自動一括分析を開始します...")
        analyzer = YouTubeAnalyzer()
        result = analyzer.analyze_csv_urls()
        
        if result.get('success'):
            logging.info(f"一括分析が完了しました。分析された動画数: {result.get('analyzed_count', 0)}")
        else:
            logging.error(f"一括分析でエラーが発生しました: {result.get('error')}")
            
    except Exception as e:
        logging.error(f"スケジューラーでエラーが発生しました: {str(e)}")

def start_scheduler():
    """スケジューラーを開始"""
    # 5日に1回、午前2時に実行
    schedule.every(5).days.at("02:00").do(run_batch_analysis)
    
    # 起動時に一度実行
    logging.info("スケジューラーが開始されました。起動時の一括分析を実行します...")
    run_batch_analysis()
    
    logging.info("5日に1回（午前2時）の自動一括分析がスケジュールされました。")
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # 1時間ごとにチェック

if __name__ == "__main__":
    start_scheduler()