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

def _pick_video(medias):
    # 1. TikTok HD no-watermark mp4
    for m in medias:
        if m.get('type') == 'video' and (m.get('extension') or m.get('ext')) == 'mp4':
            q = m.get('quality', '').lower()
            if 'hd' in q and 'no_watermark' in q:
                return m.get('url')

    # 2. YouTube/other: mp4 video with audio (combined stream)
    for m in medias:
        mtype = m.get('type', '')
        mext  = (m.get('extension') or m.get('ext') or '')
        murl  = m.get('url', '')
        if mtype == 'video' and mext == 'mp4' and murl and m.get('audioQuality'):
            return murl

    # 3. Any mp4 video
    for m in medias:
        mtype = m.get('type', '')
        mext  = (m.get('extension') or m.get('ext') or '')
        murl  = m.get('url', '')
        if mtype == 'video' and mext == 'mp4' and murl:
            return murl

    # 4. Any video
    for m in medias:
        if m.get('type') == 'video' and m.get('url'):
            return m.get('url')

    return None

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
        if resp.status_code != 200:
            print(f'[RapidAPI] Non-200: {resp.text[:200]}')
            return None
        data = resp.json()
    except Exception as e:
        print(f'[RapidAPI] Exception: {e}')
        return None

    if data.get('error'):
        print('[RapidAPI] Error flag in response')
        return None

    medias = data.get('medias') or []
    if not medias:
        print('[RapidAPI] No medias array in response')
        return None

    video_url = _pick_video(medias)
    if not video_url:
        print('[RapidAPI] No suitable video found in medias')
        return None

    title = data.get('title') or 'video'
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

    if RAPIDAPI_KEY:
        try:
            result = fetch_via_rapidapi(url)
        except Exception as e:
            print(f'[RapidAPI] Outer exception: {e}')
            result = None

    if not result:
        print('[yt-dlp] Trying fallback...')
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
