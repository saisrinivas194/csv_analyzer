"""Rebuild backend/data/sec_sic_lookup.csv from the SEC's bulk submissions file.

Usage:  python refresh_sic.py "Your Name your@email.com"
The SEC requires a User-Agent with contact details. Downloads ~1.5 GB.
"""
import csv, json, os, sys, tempfile, urllib.request, zipfile

URL = 'https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sec_sic_lookup.csv')


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    tmp = os.path.join(tempfile.gettempdir(), 'sec_submissions.zip')
    print('Downloading', URL)
    req = urllib.request.Request(URL, headers={'User-Agent': sys.argv[1]})
    with urllib.request.urlopen(req) as r, open(tmp, 'wb') as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    rows = []
    with zipfile.ZipFile(tmp) as z:
        for n in z.namelist():
            if not n.endswith('.json') or '-submissions-' in n:
                continue
            d = json.loads(z.read(n))
            sic = (d.get('sic') or '').strip()
            if sic and sic != '0000':
                rows.append((int(d['cik']), sic, d.get('sicDescription', ''), d.get('name', ''), '|'.join(d.get('tickers') or [])))
    rows.sort()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cik', 'sic', 'sic_description', 'name', 'tickers'])
        w.writerows(rows)
    os.remove(tmp)
    print(f'Wrote {len(rows):,} companies to {OUT}')


if __name__ == '__main__':
    main()
