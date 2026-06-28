import requests
import subprocess
import os
import time
import tempfile

os.environ["SSL_CERT_FILE"] = r"C:\Users\Admin\anaconda3\envs\kan_cuda\lib\site-packages\certifi\cacert.pem"

FFMPEG = r"C:\Users\Admin\anaconda3\envs\kan_cuda\Library\bin\ffmpeg.exe"
PYTHON = r"C:\Users\Admin\anaconda3\envs\kan_cuda\python.exe"
WHISPER_PATH = r"C:\Users\Admin\anaconda3\envs\kan_cuda\Library\bin"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _extract_bvid(url_or_bvid):
    import re
    m = re.search(r'(BV[A-Za-z0-9]+)', url_or_bvid)
    return m.group(1) if m else url_or_bvid


def _get_video_url_snapany(bilibili_url):
    resp = requests.post(
        "https://api.snapany.com/v1/extract/post",
        json={"link": bilibili_url},
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    title = data.get("text", "unknown")
    for m in data.get("medias", []):
        if m.get("media_type") == "video":
            return title, m["resource_url"]
    return title, None


def _get_video_url_bilibili(bilibili_url):
    bvid = _extract_bvid(bilibili_url)
    headers = {
        "User-Agent": UA,
        "Referer": f"https://www.bilibili.com/video/{bvid}",
        "Origin": "https://www.bilibili.com",
    }
    info_resp = requests.get(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        headers=headers, timeout=15,
    )
    info_resp.raise_for_status()
    info = info_resp.json()["data"]
    title = info["title"]
    cid = info["cid"]
    play_resp = requests.get(
        f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1",
        headers=headers, timeout=15,
    )
    play_resp.raise_for_status()
    durl = play_resp.json()["data"]["durl"]
    return title, durl[0]["url"]


def get_video_url(bilibili_url):
    # 主方案：snapany.com（无需登录）
    try:
        title, url = _get_video_url_snapany(bilibili_url)
        if url:
            return title, url
    except Exception as e:
        print(f"  snapany failed: {e}, trying Bilibili API...")
    # 备用方案：B站官方 API
    return _get_video_url_bilibili(bilibili_url)


def download_video(video_url, output_path, max_retries=3):
    import gc
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(video_url, stream=True, timeout=120, headers=headers)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=256 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    del chunk
                    if total:
                        pct = downloaded / total * 100
                        mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        print(f"\r  {mb:.1f}MB / {total_mb:.1f}MB ({pct:.0f}%)", end="", flush=True)
            resp.close()
            del resp
            gc.collect()
            print()
            return output_path
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError,
                MemoryError) as e:
            print(f"\n  Attempt {attempt}/{max_retries} failed: {e}")
            try:
                resp.close()
            except Exception:
                pass
            if os.path.exists(output_path):
                os.remove(output_path)
            if attempt < max_retries:
                gc.collect()
                print(f"  Retrying in 3s...")
                time.sleep(3)
            else:
                raise RuntimeError(f"Download failed after {max_retries} attempts")


def extract_audio(video_path, audio_path):
    cmd = [FFMPEG, "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-500:]}")
    return audio_path


def transcribe(audio_path, output_path, work_dir):
    script = f'''
import ssl, os, time
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PATH"] = r"{WHISPER_PATH};" + os.environ.get("PATH", "")
import whisper

start = time.time()
try:
    model = whisper.load_model("turbo", device="cuda")
    fp16 = True
except Exception as e:
    print(f"CUDA failed ({{e}}), falling back to CPU")
    model = whisper.load_model("turbo", device="cpu")
    fp16 = False
print(f"Model loaded in {{time.time()-start:.1f}}s")

start = time.time()
result = model.transcribe(r"{audio_path}", language=None, fp16=fp16)
print(f"Transcribed in {{time.time()-start:.1f}}s (lang={{result.get('language','?')}})")

with open(r"{output_path}", "w", encoding="utf-8") as f:
    f.write(result["text"])
print("Done")
'''
    script_path = os.path.join(tempfile.gettempdir(), "_whisper_tmp.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([PYTHON, script_path], capture_output=True, text=True, timeout=1800, env=env, encoding="utf-8", errors="replace")
    print(result.stdout)
    try:
        os.remove(script_path)
    except OSError:
        pass

    if result.returncode != 0:
        raise RuntimeError(f"Whisper failed: {result.stderr[-500:]}")
    with open(output_path, "r", encoding="utf-8") as f:
        return f.read()


def run(bilibili_url, work_dir=None):
    if work_dir is None:
        work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)
    ts = str(int(time.time()))

    title, video_url = get_video_url(bilibili_url)
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:50]
    print(f"[1/4] {title}")
    if not video_url:
        raise RuntimeError("No video URL returned")

    video_path = os.path.join(work_dir, f"{safe}_{ts}.mp4")
    print(f"[2/4] Downloading...")
    download_video(video_url, video_path)

    audio_path = os.path.join(work_dir, f"{safe}_{ts}.wav")
    print(f"[3/4] Extracting audio...")
    extract_audio(video_path, audio_path)

    text_path = os.path.join(work_dir, f"{safe}_{ts}.txt")
    print(f"[4/4] Transcribing...")
    text = transcribe(audio_path, text_path, work_dir)

    print(f"\nDone -> {text_path}")
    return {"title": title, "text_path": text_path, "text": text}


if __name__ == "__main__":
    run("https://www.bilibili.com/video/BV1GJ411x7h7")
