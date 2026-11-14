# Install AnyGet

AnyGet runs in two Docker containers on your own computer or server: the API (downloads,
library, database) and the website. Docker is the easiest way on every system.

## With Docker (recommended)

1. Install Docker and Git (see your system below).
2. Get AnyGet and start it:

   ```sh
   git clone https://github.com/saurabh29p/Downloader.git anyget && cd anyget
   cp .env.example .env     # optional: every setting is explained inside
   make up                  # builds the images and starts AnyGet
   ```

3. Open **http://127.0.0.1:3000**.

The first build takes a few minutes (it installs FFmpeg, OCR and Deno into the API image).
Downloads go to `./downloads` and the database and settings to `./data`, both next to
`docker-compose.yml`. The ports are bound to `127.0.0.1`, so only your own computer can
open AnyGet until you set up [remote access](README.md#reach-it-from-elsewhere).

No `make`? Run `mkdir -p downloads data && PUID=$(id -u) PGID=$(id -g) docker compose up -d --build`.
`PUID`/`PGID` make your user the owner of the downloaded files (`make up` sets them for you).

Useful commands: `make logs` (follow the logs), `make ps` (status and health), `make down`
(stop). `ANYGET_WITH_OCR=1` in `.env` adds OCR for Japanese, Chinese, French, German,
Spanish and Russian (about 150 MB more; English, Hindi and Arabic are always included).

### Windows

- Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
  with the **WSL2** backend, and an Ubuntu distribution from the Microsoft Store.
- Open Ubuntu and run everything there: `sudo apt install git make`, then the commands above.
- Keep AnyGet in the Linux file system (`~/anyget`), not under `/mnt/c`: it is much faster
  and file permissions work. Windows can still open the files at `\\wsl$\Ubuntu\home\<you>\anyget\downloads`.

### macOS

- Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) (or
  another Docker runtime such as OrbStack or Colima).
- `git` and `make` come with the Xcode command line tools: `xcode-select --install`.

### Linux

- Install [Docker Engine and the Compose plugin](https://docs.docker.com/engine/install/)
  for your distribution, then add yourself to the `docker` group
  (`sudo usermod -aG docker $USER`, then log out and back in).
- Install `git` and `make` with your package manager.

### Raspberry Pi and other ARM computers

AnyGet's images are built from multi-architecture base images (Python, Node.js, Deno, uv), so
`make up` builds natively on a 64-bit ARM system such as a Raspberry Pi 4 or 5 with
Raspberry Pi OS (64-bit). This has not been tested by the maintainers yet; expect the first
build to take a while, and use an SSD rather than the SD card for `downloads/` if you can.
Please report how it goes in an issue.

## Updating

```sh
git pull
make up          # rebuilds the images and restarts AnyGet; your downloads and data stay
```

Video sites change often; if one stops working, update yt-dlp: see the
[README](../README.md#keep-yt-dlp-up-to-date). Read [CHANGELOG.md](../CHANGELOG.md) before a
major version: it lists anything you need to change.

**Back up first** for big updates: `make backup` (see the [README](../README.md#backups)).

## From source (for development)

```sh
make setup     # installs the Python and Node.js dependencies
make dev       # API on http://127.0.0.1:8000, website on http://127.0.0.1:3000
```

You need Node.js 24 with pnpm 10, Python 3.12 with uv, FFmpeg, and Deno for full YouTube
support. See [Development setup](setup.md).

## Removing AnyGet

```sh
make down                  # stops and removes the containers
docker image rm anyget-api anyget-web
```

Your files stay in `downloads/` and `data/` until you delete them yourself.
