from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import re
import uuid
import requests as http

app = Flask(__name__)
CORS(app)

RAPIDAPI_KEY  = os.environ.get('RAPIDAPI_KEY', '')
RAPIDAPI_HOST = 'social-download-all-in-one.p.rapidapi.com'

CLICKPESA_CLIENT_ID = os.environ.get('CLICKPESA_CLIENT_ID', '')
CLICKPESA_API_KEY   = os.environ.get('CLICKPESA_API_KEY', '')
CLICKPESA_BASE_URL  = os.environ.get('CLICKPESA_BASE_URL', 'https://api.clickpesa.com')

_payments = {}

def clickpesa_headers():
    return {
        'Authorization': f'Bearer {CLICKPESA_API_KEY}',
        'client-id':     CLICKPESA_CLIENT_ID,
        'Content-Type':  'application/json',
    }

def normalize_tz_phone(phone):
    phone = re.sub(r'[^\d]', '', phone)
    if phone.startswith('0') and len(phone) == 10:
        phone = '255' + phone[1:]
    elif not phone.startswith('255'):
        phone = '255' + phone
    return phone

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0).rstrip("'\"") if match else text.strip()

def _make_filename(title, fallback='video'):
    safe = ''.join(c for c in (title or fallback) if c.isalnum() or c in ' _-').strip()[:60]
    return f"{safe or fallback}.mp4"

def _pick_video(medias):
    for m in medias:
        if m.get('type') == 'video' and (m.get('extension') or m.get('ext')) == 'mp4':
            q = m.get('quality', '').lower()
            if 'hd' in q and 'no_watermark' in q:
                return m.get('url')
    for m in medias:
        mtype = m.get('type', '')
        mext  = (m.get('extension') or m.get('ext') or '')
        murl  = m.get('url', '')
        if mtype == 'video' and mext == 'mp4' and murl and m.get('audioQuality'):
            return murl
    for m in medias:
        mtype = m.get('type', '')
        mext  = (m.get('extension') or m.get('ext') or '')
        murl  = m.get('url', '')
        if mtype == 'video' and mext == 'mp4' and murl:
            return murl
    for m in medias:
        if m.get('type') == 'video' and m.get('url'):
            return m.get('url')
    return None

def fetch_via_rapidapi(url):
    if not RAPIDAPI_KEY:
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
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        print(f'[RapidAPI] Exception: {e}')
        return None
    if data.get('error'):
        return None
    medias = data.get('medias') or []
    if not medias:
        return None
    video_url = _pick_video(medias)
    if not video_url:
        return None
    title = data.get('title') or 'video'
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
        'status':        'DakaClip API is running',
        'rapidapi_set':  bool(RAPIDAPI_KEY),
        'clickpesa_set': bool(CLICKPESA_CLIENT_ID and CLICKPESA_API_KEY),
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
    if not result:
        try:
            result = fetch_via_ytdlp(url)
        except yt_dlp.utils.DownloadError as e:
            return jsonify({'error': str(e)}), 422
        except Exception as e:
            return jsonify({'error': f'Hitilafu: {str(e)}'}), 500
    if not result or not result.get('url'):
        return jsonify({'error': 'Imeshindwa kupata URL ya video'}), 500
    return jsonify(result)

@app.route('/api/payment/initiate', methods=['POST'])
def initiate_payment():
    data   = request.get_json(silent=True) or {}
    phone  = data.get('phone', '').strip()
    amount = int(data.get('amount', 0))
    tokens = int(data.get('tokens', 0))

    if not phone or amount <= 0 or tokens <= 0:
        return jsonify({'error': 'Namba ya simu, kiasi, na tokens vinahitajika'}), 400

    if not CLICKPESA_CLIENT_ID or not CLICKPESA_API_KEY:
        return jsonify({'error': 'Malipo hayapatikani kwa sasa. Wasiliana na msaada.'}), 503

    phone     = normalize_tz_phone(phone)
    reference = f'DAKA-{uuid.uuid4().hex[:10].upper()}'
    _payments[reference] = {'status': 'pending', 'tokens': tokens, 'amount': amount}
    print(f'[Payment] Initiating {reference}: {phone} TZS {amount} for {tokens} tokens')

    try:
        resp = http.post(
            f'{CLICKPESA_BASE_URL}/third-parties/requests/ussd-push',
            headers=clickpesa_headers(),
            json={
                'amount':      amount,
                'currency':    'TZS',
                'phoneNumber': phone,
                'orderId':     reference,
                'description': f'DakaClip {tokens} tokens',
            },
            timeout=30,
        )
        print(f'[ClickPesa] HTTP {resp.status_code}: {resp.text[:300]}')
        if resp.status_code not in (200, 201, 202):
            _payments[reference]['status'] = 'failed'
            return jsonify({'error': 'Imeshindwa kutuma ombi la malipo. Angalia namba ya simu na jaribu tena.'}), 502
        return jsonify({'reference': reference})
    except Exception as e:
        print(f'[ClickPesa] Exception: {e}')
        _payments[reference]['status'] = 'failed'
        return jsonify({'error': f'Hitilafu: {str(e)}'}), 500

@app.route('/api/payment/callback', methods=['POST'])
def payment_callback():
    data = request.get_json(silent=True) or {}
    print(f'[ClickPesa Callback] {data}')
    reference = (
        data.get('orderId')
        or data.get('order_id')
        or data.get('reference')
        or ''
    )
    status = (data.get('status') or '').upper()
    if reference in _payments:
        if status in ('COMPLETED', 'SUCCESS', 'SUCCESSFUL', 'PAID'):
            _payments[reference]['status'] = 'completed'
            print(f'[Payment] {reference} COMPLETED')
        elif status in ('FAILED', 'CANCELLED', 'EXPIRED', 'REJECTED'):
            _payments[reference]['status'] = 'failed'
            print(f'[Payment] {reference} FAILED ({status})')
    return jsonify({'received': True})

@app.route('/api/payment/status/<reference>', methods=['GET'])
def payment_status(reference):
    payment = _payments.get(reference)
    if not payment:
        return jsonify({'error': 'Malipo hayapatikani'}), 404
    return jsonify({
        'status': payment['status'],
        'tokens': payment['tokens'] if payment['status'] == 'completed' else 0,
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
