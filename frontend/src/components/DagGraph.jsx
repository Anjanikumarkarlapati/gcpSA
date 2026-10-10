import React from "react";

const COL = (id) => (id === "start" ? 0 : id.startsWith("extract") ? 1 : id.startsWith("validate") ? 2 : id.startsWith("load") ? 3
  : id === "transform_staging_data" ? 4 : id === "run_data_quality_checks" ? 5 : id === "merge_into_curated_table" ? 6
  : id === "update_etl_audit_table" ? 7 : 8);
const ROW = (id) => { const m = id.match(/_(\d)/); return m ? Number(m[1]) - 1 : 1; };
const W = 124, H = 34, GX = 142, GY = 52;
const MARK = { success: "✓", failed: "✕", running: "…", up_for_retry: "↻", upstream_failed: "!", queued: "·" };

/** Colours come from CSS classes (tokens); the glyph keeps status readable without colour. */
export default function DagGraph({ cfg, tasks }) {
  const st = Object.fromEntries(tasks.map((t) => [t.task_id, t.status]));
  const pos = Object.fromEntries(cfg.tasks.map((id) => [id, { x: COL(id) * GX + 4, y: ROW(id) * GY + 8 }]));
  return (
    <div className="dag-scroll">
      <svg width={8 * GX + W + 8} height={3 * GY + 8} role="img" aria-label="DAG task graph">
        {Object.entries(cfg.edges).flatMap(([a, kids]) => kids.map((b) => (
          <line key={a + b} className="dag-edge" x1={pos[a].x + W} y1={pos[a].y + H / 2} x2={pos[b].x} y2={pos[b].y + H / 2} />
        )))}
        {cfg.tasks.map((id) => (
          <g key={id} className={`dag-node n-${st[id] || "queued"}`} transform={`translate(${pos[id].x},${pos[id].y})`}>
            <rect width={W} height={H} rx="6" />
            <text x={W / 2} y={H / 2 + 4} textAnchor="middle">
              {MARK[st[id]] || "·"} {id.replace(/_source_(\d)/, " s$1").replace(/_/g, " ").slice(0, 22)}
            </text>
            <title>{`${id}: ${st[id]}`}</title>
          </g>
        ))}
      </svg>
    </div>
  );
}
