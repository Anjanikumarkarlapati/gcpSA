import React, { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { Moon, Sun, Timer } from "@phosphor-icons/react";
import { api } from "./api.js";
import Dashboard from "./pages/Dashboard.jsx";
import Pipeline from "./pages/Pipeline.jsx";
import Data from "./pages/Data.jsx";

export default function App() {
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [err, setErr] = useState("");
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute("data-theme") || "light");

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.stats(), api.runs()]);
      setStats(s); setRuns(r);
      const id = sel || r[0]?.run_id;
      if (id && id !== sel) setSel(id);
      if (id) setDetail(await api.run(id));
      setErr("");
    } catch (e) { setErr(e.message); }
  }, [sel]);

  useEffect(() => { api.config().then(setCfg).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [refresh]);

  const toggleTheme = () => {
    const t = theme === "dark" ? "light" : "dark";
    setTheme(t);
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("theme", t); } catch { /* ignore */ }
  };
  const toggleSchedule = async () => {
    const enabled = !cfg.schedule_enabled;
    try { await api.schedule(enabled); setCfg({ ...cfg, schedule_enabled: enabled }); } catch (e) { setErr(e.message); }
  };

  return (
    <>
      <header className="topbar">
        <div className="topbar-in">
          <span className="wordmark">ETL<span> Orchestrator</span></span>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>Dashboard</NavLink>
            <NavLink to="/pipeline">Pipeline</NavLink>
            <NavLink to="/data">Data &amp; quality</NavLink>
          </nav>
          <div className="topbar-end">
            {cfg && (
              <button className="btn btn-quiet btn-sm" onClick={toggleSchedule} aria-pressed={cfg.schedule_enabled}>
                <Timer size={16} aria-hidden="true" /> Schedule {cfg.schedule_enabled ? "on" : "off"}
              </button>
            )}
            <button className="btn btn-quiet btn-icon" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
              {theme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        {err && <div className="banner banner-critical" role="alert">{err}</div>}
        <Routes>
          <Route path="/" element={<Dashboard cfg={cfg} stats={stats} runs={runs} />} />
          <Route path="/pipeline" element={<Pipeline cfg={cfg} runs={runs} sel={sel} setSel={setSel} detail={detail} setErr={setErr} refresh={refresh} />} />
          <Route path="/data" element={<Data cfg={cfg} detail={detail} />} />
        </Routes>
      </main>
    </>
  );
}
