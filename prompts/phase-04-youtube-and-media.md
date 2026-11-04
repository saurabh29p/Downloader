# Phase 4 — YouTube and media (yt-dlp + ffmpeg)

Read `CLAUDE.md` and the YouTube table in `docs/plan.md` first.

Deliverables:
- `handlers/ytdlp.py`: probe via `extract_info(url, download=False)`; choices: best, 2160p, 1440p, 1080p, 720p, 480p, audio only (mp3/m4a), subtitles (manual + auto, languages, srt or embed). Format selectors like `bv*[height<=1080]+ba/b`; merge with ffmpeg; MP3 via `-x --audio-format mp3 --audio-quality 0` with embedded thumbnail and tags; `info.json`, chapters.
- Playlists: expand entries, select all/some, keep order in filenames. Channels: Videos/Shorts/Live tabs, date range, max count, `--download-archive`. Shorts like normal videos.
- Progress hook → job progress events. Resume partial files.
- Clear errors for members-only, paid, private and geo-blocked videos (no bypass).
- Web: YouTube page with quality picker, playlist item selector, subtitle picker.
- Setting + command to update yt-dlp.
- Tests with recorded `info_dict` fixtures; `live` tests with Creative Commons videos only.

**Acceptance check:** a CC video downloads as 720p and as MP3; a 3-item playlist downloads in order.
Commit: `feat: phase 4 youtube and media`.
