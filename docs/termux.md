# AnyGet on Android with Termux

Two ways to use AnyGet from an Android phone:

1. **Install the web app (easiest).** Open your AnyGet in Chrome, then *Settings → Install AnyGet* (or the browser menu → *Install app*). AnyGet then appears in Android's **Share** menu: share any link to it and the preview opens. This needs your AnyGet to be reachable from the phone, e.g. through Cloudflare Access or Tailscale (see the deploy guide).
2. **Termux.** Use this when you want a share button that works without opening a browser, or when you want AnyGet itself to run on the phone.

## Termux: send shared links to your AnyGet

1. Install [Termux](https://f-droid.org/packages/com.termux/) and, for notifications, [Termux:API](https://f-droid.org/packages/com.termux.api/) from F-Droid.
2. In Termux:

   ```sh
   pkg install curl python termux-api
   mkdir -p ~/bin ~/.config/anyget
   curl -fsSL -o ~/bin/termux-url-opener \
     https://raw.githubusercontent.com/<you>/<repo>/main/scripts/termux/termux-url-opener
   chmod +x ~/bin/termux-url-opener
   ```

   (Or copy `scripts/termux/termux-url-opener` from this repository to `~/bin/`.)
3. Tell it where your AnyGet is, in `~/.config/anyget/termux.env`:

   ```sh
   ANYGET_URL=https://dl.example.org
   ANYGET_TOKEN=            # the server's ANYGET_API_TOKEN, if you set one
   ANYGET_MODE=api
   ```

4. In any app, choose **Share → Termux**. The link goes to your AnyGet and a notification says whether it was queued. The download happens on your computer; open AnyGet's Downloads page to follow it.

The script only sends the first `http(s)` link it finds in the shared text, and only to the address in your config.

## Termux: run AnyGet on the phone

The CLI runs in Termux too (no website, no Docker):

```sh
pkg install python ffmpeg git
pip install uv
git clone https://github.com/<you>/<repo>.git anyget && cd anyget/apps/api
uv sync
uv run anyget get "https://example.org/file.pdf"
```

Files go to `./downloads` (set `ANYGET_DOWNLOADS_DIR=~/storage/downloads/AnyGet` after running `termux-setup-storage` to see them in Android's Files app). Set `ANYGET_MODE=cli` in `termux.env` so **Share → Termux** downloads on the phone with `anyget get`.

Deno (for full YouTube support) is not packaged for Termux; most other sites work without it.
