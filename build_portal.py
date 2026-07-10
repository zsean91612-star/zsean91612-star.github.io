#!/usr/bin/env python3
"""
生成 portal/index.html —— 台灣生態社群資料庫入口首頁（標本櫃風格）。
每次更新任一資料庫後執行一次即可刷新卡片統計。
"""
import sqlite3, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent

# ── 日期只從兩個可信來源取得 ─────────────────────────────────────────────
# 1. posts.timestamp（爬蟲存入的貼文發布時間）
# 2. post_text 內明確寫出的日期字串。留言相對時間（「42週」）不可信，不使用。
DATE_PAT = re.compile(r'(20\d{2})[./年\-](1[0-2]|0?[1-9])[./月\-](3[01]|[12]\d|0?[1-9])')
DATE_NOISE = {'2023-11-07', '2023-11-08'}  # Messenger 洩漏假日期


def text_date(txt: str):
    if not txt:
        return None
    best = None
    for m in DATE_PAT.finditer(txt):
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        dt = f"{y}-{mo}-{d}"
        if dt in DATE_NOISE or dt < '2020-01-01':
            continue
        if best is None or dt > best:
            best = dt
    return best


def get_count(db_path: str) -> int:
    db = sqlite3.connect(db_path)
    n = db.execute("""
        SELECT COUNT(*) FROM ai_annotations a
        JOIN post_details d ON d.post_id=a.post_id
        WHERE a.category='wild_taiwan' AND d.quality_status='complete'
    """).fetchone()[0]
    db.close()
    return n


def get_species_count(db_path: str) -> int:
    db = sqlite3.connect(db_path)
    n = db.execute("""
        SELECT COUNT(DISTINCT species_common) FROM ai_annotations
        WHERE category='wild_taiwan'
          AND species_common IS NOT NULL AND species_common!=''
    """).fetchone()[0]
    db.close()
    return n


