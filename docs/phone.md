# AnyGet on your phone

AnyGet runs on a computer or a small server. Your phone opens it in the browser, and you can
install it so it works like an app. Downloads are saved on the computer running AnyGet; open
a file from the Library to watch, read or save it on the phone.

## 1. Reach AnyGet from the phone

AnyGet only listens on its own computer (`127.0.0.1`), so a phone needs a private way in:

- **[Tailscale](tailscale.md)** (easiest): install Tailscale on the computer and the phone,
  and open AnyGet at its Tailscale address. No domain needed, and only your devices can
  reach it.
- **[Cloudflare Tunnel + Access](deploy.md):** a web address such as
  `https://anyget.example.com`, protected by an email code. Needs a domain.
- **[A hosted AnyGet](hosted.md)** with the owner sign-in.

## 2. Install the app

Open AnyGet in the phone's browser, then:

- **Android (Chrome, Edge):** Settings → **Install AnyGet**, or the browser menu → *Install app*.
- **iPhone and iPad (Safari):** the Share button → *Add to Home Screen*.
- **Firefox on Android:** the menu → *Install* or *Add to Home screen*.

The installed app opens in its own window, without the browser's address bar.

## 3. Share links to AnyGet (Android)

Once installed, **AnyGet appears in Android's Share menu.** In any app (YouTube, a browser,
a chat), choose Share → AnyGet: AnyGet opens with the link already checked, ready to
download. On iPhone, copy the link and paste it into AnyGet's box.

## Listening on a phone

Audio plays in a mini-player that keeps going while you move between AnyGet's pages, with
lock-screen controls where the browser supports them. Playing with the screen locked or from
another app depends on the browser and the phone: Android Chrome usually keeps playing;
iPhone Safari usually does in a Safari tab, and less reliably in the app added to the Home
Screen. Your phone's battery settings may also stop it.

## Advanced: Termux on Android

[Termux](termux.md) can send shared links to your AnyGet from the command line, or run
AnyGet on the phone itself.
