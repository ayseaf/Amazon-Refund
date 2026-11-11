import { NavLink, Route, Routes } from "react-router-dom";
import { CatalogProvider } from "./catalog";
import { DashboardPage } from "./pages/Dashboard";
import { MonitoringPage } from "./pages/Monitoring";
import { OrdersPage } from "./pages/Orders";
import { RefundsPage } from "./pages/Refunds";
import { ReturnsPage } from "./pages/Returns";
import { SavingsPage } from "./pages/Savings";
import { SettingsPage } from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard", testId: "nav-dashboard", end: true },
  { to: "/orders", label: "Amazon Orders", testId: "nav-orders", end: false },
  { to: "/monitoring", label: "Price Monitoring", testId: "nav-monitoring", end: false },
  { to: "/refunds", label: "Refund Assistant", testId: "nav-refunds", end: false },
  { to: "/returns", label: "Returns and Deadlines", testId: "nav-returns", end: false },
  { to: "/savings", label: "Savings History", testId: "nav-savings", end: false },
  { to: "/settings", label: "Settings", testId: "nav-settings", end: false },
];

export function AppRoutes() {
  return (
    <CatalogProvider>
      <div className="app">
        <a className="skip-link" href="#content">
          Skip to content
        </a>
        <aside className="sidebar">
          <p className="brand-kicker">Phase 1 · local</p>
          <p className="brand">Price Tracker & Refund Assistant</p>
          <p className="brand-note">Independent tool. Not affiliated with Amazon.</p>
          <nav aria-label="Sections">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                data-testid={item.testId}
                className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="main">
          <div className="sample-banner" data-testid="sample-banner" role="note">
            SAMPLE DATA. The orders, prices, and refund amounts in this window are fictional
            illustrations. Nothing is loaded from an Amazon account. A price adjustment or refund is
            not guaranteed.
          </div>
          <main id="content">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/orders" element={<OrdersPage />} />
              <Route path="/monitoring" element={<MonitoringPage />} />
              <Route path="/refunds" element={<RefundsPage />} />
              <Route path="/returns" element={<ReturnsPage />} />
              <Route path="/savings" element={<SavingsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<h1>Section not found</h1>} />
            </Routes>
          </main>
        </div>
      </div>
    </CatalogProvider>
  );
}
