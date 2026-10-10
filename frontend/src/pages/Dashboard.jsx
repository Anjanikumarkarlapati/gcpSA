import React from "react";
import { Link } from "react-router-dom";
import { Play } from "@phosphor-icons/react";
import PageHead from "../components/PageHead.jsx";
import Status from "../components/Status.jsx";

export default function Dashboard({ cfg, stats, runs }) {
  const recent = runs.slice(0, 8).reverse();
  const max = Math.max(1, ...recent.map((r) => r.rows_loaded));
  return (
    <>
      <PageHead eyebrow="Overview" title="Daily pipeline" sub={cfg ? `${cfg.dag_id} · cron ${cfg.schedule}` : "Connecting…"}>
        <Link className="btn btn-primary" to="/pipeline"><Play size={16} weight="bold" aria-hidden="true" /> Run pipeline</Link>
      </PageHead>

      <section className="hero">
        <div>
          <div className="hero-label">Rows in curated sales</div>
          <div className="hero-num">{stats?.curated_rows ?? "—"}</div>
          <div className="hero-sub">{stats?.quarantined_rows ?? 0} records quarantined</div>
        </div>
        <div className="bars" aria-label="Rows loaded in recent runs" role="img">
          {recent.map((r, i) => (
            <span key={r.run_id} className={`bar bar-${r.status}`} style={{ height: `${Math.max(8, (r.rows_loaded / max) * 100)}%`, animationDelay: `${i * 60}ms` }} title={`${r.batch_id}: ${r.rows_loaded} rows`} />
          ))}
        </div>
      </section>

      <section className="bento">
        <div className="card tile"><span className="tile-k">Runs</span><strong>{stats?.runs ?? "—"}</strong></div>
        <div className="card tile"><span className="tile-k">Success rate</span><strong>{stats?.success_rate != null ? `${stats.success_rate}%` : "—"}</strong></div>
        <div className="card tile"><span className="tile-k">Average duration</span><strong>{stats?.avg_duration_s != null ? `${stats.avg_duration_s}s` : "—"}</strong></div>
        <div className="card tile wide">
          <span className="tile-k">Latest runs</span>
          {runs.slice(0, 4).map((r) => (
            <div className="row spread" key={r.run_id}>
              <span className="mono">{r.batch_id}</span><span className="tag">{r.trigger}</span><Status s={r.status} />
            </div>
          ))}
          {!runs.length && <div className="empty">No runs yet.</div>}
        </div>
      </section>
    </>
  );
}
