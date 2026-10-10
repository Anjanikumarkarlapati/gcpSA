async function req(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
export const api = {
  config: () => req("/api/config"),
  stats: () => req("/api/stats"),
  runs: () => req("/api/runs"),
  run: (id) => req(`/api/runs/${id}`),
  curated: (source) => req(`/api/curated?limit=50${source ? `&source=${source}` : ""}`),
  quarantine: () => req("/api/quarantine?limit=100"),
  trigger: (body) =>
    req("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  schedule: (enabled) => req(`/api/schedule?enabled=${enabled}`, { method: "POST" }),
};
