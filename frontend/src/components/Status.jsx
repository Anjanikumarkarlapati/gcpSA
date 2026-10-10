import React from "react";
import { CheckCircle, WarningCircle, XCircle, Info, CircleDashed, ArrowsClockwise } from "@phosphor-icons/react";

const ICON = { good: CheckCircle, warning: WarningCircle, critical: XCircle, info: Info, muted: CircleDashed };
const TONE = {
  success: "good", passed: "good",
  failed: "critical", upstream_failed: "warning", null_key: "critical", invalid_date: "critical",
  duplicate_key: "critical", invalid_amount: "critical",
  running: "info", up_for_retry: "warning", quarantined: "warning", queued: "muted",
};

/** Status is never colour alone: tone colour + icon shape + word. */
export default function Status({ s }) {
  const key = String(s).toLowerCase();
  const tone = TONE[key] || "muted";
  const Icon = key === "running" ? ArrowsClockwise : ICON[tone];
  return (
    <span className={`status status-${tone}`}>
      <Icon size={14} weight="bold" aria-hidden="true" />
      {key.replace(/_/g, " ")}
    </span>
  );
}
