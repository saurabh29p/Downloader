/** A 401 means the session ended: go to the sign-in page and come back afterwards. */
export function toSignIn() {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  const [, locale = "en", page] = pathname.split("/");
  if (page === "login") return;
  const next = encodeURIComponent(pathname + search);
  // A full load on purpose: it drops every cached query of the old session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/${locale}/login?next=${next}`);
}
