from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import re
import requests as http

app = Flask(__name__)
CORS(app)

RAPIDAPI_KEY  = os.environ.get('RAPIDAPI_KEY', '')
RAPIDAPI_HOST = 'social-download-all-in-one.p.rapidapi.com'

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0).rstrip("'\"") if match else text.strip()

def _make_filename(title, fallback='video'):
    safe = ''.join(c for c in (title or fallback) if c.isalnum() or c in ' _-').strip()[:60]
    return f"{safe or fallback}.mp4"

def fetch_via_rapidapi(url):
    if not RAPIDAPI_KEY:
        print('[RapidAPI] No API key set')
        return None

    headers = {
        'x-rapidapi-key':  RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST,
        'Content-Type':    'application/json',
    }
    try:
        resp = http.post(
            f'https://{RAPIDAPI_HOST}/v1/social/autolink',
            headers=headers,
            json={'url': url},
            timeout=30,
        )
        print(f'[RapidAPI] HTTP {resp.status_code}')
        print(f'[RapidAPI] Response: {resp.text[:300]}')

        if resp.status_code != 200:
            return None

        data = resp.json()
    except Exception as e:
        print(f'[RapidAPI] Exception: {e}')
        return None

    if data.get('status') != 'ok':
        print(f'[RapidAPI] Bad status: {data.get("status")} | {data}')
        return None

    links = data.get('url') or []
    video_url = None
    for link in links:
        ltype = link.get('type', '')
        lext  = link.get('ext', '')
        lqual = link.get('quality', '')
        if lext == 'mp4' or 'video' in ltype or 'hd' in lqual.lower():
            video_url = link.get('url')
            break
    if not video_url and links:
        video_url = links[0].get('url')

    if not video_url:
        print('[RapidAPI] No video URL found in response')
        return None

    title = data.get('title', 'video')
    print(f'[RapidAPI] Success: {title}')
    return {
        'url':       video_url,
        'title':     title,
        'filename':  _make_filename(title),
        'thumbnail': data.get('thumbnail'),
    }

def fetch_via_ytdlp(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][protocol=https]/best[ext=mp4]/best[protocol=https]/best',
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']},
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return None

    video_url = info.get('url')
    if not video_url:
        for f in reversed(info.get('formats') or []):
            if f.get('url') and f.get('protocol', '').startswith('http'):
                video_url = f['url']
                break

    if not video_url:
        return None

    title = info.get('title') or info.get('id') or 'video'
    return {
        'url':       video_url,
        'title':     title,
        'filename':  _make_filename(title, info.get('id', 'video')),
        'thumbnail': info.get('thumbnail'),
    }

@app.route('/')
def home():
    return jsonify({
        'status': 'DakaClip API is running',
        'rapidapi_key_set': bool(RAPIDAPI_KEY),
    })

@app.route('/api/video', methods=['POST'])
def get_video():
    data = request.get_json(silent=True) or {}
    raw  = data.get('url', '').strip()

    if not raw:
        return jsonify({'error': 'URL inahitajika'}), 400

    url    = extract_url(raw)
    result = None

    # 1) Try RapidAPI
    if RAPIDAPI_KEY:
        try:
            result = fetch_via_rapidapi(url)
        except Exception as e:
            print(f'[RapidAPI] Outer exception: {e}')
            result = None

    # 2) Fallback: yt-dlp
    if not result:
        print('[yt-dlp] Trying yt-dlp fallback...')
        try:
            result = fetch_via_ytdlp(url)
        except yt_dlp.utils.DownloadError as e:
            return jsonify({'error': str(e)}), 422
        except Exception as e:
            return jsonify({'error': f'Hitilafu: {str(e)}'}), 500

    if not result or not result.get('url'):
        return jsonify({'error': 'Imeshindwa kupata URL ya video'}), 500

    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
