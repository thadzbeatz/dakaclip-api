from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import re

app = Flask(__name__)
CORS(app)

def extract_url(text):
    """Extract first URL from any text (handles share text like 'Check out this TikTok...')"""
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0).rstrip("'\"") if match else text.strip()

@app.route('/')
def home():
    return jsonify({'status': 'DakaClip API is running'})

@app.route('/api/video', methods=['POST'])
def get_video():
    data = request.get_json(silent=True) or {}
    raw = data.get('url', '').strip()

    if not raw:
        return jsonify({'error': 'URL inahitajika'}), 400

    # Extract clean URL from share text
    url = extract_url(raw)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][protocol=https]/best[ext=mp4]/best[protocol=https]/best',
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        # Use Android client to bypass YouTube bot detection
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return jsonify({'error': 'Video haikupatikana'}), 404

        video_url = info.get('url')
        if not video_url:
            formats = info.get('formats') or []
            for f in reversed(formats):
                if f.get('url') and f.get('protocol', '').startswith('http'):
                    video_url = f['url']
                    break

        if not video_url:
            return jsonify({'error': 'Imeshindwa kupata URL ya video'}), 500

        vid_id   = info.get('id') or 'video'
        title    = info.get('title') or vid_id
        safe     = ''.join(c for c in title if c.isalnum() or c in ' _-').strip()[:60]
        filename = f"{safe or vid_id}.mp4"

        return jsonify({
            'url':       video_url,
            'title':     title,
            'filename':  filename,
            'thumbnail': info.get('thumbnail'),
        })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': str(e)}), 422
    except Exception as e:
        return jsonify({'error': f'Hitilafu: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
