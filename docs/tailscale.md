# Use AnyGet from anywhere with Tailscale (no domain needed)

[Tailscale](https://tailscale.com) connects your phone and your computer in a private
network (a *tailnet*). Only your own signed-in devices can reach AnyGet; nothing is public
and no router ports are opened. The free plan is enough.

1. Install Tailscale on the computer that runs AnyGet and on your phone, and sign in to
   the same account on both.
2. In the Tailscale admin console, turn on **MagicDNS** and **HTTPS certificates**
   (DNS → HTTPS Certificates).
3. Start AnyGet as usual (`make up`), then on that computer run:

   ```sh
   tailscale serve --bg 3000
   ```

   Tailscale prints an address like `https://my-pc.tail1234.ts.net`. It forwards to
   AnyGet's website on `127.0.0.1:3000` with a real HTTPS certificate.
4. On the phone (Tailscale on), open that address. Install the app from **Settings →
   Install AnyGet** to add it to the Share menu.

To stop sharing: `tailscale serve --https=443 off`.

Notes:
- Requests through `tailscale serve` reach AnyGet as local requests, so no Access login is
  asked: your tailnet already decides who gets in. Keep the tailnet to your own devices,
  or set `ANYGET_AUTH_MODE=always` with an `ANYGET_API_TOKEN`.
- Don't use **Funnel** (`tailscale funnel`) for AnyGet: it makes the address public to the
  whole internet. Use Cloudflare Access ([deploy.md](deploy.md)) for that.
