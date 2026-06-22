import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";

const PALETTE = ["#7c5cff", "#2dd4bf", "#fbbf24", "#fb7185", "#60a5fa",
  "#a78bfa", "#34d399", "#f472b6", "#38bdf8", "#c084fc"];

const money = (sym, v, d = 0) =>
  `${sym} ${(v ?? 0).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const pct = (v) => `${((v ?? 0) * 100).toFixed(1)}%`;

const LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#cdd5e8", family: "Inter", size: 12 },
  margin: { l: 10, r: 10, t: 30, b: 10 },
  xaxis: { gridcolor: "rgba(255,255,255,0.06)", zeroline: false },
  yaxis: { gridcolor: "rgba(255,255,255,0.06)", zeroline: false },
  legend: { bgcolor: "rgba(0,0,0,0)", orientation: "h", y: 1.12, x: 0 },
  hoverlabel: { bgcolor: "#0d1424", bordercolor: "#7c5cff", font: { color: "#e8edf7" } },
};
const CHART = { displayModeBar: false, responsive: true };
const Chart = ({ data, layout, height = 320 }) => (
  <Plot data={data} layout={{ ...LAYOUT, height, ...layout }} config={CHART}
        style={{ width: "100%" }} useResizeHandler />
);

function Kpi({ tone, label, value, sub }) {
  return (
    <div className={`kpi ${tone}`}>
      <div className="bar" />
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

function Progress({ value, max = 1, color = "#2dd4bf" }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <span>
      <span className="bar-track"><span className="bar-fill" style={{ width: `${w}%`, background: color }} /></span>
      <span style={{ marginLeft: 8 }}>{(value * 100).toFixed(0)}%</span>
    </span>
  );
}

export default function App() {
  const [db, setDb] = useState(null);
  const [err, setErr] = useState(null);
  const [country, setCountry] = useState(null);
  const [city, setCity] = useState("All cities");
  const [building, setBuilding] = useState("All buildings");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setDb(d); setCountry(d.nav[0]?.name ?? null); })
      .catch((e) => setErr(String(e)));
  }, []);

  const countryObj = useMemo(
    () => db?.nav.find((c) => c.name === country) ?? null, [db, country]);
  const cityObj = useMemo(
    () => countryObj?.cities.find((c) => c.name === city) ?? null, [countryObj, city]);

  // Resolve scope
  let scopeKey = country;
  let scope = "country";
  let here = country;
  if (city !== "All cities") {
    if (building !== "All buildings") { scopeKey = `${country}|${city}|${building}`; scope = "building"; here = building; }
    else { scopeKey = `${country}|${city}`; scope = "city"; here = city; }
  }
  const sd = db?.scopes[scopeKey] ?? null;
  const sym = countryObj?.currency ?? "$";

  if (err) return <div className="center-load">Failed to load data · {err}</div>;
  if (!db || !countryObj) return <div className="center-load">Loading…</div>;

  const crumbs = [country, ...(city !== "All cities" ? [city] : []), ...(scope === "building" ? [building] : [])];
  const scopeLabel = { country: "Country view", city: "City view", building: "Building view" }[scope];
  const m = sd?.metrics;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><span className="dot" />Lobby<span style={{ color: "#7c5cff" }}>Metrics</span></div>
        <div className="brand-sub">Co-living performance intelligence</div>

        <label>Country</label>
        <select value={country} onChange={(e) => { setCountry(e.target.value); setCity("All cities"); setBuilding("All buildings"); }}>
          {db.nav.map((c) => <option key={c.name} value={c.name}>{c.flag} {c.name}</option>)}
        </select>

        <label>City</label>
        <select value={city} onChange={(e) => { setCity(e.target.value); setBuilding("All buildings"); }}>
          {["All cities", ...countryObj.cities.map((c) => c.name)].map((c) => <option key={c}>{c}</option>)}
        </select>

        {cityObj && (
          <>
            <label>Building</label>
            <select value={building} onChange={(e) => setBuilding(e.target.value)}>
              {["All buildings", ...cityObj.buildings].map((b) => <option key={b}>{b}</option>)}
            </select>
          </>
        )}

        <div className="refreshed">
          Data refreshed<br /><b style={{ color: "#cdd5e8" }}>{new Date(db.generated_at).toLocaleString()}</b><br />
          Monthly figures · weekly rates ×{db.weeks_per_month?.toFixed(5)}. Rooms classified by Lobby Board availability label.
        </div>
      </aside>

      <main className="main">
        <div className="hero">
          <div className="breadcrumb">
            {crumbs.map((c, i) => (
              <span key={i}>
                {i > 0 && <span className="sep">/</span>}{" "}
                <span className={i === crumbs.length - 1 ? "here" : ""}>{c}</span>{" "}
              </span>
            ))}
          </div>
          <h1>{here}<span className="scope-pill">{scopeLabel}</span></h1>
          <p>Monthly performance snapshot · figures in {sym}</p>
        </div>

        {!sd || !m || m.rooms === 0 ? (
          <div className="coming"><h2>Nothing to show</h2><p>No Lobby Board data is connected for this selection.</p></div>
        ) : (
          <>
            <div className="kpi-grid">
              <Kpi tone="accent" label="Total Market Rent" value={money(sym, m.market_rent)} sub="monthly potential" />
              <Kpi tone="teal" label="Collected Rent" value={money(sym, m.collected)} sub="monthly actual" />
              <Kpi tone="accent" label="Occupancy" value={pct(m.occupancy)} sub={`${m.occupied} / ${m.rooms} rooms`} />
              <Kpi tone="rose" label="Price Optimization Loss" value={money(sym, m.price_loss)} sub="occupied below market" />
              <Kpi tone="amber" label="Vacancy Loss" value={money(sym, m.vacancy_loss)} sub={`${m.vacant} vacant · ${m.booked} booked`} />
              <Kpi tone="teal" label="Revenue Capture" value={pct(m.capture)} sub="collected / market" />
            </div>

            <RevenueBridge m={m} sym={sym} />
            <Arrears a={sd.arrears} />

            {scope !== "building"
              ? <GroupViews sd={sd} sym={sym} />
              : <BuildingViews sd={sd} m={m} sym={sym} />}

            <div className="note">
              Source: Lobby Board (Google Sheets), rebuilt on a schedule. Market Rent is weekly ×{db.weeks_per_month?.toFixed(5)}.
              Occupancy is read from each room's availability label (occupied / booked / vacant / facilities),
              so stale Amounts on handed-back buildings no longer count as occupied. Arrears: live from the team Lobbyboard, CAD-normalized.
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function RevenueBridge({ m, sym }) {
  const x = ["Market Rent", "Price opt. loss", "Vacancy (booked)", "Vacancy (vacant)", "Collected"];
  const y = [m.market_rent, -m.price_loss, -m.booked_loss, -m.vacant_loss, 0];
  const labels = [m.market_rent, m.price_loss, m.booked_loss, m.vacant_loss, m.collected];
  return (
    <>
      <div className="section-title">Revenue bridge <span className="muted">· market rent = collected + price optimization loss + vacancy loss</span></div>
      <div className="panel">
        <Chart height={320} data={[{
          type: "waterfall", orientation: "v", x, y,
          measure: ["absolute", "relative", "relative", "relative", "total"],
          text: labels.map((v) => money(sym, v)), textposition: "outside", textfont: { color: "#cdd5e8" },
          connector: { line: { color: "rgba(255,255,255,0.18)" } },
          decreasing: { marker: { color: "#fb7185" } },
          increasing: { marker: { color: "#fbbf24" } },
          totals: { marker: { color: "#2dd4bf" } },
          hovertemplate: "%{x}: %{text}<extra></extra>",
        }]} layout={{ showlegend: false, yaxis: { ...LAYOUT.yaxis, tickprefix: `${sym} ` } }} />
      </div>
    </>
  );
}

function Arrears({ a }) {
  return (
    <>
      <div className="section-title">Rent Arrears <span className="muted">· live from the team Lobbyboard · overdue rent, aged by due date · CAD-normalized</span></div>
      {!a ? (
        <div className="note">Arrears source not connected for this build.</div>
      ) : a.error ? (
        <div className="note">Arrears could not load · {a.error}</div>
      ) : (
        <>
          <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            <Kpi tone="rose" label="Total Owed" value={money("CA$", a.total)} sub="overdue, CAD" />
            <Kpi tone="amber" label="Tenants in Arrears" value={a.count.toLocaleString()} sub="with overdue rent" />
            <Kpi tone="rose" label="60+ Days" value={money("CA$", a.b60)} sub={`${a.chronic} chronic tenants`} />
            <Kpi tone="teal" label="0-30 Days" value={money("CA$", a.b030)} sub="most recent" />
          </div>
          {a.unmatched?.length > 0 && (
            <div className="note">Note · no edge match for: <b>{a.unmatched.join(", ")}</b> — their arrears are not included.</div>
          )}
          {a.count === 0 ? (
            <div className="note">No overdue rent for this selection. ✅</div>
          ) : (
            <div className="row c2-15">
              <div className="panel">
                <Chart height={300} data={[{
                  type: "bar", x: ["0-30", "31-60", "60+"], y: [a.b030, a.b3160, a.b60],
                  marker: { color: ["#2dd4bf", "#fbbf24", "#fb7185"] },
                  text: [a.b030, a.b3160, a.b60].map((v) => money("CA$", v)), textposition: "outside",
                  hovertemplate: "%{x} days: %{y:,.0f}<extra></extra>",
                }]} layout={{ showlegend: false, yaxis: { ...LAYOUT.yaxis, tickprefix: "CA$ " } }} />
              </div>
              <div className="tbl-wrap">
                <table className="grid">
                  <thead><tr><th>Tenant</th><th>Building</th><th>Owed</th><th>Max Days</th><th>Lines</th></tr></thead>
                  <tbody>
                    {(a.top ?? []).map((t, i) => (
                      <tr key={i}>
                        <td>{t.tenant_name}</td><td>{t.building_id}</td>
                        <td>{money("CA$", t.total_owed_cad)}</td>
                        <td>{Math.round(t.max_overdue_days)}</td><td>{t.overdue_lines}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}

function GroupViews({ sd, sym }) {
  const gc = sd.groupCol;
  const groups = [...sd.groups].sort((a, b) => b.collected - a.collected);
  const rt = (sd.roomTypes ?? []).filter((r) => r.collected > 0);
  const byOcc = [...groups].sort((a, b) => a.occupancy - b.occupancy);
  const byCap = [...groups].sort((a, b) => a.capture - b.capture);
  return (
    <>
      <div className="row c2-15">
        <div>
          <div className="section-title">Market vs Collected <span className="muted">· per {gc}</span></div>
          <div className="panel">
            <Chart height={340} data={[
              { type: "bar", x: groups.map((g) => g[gc]), y: groups.map((g) => g.market_rent), name: "Market Rent", marker: { color: "rgba(124,92,255,0.55)" } },
              { type: "bar", x: groups.map((g) => g[gc]), y: groups.map((g) => g.collected), name: "Collected", marker: { color: "#2dd4bf" } },
            ]} layout={{ barmode: "group" }} />
          </div>
        </div>
        <div>
          <div className="section-title">Revenue mix</div>
          <div className="panel">
            <Chart height={340} data={[{
              type: "pie", labels: rt.map((r) => r.room_type), values: rt.map((r) => r.collected), hole: 0.62,
              marker: { colors: PALETTE, line: { color: "#0d1424", width: 2 } },
              textinfo: "percent", hovertemplate: "%{label}<br>%{value:,.0f}<extra></extra>",
            }]} layout={{ annotations: [{ text: "Collected<br>by room type", showarrow: false, font: { size: 12, color: "#8b97b3" } }] }} />
          </div>
        </div>
      </div>

      <div className="section-title">Occupancy &amp; capture <span className="muted">· per {gc}</span></div>
      <div className="row c2">
        <div className="panel">
          <Chart height={300} data={[{
            type: "bar", orientation: "h", y: byOcc.map((g) => g[gc]), x: byOcc.map((g) => g.occupancy * 100),
            marker: { color: byOcc.map((g) => g.occupancy * 100), colorscale: "Tealgrn", cmin: 0, cmax: 100 },
            text: byOcc.map((g) => `${(g.occupancy * 100).toFixed(0)}%`), textposition: "auto",
            hovertemplate: "%{y}: %{x:.1f}%<extra></extra>",
          }]} layout={{ xaxis: { ...LAYOUT.xaxis, title: "Occupancy %" } }} />
        </div>
        <div className="panel">
          <Chart height={300} data={[{
            type: "bar", orientation: "h", y: byCap.map((g) => g[gc]), x: byCap.map((g) => g.capture * 100),
            marker: { color: byCap.map((g) => g.capture * 100), colorscale: "Purp", cmin: 0, cmax: 120 },
            text: byCap.map((g) => `${(g.capture * 100).toFixed(0)}%`), textposition: "auto",
            hovertemplate: "%{y}: %{x:.1f}%<extra></extra>",
          }]} layout={{ xaxis: { ...LAYOUT.xaxis, title: "Revenue capture %" } }} />
        </div>
      </div>

      <div className="section-title">Breakdown <span className="muted">· every {gc}</span></div>
      <div className="tbl-wrap">
        <table className="grid">
          <thead><tr>
            <th>{gc[0].toUpperCase() + gc.slice(1)}</th><th>Rooms</th><th>Occ.</th><th>Vac.</th>
            <th>Market Rent</th><th>Collected</th><th>Price Opt. Loss</th><th>Vacancy Loss</th><th>Occupancy</th><th>Capture</th>
          </tr></thead>
          <tbody>
            {groups.map((g, i) => (
              <tr key={i}>
                <td>{g[gc]}</td><td>{g.rooms}</td><td>{g.occupied}</td><td>{g.vacant}</td>
                <td>{money(sym, g.market_rent)}</td><td>{money(sym, g.collected)}</td>
                <td>{money(sym, g.price_loss)}</td><td>{money(sym, g.vacancy_loss)}</td>
                <td><Progress value={g.occupancy} color="#2dd4bf" /></td>
                <td><Progress value={g.capture} max={1.2} color="#7c5cff" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function BuildingViews({ sd, m, sym }) {
  const rt = sd.roomTypes ?? [];
  return (
    <>
      <div className="row c3">
        <div>
          <div className="section-title">Occupancy</div>
          <div className="panel">
            <Chart height={300} data={[{
              type: "pie", labels: ["Occupied", "Vacant"], values: [m.occupied, m.vacant], hole: 0.66,
              marker: { colors: ["#2dd4bf", "rgba(251,113,133,0.85)"], line: { color: "#0d1424", width: 2 } },
              textinfo: "value", hovertemplate: "%{label}: %{value}<extra></extra>",
            }]} layout={{ annotations: [{ text: `<b>${pct(m.occupancy)}</b>`, showarrow: false, font: { size: 20, color: "#e8edf7" } }] }} />
          </div>
        </div>
        <div>
          <div className="section-title">Revenue capture</div>
          <div className="panel">
            <Chart height={300} data={[{
              type: "indicator", mode: "gauge+number", value: m.capture * 100,
              number: { suffix: "%", font: { color: "#e8edf7", size: 30 } },
              gauge: {
                axis: { range: [0, 120], tickcolor: "#8b97b3" }, bar: { color: "#7c5cff" },
                bgcolor: "rgba(255,255,255,0.04)", borderwidth: 0,
                steps: [
                  { range: [0, 70], color: "rgba(251,113,133,0.18)" },
                  { range: [70, 100], color: "rgba(251,191,36,0.16)" },
                  { range: [100, 120], color: "rgba(45,212,191,0.18)" },
                ],
              },
            }]} />
          </div>
        </div>
        <div>
          <div className="section-title">Collected by room type</div>
          <div className="panel">
            <Chart height={300} data={[{
              type: "bar", orientation: "h", y: rt.map((r) => r.room_type), x: rt.map((r) => r.collected),
              marker: { color: PALETTE.slice(0, rt.length) },
              text: rt.map((r) => money(sym, r.collected)), textposition: "auto",
              hovertemplate: "%{y}: %{x:,.0f}<extra></extra>",
            }]} />
          </div>
        </div>
      </div>

      <div className="section-title">Rooms <span className="muted">· room-level detail</span></div>
      <div className="tbl-wrap">
        <table className="grid">
          <thead><tr><th>No.</th><th>Apt</th><th>Room Type</th><th>Plan</th><th>Resident</th><th>Market /mo</th><th>Collected /mo</th><th>Status</th></tr></thead>
          <tbody>
            {(sd.rooms ?? []).map((r, i) => (
              <tr key={i}>
                <td>{r.no}</td><td>{r.apartment}</td><td>{r.room_type}</td><td>{r.plan}</td><td>{r.resident}</td>
                <td>{money(sym, r.market_rent_monthly)}</td><td>{money(sym, r.amount_monthly)}</td>
                <td><span className={`pill ${r.status}`}>{r.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
