import React, { useState } from "react";
import { Play } from "@phosphor-icons/react";
import { api } from "../api.js";
import PageHead from "../components/PageHead.jsx";
import Status from "../components/Status.jsx";
import DagGraph from "../components/DagGraph.jsx";

const today = () => new Date().toISOString().slice(0, 10);
const dur = (a, b) => (a && b ? `${Math.max(0, Math.round((new Date(b) - new Date(a)) / 1000))}s` : "—");

export default function Pipeline({ cfg, runs, sel, setSel, detail, setErr, refresh }) {
  const [form, setForm] = useState({ batch_id: today(), fail_source: "" });
  const trigger = async (e) => {
    e.preventDefault();
    try {
      const { run_id } = await api.trigger({ batch_id: form.batch_id, fail_source: form.fail_source || null });
      setSel(run_id); setErr(""); refresh();
    } catch (e2) { setErr(e2.message); }
  };
  return (
    <>
      <PageHead eyebrow="Orchestration" title="Pipeline runs" sub="Trigger a DAG run and follow each task live." />
      <form className="card" onSubmit={trigger}>
        <div className="card-body row wrap">
          <label className="field">Batch date
            <input className="input" type="date" required value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} />
          </label>
          <label className="field">Simulate failure
            <select className="input" value={form.fail_source} onChange={(e) => setForm({ ...form, fail_source: e.target.value })}>
              <option value="">None</option>
              {cfg && Object.keys(cfg.sources).map((s) => <option key={s} value={s}>{s} schema mismatch</option>)}
            </select>
          </label>
          <button className="btn btn-primary" type="submit"><Play size={16} weight="bold" aria-hidden="true" /> Trigger DAG run</button>
        </div>
      </form>

      <div className="grid">
        <div className="card">
          <div className="card-head"><h2>Run history</h2></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Batch</th><th>Trigger</th><th>Status</th><th>Duration</th><th>Rows</th></tr></thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className={`clickable ${r.run_id === sel ? "sel" : ""}`} onClick={() => setSel(r.run_id)}>
                    <td className="mono">{r.batch_id}</td><td><span className="tag">{r.trigger}</span></td>
                    <td><Status s={r.status} /></td><td>{dur(r.start_time, r.end_time)}</td><td>{r.rows_loaded}</td>
                  </tr>
                ))}
                {!runs.length && <tr><td colSpan="5" className="empty">No runs yet. Trigger one above.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h2>Task graph</h2>{detail && <Status s={detail.status} />}</div>
          <div className="card-body">
            {detail && cfg ? <DagGraph cfg={cfg} tasks={detail.tasks} /> : <div className="empty">Select a run.</div>}
          </div>
          {detail && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Task</th><th>Status</th><th>Tries</th><th>Rows</th><th>Message</th></tr></thead>
                <tbody>
                  {detail.tasks.map((t) => (
                    <tr key={t.task_id}><td className="mono">{t.task_id}</td><td><Status s={t.status} /></td>
                      <td>{t.attempts}</td><td>{t.rows}</td><td className="msg">{t.message}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
