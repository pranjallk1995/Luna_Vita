import { CalendarDays, CalendarRange, LogOut, type LucideIcon } from "lucide-react";
import { useState } from "react";

import type { Settings } from "./api";
import { today } from "./clock";
import { FoodLog } from "./components/FoodLog";
import { Brand, ForbiddenPage, SignInPage, UnreachablePage } from "./components/Gate";
import { Measurements } from "./components/Measurements";
import { Monthly } from "./components/Monthly";
import { Summary } from "./components/Summary";
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

  return (
    <main className="lv-page">
      <div className="lv-header-row">
        <Brand />
        <div className="lv-header-actions">
          <input
            className="lv-input lv-date-input"
            type="date"
            aria-label="Log date"
            value={day}
            required
            onChange={(event) => event.target.value && setDay(event.target.value)}
          />
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
          <Summary day={day} />
          <FoodLog day={day} settings={settings} />
          <Workout day={day} />
          <Measurements day={day} settings={settings} />
        </>
      ) : (
        <Monthly day={day} settings={settings} />
      )}
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
