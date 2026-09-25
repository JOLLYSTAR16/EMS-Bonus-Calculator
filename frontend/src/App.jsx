import React, { useMemo, useRef, useState } from "react";
import {
  Calculator,
  Camera,
  Clipboard,
  Copy,
  FileText,
  Home,
  ImagePlus,
  ListChecks,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  Trash2,
  Upload,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { createWorker } from "tesseract.js";

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "ems_bonus_entries_v1";
const RATES_KEY = "ems_bonus_rates_v1";
const REPORT_KEY = "ems_bonus_report_settings_v1";

const defaultRates = {
  captcha: 10000,
  deliveryBonus: 5000,
  day1Training: 55000,
  day2Training: 50000,
  labtechTraining: 30000,
  refresherTraining: 30000,
  unscriptedEvent: 15000,
  scriptedEvent: 25000,
  highCommandHourly: 10000,
  lobbies: {
    PH1: { day: 10000, night: 20000, late: 20000 },
    PH2: { day: 10000, night: 20000, late: 20000 },
    SH: { day: 10000, night: 20000, late: 20000 },
  },
  timeWindows: {
    dayStart: "06:00",
    dayEnd: "18:00",
    nightStart: "18:00",
    nightEnd: "23:00",
    lateStart: "23:00",
    lateEnd: "06:00",
  },
};

const defaultReportSettings = {
  footer:
    "Bonus missing? DM me with logs or bodycam proof.\nPartial shifts are not paid; hourly bonuses require a completed hour.",
  mention: "<@758312706267938836>",
};

function money(value) {
  return "$" + Number(value || 0).toLocaleString("en-US");
}

function minutesBetween(start, end) {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  let a = sh * 60 + sm;
  let b = eh * 60 + em;
  if (b < a) b += 24 * 60;
  return b - a;
}

function formatDuration(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}h ${m.toString().padStart(2, "0")}m`;
}

function formatMoneyRate(rate) {
  return money(rate) + "/hr";
}

function lobbyPeriod(start, rates) {
  const [h] = start.split(":").map(Number);
  const hour = h;
  const dayStart = Number(rates.timeWindows.dayStart.split(":")[0]);
  const dayEnd = Number(rates.timeWindows.dayEnd.split(":")[0]);
  const nightEnd = Number(rates.timeWindows.nightEnd.split(":")[0]);

  if (dayStart <= hour && hour < dayEnd) return "day";
  if (dayEnd <= hour && hour < nightEnd) return "night";
  return "late";
}

function rateForLobby(lobby, start, rates) {
  const key = (lobby || "PH1").toUpperCase();
  const period = lobbyPeriod(start, rates);
  return {
    period,
    rate: rates.lobbies[key]?.[period] ?? rates.highCommandHourly,
  };
}

function escapeReportText(text) {
  return text;
}

function groupByDepartment(entries) {
  const groups = {};
  for (const entry of entries) {
    const dept = entry.department || "Unassigned";
    if (!groups[dept]) groups[dept] = [];
    groups[dept].push(entry);
  }
  return groups;
}

function employeeGroups(entries) {
  const map = new Map();
  for (const entry of entries) {
    const key = `${entry.employeeName}||${entry.employeeId}`;
    if (!map.has(key)) {
      map.set(key, {
        name: entry.employeeName,
        id: entry.employeeId,
        entries: [],
      });
    }
    map.get(key).entries.push(entry);
  }
  return Array.from(map.values());
}

function activityLabel(entry) {
  if (entry.type === "lobby") {
    const hr = entry.payableHours;
    const lobby = entry.lobby || "Lobby";
    const period = entry.period ? `${entry.period[0].toUpperCase()}${entry.period.slice(1)}` : "";
    return `${hr}Hr ${period} ${lobby}`;
  }
  if (entry.type === "training") {
    return `${entry.quantity}x ${entry.activity}`;
  }
  if (entry.type === "event") {
    return `${entry.quantity} ${entry.activity}`;
  }
  if (entry.type === "captcha") return `${entry.quantity}x Captcha`;
  if (entry.type === "delivery") return `${entry.quantity}x Delivery`;
  if (entry.type === "hourly") return `${entry.quantity}Hr ${entry.activity || "Hourly Bonus"}`;
  return `${entry.quantity || 1}x ${entry.activity || "Bonus"}`;
}

function buildReport(entries, reportSettings) {
  const groups = groupByDepartment(entries);
  const departments = Object.keys(groups);
  let allTotal = 0;
  const lines = [];

  for (const department of departments) {
    const deptEntries = groups[department];
    const people = employeeGroups(deptEntries);
    lines.push("===================");
    lines.push(department);
    lines.push("===================");

    let departmentTotal = 0;

    for (const person of people) {
      let personTotal = 0;
      const activityParts = [];
      for (const e of person.entries) {
        personTotal += Number(e.amount || 0);
        const label = activityLabel(e);
        activityParts.push(`${label} = ${money(e.amount)}`);
      }
      departmentTotal += personTotal;
      lines.push(
        `${person.name} | ${person.id} (${activityParts.join(" , ")}) Total = ${money(personTotal)}`
      );
      lines.push("");
    }

    lines.push(`Department Total: ${money(departmentTotal)}`);
    allTotal += departmentTotal;
  }

  lines.push("====================================");
  lines.push(`All Total = ${money(allTotal)}`);
  lines.push("====================================");
  lines.push(escapeReportText(reportSettings.footer));
  if (reportSettings.mention) lines.push(reportSettings.mention);

  return lines.join("\n");
}

function loadJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

const departments = [
  "Human Resources (HR)",
  "Rescue Officer",
  "High Commands",
  "Labtech",
  "Unassigned",
];

function emptyManual() {
  return {
    employeeName: "",
    employeeId: "",
    department: "Human Resources (HR)",
    type: "training",
    activity: "Day 1 Training",
    lobby: "PH1",
    start: "",
    end: "",
    quantity: 1,
  };
}

function App() {
  const [tab, setTab] = useState("dashboard");
  const [entries, setEntries] = useState(() => loadJson(STORAGE_KEY, []));
  const [rates, setRates] = useState(() => loadJson(RATES_KEY, defaultRates));
  const [reportSettings, setReportSettings] = useState(() =>
    loadJson(REPORT_KEY, defaultReportSettings)
  );
  const [manual, setManual] = useState(emptyManual());
  const [ocrRows, setOcrRows] = useState([]);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrProgress, setOcrProgress] = useState(0);
  const [toast, setToast] = useState("");
  const fileRef = useRef(null);

  const total = useMemo(
    () => entries.reduce((sum, e) => sum + Number(e.amount || 0), 0),
    [entries]
  );

  const departmentSummary = useMemo(() => {
    const map = {};
    entries.forEach((e) => {
      const d = e.department || "Unassigned";
      map[d] = (map[d] || 0) + Number(e.amount || 0);
    });
    return map;
  }, [entries]);

  const report = useMemo(
    () => buildReport(entries, reportSettings),
    [entries, reportSettings]
  );

  function notify(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2500);
  }

  function persistEntries(next) {
    setEntries(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function persistRates(next) {
    setRates(next);
    localStorage.setItem(RATES_KEY, JSON.stringify(next));
  }

  function persistReportSettings(next) {
    setReportSettings(next);
    localStorage.setItem(REPORT_KEY, JSON.stringify(next));
  }

  function makeEntry(data) {
    return {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      ...data,
    };
  }

  function addManual() {
    if (!manual.employeeName.trim() || !manual.employeeId.trim()) {
      notify("Enter employee name and ID.");
      return;
    }

    let amount = 0;
    let labelData = { ...manual };

    if (manual.type === "lobby") {
      if (!manual.start || !manual.end) {
        notify("Enter both On Duty and Off Duty times.");
        return;
      }
      const minutes = minutesBetween(manual.start, manual.end);
      const payableHours = Math.floor(minutes / 60);
      const { period, rate } = rateForLobby(manual.lobby, manual.start, rates);
      amount = payableHours * rate;
      labelData = {
        ...labelData,
        minutes,
        payableHours,
        period,
        rate,
        amount,
        activity: `${period} ${manual.lobby}`,
      };
    } else {
      const quantity = Math.max(1, Number(manual.quantity) || 1);
      let rate = 0;
      if (manual.type === "training") {
        const key = {
          "Day 1 Training": "day1Training",
          "Day 2 Training": "day2Training",
          "Labtech Training": "labtechTraining",
          "Refresher Training": "refresherTraining",
        }[manual.activity];
        rate = rates[key] || 0;
      } else if (manual.type === "event") {
        rate = manual.activity === "Scripted Event" ? rates.scriptedEvent : rates.unscriptedEvent;
      } else if (manual.type === "captcha") {
        rate = rates.captcha;
      } else if (manual.type === "delivery") {
        rate = rates.deliveryBonus;
      } else if (manual.type === "hourly") {
        rate = rates.highCommandHourly;
      }
      amount = quantity * rate;
      labelData = { ...labelData, quantity, rate, amount };
    }

    persistEntries([...entries, makeEntry(labelData)]);
    setManual(emptyManual());
    notify("Bonus added.");
  }

  function addOcrRows() {
    const valid = ocrRows.filter((r) => r.include && r.employeeName && r.employeeId && r.start && r.end);
    if (!valid.length) {
      notify("Select at least one valid OCR row.");
      return;
    }

    const converted = valid.map((r) => {
      const minutes = minutesBetween(r.start, r.end);
      const payableHours = Math.floor(minutes / 60);
      const { period, rate } = rateForLobby(r.lobby, r.start, rates);
      return makeEntry({
        employeeName: r.employeeName,
        employeeId: r.employeeId,
        department: r.department || "Unassigned",
        type: "lobby",
        activity: `${period} ${r.lobby}`,
        lobby: r.lobby,
        start: r.start,
        end: r.end,
        minutes,
        payableHours,
        period,
        rate,
        amount: payableHours * rate,
        source: "OCR",
      });
    });

    persistEntries([...entries, ...converted]);
    setOcrRows([]);
    notify(`${converted.length} log(s) added.`);
  }

  function removeEntry(id) {
    persistEntries(entries.filter((e) => e.id !== id));
  }

  function clearAll() {
    if (!window.confirm("Delete all current bonus entries?")) return;
    persistEntries([]);
  }

  function copyReport() {
    navigator.clipboard.writeText(report);
    notify("Report copied to clipboard.");
  }

  function downloadReport() {
    const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ems-bonus-report.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function runOCR(files) {
    const selected = Array.from(files || []);
    if (!selected.length) return;

    setOcrBusy(true);
    setOcrProgress(0);
    setOcrRows([]);

    const worker = await createWorker("eng", 1, {
      logger: (m) => {
        if (m.status === "recognizing text" && m.progress) {
          setOcrProgress(Math.round(m.progress * 100));
        }
      },
    });

    const allRows = [];

    try {
      for (const file of selected) {
        const result = await worker.recognize(file);
        const text = result.data.text;
        allRows.push(...parseDiscordDutyText(text));
      }
      setOcrRows(allRows.length ? allRows : [{
        id: crypto.randomUUID(),
        include: false,
        employeeName: "",
        employeeId: "",
        department: "Rescue Officer",
        lobby: "PH1",
        start: "",
        end: "",
        raw: "No matching duty logs found. Try a clearer screenshot.",
      }]);
    } finally {
      await worker.terminate();
      setOcrBusy(false);
      setOcrProgress(100);
    }
  }

  function parseDiscordDutyText(text) {
    const lines = text
      .split(/\r?\n/)
      .map((x) => x.replace(/\s+/g, " ").trim())
      .filter(Boolean);

    const results = [];
    let currentPerson = null;
    const pending = {};

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Common OCR shape: "Melviin Cooper | 395012"
      const personMatch = line.match(/^(.+?)\s*\|\s*(\d{4,8})(?:\s|$)/);
      if (personMatch) {
        currentPerson = {
          name: personMatch[1].trim(),
          id: personMatch[2],
        };
        continue;
      }

      const dutyMatch = line.match(/On\s*Duty\s*(PH1|PH2|SH)\s*:\s*(\d{1,2}:\d{2})/i);
      const offMatch = line.match(/Off\s*Duty\s*(PH1|PH2|SH)\s*:\s*(\d{1,2}:\d{2})/i);

      if (dutyMatch && currentPerson) {
        const lobby = dutyMatch[1].toUpperCase();
        pending[lobby] = {
          ...(pending[lobby] || {}),
          start: normalizeTime(dutyMatch[2]),
          lobby,
        };
      }

      if (offMatch && currentPerson) {
        const lobby = offMatch[1].toUpperCase();
        const start = pending[lobby]?.start;
        const end = normalizeTime(offMatch[2]);

        if (start) {
          results.push({
            id: crypto.randomUUID(),
            include: true,
            employeeName: currentPerson.name,
            employeeId: currentPerson.id,
            department: "Rescue Officer",
            lobby,
            start,
            end,
            raw: `${currentPerson.name} | ${currentPerson.id} — ${lobby} ${start} → ${end}`,
          });
          delete pending[lobby];
        }
      }
    }

    return results;
  }

  function normalizeTime(value) {
    const [h, m] = value.split(":").map(Number);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }

  function updateOcrRow(id, patch) {
    setOcrRows((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function renderManualForm() {
    return (
      <div className="card">
        <div className="card-title">
          <div>
            <h2>Add Bonus Manually</h2>
            <p>Add training, events, captcha, delivery, or duty hours.</p>
          </div>
          <Calculator size={22} />
        </div>

        <div className="form-grid">
          <label>
            Employee Name
            <input
              value={manual.employeeName}
              onChange={(e) => setManual({ ...manual, employeeName: e.target.value })}
              placeholder="Kevin Sims"
            />
          </label>
          <label>
            Employee ID
            <input
              value={manual.employeeId}
              onChange={(e) => setManual({ ...manual, employeeId: e.target.value })}
              placeholder="163100"
            />
          </label>
          <label>
            Department
            <select
              value={manual.department}
              onChange={(e) => setManual({ ...manual, department: e.target.value })}
            >
              {departments.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label>
            Bonus Type
            <select
              value={manual.type}
              onChange={(e) => setManual({ ...manual, type: e.target.value })}
            >
              <option value="training">Training</option>
              <option value="event">Event</option>
              <option value="lobby">Lobby Hours</option>
              <option value="captcha">Captcha</option>
              <option value="delivery">Delivery</option>
              <option value="hourly">Hourly Bonus</option>
            </select>
          </label>

          {manual.type === "lobby" ? (
            <>
              <label>
                Lobby
                <select
                  value={manual.lobby}
                  onChange={(e) => setManual({ ...manual, lobby: e.target.value })}
                >
                  <option>PH1</option>
                  <option>PH2</option>
                  <option>SH</option>
                </select>
              </label>
              <label>
                On Duty
                <input
                  type="time"
                  value={manual.start}
                  onChange={(e) => setManual({ ...manual, start: e.target.value })}
                />
              </label>
              <label>
                Off Duty
                <input
                  type="time"
                  value={manual.end}
                  onChange={(e) => setManual({ ...manual, end: e.target.value })}
                />
              </label>
            </>
          ) : manual.type === "training" ? (
            <label>
              Training
              <select
                value={manual.activity}
                onChange={(e) => setManual({ ...manual, activity: e.target.value })}
              >
                <option>Day 1 Training</option>
                <option>Day 2 Training</option>
                <option>Labtech Training</option>
                <option>Refresher Training</option>
              </select>
            </label>
          ) : manual.type === "event" ? (
            <label>
              Event
              <select
                value={manual.activity}
                onChange={(e) => setManual({ ...manual, activity: e.target.value })}
              >
                <option>Unscripted Event</option>
                <option>Scripted Event</option>
              </select>
            </label>
          ) : manual.type === "hourly" ? (
            <label>
              Hourly Activity
              <input
                value={manual.activity}
                onChange={(e) => setManual({ ...manual, activity: e.target.value })}
                placeholder="Day PH2"
              />
            </label>
          ) : null}

          {manual.type !== "lobby" && (
            <label>
              Quantity / Hours
              <input
                type="number"
                min="1"
                value={manual.quantity}
                onChange={(e) => setManual({ ...manual, quantity: e.target.value })}
              />
            </label>
          )}
        </div>

        <button className="primary" onClick={addManual}>
          <Plus size={18} /> Add Bonus
        </button>
      </div>
    );
  }

  function updateRate(path, value) {
    const copy = structuredClone(rates);
    const parts = path.split(".");
    let target = copy;
    for (let i = 0; i < parts.length - 1; i++) target = target[parts[i]];
    target[parts.at(-1)] = Number(value);
    persistRates(copy);
  }

  function renderSettings() {
    const rateFields = [
      ["captcha", "Captcha"],
      ["deliveryBonus", "Delivery Bonus"],
      ["day1Training", "Day 1 Training"],
      ["day2Training", "Day 2 Training"],
      ["labtechTraining", "Labtech Training"],
      ["refresherTraining", "Refresher Training"],
      ["unscriptedEvent", "Unscripted Event"],
      ["scriptedEvent", "Scripted Event"],
      ["highCommandHourly", "High Command / Hour"],
    ];

    return (
      <div className="stack">
        <div className="card">
          <div className="card-title">
            <div>
              <h2>Bonus Rates</h2>
              <p>Change rates without touching the code.</p>
            </div>
            <Settings size={22} />
          </div>
          <div className="rate-grid">
            {rateFields.map(([key, label]) => (
              <label key={key}>
                {label}
                <div className="money-input">
                  <span>$</span>
                  <input
                    type="number"
                    min="0"
                    value={rates[key]}
                    onChange={(e) => updateRate(key, e.target.value)}
                  />
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">
            <div>
              <h2>Lobby Hourly Rates</h2>
              <p>Partial hours are automatically excluded.</p>
            </div>
            <Wallet size={22} />
          </div>
          <div className="rate-table">
            <div className="rate-row header"><span>Lobby</span><span>Day</span><span>Night</span><span>Late</span></div>
            {["PH1", "PH2", "SH"].map((lobby) => (
              <div className="rate-row" key={lobby}>
                <strong>{lobby}</strong>
                {["day", "night", "late"].map((period) => (
                  <div className="money-input" key={period}>
                    <span>$</span>
                    <input
                      type="number"
                      value={rates.lobbies[lobby][period]}
                      onChange={(e) => updateRate(`lobbies.${lobby}.${period}`, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">
            <div>
              <h2>Report Footer</h2>
              <p>This text is appended to every Discord report.</p>
            </div>
            <FileText size={22} />
          </div>
          <textarea
            rows="4"
            value={reportSettings.footer}
            onChange={(e) => persistReportSettings({ ...reportSettings, footer: e.target.value })}
          />
          <label className="block-label">
            Discord Mention
            <input
              value={reportSettings.mention}
              onChange={(e) => persistReportSettings({ ...reportSettings, mention: e.target.value })}
            />
          </label>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">+</div>
          <div>
            <strong>EMS Bonus</strong>
            <span>Calculator</span>
          </div>
        </div>

        <nav>
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
            <Home size={19} /> Dashboard
          </button>
          <button className={tab === "upload" ? "active" : ""} onClick={() => setTab("upload")}>
            <Camera size={19} /> Upload Logs
          </button>
          <button className={tab === "entries" ? "active" : ""} onClick={() => setTab("entries")}>
            <ListChecks size={19} /> Bonus Entries
          </button>
          <button className={tab === "report" ? "active" : ""} onClick={() => setTab("report")}>
            <FileText size={19} /> Report
          </button>
          <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>
            <Settings size={19} /> Settings
          </button>
        </nav>

        <div className="sidebar-note">
          <span>No login required</span>
          <small>Your entries are saved in this browser.</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">LOS SANTOS EMS</div>
            <h1>
              {tab === "dashboard" && "Bonus Dashboard"}
              {tab === "upload" && "Duty Log Scanner"}
              {tab === "entries" && "Bonus Entries"}
              {tab === "report" && "Discord Report"}
              {tab === "settings" && "Bonus Settings"}
            </h1>
          </div>
          <button className="ghost" onClick={() => setTab("upload")}>
            <ImagePlus size={18} /> Scan Logs
          </button>
        </header>

        {tab === "dashboard" && (
          <div className="stack">
            <section className="hero">
              <div>
                <div className="pill">NO LOGIN • LOCAL DATA</div>
                <h2>Calculate EMS bonuses from Discord logs.</h2>
                <p>
                  Upload duty screenshots, review the detected times, automatically remove
                  unpaid partial hours, and generate a Discord-ready report.
                </p>
                <div className="hero-actions">
                  <button className="primary" onClick={() => setTab("upload")}><Upload size={18} /> Upload Logs</button>
                  <button className="secondary" onClick={() => setTab("entries")}><Plus size={18} /> Add Manually</button>
                </div>
              </div>
              <div className="hero-symbol"><Calculator size={72} strokeWidth={1.3} /></div>
            </section>

            <div className="stats">
              <div className="stat"><span>Total Bonus</span><strong>{money(total)}</strong><Wallet /></div>
              <div className="stat"><span>Employees</span><strong>{new Set(entries.map((e) => `${e.employeeName}|${e.employeeId}`)).size}</strong><Users /></div>
              <div className="stat"><span>Entries</span><strong>{entries.length}</strong><ListChecks /></div>
              <div className="stat"><span>Departments</span><strong>{Object.keys(departmentSummary).length}</strong><FileText /></div>
            </div>

            <div className="two-col">
              <div className="card">
                <div className="card-title">
                  <div><h2>Department Totals</h2><p>Current browser data.</p></div>
                </div>
                {Object.keys(departmentSummary).length === 0 ? (
                  <div className="empty">No bonuses entered yet.</div>
                ) : (
                  Object.entries(departmentSummary).map(([d, value]) => (
                    <div className="summary-row" key={d}><span>{d}</span><strong>{money(value)}</strong></div>
                  ))
                )}
              </div>

              <div className="card">
                <div className="card-title">
                  <div><h2>Quick Add</h2><p>For training and event bonuses.</p></div>
                  <Plus size={22} />
                </div>
                <button className="quick" onClick={() => { setTab("entries"); setManual({ ...emptyManual(), type: "training", activity: "Day 1 Training" }); }}>
                  <span>Day 1 Training</span><strong>{money(rates.day1Training)}</strong>
                </button>
                <button className="quick" onClick={() => { setTab("entries"); setManual({ ...emptyManual(), type: "training", activity: "Day 2 Training" }); }}>
                  <span>Day 2 Training</span><strong>{money(rates.day2Training)}</strong>
                </button>
                <button className="quick" onClick={() => { setTab("entries"); setManual({ ...emptyManual(), type: "event", activity: "Unscripted Event" }); }}>
                  <span>Unscripted Event</span><strong>{money(rates.unscriptedEvent)}</strong>
                </button>
              </div>
            </div>

            {renderManualForm()}
          </div>
        )}

        {tab === "upload" && (
          <div className="stack">
            <div className="card upload-card">
              <div className="upload-icon"><Camera size={30} /></div>
              <h2>Upload Discord duty screenshots</h2>
              <p>
                The browser OCR reads names, IDs, lobby names, On Duty and Off Duty times.
                You can upload multiple screenshots at once.
              </p>
              <input
                ref={fileRef}
                hidden
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => runOCR(e.target.files)}
              />
              <button className="primary big" disabled={ocrBusy} onClick={() => fileRef.current?.click()}>
                {ocrBusy ? <><RefreshCw className="spin" size={18} /> Reading {ocrProgress}%</> : <><Upload size={18} /> Choose Screenshots</>}
              </button>
              <div className="ocr-help">
                <span>✓ PH1 / PH2 / SH</span>
                <span>✓ Overnight times</span>
                <span>✓ Partial-hour removal</span>
                <span>✓ Manual correction</span>
              </div>
            </div>

            {ocrRows.length > 0 && (
              <div className="card">
                <div className="card-title">
                  <div><h2>Review Detected Logs</h2><p>Correct anything OCR misread before adding.</p></div>
                  <ListChecks size={22} />
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Use</th><th>Employee</th><th>ID</th><th>Dept.</th><th>Lobby</th><th>On</th><th>Off</th><th>Duration</th><th>Payable</th></tr>
                    </thead>
                    <tbody>
                      {ocrRows.map((r) => {
                        const mins = r.start && r.end ? minutesBetween(r.start, r.end) : 0;
                        return (
                          <tr key={r.id}>
                            <td><input type="checkbox" checked={r.include} onChange={(e) => updateOcrRow(r.id, { include: e.target.checked })} /></td>
                            <td><input value={r.employeeName} onChange={(e) => updateOcrRow(r.id, { employeeName: e.target.value })} /></td>
                            <td><input value={r.employeeId} onChange={(e) => updateOcrRow(r.id, { employeeId: e.target.value })} /></td>
                            <td>
                              <select value={r.department} onChange={(e) => updateOcrRow(r.id, { department: e.target.value })}>
                                {departments.map((d) => <option key={d}>{d}</option>)}
                              </select>
                            </td>
                            <td>
                              <select value={r.lobby} onChange={(e) => updateOcrRow(r.id, { lobby: e.target.value })}>
                                <option>PH1</option><option>PH2</option><option>SH</option>
                              </select>
                            </td>
                            <td><input type="time" value={r.start} onChange={(e) => updateOcrRow(r.id, { start: e.target.value })} /></td>
                            <td><input type="time" value={r.end} onChange={(e) => updateOcrRow(r.id, { end: e.target.value })} /></td>
                            <td>{formatDuration(mins)}</td>
                            <td><strong>{Math.floor(mins / 60)}h</strong></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="action-row">
                  <button className="primary" onClick={addOcrRows}><Plus size={18} /> Add Selected Logs</button>
                  <button className="secondary" onClick={() => setOcrRows([])}><X size={18} /> Clear</button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "entries" && (
          <div className="stack">
            {renderManualForm()}
            <div className="card">
              <div className="card-title">
                <div><h2>Current Entries</h2><p>{entries.length} entries • {money(total)} total</p></div>
                <button className="danger-outline" onClick={clearAll}><Trash2 size={17} /> Clear All</button>
              </div>
              {entries.length === 0 ? (
                <div className="empty">No entries yet.</div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Employee</th><th>Department</th><th>Activity</th><th>Time</th><th>Bonus</th><th></th></tr></thead>
                    <tbody>
                      {entries.map((e) => (
                        <tr key={e.id}>
                          <td><strong>{e.employeeName}</strong><small>{e.employeeId}</small></td>
                          <td>{e.department}</td>
                          <td>{activityLabel(e)}</td>
                          <td>{e.type === "lobby" ? `${e.start} → ${e.end} (${formatDuration(e.minutes)})` : `${e.quantity || 1}x`}</td>
                          <td><strong>{money(e.amount)}</strong></td>
                          <td><button className="icon-btn" onClick={() => removeEntry(e.id)} title="Delete"><Trash2 size={16} /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "report" && (
          <div className="stack">
            <div className="report-toolbar">
              <button className="primary" onClick={copyReport}><Copy size={18} /> Copy Report</button>
              <button className="secondary" onClick={downloadReport}><FileText size={18} /> Download .txt</button>
              <span>{entries.length} entries • {money(total)}</span>
            </div>
            <div className="report-card">
              <pre>{report}</pre>
            </div>
          </div>
        )}

        {tab === "settings" && renderSettings()}
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

export default App;
