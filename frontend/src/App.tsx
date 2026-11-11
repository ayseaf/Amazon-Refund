import { useEffect, useState } from "react";
import { Mark } from "./components";
import {
  DashboardPage,
  MonitoringPage,
  OrdersPage,
  RefundsPage,
  ReturnsPage,
  SavingsPage,
  SettingsPage,
} from "./pages";

const NAV = [
  ["dashboard", "Dashboard"],
  ["orders", "Amazon Orders"],
  ["monitoring", "Price Monitoring"],
  ["refunds", "Refund Assistant"],
  ["returns", "Returns and Deadlines"],
  ["savings", "Savings History"],
  ["settings", "Settings"],
] as const;

type Route = (typeof NAV)[number][0];

function readRoute(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  const match = NAV.find(([id]) => id === raw);
  return match ? match[0] : "dashboard";
}

export function App() {
  const [route, setRoute] = useState<Route>(readRoute);

  useEffect(() => {
    const onHash = () => setRoute(readRoute());
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) {
      window.location.hash = "#/dashboard";
    }
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="app">
      <nav className="rail" aria-label="Sections">
        <a className="brand" href="#/dashboard">
          <Mark />
          <span>
            <strong>Amazon Price Tracker</strong>
            <span className="brand-sub">Refund Assistant</span>
          </span>
        </a>
        {NAV.map(([id, label]) => (
          <a key={id} href={`#/${id}`} aria-current={route === id ? "page" : undefined}>
            {label}
          </a>
        ))}
      </nav>
      <main className="main">
        {route === "dashboard" ? <DashboardPage /> : null}
        {route === "orders" ? <OrdersPage /> : null}
        {route === "monitoring" ? <MonitoringPage /> : null}
        {route === "refunds" ? <RefundsPage /> : null}
        {route === "returns" ? <ReturnsPage /> : null}
        {route === "savings" ? <SavingsPage /> : null}
        {route === "settings" ? <SettingsPage /> : null}
      </main>
    </div>
  );
}
