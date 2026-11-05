import { DEFAULT_BASE, isLocal, normalizeBase, originPattern } from "./lib.js";

const api = globalThis.browser ?? globalThis.chrome;
const form = document.getElementById("form");
const status = document.getElementById("status");
/** @type {{ base: HTMLInputElement, token: HTMLInputElement }} */
const fields = {
  base: /** @type {HTMLInputElement} */ (document.getElementById("base")),
  token: /** @type {HTMLInputElement} */ (document.getElementById("token")),
};

const show = (text) => {
  status.textContent = text;
};

api.storage.sync.get({ base: DEFAULT_BASE, token: "" }).then((saved) => {
  fields.base.value = saved.base;
  fields.token.value = saved.token;
});

async function readForm() {
  const base = normalizeBase(fields.base.value);
  if (!isLocal(base)) {
    // Talking to a non-local AnyGet needs the user's OK for that one site.
    const granted = await api.permissions.request({ origins: [originPattern(base)] });
    if (!granted) throw new Error(`Permission for ${new URL(base).host} was not given`);
  }
  return { base, token: fields.token.value.trim() };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const values = await readForm();
    await api.storage.sync.set(values);
    fields.base.value = values.base;
    show("Saved.");
  } catch (error) {
    show(error.message);
  }
});

document.getElementById("test").addEventListener("click", async () => {
  try {
    const { base, token } = await readForm();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const response = await fetch(`${base}/api/health`, { headers });
    show(response.ok ? `Connected to ${base}.` : `${base} answered ${response.status}.`);
  } catch (error) {
    show(error instanceof TypeError ? "Could not reach AnyGet. Is it running?" : error.message);
  }
});
