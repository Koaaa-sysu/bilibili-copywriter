"""
Bilibili WBI 搜索脚本 — 通用版
用法: python search_bilibili.py --keywords "关键词1" "关键词2" [--min-duration 5] [--min-plays 10000] [--top 20] [--output results.json]
"""
import argparse
import json
import hashlib
import time
import urllib.parse
import os
import requests
import sys

# 加载 config.env 中的 SSL_CERT_FILE（如果尚未设置）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(_SCRIPT_DIR, "..", "config.env")
if os.path.isfile(_ENV_FILE):
    with open(_ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "SSL_CERT_FILE" and v and not os.environ.get("SSL_CERT_FILE"):
                    os.environ["SSL_CERT_FILE"] = v

import ssl
if not os.environ.get("SSL_CERT_FILE"):
    # fallback: disable SSL verification if cert not found
    ssl._create_default_https_context = ssl._create_unverified_context


def get_wbi_keys():
    resp = requests.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    data = resp.json().get("data", {})
    img_url = data.get("wbi_img", {}).get("img_url", "")
    sub_url = data.get("wbi_img", {}).get("sub_url", "")
    return img_url.rsplit("/", 1)[-1].split(".")[0], sub_url.rsplit("/", 1)[-1].split(".")[0]


def enc_wbi(params, img_key, sub_key):
    tab = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
    raw = img_key + sub_key
    mk = "".join(raw[i] for i in tab)[:32]
    params["wts"] = round(time.time())
    params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mk).encode()).hexdigest()
    return params


def search_one(keyword, page=1, page_size=20):
    img_key, sub_key = get_wbi_keys()
    params = {"search_type": "video", "keyword": keyword, "page": page, "page_size": page_size, "order": "click"}
    signed = enc_wbi(params, img_key, sub_key)
    resp = requests.get(
        "https://api.bilibili.com/x/web-interface/wbi/search/all/v2",
        params=signed,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://search.bilibili.com/"},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"API error for '{keyword}': {data.get('message')}", file=sys.stderr)
        return []
    results = []
    for item in data.get("data", {}).get("result", []):
        if item.get("result_type") == "video":
            for v in item.get("data", []):
                title = v.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
                dur = v.get("duration", "")
                mins = 0
                if ":" in dur:
                    parts = dur.split(":")
                    mins = int(parts[0])
                results.append({
                    "bv": v.get("bvid", ""),
                    "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
                    "title": title,
                    "author": v.get("author", ""),
                    "plays": v.get("play", 0),
                    "duration": dur,
                    "mins": mins,
                    "desc": v.get("description", "")[:200],
                    "tag": v.get("tag", ""),
                    "keyword": keyword,
                })
    return results


def score_result(r):
    text = f"{r['title']} {r['desc']} {r['tag']}"
    s = 0
    positive = ["深度","思考","觉醒","成长","独立","女性","自我","接纳","勇敢","真实","内在","焦虑","内耗","讨好","拒绝","安全感","取悦","悦己","活出","爱自己","科普","心理学","亲密关系","性教育","性愉悦","身体","self"]
    negative = ["技巧","教程","攻略","推荐","测评","开箱","广告","带货"]
    for kw in positive:
        if kw in text:
            s += 5
    for kw in negative:
        if kw in text:
            s -= 3
    s += min(r.get("mins", 0), 20)
    plays = r.get("plays", 0)
    if isinstance(plays, int):
        if plays > 500000: s += 20
        elif plays > 100000: s += 15
        elif plays > 30000: s += 10
    return s


def main():
    parser = argparse.ArgumentParser(description="Bilibili WBI search")
    parser.add_argument("--keywords", nargs="+", required=True, help="搜索关键词列表")
    parser.add_argument("--min-duration", type=int, default=0, help="最短时长(分钟)，0=不过滤")
    parser.add_argument("--min-plays", type=int, default=0, help="最少播放量，0=不过滤")
    parser.add_argument("--top", type=int, default=20, help="输出前N条")
    parser.add_argument("--output", default="bilibili_search_results.json", help="输出JSON路径")
    args = parser.parse_args()

    all_results = []
    seen_bv = set()

    for kw in args.keywords:
        time.sleep(0.3)
        results = search_one(kw, page_size=20)
        added = 0
        for r in results:
            if r["bv"] not in seen_bv:
                seen_bv.add(r["bv"])
                all_results.append(r)
                added += 1
        print(f"[{kw}] found {len(results)}, added {added} new", file=sys.stderr)

    # Filter
    if args.min_duration > 0:
        all_results = [r for r in all_results if r.get("mins", 0) >= args.min_duration]
    if args.min_plays > 0:
        all_results = [r for r in all_results if isinstance(r.get("plays"), int) and r["plays"] >= args.min_plays]

    # Score and sort
    all_results.sort(key=score_result, reverse=True)
    output = all_results[:args.top]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nTotal unique: {len(all_results)}, output: {len(output)}", file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
