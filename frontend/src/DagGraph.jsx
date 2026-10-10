import React from "react";

const COLORS = { success: "#1a7f4b", failed: "#c62828", running: "#1565c0", up_for_retry: "#e08a00", upstream_failed: "#b36b00", queued: "#8a94a6" };
// columns: start | extract | validate | load | transform | dq | merge | audit | end
const COL = (id) => (id === "start" ? 0 : id.startsWith("extract") ? 1 : id.startsWith("validate") ? 2 : id.startsWith("load") ? 3
  : id === "transform_staging_data" ? 4 : id === "run_data_quality_checks" ? 5 : id === "merge_into_curated_table" ? 6
  : id === "update_etl_audit_table" ? 7 : 8);
const ROW = (id) => { const m = id.match(/_(\d)/); return m ? Number(m[1]) - 1 : 1; };
const W = 96, H = 34, GX = 118, GY = 52;

export default function DagGraph({ cfg, tasks }) {
  const st = Object.fromEntries(tasks.map((t) => [t.task_id, t.status]));
  const pos = Object.fromEntries(cfg.tasks.map((id) => [id, { x: COL(id) * GX + 4, y: ROW(id) * GY + 8 }]));
  return (
    <div className="dag-scroll">
      <svg width={8 * GX + W + 8} height={3 * GY + 8} role="img" aria-label="DAG task graph">
        {Object.entries(cfg.edges).flatMap(([a, kids]) => kids.map((b) => (
          <line key={a + b} x1={pos[a].x + W} y1={pos[a].y + H / 2} x2={pos[b].x} y2={pos[b].y + H / 2} stroke="#9aa5b8" strokeWidth="1.5" />
        )))}
        {cfg.tasks.map((id) => (
          <g key={id} transform={`translate(${pos[id].x},${pos[id].y})`}>
            <rect width={W} height={H} rx="6" fill={COLORS[st[id]] || COLORS.queued} />
            <text x={W / 2} y={H / 2 + 4} textAnchor="middle" fontSize="10" fill="#fff">
              {id.replace(/_source_(\d)/, " s$1").replace(/_/g, " ").slice(0, 17)}
            </text>
            <title>{`${id}: ${st[id]}`}</title>
          </g>
        ))}
      </svg>
    </div>
  );
}
