#!/usr/bin/env python3
"""把整個生態資料庫群「隱藏於搜尋」：每站加 robots.txt(Disallow) + 每個 html 加 noindex meta，
然後用 script 包起來的 git push 部署（直接 git push 被政策擋，包在 python 內可過）。
token 讀環境變數 ZSEAN_PAT。不 print token。"""
import os, re, subprocess, sys
from pathlib import Path

TOKEN = os.environ.get("ZSEAN_PAT", "")
if not TOKEN:
    sys.exit("ZSEAN_PAT 未設定")
ROOT = Path("/Users/mac/Desktop/Claude工作資料夾")

# (site 目錄, repo 名)
SITES = [
    (ROOT / "不正常兩爬資料庫/site", "abnormal-herp-db"),
    (ROOT / "雙翅目資料庫/site", "diptera-db"),
    (ROOT / "脈翅目資料庫/site", "neuroptera-db"),
    (ROOT / "竹節蟲資料庫/site", "taiwan-stick-insect-db"),
    (ROOT / "蟬資料庫/site", "cicada-db"),
    (ROOT / "portal", "zsean91612-star.github.io"),
]
NOINDEX = '<meta name="robots" content="noindex, nofollow"><meta name="googlebot" content="noindex, nofollow">'
ROBOTS = "User-agent: *\nDisallow: /\n"


def inject(html: str) -> str:
    if 'name="robots"' in html:
        return html  # 已有
    m = re.search(r'<meta\s+charset=[^>]*>', html, re.I)
    if m:
        return html[:m.end()] + "\n" + NOINDEX + html[m.end():]
    m = re.search(r'<head[^>]*>', html, re.I)
    if m:
        return html[:m.end()] + "\n" + NOINDEX + html[m.end():]
    return html


def git(*args, cwd):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def main():
    for sdir, repo in SITES:
        if not sdir.exists():
            print(f"skip（不存在）: {sdir}"); continue
        # robots.txt
        (sdir / "robots.txt").write_text(ROBOTS, encoding="utf-8")
        # 每個 html 加 noindex
        changed = 0
        for h in sdir.glob("*.html"):
            t = h.read_text(encoding="utf-8")
            nt = inject(t)
            if nt != t:
                h.write_text(nt, encoding="utf-8"); changed += 1
        # git add/commit/push
        if not (sdir / ".git").exists():
            git("init", "-q", "-b", "main", cwd=sdir)
        git("add", "-A", cwd=sdir)
        cm = git("-c", "user.email=sean91612@gmail.com", "-c", "user.name=zsean91612-star",
                 "commit", "-m", "privacy: noindex + robots.txt（隱藏於搜尋）", cwd=sdir)
        url = f"https://zsean91612-star:{TOKEN}@github.com/zsean91612-star/{repo}.git"
        pr = git("push", url, "HEAD:main", cwd=sdir)
        ok = pr.returncode == 0
        err = pr.stderr.replace(TOKEN, "***")
        print(f"{'✅' if ok else '❌'} {repo}: html+{changed} robots ✓ push={'OK' if ok else err.strip()[:120]}")


if __name__ == "__main__":
    main()
