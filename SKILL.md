---
name: bilibili-copywriter
description: 从B站视频提取文案素材：搜索→下载→Whisper转写→提炼可发布文案。用于Twitter/小红书等平台配文。
metadata:
  author: baba
  version: "1.0.0"
---

# bilibili-copywriter Skill

从B站视频自动提取文案素材的完整工具链：B站搜索 → 视频下载 → 音频提取 → Whisper转写 → Claude提炼文案 → 可发布 Markdown。

## 前置依赖

- **Python**: conda 环境 `kan_cuda`（含 whisper, requests）
- **ffmpeg**: 用于音视频转换
- **CUDA GPU**: whisper turbo 转写加速（可退化为 CPU，但慢）
- **网络**: 需要访问 bilibili API 和 snapany.com

## 配置

首次使用前，检查 `${CLAUDE_SKILL_DIR}/config.env` 中的路径是否与本机环境匹配：

```
PYTHON_PATH     — conda python.exe 路径
FFMPEG_PATH     — ffmpeg.exe 路径
SSL_CERT_FILE   — SSL 证书路径（解决证书问题）
WHISPER_MODEL   — 模型大小（默认 turbo）
WHISPER_DEVICE  — cuda 或 cpu
```

路径中的 `kan_cuda` 是当前用户的 conda 环境名，如果你使用不同环境请修改。

## 完整工作流程

### 阶段一：搜索 B 站视频

使用搜索脚本按关键词查找视频：

```bash
conda run -n kan_cuda python "${CLAUDE_SKILL_DIR}/scripts/search_bilibili.py" \
  --keywords "关键词1" "关键词2" "关键词3" \
  --min-duration 5 \
  --min-plays 10000 \
  --top 20 \
  --output "${WORK_DIR}/search_results.json"
```

**参数说明**:
- `--keywords`: 搜索关键词，支持多个
- `--min-duration`: 最短视频时长（分钟），建议 ≥5 分钟以保证内容深度
- `--min-plays`: 最少播放量，建议 ≥10000
- `--top`: 输出前 N 条结果（按相关度+播放量评分排序）
- `--output`: 结果 JSON 保存路径

**搜索完成后**：向用户展示结果列表（标题、作者、播放量、时长），让用户选择要处理的视频。

### 阶段一B：获取UP主全部视频（可选）

B站空间 API 需要 WBI 签名且反爬严格，推荐用 **浏览器 CDP** 从 DOM 提取：

1. 用 web-access skill 打开 `https://space.bilibili.com/{MID}/video`
2. 滚动到底部触发懒加载
3. 用 JS 从 `.upload-video-card` 提取数据：

```javascript
(() => {
  const cards = document.querySelectorAll(".upload-video-card");
  const seen = new Set();
  const videos = [];
  cards.forEach(card => {
    const link = card.querySelector("a.bili-cover-card");
    if (!link) return;
    const m = (link.getAttribute("href")||"").match(/(BV[a-zA-Z0-9]+)/);
    if (!m || seen.has(m[1])) return;
    seen.add(m[1]);
    const title = card.querySelector(".bili-video-card__title")?.getAttribute("title") || "";
    const stats = card.querySelectorAll(".bili-cover-card__stat span");
    videos.push({bv: m[1], title, play: stats[0]?.textContent?.trim(), duration: stats[2]?.textContent?.trim()});
  });
  return JSON.stringify(videos);
})()
```

**注意**：B站空间 API（`/x/space/wbi/arc/search`）需要 WBI 签名，未登录状态下频繁请求会被封 IP（-412/-352），不建议用纯 API 方式。

### 阶段二：下载 + 转写

对用户选定的视频，使用项目中的 `pipeline.py` 执行：

```bash
conda run -n kan_cuda python "D:/Desktop/文案获取/pipeline.py"
```

或批量处理，在项目目录下编写临时 batch 脚本（参考 `batch_run.py` 格式），然后执行：

```bash
conda run -n kan_cuda python "${WORK_DIR}/batch_tmp.py"
```

