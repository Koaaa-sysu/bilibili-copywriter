# bilibili-copywriter

从B站视频自动提取文案素材的 Claude Code Skill，用于 Twitter / 小红书等平台配文。

## 功能

```
B站关键词搜索 → 视频下载 → 音频提取 → Whisper 转写 → Claude 提炼文案 → 可发布 Markdown
```

完整覆盖内容创作的素材采集链路，一条命令即可从选题到成稿。

## 依赖

| 依赖项 | 用途 | 备注 |
|--------|------|------|
| conda 环境 | Python 运行环境 | 需含 `requests`、`whisper` |
| ffmpeg | 音视频格式转换 | |
| CUDA GPU | Whisper turbo 加速 | 可退化为 CPU，转写速度慢 10-20 倍 |
| Claude Code | 文案提炼引擎 | 本 Skill 的运行宿主 |

## 安装

将 `bilibili-copywriter` 目录放入 Claude Code Skills 目录：

```bash
# 通常位于：
# ~/.claude/skills/bilibili-copywriter/

# 或通过 symlink：
ln -s /path/to/this/repo ~/.claude/skills/bilibili-copywriter
```

首次使用前，编辑 `config.env` 修改本机路径：

```env
PYTHON_PATH=C:\Users\你的用户名\anaconda3\envs\你的环境名\python.exe
FFMPEG_PATH=C:\Users\你的用户名\anaconda3\envs\你的环境名\Library\bin\ffmpeg.exe
SSL_CERT_FILE=C:\Users\你的用户名\anaconda3\envs\你的环境名\lib\site-packages\certifi\cacert.pem
```

## 使用

在 Claude Code 对话中直接描述需求即可触发：

```
帮我搜索B站关于"女性成长"的视频，下载并转写，提炼可发Twitter的文案
```

### 完整工作流程

**阶段一：搜索**
```bash
conda run -n kan_cuda python scripts/search_bilibili.py \
  --keywords "女性悦己" "亲密关系" \
  --min-duration 5 \
  --min-plays 10000 \
  --top 20 \
  --output results.json
```

**阶段二：下载 + 转写**

Claude 会自动调用项目中的 `pipeline.py` 处理选定视频。

**阶段三：文案提炼**

读取转写文本，按以下风格生成文案：
- 第一人称记录式
- 每个视频 2-4 条帖子
- 适合 Twitter 配图发布

**阶段四：输出**

整合到 `output/可发布文案_v*.md`，可直接复制发布。

## config.env 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `PYTHON_PATH` | conda Python 路径 | — |
| `FFMPEG_PATH` | ffmpeg 路径 | — |
| `SSL_CERT_FILE` | SSL 证书路径（解决证书错误） | — |
| `WHISPER_MODEL` | whisper 模型大小 | `turbo` |
| `WHISPER_DEVICE` | 运行设备 | `cuda` |
| `DEFAULT_OUTPUT_DIR` | 默认输出目录 | `output` |

## 搜索脚本参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keywords` | 搜索关键词（多个） | 必填 |
| `--min-duration` | 最短视频时长（分钟） | `0` |
| `--min-plays` | 最少播放量 | `0` |
| `--top` | 输出前 N 条 | `20` |
| `--output` | 结果 JSON 路径 | `bilibili_search_results.json` |

## 安全说明

- 搜索 API 参数自动 URL 编码，无注入风险
- `config.env` 包含本机路径，**请勿提交至公开仓库**
- SSL 证书 fallback 仅在 `SSL_CERT_FILE` 未设置时触发
- 视频下载通过第三方服务 snapany.com，可用性可能变化

## License

MIT
