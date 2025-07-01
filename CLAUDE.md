# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Comment Analysis Web Application that analyzes sentiment of YouTube video comments and provides various visualizations and rankings. Built with Flask backend and vanilla JavaScript frontend.

## Core Architecture

### Backend Components
- **`app.py`**: Flask web server with REST API endpoints for video analysis, charts, rankings, and database management
- **`youtube_analyzer.py`**: Core analysis engine containing the `YouTubeAnalyzer` class that handles YouTube API integration, sentiment analysis, and database operations
- **SQLite Database**: Persistent storage with optimized WAL mode for concurrent access

### Key Data Flow
1. User inputs YouTube URL → Flask endpoint → YouTubeAnalyzer
2. YouTubeAnalyzer fetches video/comments via YouTube API → TextBlob sentiment analysis → SQLite storage
3. Analysis results returned as JSON → Frontend renders charts/tables

### Database Schema
- **videos**: Video metadata (title, view_count, like_count, published_at)
- **comments**: Individual comments with sentiment analysis results
- **view_snapshots**: Time-series data for tracking view count changes
- **monthly_stats**: Aggregated monthly statistics for rankings

## Environment Setup

### Required Environment Variables
Create `.env` file with:
```
YOUTUBE_API_KEY=your_youtube_api_key_here
SECRET_KEY=your_secret_key_here
```

### Installation and Startup
```bash
# Install dependencies
pip install -r requirements.txt

# Download NLTK data for TextBlob
python -c "import nltk; nltk.download('punkt')"

# Start development server
python app.py
```

Application runs on `http://localhost:5001` (changed from default 5000 to avoid conflicts).

## Key Features

### Sentiment Analysis Engine
- Uses TextBlob for base sentiment scoring
- Enhanced with Japanese keyword dictionaries (positive/negative/neutral expressions)
- Balances aggressive classification vs. accuracy to minimize inappropriate neutral classifications
- Handles both Japanese and English content

### Data Visualization
- **Monthly Comments Chart**: Shows comment volume over time by month
- **Monthly Views Chart**: Tracks view count progression using snapshot data
- **Rankings**: Top 10 positive/negative videos, Top 20 by comment count
- **Representative Comments**: Top 5 comments per sentiment category sorted by likes

### Batch Processing
- CSV-based bulk analysis via `__46_1st_12th______.csv` file
- Supports analyzing multiple videos sequentially with progress tracking

## API Endpoints

Key REST endpoints:
- `POST /analyze`: Analyze single video URL
- `POST /analyze_csv`: Batch analyze URLs from CSV file
- `GET /monthly_comments_chart`: Comment count time series data
- `GET /monthly_views_chart`: View count progression data
- `GET /rankings`: Monthly ranking data
- `GET /database_management`: List all analyzed videos
- `POST /delete_video`: Remove specific video data
- `POST /clear_database`: Clear all data

## Database Management

The application includes built-in database management tools accessible via the web interface:
- View all analyzed videos with metadata
- Individual video deletion
- Complete database reset functionality

## YouTube API Considerations

- API quota limits apply (carefully managed in comment fetching)
- Comment retrieval limited to ~2000 most recent/relevant comments per video
- Handles API errors gracefully with retry logic
- Uses both 'time' and 'relevance' ordering to maximize comment coverage

## Special Files

- **`__46_1st_12th______.csv`**: Contains URLs for batch analysis of specific video set
- **`youtube_analysis.db`**: SQLite database (automatically created)
- **`.env`**: Environment variables (should not be committed)