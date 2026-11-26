"""Download small CC0 pure-sky HDRIs; no asset/image generation service needed."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent':'CityG-Viewer-Sky-Preparation/1.0'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main():
    config = json.loads((ROOT/'configs/viewer_skies.json').read_text())
    target = ROOT/'assets/incoming/hdri/skies'
    target.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, preset in config['presets'].items():
        asset = preset['asset']
        info = json.loads(fetch(f'https://api.polyhaven.com/files/{asset}'))['hdri'][config['resolution']]['hdr']
        filename = f'{asset}_{config["resolution"]}.hdr'
        file = target/filename
        data = file.read_bytes() if file.is_file() else fetch(info['url'])
        if len(data) != info['size'] or hashlib.md5(data).hexdigest() != info['md5']:
            raise ValueError(f'Size/checksum mismatch: {asset}')
        if not file.exists():
            file.write_bytes(data)
        records[key] = {**preset,'file':filename,'source':f'https://polyhaven.com/a/{asset}',
                        'download_url':info['url'],'license':'CC0-1.0','bytes':len(data),
                        'sha256':hashlib.sha256(data).hexdigest()}
        print(f'{key}: {filename} ({len(data)/1024/1024:.1f} MiB)',flush=True)
    (target/'manifest.json').write_text(json.dumps({'version':1,'presets':records},indent=2)+'\n')


if __name__ == '__main__': main()
