# User guide

## Paste a link

Paste one link, many links (one per line), or a `.txt` list into the box on **Home**, or drop
it anywhere in the app. AnyGet checks the link (*Reading link → Finding formats → Ready*) and
shows what is behind it:

- **Videos and audio** (1,800+ sites through yt-dlp): pick a quality, or **Audio only** (MP3
  and other formats), subtitles, and whether to add the cover and tags. Playlists and
  channels list their items so you can pick some or all.
- **archive.org items, code repositories, galleries and web pages:** pick the files you want.
- **Library items** (IIIF): every page at full size, or one merged PDF.
- **Direct file links** download as they are, with resume if the connection drops.

Press **Download**. The **Downloads** page shows live progress, and each download can be
paused, resumed, cancelled, retried or removed (with Undo). **Retry all failed** retries
every failed one at once. When a site gives a checksum, AnyGet verifies the file
("Checksum OK").

Typing words instead of a link searches everything (below). The chips under the box (Movies,
Books, Music…) narrow the search to one section.

## Search everything and Sections

**Search** asks archive.org, the book sources, the world's libraries and video sites at once,
and shows results as they arrive. Each result shows its kind, source, year and licence, with
Preview, Download, Save to Library and Open source.

**Sections** (Movies, Books, Music, Video, Declassified, Maps, Newspapers, Photos,
Manuscripts…) group ready-made searches and official sites. Movies shows where to watch a
film legally (with a free TMDB key in Connections) plus public-domain classics.

**Books** finds the best legal copy across Project Gutenberg, Standard Ebooks, Open Library,
the Internet Archive, Wikisource, HathiTrust and national libraries: full view first, then
EPUB, text PDF, scanned PDF and page images. Books still in copyright are shown as "not
legally downloadable", with links to borrow or buy them. **Libraries** lists national
libraries by region; paste an item link to save its pages.

## The Library

Every finished download appears in the **Library**. You can:

- search titles **and the text inside files** (PDF text, EPUB, HTML, text, and scanned PDFs
  after OCR), and filter by kind, section, source and licence;
- open files in AnyGet itself:
  - **video**: speed, subtitles from `.srt`/`.vtt` files saved next to it, resume where you
    left off;
  - **audio**: a mini-player at the bottom that keeps playing while you move between pages,
    with lock-screen controls where the browser supports them;
  - **PDF** (pages, zoom, search), **EPUB** (contents, font size, remembers your place; the
    book's own HTML and scripts never run), **text** (paged, search) and **pictures** (zoom,
    full screen, previous/next);
  - other files (office documents, archives) get a short reason plus Download / Open;
- tag files into collections, find copies of the same file, and remove what you don't need;
- **Scan folder** to add files you copied into the downloads folder yourself.

Some formats (MKV, MOV) don't play in every browser; AnyGet says so and offers Download. It
never converts a file unless you ask.

## Watches

A **watch** checks a channel, playlist or archive.org collection on a schedule (from every
hour to once a week) and downloads only what is new. The first check fetches the newest
few items you choose and marks everything older as seen. Watches run while the API is running.

## Convert and OCR

From **Downloads**, a finished file can be converted: save audio as MP3, merge page images
into one PDF, or make a scanned PDF searchable with **OCR** (`<name> (OCR).pdf` plus a text
file). OCR reads English, Hindi and Arabic out of the box; see [Install](install.md) for more
languages.

## Connections

**Connections** keeps your own accounts and free API keys, encrypted on your machine:

- **Sites you sign in to** (YouTube, Instagram, X, Facebook, Reddit, Vimeo…): add a
  `cookies.txt` exported from your browser while you are signed in, so AnyGet downloads what
  your account can see. Use only your own accounts. AnyGet never gets around members-only,
  paid or region-blocked content.
- **Free keys** for GitHub, Hugging Face, Kaggle, TMDB (Movies) and library APIs (Europeana,
  DPLA, Trove, DigitalNZ, Biodiversity Heritage Library, Deutsche Digitale Bibliothek): more
  results and higher limits.

When a download fails because a site wants a sign-in, the error links straight to that
site's Connections entry.

## AI helper (optional)

With an [OpenRouter](https://openrouter.ai) key (Connections → OpenRouter), search gets
smarter plans, short answers to questions with sources, and better ordering. **Everything
works without it.** Settings → AI helper has a **free mode** (only free models) and a daily
limit. AnyGet never sends cookies, keys, passwords or file contents to the AI helper.

## Cleaning up old files (off by default)

Downloaded files are **kept forever** by default. To have old files removed, set a number of
days in Settings → Downloads (or `ANYGET_RETENTION_DAYS`; `0` turns it off again).

- The first removals happen that many days after you switch it on, so turning it on never
  deletes old files at once.
- Files tagged `keep`, and downloads still running, are never removed.
- Only files AnyGet saved and indexed are considered; nothing outside the downloads folder is
  touched.
- The Library keeps an entry for each removed file, with **Download again**.
- `uv run anyget cleanup` lists what would be removed (it deletes nothing); `--apply` runs it.

## Torrents (off by default)

Magnet links and `.torrent` files are **off by default**. Torrent peers are other people's
computers, outside AnyGet's network guard, so use them only for files you may share (Linux
images, public-domain films, Creative Commons releases). To allow them when you run AnyGet
from source, install the optional engine (`cd apps/api && uv sync --extra torrent`; the
Docker image does not include it) and switch them on in Settings → Advanced.