**pipeline.py 执行流程**:
1. 通过 snapany.com API 获取视频直链（主方案），失败时自动降级到 B站官方 API
2. 下载视频到 output 目录（带重试机制）
3. ffmpeg 提取音频为 16kHz WAV
4. Whisper turbo 转写为文本（CUDA 优先，失败自动降级 CPU）
5. 输出 `.txt` 文件到 output 目录

**预计耗时**:
- 搜索：~2秒/关键词
- 下载：取决于网速，通常 10-60秒
- 转写：GPU 约 1-3分钟/分钟视频，CPU 约 10-20倍

### 阶段三：提炼文案

读取转写文本（`.txt` 文件），提炼可发布文案。

**提炼规则**:
1. **风格**: 第一人称记录式，温暖但不保守，大胆但不低俗
2. **格式**: 每条帖子独立成段，可直接复制发 Twitter
3. **结构**: 每个视频提炼 2-4 条帖子
4. **内容类型**:
   - 金句/鸡汤句（适合配图发布）
   - 观点/论证（适合 thread 长文）
   - 科普知识（适合 carousel 图文）
5. **避免**: 过度露骨、男性视角、物化女性的表达
6. **关键词调性**: self-love, pleasure, empowerment, unapologetic, your body your rules

**文案模板**:

```markdown
### 帖子N：[小标题]

[第一人称引入语，如"今天看到/听到..."]

"[原文金句或转述观点，用引号包裹]"

[个人感悟/延伸解读，1-2句话]

---
```

### 阶段四：输出整理

将所有文案整合到一个 Markdown 文件：

```
output/可发布文案_v[N].md
```

文件格式：
```markdown
# 可发布文案素材 — 按视频分类

> 每条文案都来自B站视频转写，可直接发 Twitter。
> 长的可以拆篇，短的独立成帖。风格：第一人称记录式。

---

## 一、[视频主题标题]

**来源**: BV号 — 标题

### 帖子1：[小标题]
[文案内容]

---

### 帖子2：[小标题]
[文案内容]
```

## 安全注意事项

1. **API 限速**: B站搜索 API 有频率限制，关键词之间自动间隔 0.3 秒
2. **SSL 证书**: 部分环境需要设置 SSL_CERT_FILE 才能正常请求
3. **磁盘空间**: 每个视频约 50-200MB（视频+音频+转写），批量处理前检查剩余空间
4. **Whisper GPU 显存**: turbo 模型约需 4-6GB 显存，确保没有其他程序占满显存
5. **版权**: 转写文本用于个人内容创作参考，发布时需改写为原创文案，不可直接搬运
6. **snapany.com**: 第三方服务，可用性可能变化，如失败可更换下载源

## 常见问题

**Q: 搜索返回空结果**
A: 检查网络连接；B站 API 可能临时限流，稍后重试；确认关键词编码正确。

**Q: 下载失败（No video URL returned）**
A: snapany.com API 可能暂时不可用；视频可能设有权限限制；检查视频是否仍存在。

**Q: Whisper 报错 CUDA out of memory**
A: 关闭其他 GPU 程序；或将 config.env 中 `WHISPER_DEVICE=cpu`（会慢很多）。

**Q: 转写文本质量差**
A: 视频本身音质问题（背景音乐太大）；可尝试 `WHISPER_MODEL=large-v3` 但更慢。

## 目录结构

```
${CLAUDE_SKILL_DIR}/
├── .claude-plugin/plugin.json
├── SKILL.md          ← 本文件
├── config.env        ← 路径配置
└── scripts/
    └── search_bilibili.py  ← 通用搜索脚本
```

项目目录（`D:/Desktop/文案获取/`）：
```
├── pipeline.py       ← 核心处理流水线（搜索→下载→转写）
├── batch_run.py      ← 批量处理脚本模板
├── agents.md         ← 内容策略文档
└── output/
    ├── *.mp4         ← 下载的视频
    ├── *.wav         ← 提取的音频
    ├── *.txt         ← 转写文本
    └── 可发布文案_v*.md ← 最终文案
```
