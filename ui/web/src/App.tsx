import { CalendarDays, CalendarRange, ChevronLeft, ChevronRight, LogOut, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { Settings } from "./api";
import { addDays, today } from "./clock";
import { EnergySplit, FoodLog } from "./components/FoodLog";
import { Brand, ForbiddenPage, SignInPage, UnreachablePage } from "./components/Gate";
import { Measurements } from "./components/Measurements";
import { Monthly } from "./components/Monthly";
import { DayHeading, Summary } from "./components/Summary";
import { Workout } from "./components/Workout";
import { useSession } from "./http";
import { remember, remembered } from "./lib";

const PERIODS = ["daily", "monthly"] as const;
type Period = (typeof PERIODS)[number];

const NAV: { id: Period; label: string; icon: LucideIcon }[] = [
  { id: "daily", label: "Daily Tracking", icon: CalendarDays },
  { id: "monthly", label: "Monthly Tracking", icon: CalendarRange },
];

function Workspace({ logoutUrl, settings }: { logoutUrl: string; settings: Settings }) {
  const [period, setPeriod] = useState<Period>(() => remembered("lv-period", PERIODS, "daily"));
  const [day, setDay] = useState(() => today(settings));
  const [unsaved, setUnsaved] = useState(false);
  const onDirtyChange = useCallback((dirty: boolean) => setUnsaved(dirty), []);

  // An open food edit would be lost by changing day or leaving, so ask first.
  const changeDay = (next: string) => {
    if (next === day || !next) return;
    if (unsaved && !window.confirm("Discard your unsaved changes to this food?")) return;
    setUnsaved(false);
    setDay(next);
  };

  useEffect(() => {
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [unsaved]);

  return (
    <main className="lv-page">
      <div className="lv-header-row">
        <Brand />
        <div className="lv-header-actions">
          <button className="lv-button" type="button" aria-label="Previous day" title="Previous day" onClick={() => changeDay(addDays(day, -1))}>
            <ChevronLeft size={18} />
          </button>
          <input
            className="lv-input lv-date-input"
            type="date"
            aria-label="Log date"
            value={day}
            required
            onChange={(event) => changeDay(event.target.value)}
          />
          <button className="lv-button" type="button" aria-label="Next day" title="Next day" onClick={() => changeDay(addDays(day, 1))}>
            <ChevronRight size={18} />
          </button>
          <a className="lv-button lv-sign-out" href={logoutUrl}>
            <LogOut size={16} />
            Sign out
          </a>
        </div>
      </div>

      <nav className="lv-nav" aria-label="Period">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            className={period === id ? "lv-nav-item lv-nav-active" : "lv-nav-item"}
            type="button"
            key={id}
            aria-label={label}
            aria-current={period === id ? "page" : undefined}
            onClick={() => {
              setPeriod(id);
              remember("lv-period", id);
            }}
          >
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {period === "daily" ? (
        <>
          <DayHeading day={day} today={today(settings)} onToday={() => changeDay(today(settings))} />
          <Summary day={day} />
          <div className="vt-day-grid">
            <FoodLog day={day} settings={settings} onDirtyChange={onDirtyChange} />
            <aside className="vt-aside" aria-label="Rest of the day">
              <EnergySplit day={day} />
              <div className="vt-rail">
                <Workout day={day} />
                <Measurements day={day} settings={settings} />
              </div>
            </aside>
          </div>
        </>
      ) : (
        <Monthly day={day} settings={settings} />
      )}
      <footer className="lv-footer">Luna Vita · v{settings.version}</footer>
    </main>
  );
}

export function App() {
  const { data: session, error, refetch } = useSession<Settings>();

  if (error) return <UnreachablePage onRetry={() => refetch()} />;
  if (!session) return null;
  if (session.status === "signed_out") return <SignInPage url={session.login_url} />;
  if (session.status === "forbidden") return <ForbiddenPage email={session.email} logoutUrl={session.logout_url} />;
  return <Workspace logoutUrl={session.logout_url} settings={session.settings} />;
}
