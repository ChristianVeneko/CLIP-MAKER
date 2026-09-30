# clipmaker

Turn a long YouTube, Twitch or Kick video into short Spanish clips with eye-catching burned-in subtitles
(Opus Clip style): download, transcribe (mlx-whisper), pick viral moments (OpenAI), crop with
face tracking, and burn karaoke-style word-highlighted subtitles.

## Setup

Requires macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned
via `.python-version`.

```bash
uv sync
export OPENAI_API_KEY=sk-...                 # only needed for automatic clip selection
export OPENAI_MODEL_POWERFUL=gpt-5.6-sol     # optional override (default: gpt-5.6-sol)
export OPENAI_MODEL_LIGHT=gpt-5.6-terra      # optional override (default: gpt-5.6-terra)
```

`ffmpeg` must be on `PATH` (used by mlx-whisper to decode audio). Rendering needs an ffmpeg
build with the `ass` (libass) filter; if the system one lacks it (e.g. Homebrew's default),
the bundled `imageio-ffmpeg` binary is used automatically. Override with `CLIPMAKER_FFMPEG=/path/to/ffmpeg`.

## Usage

```bash
# Full pipeline with automatic clip selection (OpenAI)
uv run clipmaker run "https://youtu.be/VIDEO_ID" --genre podcast --max-clips 5 --caption-style mozi

# No OpenAI key needed: force explicit ranges as clips
uv run clipmaker run "https://youtu.be/VIDEO_ID" --moments "10:30-11:15, 25:00-26:10" \
    --aspect-ratio 1:1 --caption-style think_media --auto-zoom

# Only look at part of the video (cut before whisper, timestamps stay in source time)
uv run clipmaker run URL --time-range 10:00-30:00 --language en

# Provide your own transcript / clips
uv run clipmaker run URL --srt subs.srt --clips-file my_clips.json

# Individual steps
uv run clipmaker download   URL
uv run clipmaker transcribe URL [--time-range A-B] [--language es]
uv run clipmaker select     URL [--genre G] [--clip-length L] [--max-clips N]
uv run clipmaker render     VIDEO_ID --clips-file f.json --aspect-ratio 9:16
uv run clipmaker preview-styles VIDEO_ID --at 380     # output/style_previews/<preset>.png
```

### Supported platforms

| Platform | Accepted URLs | Notes |
|----------|---------------|-------|
| YouTube | `youtu.be/ID`, `youtube.com/watch?v=ID`, `/shorts/ID`, `/embed/ID` | Full download, cached as `workdir/<id>/` |
| Twitch | `clips.twitch.tv/SLUG`, `twitch.tv/CHANNEL/clip/SLUG`, `twitch.tv/videos/ID` | Cached as `workdir/twitch_<id>/` |
| Kick | `kick.com/CHANNEL/clips/clip_ID`, `kick.com/CHANNEL?clip=clip_ID`, `kick.com/CHANNEL/videos/UUID`, `kick.com/video/UUID` | Cached as `workdir/kick_<id>/`. Kick sits behind Cloudflare, so yt-dlp impersonates Chrome via `curl-cffi` (installed as `yt-dlp[curl-cffi]`) |

- **Live streams are rejected** (they never end): use the link of a finished clip or VOD.
- **Long VODs**: with `--time-range A-B` (or the range in the web UI) only that section of a Twitch/Kick VOD is downloaded
  (`--download-sections` + `--force-keyframes-at-cuts`) to `workdir/<platform>_<id>/source.rA-B.mp4`, cached per range.
  Clip and caption times stay relative to the original VOD (the pipeline knows the section starts at `A`),
  and explicit ranges in `--moments` are VOD times. `uv run clipmaker download URL --time-range A-B` does the same.
- **Short sources** (Twitch/Kick clips are often under a minute): when the whole source is not longer than the maximum clip
  length, it becomes a single clip with captions and reframing, and OpenAI is skipped (no API key needed).
- **Subscriber-only Twitch VODs** and other login-gated videos: set `CLIPMAKER_COOKIES_FROM_BROWSER` to a browser name
  (`chrome`, `safari`, `firefox`, ...) and yt-dlp reads that browser's cookies (`--cookies-from-browser`).
  Log in to the platform in that browser first.

### Options (`run`; the same set is the `JobOptions` model used by the web app)

| Flag | Values | Notes |
|------|--------|-------|
| `--model-tier` | `powerful` (default), `light` | Ids come from `$OPENAI_MODEL_POWERFUL` / `$OPENAI_MODEL_LIGHT`; `--model ID` overrides both |
| `--genre` | podcast, interview, educational, comedy, motivational, gaming, sports, news, vlog, other | Injects genre-specific guidance into the selection prompt |
| `--clip-length` | `auto`, `<30s`, `30-60s`, `60-90s`, `90s-3m` | Used in the prompt and as hard clamps after selection |
| `--max-clips` | 1-20 (default 5) | Forced ranges are never dropped |
| `--auto-zoom` | flag | Eased 1.0 to 1.12 punch-in on sentence starts / emphasis (`zoom.py`) |
| `--moments TEXT` | free text | Text goes to the prompt; ranges such as `10:30-11:15`, `1:00 to 1:30`, `de 2:00 a 2:45` are forced as clips. With ranges and no `OPENAI_API_KEY`, OpenAI is skipped |
| `--time-range A-B` | e.g. `10:30-25:00` | Audio is cut with ffmpeg before whisper; timestamps are re-offset; cached per range |
| `--aspect-ratio` | `9:16` (1080x1920), `1:1` (1080x1080), `4:5` (1080x1350), `16:9` (1920x1080) | Face-tracked crop for every non-16:9 ratio |
| `--language` | `auto`, `es`, `en`, `pt`, `fr`, `it`, `de`, ... | Whisper language; clip titles are written in it |
| `--srt FILE` | SRT path | Replaces whisper. Word timings are synthesised from cue durations weighted by word length |
| `--caption-style` | see below, or `none` | `bold-yellow` and `clean-white` are kept as aliases of `mozi` / `youshaei` |

Other flags: `--clips-file`, `--whisper-model`, `--workdir`, `--output`.

### Caption presets

Each preset is an ASS style plus per-word override tags (fonts in `assets/fonts/`, all SIL OFL):

| id | Look | Font |
|----|------|------|
| `karaoke` | white uppercase, 2 lines, words fill yellow as they are spoken | Montserrat Black |
| `deep_diver` | sentence case on a light-gray rounded box, spoken word dark | Barlow Condensed SemiBold |
| `youshaei` | uppercase single line, active word mint, soft shadow | Poppins SemiBold |
| `pod_p` | 1-2 words, active word magenta with darker edge | Anton |
| `mozi` | white uppercase, thick outline, active word bright green + pop | Montserrat Black |
| `beasty` | slanted heavy 1-3 words, strong bounce pop-in | Bangers |
| `simple` | 1-2 words, white with black outline, no colour change | Anton |
| `popline` | uppercase, active word on a purple rounded box | Montserrat ExtraBold |
| `think_media` | two lines, first white, second yellow | Bebas Neue |

`clipmaker.captions.preset_catalog()` returns a machine-readable catalog (id, display name,
font family, colours, ...) for UIs that render sample cards. Caption size follows the Opus scale
(about 80-100 px em size on a 1080-wide canvas, at most 2 lines, block at about 70% of the height)
and scales with the output size.

Files:

- `workdir/<video_id>/source.mp4`, `transcript*.json`, `clips.json` (cached between runs)
- `output/<video_id>/<nn>_<slug>.mp4` and the matching `.ass` caption file

### Clips file schema

```json
{"clips": [{"start": 370.0, "end": 418.0, "title": "Title", "hook": "why it works", "score": 88}]}
```

`hook` and `score` are optional. With `run --clips-file`, start/end are snapped to word/sentence
boundaries and clamped to the `--clip-length` range; `render` uses the file as is.

## Design notes

- Speaker-aware framing (`detection`, `speaker`, `framing`): faces (OpenCV YuNet with landmarks,
  Haar fallback) are sampled at 6 fps, small false positives (posters, logos) are filtered, and
  detections are associated into tracks. The active speaker is the track with the highest mouth-region
  frame-difference energy (brightness invariant, smoothed over 1 s), with hysteresis (needs 1.3x the
  current speaker's energy) and a 1.5 s minimum hold. A switch is a hard cut (a 1 ms ramp in the
  ffmpeg crop expression), which suits split-screen. If every visible face fits in the crop window
  they are framed together. Fallbacks: largest face when nobody is moving, then centred crop.
- Auto zoom: punch-ins are keyframes with smoothstep easing, emitted as one ffmpeg expression
  of `t` (`scale eval=frame` then a re-crop), tested against a Python evaluator.
- Captions: layout uses the real font metrics (fontTools), so highlight boxes line up with text;
  libass sizes fonts by ascent+descent, which is accounted for.
- Pure logic (`captions`, `selection`, `moments`, `srt`, `speaker`, `framing`, `zoom`, `cropping`,
  ffmpeg arg building in `render`) is unit tested.

```bash
uv run pytest
```


## Web app

A local single-user UI (FastAPI backend + React/Vite frontend in `web/`).

```bash
# Production-like: build the frontend once, then one process serves UI + API
cd web && npm install && npm run build && cd ..
uv run clipmaker serve                 # http://127.0.0.1:8000  (--host, --port, --workdir, --output)

# Development: backend on :8000, Vite dev server with hot reload and an /api proxy
uv run clipmaker serve &
cd web && npm run dev                  # http://localhost:5173  (CLIPMAKER_API overrides the proxy target)
```

`web/dist` is **not committed**: build it with `npm run build`. Without it, `serve` exposes only the API
(`/api/config`, `/api/probe`, `/api/uploads/{video,srt}`, `/api/jobs`, `/api/jobs/{id}`, `/api/jobs/{id}/clips`,
`/api/jobs/{id}/media/{file}`, `/api/fonts/{file}`).

- Jobs run one at a time in a background thread; progress is reported per stage (download, transcribe, select,
  render clip i/n). State is kept in memory and in `output/jobs/<id>/job.json`; finished jobs survive restarts,
  unfinished ones are marked failed. Clips and thumbnails live in `output/jobs/<id>/`.
- Without `OPENAI_API_KEY`, generation is only accepted when "Momentos específicos" contains explicit ranges
  (validated in the UI and the backend).
- Caption cards are drawn from `captions.preset_catalog()` using the fonts in `assets/fonts/`, served by the backend.
- Frontend tests: `cd web && npm test` (vitest, pure helpers). Backend tests: `uv run pytest`.