def get_latest(db_path: str) -> dict:
    """最新收錄 = timestamp 或 post_text 日期最大的那筆；只用可信來源，不猜估。"""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT p.post_url, p.timestamp,
               COALESCE(NULLIF(d.author,''),p.author,'') AS author,
               a.species_common, d.post_text
        FROM ai_annotations a
        JOIN post_details d ON d.post_id=a.post_id
        JOIN posts p ON p.post_id=a.post_id
        WHERE a.category='wild_taiwan' AND d.quality_status='complete'
          AND a.species_common IS NOT NULL
    """).fetchall()
    db.close()

    best = None
    for r in rows:
        ts = (r['timestamp'] or '')[:10]
        dt = ts if ts >= '2020-01-01' else text_date(r['post_text'] or '')
        if dt and (best is None or dt > best[0]):
            best = (dt, r['author'], r['species_common'] or '（未知）', r['post_url'])
    if best:
        return {'date': best[0], 'author': best[1], 'species': best[2], 'url': best[3]}

    # 無可信日期（如雙翅目）→ 退回收錄順序：FB 貼文 ID 隨時間遞增，取最大者近似最新收錄。
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    fr = db.execute("""
        SELECT p.post_url, COALESCE(NULLIF(d.author,''),p.author,'') AS author, a.species_common
        FROM ai_annotations a
        JOIN post_details d ON d.post_id=a.post_id
        JOIN posts p ON p.post_id=a.post_id
        WHERE a.category='wild_taiwan' AND d.quality_status='complete'
          AND a.species_common IS NOT NULL AND a.species_common!=''
        ORDER BY CAST(p.post_id AS INTEGER) DESC LIMIT 1
    """).fetchone()
    db.close()
    if fr:
        return {'date': None, 'author': fr['author'], 'species': fr['species_common'], 'url': fr['post_url']}
    return {}


# ── 資料庫清單 ───────────────────────────────────────────────────────────
SITES = [
    {
        'icon': '🎵', 'accent': '#d98a3d',
        'zh': '台灣蟬資料庫', 'latin': 'Cicadidae',
        'group': '台灣蟬保育學會',
        'db': '/Users/mac/Desktop/Claude工作資料夾/蟬資料庫/data/posts.db',
        'url': 'https://zsean91612-star.github.io/cicada-db/',
        'url_sp': 'https://zsean91612-star.github.io/cicada-db/species.html',
    },
    {
        'icon': '🌿', 'accent': '#8faa54',
        'zh': '台灣竹節蟲資料庫', 'latin': 'Phasmatodea',
        'group': '台灣竹節蟲同好會',
        'db': '/Users/mac/Desktop/Claude工作資料夾/竹節蟲資料庫/data/posts.db',
        'url': 'https://zsean91612-star.github.io/taiwan-stick-insect-db/',
        'url_sp': 'https://zsean91612-star.github.io/taiwan-stick-insect-db/species.html',
    },
    {
        'icon': '🍃', 'accent': '#4dba7f',
        'zh': '台灣脈翅目資料庫', 'latin': 'Neuropterida',
        'group': '台灣脈翅總目貼圖討論區',
        'db': '/Users/mac/Desktop/Claude工作資料夾/脈翅目資料庫/data/posts.db',
        'url': 'https://zsean91612-star.github.io/neuroptera-db/',
        'url_sp': 'https://zsean91612-star.github.io/neuroptera-db/species.html',
    },
    {
        'icon': '🪰', 'accent': '#5aa9c7',
        'zh': '台灣雙翅目資料庫', 'latin': 'Diptera',
        'group': '臺灣的雙翅目 Diptera of Taiwan',
        'db': '/Users/mac/Desktop/Claude工作資料夾/雙翅目資料庫/data/posts.db',
        'url': 'https://zsean91612-star.github.io/diptera-db/',
        'url_sp': 'https://zsean91612-star.github.io/diptera-db/species.html',
    },
]

tot_records = tot_species = 0
cards_html = []
for s in SITES:
    count = get_count(s['db'])
    species = get_species_count(s['db'])
    latest = get_latest(s['db'])
    tot_records += count
    tot_species += species

    latest_html = ''
    if latest:
        label = '最新收錄' if latest.get('date') else '近期收錄'
        date_part = f" · {latest['date']}" if latest.get('date') else ''
        latest_html = f"""
      <div class="latest">
        <span class="latest-k">{label}</span>
        <a class="latest-v" href="{latest['url']}" target="_blank" rel="noopener">
          <em>{latest['species']}</em> · {latest['author']}{date_part} ↗
        </a>
      </div>"""

    cards_html.append(f"""
  <article class="plate" style="--accent:{s['accent']}">
    <div class="plate-spine"></div>
    <div class="plate-body">
      <div class="plate-head">
        <span class="plate-icon">{s['icon']}</span>
        <div>
          <h2 class="plate-zh">{s['zh']}</h2>
          <div class="plate-latin"><em>{s['latin']}</em></div>
        </div>
      </div>
      <div class="plate-group">{s['group']}</div>
      <div class="chips">
        <span class="chip"><b>{count:,}</b>筆野外紀錄</span>
        <span class="chip"><b>{species}</b>物種</span>
      </div>{latest_html}
      <div class="plate-actions">
        <a class="btn btn-go" href="{s['url']}" target="_blank" rel="noopener">進入資料庫</a>
        <a class="btn btn-sp" href="{s['url_sp']}" target="_blank" rel="noopener">物種圖鑑</a>
      </div>
    </div>
  </article>""")

# ── 不正常兩爬（策展型，非物種圖鑑，單獨處理）──────────────────────────────
HERP_DB = '/Users/mac/Desktop/Claude工作資料夾/不正常兩爬資料庫/data/posts.db'
try:
    _h = sqlite3.connect(HERP_DB)
    herp_n = _h.execute("SELECT COUNT(*) FROM ai_annotations WHERE review_status='complete' AND highlight IS NOT NULL AND highlight!=''").fetchone()[0]
    herp_k = _h.execute("SELECT COUNT(*) FROM ai_annotations WHERE knowledge_text IS NOT NULL AND knowledge_text!=''").fetchone()[0]
    _h.close()
    tot_records += herp_n
    cards_html.append(f"""
  <article class="plate" style="--accent:#e2643c">
    <div class="plate-spine"></div>
    <div class="plate-body">
      <div class="plate-head">
        <span class="plate-icon">🦎</span>
        <div>
          <h2 class="plate-zh">不正常兩爬・精選庫</h2>
          <div class="plate-latin"><em>Abnormal Herp</em></div>
        </div>
      </div>
      <div class="plate-group">不正常兩棲爬行動物貼圖區</div>
      <div class="chips">
        <span class="chip"><b>{herp_n:,}</b>則精選</span>
        <span class="chip"><b>{herp_k}</b>則冷知識</span>
      </div>
      <div class="plate-actions">
        <a class="btn btn-go" href="https://zsean91612-star.github.io/abnormal-herp-db/" target="_blank" rel="noopener">進入資料庫</a>
        <a class="btn btn-sp" href="https://zsean91612-star.github.io/abnormal-herp-db/knowledge.html" target="_blank" rel="noopener">冷知識</a>
      </div>
    </div>
  </article>""")
    N_DB = len(SITES) + 1
except Exception as _e:
    N_DB = len(SITES)
    print("⚠️ 兩爬卡片略過：", _e)

updated = datetime.now().strftime('%Y-%m-%d')

HTML = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台灣生態社群資料庫</title>
<meta name="robots" content="noindex, nofollow">
<meta name="googlebot" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;700;900&family=Noto+Sans+TC:wght@400;500;700&family=Newsreader:ital,wght@1,400;1,500;1,600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#12181a; --bg2:#0d1214; --panel:#1a2225; --panel2:#212b2f;
    --ink:#ece7db; --sub:#a6b0ab; --muted:#7d8983; --line:#2b3439;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    font-family:"Noto Sans TC",-apple-system,sans-serif;
    background:
      radial-gradient(1200px 600px at 50% -10%, #1c2a2620, transparent),
      linear-gradient(180deg, var(--bg), var(--bg2));
    color:var(--ink); min-height:100vh;
    padding:clamp(2rem,6vw,4.5rem) 1.2rem 4rem;
    -webkit-font-smoothing:antialiased;
  }}
  em {{ font-family:"Newsreader",serif; font-style:italic; }}

  /* ── Hero ── */
  header {{ max-width:1080px; margin:0 auto clamp(2.2rem,5vw,3.4rem); text-align:center; }}
  .eyebrow {{
    font-size:.74rem; letter-spacing:.32em; text-transform:uppercase;
    color:var(--muted); margin-bottom:1rem; font-weight:500;
  }}
  h1 {{
    font-family:"Noto Serif TC",serif; font-weight:900;
    font-size:clamp(1.9rem,5.5vw,3.1rem); line-height:1.12; letter-spacing:.02em;
  }}
  .lede {{
    margin:1.1rem auto 0; max-width:34rem; color:var(--sub);
    font-size:clamp(.9rem,2.3vw,1.02rem); line-height:1.75;
  }}
  .ribbon {{
    display:inline-flex; flex-wrap:wrap; justify-content:center;
    gap:.2rem 1.6rem; margin-top:1.8rem; padding:.85rem 1.6rem;
    border:1px solid var(--line); border-radius:999px; background:#ffffff06;
  }}
  .ribbon .r {{ display:flex; align-items:baseline; gap:.4rem; }}
  .ribbon b {{ font-family:"Noto Serif TC",serif; font-size:1.35rem; font-weight:700; }}
  .ribbon span {{ font-size:.8rem; color:var(--muted); }}

  /* ── Grid ── */
  .grid {{
    display:grid; grid-template-columns:repeat(auto-fill, minmax(320px,1fr));
    gap:1.3rem; max-width:1080px; margin:0 auto;
  }}
  .plate {{
    position:relative; display:flex; overflow:hidden;
    background:linear-gradient(180deg, var(--panel), var(--panel2));
    border:1px solid var(--line); border-radius:16px;
    transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
  }}
  .plate:hover {{
    transform:translateY(-4px);
    border-color:color-mix(in srgb, var(--accent) 55%, var(--line));
    box-shadow:0 14px 34px #0007, 0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent);
  }}
  .plate-spine {{ width:6px; flex:0 0 6px; background:var(--accent); }}
  .plate-body {{ flex:1; padding:1.5rem 1.5rem 1.35rem; display:flex; flex-direction:column; }}
  .plate-head {{ display:flex; align-items:center; gap:.85rem; margin-bottom:.7rem; }}
  .plate-icon {{
    font-size:1.5rem; width:2.9rem; height:2.9rem; flex:0 0 2.9rem;
    display:grid; place-items:center; border-radius:12px;
    background:color-mix(in srgb, var(--accent) 16%, transparent);
    border:1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  }}
  .plate-zh {{ font-family:"Noto Serif TC",serif; font-size:1.24rem; font-weight:700; letter-spacing:.01em; }}
  .plate-latin {{ font-size:1rem; color:var(--accent); margin-top:.05rem; }}
  .plate-group {{
    font-size:.78rem; color:var(--muted); margin-bottom:1rem;
    padding-left:.7rem; border-left:2px solid var(--line);
  }}
  .chips {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-bottom:1rem; }}
  .chip {{
    display:inline-flex; align-items:baseline; gap:.3rem;
    background:#ffffff08; border:1px solid var(--line);
    border-radius:8px; padding:.34rem .7rem; font-size:.78rem; color:var(--sub);
  }}
  .chip b {{ font-family:"Noto Serif TC",serif; font-size:1.05rem; font-weight:700; color:var(--ink); }}
  .latest {{ margin-bottom:1.15rem; font-size:.78rem; line-height:1.5; }}
  .latest-k {{
    display:block; color:var(--muted); font-size:.68rem;
    letter-spacing:.14em; text-transform:uppercase; margin-bottom:.25rem;
  }}
  .latest-v {{ color:var(--sub); text-decoration:none; }}
  .latest-v em {{ color:var(--ink); font-size:.95rem; }}
  .latest-v:hover {{ color:var(--accent); }}
  .plate-actions {{ display:flex; gap:.55rem; margin-top:auto; }}
  .btn {{
    padding:.58rem 1rem; border-radius:9px; font-size:.85rem; font-weight:700;
    text-decoration:none; text-align:center; transition:filter .15s, background .15s;
  }}
  .btn-go {{ flex:1; background:var(--accent); color:#0c1214; }}
  .btn-go:hover {{ filter:brightness(1.12); }}
  .btn-sp {{ color:var(--sub); border:1px solid var(--line); background:#ffffff05; }}
  .btn-sp:hover {{ color:var(--ink); border-color:var(--accent); }}
  .btn:focus-visible, .latest-v:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

  footer {{
    max-width:1080px; margin:clamp(2.4rem,5vw,3.4rem) auto 0; text-align:center;
    color:var(--muted); font-size:.78rem; line-height:1.9;
    padding-top:1.6rem; border-top:1px solid var(--line);
  }}
  footer a {{ color:var(--sub); }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; scroll-behavior:auto; }} }}
</style>
</head>
<body>
<header>
  <div class="eyebrow">公民科學 · 田野觀察紀錄</div>
  <h1>台灣生態社群資料庫</h1>
  <p class="lede">把散落在 Facebook 社群的野外昆蟲照片與專家鑑定，整理成可搜尋、可瀏覽的觀察紀錄與物種圖鑑。</p>
  <div class="ribbon">
    <div class="r"><b>{N_DB}</b><span>個資料庫</span></div>
    <div class="r"><b>{tot_records:,}</b><span>筆野外紀錄</span></div>
    <div class="r"><b>{tot_species:,}</b><span>種昆蟲</span></div>
  </div>
</header>

<main class="grid">
{"".join(cards_html)}
</main>

<footer>
  資料來源為各 Facebook 社群公開貼文與留言鑑定，物種名以社群專家意見為準。<br>
  由觀察紀錄整理 · 蟲蟲工作室 · 最後更新 {updated}
</footer>
</body>
</html>
"""

