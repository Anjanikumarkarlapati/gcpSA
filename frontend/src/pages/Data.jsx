import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import PageHead from "../components/PageHead.jsx";
import Status from "../components/Status.jsx";

export default function Data({ cfg, detail }) {
  const [tab, setTab] = useState("curated");
  return (
    <>
      <PageHead eyebrow="Warehouse" title="Data & quality" sub="Curated output, data-quality checks and quarantined records." />
      <div className="tabs" role="tablist">
        {[["curated", "Curated"], ["quality", "Quality checks"], ["quarantine", "Quarantine"]].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "curated" && <Curated cfg={cfg} />}
      {tab === "quality" && <Quality detail={detail} />}
      {tab === "quarantine" && <Quarantine />}
    </>
  );
}

function Curated({ cfg }) {
  const [source, setSource] = useState("");
  const [data, setData] = useState({ rows: [], summary: [] });
  useEffect(() => { api.curated(source).then(setData).catch(() => {}); }, [source]);
  return (
    <div className="card">
      <div className="card-head">
        <h2>Curated sales <code>etl_curated.sales</code></h2>
        <select className="input input-sm" aria-label="Filter by source" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {cfg && Object.keys(cfg.sources).map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      <div className="card-body row wrap">
        {data.summary.map((s) => <span className="tag" key={s.source_system}>{s.source_system}: {s.rows} rows · {s.total_amount}</span>)}
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Record key</th><th>Customer</th><th>Amount</th><th>Date</th><th>Country</th><th>Batch</th></tr></thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.record_key}><td className="mono">{r.record_key}</td><td>{r.customer_id}</td><td>{r.amount.toFixed(2)}</td>
                <td>{r.txn_date}</td><td>{r.country}</td><td className="mono">{r.batch_id}</td></tr>
            ))}
            {!data.rows.length && <tr><td colSpan="6" className="empty">Nothing loaded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Quality({ detail }) {
  const dq = detail?.dq || [];
  const issues = dq.filter((d) => d.check_status === "FAILED").length;
  return (
    <>
      {issues > 0 && <div className="banner banner-critical" role="alert">{issues} check{issues > 1 ? "s" : ""} failed in the selected run. Downstream loading was stopped.</div>}
      <div className="card">
        <div className="card-head"><h2>Data-quality results {detail && <span className="mono">{detail.batch_id}</span>}</h2></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Source</th><th>Check</th><th>Status</th><th>Failed records</th></tr></thead>
            <tbody>
              {dq.map((d, i) => <tr key={i}><td>{d.source_system}</td><td className="mono">{d.check_name}</td><td><Status s={d.check_status} /></td><td>{d.failed_records}</td></tr>)}
              {!dq.length && <tr><td colSpan="4" className="empty">No checks for the selected run.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Quarantine() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.quarantine().then(setRows).catch(() => {}); }, []);
  return (
    <div className="card">
      <div className="card-head"><h2>Quarantined records</h2></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Batch</th><th>Source</th><th>Reason</th><th>Record</th></tr></thead>
          <tbody>
            {rows.map((r, i) => <tr key={i}><td className="mono">{r.batch_id}</td><td>{r.source_system}</td><td><Status s={r.reason} /></td><td className="msg mono">{r.record}</td></tr>)}
            {!rows.length && <tr><td colSpan="4" className="empty">No quarantined records.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
