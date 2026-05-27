import requests
import json
import re
from lxml import etree
from datetime import datetime, timezone, timedelta
import time

# enter your ListenBrainz token here (https://listenbrainz.org/settings/)
listenbrainz_token = 'listenbrainz_token_here'
# set your beginning timestamp here (https://www.epochconverter.com/)
min_timestamp = 946684800
file_path = r'file_path_here'

TIMEZONE_OFFSETS = {
    'CDT': -5, 'CST': -6,
    'EDT': -4, 'EST': -5,
    'PDT': -7, 'PST': -8,
    'MDT': -6, 'MST': -7,
}

# video/song title suffix edge cases to clean up for better matching
VIDEO_SUFFIXES_RE = re.compile(
    r'[\s\-–—]*'
    r'[\(\[]?'
    r'('
    r'official audio|official video|official music video|official lyric video|'
    r'lyric video|lyrics video|lyrics|visualizer|audio only|'
    r'live video|performance video|4k video|hd video|m/v|mv'
    r')'
    r'[\)\]]?'
    r'\s*$',
    re.IGNORECASE
)

# cleans track name of any common suffixes or artist name within
def clean_track_name(text, artist_name=None):
    if artist_name:
        text_normalized = re.sub(r'\s+', '', text).lower()
        artist_normalized = re.sub(r'\s+', '', artist_name).lower()
        if text_normalized.startswith(artist_normalized):
            text = re.sub(r'^.+?\s*[-–—]\s*', '', text, count=1)
    return VIDEO_SUFFIXES_RE.sub('', text).strip()

# cleans the artist names with VEVO suffixes
def clean_artist_name(text):
    if text.upper().endswith('VEVO'):
        return re.sub(r'(?i)VEVO$', '', text).strip()
    return text

# batching helper
def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

# parse the timestamp to Epoch from the format like "Mar 15, 2021, 10:30:00 PM PDT"
def parse_timestamp(text):
    text = re.sub(r'\s+', ' ', text).strip()
    m = re.match(r'(.+?)\s+([A-Z]{2,5})$', text)
    if not m:
        return None
    dt_str, tz_abbr = m.group(1), m.group(2)
    try:
        dt = datetime.strptime(dt_str, '%b %d, %Y, %I:%M:%S %p')
    except ValueError:
        return None
    offset = TIMEZONE_OFFSETS.get(tz_abbr, 0)
    dt = dt - timedelta(hours=offset)
    return int(dt.replace(tzinfo=timezone.utc).timestamp())

def parse_html_takeout(file_path, min_timestamp=0):
    entries = []
    skipped = []
    parser = etree.HTMLParser(encoding='utf-8')
    tree = etree.parse(file_path, parser)

    outer_cells = tree.findall('.//{*}div[@class="outer-cell mdl-cell mdl-cell--12-col mdl-shadow--2dp"]')
    print(f"Total entries in file: {len(outer_cells)}")

    for outer in outer_cells:
        header = outer.find('.//{*}div[@class="header-cell mdl-cell mdl-cell--12-col"]')
        if header is None:
            continue
        if 'YouTube Music' not in ''.join(header.itertext()):
            continue

        content = outer.find('.//{*}div[@class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1"]')
        if content is None:
            continue

        full_text = ' | '.join(content.itertext()).strip()

        anchors = content.findall('.//{*}a')
        if len(anchors) < 2:
            skipped.append(('not enough anchors', full_text))
            continue

        title_url = anchors[0].get('href', '')
        if not title_url or 'watch?v=' not in title_url:
            skipped.append(('no watch url', full_text))
            continue

        if anchors[1].text and anchors[1].text == 'tm':
            title_url = anchors[0].get('href', '')
            track_name = anchors[0].text.split(' - ')[0].strip() if anchors[0].text else ''
            artist_name = anchors[0].text.split(' - ')[1].strip() if anchors[0].text else ''
        elif anchors[1].text and 'Topic' in anchors[1].text:
            title_url = anchors[0].get('href', '')
            track_name = anchors[0].text.split(' - ')[0].strip() if anchors[0].text else ''
            artist_name = anchors[1].text.split(' - ')[0].strip() if anchors[0].text else ''
        else:
            title_url = anchors[0].get('href', '')
            track_name = ''.join(anchors[0].itertext()).strip()
            artist_name = ''.join(anchors[1].itertext()).strip()

        if not track_name or not artist_name:
            skipped.append(('empty track or artist', full_text))
            continue

        artist_name = clean_artist_name(artist_name)
        track_name = clean_track_name(re.sub(r'^Watched\s+', '', track_name), artist_name=artist_name)


        timestamp_str = None
        for br in content.findall('.//{*}br'):
            if br.tail and re.search(r'\d{4}', br.tail):
                timestamp_str = br.tail.strip()
                break

        if not timestamp_str:
            skipped.append(('no timestamp', full_text))
            continue

        listened_at = parse_timestamp(timestamp_str)
        if listened_at is None:
            skipped.append(('timestamp parse failed', full_text))
            continue
        if listened_at < min_timestamp:
            skipped.append(('before min_timestamp', full_text))
            continue

        entries.append({
            'listened_at': listened_at,
            'track_metadata': {
                'artist_name': artist_name,
                'track_name': track_name,
                'additional_info': {
                    'music_service': 'music.youtube.com',
                    'origin_url': title_url,
                    'submission_client': 'https://github.com/BlakeAlvarez/YTMusic-ListenBrainz-Importer',
                }
            }
        })

    print(f"Parsed {len(entries)} YouTube Music entries")
    print(f"Skipped {len(skipped)} entries")

    if skipped:
        with open('skipped.log', 'w', encoding='utf-8') as f:
            for reason, text in skipped:
                f.write(f"[{reason}]\n{text}\n\n")
        print("Skipped entries written to skipped.log")

    with open('parsed_entries.json', 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    
    return entries

def submit_to_listenbrainz(entries, token):
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json'
    }
    listenbrainz_url = 'https://api.listenbrainz.org/1/submit-listens'

    print(f"Submitting {len(entries)} listens...")
    responses = []

    for i, listen_batch in enumerate(batch(entries, 1000), 1):
        payload = {
            'listen_type': 'import',
            'payload': listen_batch
        }
        response = requests.post(listenbrainz_url, headers=headers, data=json.dumps(payload))
        print(f"Batch {i}: submitted {len(listen_batch)} listens")
        if not response.ok:
            print(f"  Error: {response.text}")
        reset_in = int(response.headers.get('X-RateLimit-Reset-In', 1))
        time.sleep(reset_in)
        responses.append(response)

    return responses

entries = parse_html_takeout(
    file_path if file_path != 'file_path_here' else 'watch-history.html',
    min_timestamp=min_timestamp
)

responses = submit_to_listenbrainz(entries, listenbrainz_token)
