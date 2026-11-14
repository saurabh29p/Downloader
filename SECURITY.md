# Security policy

## Supported versions

AnyGet is maintained by volunteers. Security fixes go into `main` and the latest release.
Please update to the latest release before reporting.

| Version | Supported |
|---|---|
| Latest release and `main` | Yes |
| Older releases | No: please update |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

- Preferred: GitHub's private vulnerability reporting. Open the repository's **Security**
  tab and choose **Report a vulnerability**.
- Or email `<security contact email>`. <!-- TODO(owner): fill in before the repository is public. -->

Please include what you found, the steps to reproduce it (a small proof of concept
helps), which version or commit you tested, and how you run AnyGet (Docker, from source,
hosted). Never include real cookies, keys or passwords.

What to expect:

- We aim to acknowledge your report within **7 days** and to tell you whether we accept
  it within **14 days**.
- We fix accepted issues as fast as we can and credit you in the release notes, unless you
  prefer not to be named.
- Please give us a reasonable time (normally up to 90 days) to release a fix before you
  publish details.

## In scope

AnyGet fetches links that users paste, runs other programs and can be reachable from the
internet, so these matter most:

- **SSRF:** reaching private, loopback, link-local or cloud-metadata addresses, through a
  link, a redirect, DNS rebinding, IPv6 or IPv4 tricks, or through yt-dlp, FFmpeg or
  gallery-dl inputs.
- **Path traversal:** writing or reading outside the downloads or data folders, through
  file names, archives, symlinks or torrent metadata.
- **Authentication and access bypass:** the owner sign-in, session cookies, the bearer
  token, Cloudflare Access JWT checks, CSRF on writes, open redirects.
- **XSS and script injection:** in previews (EPUB, HTML, text, SVG, PDF), search results,
  file names or titles.
- **Command injection** in any program AnyGet starts.
- **Secret leaks:** cookies, API keys, tokens or passwords reaching logs, error messages,
  API responses or the optional AI helper.

## Not security issues

- Downloading copyrighted content. AnyGet follows strict legal rules (see the Legal page
  and [CONTRIBUTING.md](CONTRIBUTING.md)); misuse is the user's responsibility and is not
  a vulnerability.
- A site blocking AnyGet, asking it to sign in, or showing a bot check.
- Problems that need someone who already controls your machine or your AnyGet settings.
- Missing hardening that does not lead to a concrete attack (open a normal issue instead).
