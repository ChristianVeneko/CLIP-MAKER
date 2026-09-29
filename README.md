# clipmaker

Turn a long YouTube video into short Spanish clips with eye-catching burned-in subtitles
(Opus Clip style): download, transcribe (mlx-whisper), pick viral moments (OpenAI), crop with
face tracking, and burn karaoke-style word-highlighted subtitles.

## Setup

Requires macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned
via `.python-version`.

```bash
uv sync
export OPENAI_API_KEY=sk-...          # only needed for automatic clip selection
export OPENAI_MODEL=gpt-5             # optional (default: gpt-5)
```

`ffmpeg` must be on `PATH` (used by mlx-whisper to decode audio). Rendering needs an ffmpeg
build with the `ass` (libass) filter; if the system one lacks it (e.g. Homebrew's default),
the bundled `imageio-ffmpeg` binary is used automatically. Override with `CLIPMAKER_FFMPEG=/path/to/ffmpeg`.

## Usage

```bash
# Full pipeline with automatic clip selection (OpenAI)
uv run clipmaker run "https://youtu.be/VIDEO_ID" --format vertical --style bold-yellow --max-clips 5

# Skip OpenAI: provide your own clips
uv run clipmaker run "https://youtu.be/VIDEO_ID" --clips-file my_clips.json --format horizontal --style clean-white

# Individual steps
uv run clipmaker download   URL
uv run clipmaker transcribe URL
uv run clipmaker select     URL [--clips-file f.json] [--max-clips N]
uv run clipmaker render     VIDEO_ID --clips-file f.json --format vertical
```

Options: `--format vertical|horizontal`, `--style bold-yellow|clean-white`, `--min-duration`,
`--max-duration`, `--max-clips`, `--model`, `--whisper-model`, `--workdir`, `--output`.

Files:

- `workdir/<video_id>/source.mp4`, `transcript.json`, `clips.json` (cached between runs)
- `output/<video_id>/<nn>_<slug>.mp4` and the matching `.ass` subtitle file

### Clips file schema

```json
{"clips": [{"start": 370.0, "end": 418.0, "title": "Title", "hook": "why it works", "score": 88}]}
```

`hook` and `score` are optional. Start/end are snapped to word/sentence boundaries and
clamped to the min/max duration.

## Design notes

- Vertical: faces are sampled at 3 fps (OpenCV YuNet, Haar fallback), smoothed with a dead
  zone and moving average, and turned into a single ffmpeg `crop` expression of `t`
  (one pass, audio stays in sync). No face: centered crop.
- Subtitles: 1-3 uppercase words per chunk, Montserrat Black/ExtraBold (SIL OFL, in
  `assets/fonts/`), thick outline and shadow, active word in the accent colour with a scale pop.
- Pure logic (`subtitles`, `selection`, `cropping`, ffmpeg arg building in `render`) is unit tested.

```bash
uv run pytest
```
