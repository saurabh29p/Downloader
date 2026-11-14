# Troubleshooting

First steps for almost anything: `make ps` (are both containers healthy?) and `make logs`
(what went wrong?). In the app, a failed download shows a plain message, and **Details**
shows the technical one.

## Downloads

**A site that used to work now fails.** Sites change often; update yt-dlp first (see the
[README](../README.md#keep-yt-dlp-up-to-date)). Settings → Advanced → yt-dlp → Check for
updates shows the installed and latest versions. Still failing? Open a
["Site stopped working" issue](https://github.com/saurabh29p/Downloader/issues/new/choose).

**YouTube says "Sign in to confirm you're not a bot" or asks you to sign in.** YouTube limits
downloads, especially from servers and data centres. Run AnyGet from home, or add your own
account on the **Connections** page: export a `cookies.txt` from your browser while signed in
(the page explains how). It stays on your machine.

**"Members-only", "not available in your region", "borrow only", "DRM".** These are not
bugs. AnyGet never gets around them; it tells you why it stopped.

**archive.org or a library is slow.** AnyGet downloads at most 2 files at a time from
archive.org and the big libraries, and slows down when a site asks it to. That is on purpose.

**A video doesn't play in the browser.** Some formats (MKV, MOV) don't play in every browser.
Use **Download**, or pick MP4 in the format picker next time.

**Where are my files?** In `./downloads` next to `docker-compose.yml` (or in
`ANYGET_DOWNLOADS_DIR` when running from source). The Library has a Download button for each
file.

## Docker

**"Permission denied" or "unable to open database file" on Linux.** The `downloads` and
`data` folders must belong to your user. Start AnyGet with `make up` (it passes your user and
group ids), or run `PUID=$(id -u) PGID=$(id -g) docker compose up -d`. If the folders were
created by root earlier: `sudo chown -R $(id -u):$(id -g) downloads data`.

**Port 3000 or 8000 is already in use.** Stop the other program, or change the left-hand
port in `docker-compose.yml` (for example `"127.0.0.1:3001:3000"`).

**The website says the server can't be reached.** The API container may still be starting or
may have stopped: `make ps`, then `make logs`. Help → Server status shows whether the
website can reach the API.

**Windows: everything is very slow.** Keep the folder in the WSL2 Linux file system
(`~/anyget`), not under `/mnt/c` ([install.md](install.md#windows)).

## Sign-in and remote access

**The sign-in page shows "Set up the owner sign-in".** AnyGet is reachable from the internet
and no owner is set, so it refuses every request. Follow the steps on that page or in
[hosted.md](hosted.md).

**I forgot the password.** Make a new hash (`docker compose run --rm api anyget
hash-password`), put it in `ANYGET_OWNER_PASSWORD_HASH` and restart the API. Everyone is
signed out, because sessions are tied to the hash.

**The browser extension or the command line gets "401".** Set `ANYGET_API_TOKEN` on the
API and the same token in the extension's options (or the `Authorization: Bearer` header).

## Previews, OCR and audio

**No thumbnails or PDF previews (running from source).** Thumbnails need FFmpeg and
`pdftoppm` (poppler). The Docker image includes both.

**"The tool for this conversion is not installed."** OCR needs OCRmyPDF and Tesseract
(included in the Docker image). For languages beyond English, Hindi and Arabic, build with
`ANYGET_WITH_OCR=1`.

**Audio stops when the phone's screen locks.** That depends on the browser and the phone;
see [phone.md](phone.md#listening-on-a-phone).
