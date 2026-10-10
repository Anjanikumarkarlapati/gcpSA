import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import DagGraph from "./DagGraph.jsx";

const today = () => new Date().toISOString().slice(0, 10);
const dur = (a, b) => (a && b ? `${Math.max(0, Math.round((new Date(b) - new Date(a)) / 1000))}s` : "—");
const Badge = ({ s }) => <span className={`badge ${s}`}>{s.replace(/_/g, " ")}</span>;

export default function App() {
  const [tab, setTab] = useState("pipeline");
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ batch_id: today(), fail_source: "" });

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.stats(), api.runs()]);
      setStats(s);
      setRuns(r);
      setSel((cur) => cur || r[0]?.run_id || null);
      if (sel) setDetail(await api.run(sel));
      setErr("");
    } catch (e) {
      setErr(e.message);
    }
  }, [sel]);

  useEffect(() => { api.config().then(setCfg).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [refresh]);

  const trigger = async (e) => {
    e.preventDefault();
    try {
      const { run_id } = await api.trigger({ batch_id: form.batch_id, fail_source: form.fail_source || null });
      setSel(run_id);
      setErr("");
    } catch (e2) {
      setErr(e2.message);
    }
  };

  return (
    <div className="app">
      <header>
        <div>
          <h1>Daily Multi-Source ETL</h1>
          <p className="sub">
            {cfg ? `${cfg.dag_id} · cron ${cfg.schedule}` : "connecting…"}
          </p>
        </div>
        {cfg && (
          <label className="toggle">
            <input
              type="checkbox"
              checked={cfg.schedule_enabled}
              onChange={async (e) => { await api.schedule(e.target.checked); setCfg({ ...cfg, schedule_enabled: e.target.checked }); }}
            />
            Daily schedule {cfg.schedule_enabled ? "on" : "off"}
          </label>
        )}
      </header>
      {err && <div className="error" role="alert">{err}</div>}

      <section className="stats">
        {[["Runs", stats?.runs], ["Success rate", stats?.success_rate != null ? `${stats.success_rate}%` : "—"],
          ["Avg duration", stats?.avg_duration_s != null ? `${stats.avg_duration_s}s` : "—"],
          ["Curated rows", stats?.curated_rows], ["Quarantined", stats?.quarantined_rows]].map(([k, v]) => (
          <div className="card stat" key={k}><span>{k}</span><strong>{v ?? "—"}</strong></div>
        ))}
      </section>

      <form className="card trigger" onSubmit={trigger}>
        <label>Batch date
          <input type="date" value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} required />
        </label>
        <label>Simulate failure
          <select value={form.fail_source} onChange={(e) => setForm({ ...form, fail_source: e.target.value })}>
            <option value="">None</option>
            {cfg && Object.keys(cfg.sources).map((s) => <option key={s} value={s}>{s} schema mismatch</option>)}
          </select>
        </label>
        <button type="submit">Trigger DAG run</button>
      </form>

      <nav>
        {["pipeline", "data", "quality", "quarantine"].map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>

      {tab === "pipeline" && (
        <div className="grid">
          <div className="card">
            <h2>Run history</h2>
            <table>
              <thead><tr><th>Batch</th><th>Trigger</th><th>Status</th><th>Duration</th><th>Rows</th></tr></thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className={r.run_id === sel ? "sel" : ""} onClick={() => setSel(r.run_id)}>
                    <td>{r.batch_id}</td><td>{r.trigger}</td><td><Badge s={r.status} /></td>
                    <td>{dur(r.start_time, r.end_time)}</td><td>{r.rows_loaded}</td>
                  </tr>
                ))}
                {!runs.length && <tr><td colSpan="5" className="empty">No runs yet — trigger one above.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h2>Task graph {detail && <Badge s={detail.status} />}</h2>
            {detail && cfg ? <DagGraph cfg={cfg} tasks={detail.tasks} /> : <p className="empty">Select a run.</p>}
            {detail && (
              <table className="tasks">
                <thead><tr><th>Task</th><th>Status</th><th>Tries</th><th>Rows</th><th>Message</th></tr></thead>
                <tbody>
                  {detail.tasks.map((t) => (
                    <tr key={t.task_id}><td>{t.task_id}</td><td><Badge s={t.status} /></td>
                      <td>{t.attempts}</td><td>{t.rows}</td><td className="msg">{t.message}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
      {tab === "data" && <Curated cfg={cfg} />}
      {tab === "quality" && (
        <div className="card">
          <h2>Data-quality results {detail && `· ${detail.batch_id}`}</h2>
          <table>
            <thead><tr><th>Source</th><th>Check</th><th>Status</th><th>Failed records</th></tr></thead>
            <tbody>
              {(detail?.dq || []).map((d, i) => (
                <tr key={i}><td>{d.source_system}</td><td>{d.check_name}</td><td><Badge s={d.check_status.toLowerCase()} /></td><td>{d.failed_records}</td></tr>
              ))}
              {!detail?.dq?.length && <tr><td colSpan="4" className="empty">No checks for this run.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {tab === "quarantine" && <Quarantine />}
    </div>
  );
}

function Curated({ cfg }) {
  const [source, setSource] = useState("");
  const [data, setData] = useState({ rows: [], summary: [] });
  useEffect(() => { api.curated(source).then(setData).catch(() => {}); }, [source]);
  return (
    <div className="card">
      <h2>Curated sales (BigQuery <code>etl_curated.sales</code>)</h2>
      <div className="chips">
        {data.summary.map((s) => <span className="chip" key={s.source_system}>{s.source_system}: {s.rows} rows · {s.total_amount}</span>)}
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {cfg && Object.keys(cfg.sources).map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      <table>
        <thead><tr><th>Record key</th><th>Customer</th><th>Amount</th><th>Date</th><th>Country</th><th>Batch</th></tr></thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.record_key}><td>{r.record_key}</td><td>{r.customer_id}</td><td>{r.amount.toFixed(2)}</td>
              <td>{r.txn_date}</td><td>{r.country}</td><td>{r.batch_id}</td></tr>
          ))}
          {!data.rows.length && <tr><td colSpan="6" className="empty">Nothing loaded yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function Quarantine() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.quarantine().then(setRows).catch(() => {}); }, []);
  return (
    <div className="card">
      <h2>Quarantined records</h2>
      <table>
        <thead><tr><th>Batch</th><th>Source</th><th>Reason</th><th>Record</th></tr></thead>
        <tbody>
          {rows.map((r, i) => <tr key={i}><td>{r.batch_id}</td><td>{r.source_system}</td><td><Badge s={r.reason} /></td><td className="msg">{r.record}</td></tr>)}
          {!rows.length && <tr><td colSpan="4" className="empty">No quarantined records.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
