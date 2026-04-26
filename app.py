from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'DakaClip API is running'})

@app.route('/api/video', methods=['POST'])
def get_video():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL inahitajika'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # Best single-file mp4 with direct https URL (no HLS/DASH manifests)
        'format': 'best[ext=mp4][protocol=https]/best[ext=mp4]/best[protocol=https]/best',
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return jsonify({'error': 'Video haikupatikana'}), 404

        # Resolve direct URL — handle both flat and format-list results
        video_url = info.get('url')
        if not video_url:
            formats = info.get('formats') or []
            # Pick last (best) format that has a direct url
            for f in reversed(formats):
                if f.get('url') and f.get('protocol', '').startswith('http'):
                    video_url = f['url']
                    break

        if not video_url:
            return jsonify({'error': 'Imeshindwa kupata URL ya video'}), 500

        vid_id  = info.get('id') or 'video'
        title   = info.get('title') or vid_id
        # Sanitise filename
        safe    = ''.join(c for c in title if c.isalnum() or c in ' _-').strip()[:60]
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
        return jsonify({'error': f'Hitilafu ya seva: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