out = ROOT / "index.html"
out.write_text(HTML, encoding="utf-8")
print(f"✅ portal/index.html 已生成（{updated}）")
print(f"   合計 {tot_records:,} 筆 · {tot_species} 物種 · {len(SITES)} 個資料庫")
for s in SITES:
    print(f"   {s['zh']}: {get_count(s['db'])} 筆 / {get_species_count(s['db'])} 種")

# ── Push（若有 PAT）──────────────────────────────────────────────────────
import subprocess, os
PAT = os.environ.get("ZSEAN_PAT", "")
if not PAT:
    try:
        import json as _json
        _cfg = _json.loads(Path.home().joinpath(".claude.json").read_text())
        PAT = (_cfg.get("env") or {}).get("ZSEAN_PAT", "")
    except Exception:
        pass
if PAT:
    AUTH = f"https://zsean91612-star:{PAT}@github.com/zsean91612-star/zsean91612-star.github.io.git"
    CLEAN = "https://github.com/zsean91612-star/zsean91612-star.github.io.git"
    subprocess.run(["git", "-C", str(ROOT), "remote", "set-url", "origin", AUTH], check=True)
    subprocess.run(["git", "-C", str(ROOT), "add", "index.html"], check=True)
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", f"update: {updated}"], check=True)
        subprocess.run(["git", "-C", str(ROOT), "push", "origin", "main"], check=True)
        print("🚀 已推送")
    subprocess.run(["git", "-C", str(ROOT), "remote", "set-url", "origin", CLEAN], check=True)
else:
    print("ℹ️  未設 ZSEAN_PAT，手動 push")
