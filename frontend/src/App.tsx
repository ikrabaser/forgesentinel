import { useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import { AlertToastStack } from "./components/AlertToastStack";
import { BackgroundFX } from "./components/BackgroundFX";
import { OverviewPage } from "./pages/OverviewPage";
import { TelemetryPage } from "./pages/TelemetryPage";
import { AlertsPage } from "./pages/AlertsPage";
import { AssetsPage } from "./pages/AssetsPage";
import { AuditLogPage } from "./pages/AuditLogPage";

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "Security Overview",
    subtitle: "Real-time operational security posture across your infrastructure.",
  },
  "/telemetry": {
    title: "Live Telemetry",
    subtitle: "Streaming process data from PLC-001",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Detection engine findings across all assets",
  },
  "/assets": {
    title: "Assets",
    subtitle: "OT asset inventory and connectivity status",
  },
  "/audit-log": {
    title: "Audit Log",
    subtitle: "Who did what, when — API actions and Modbus write commands",
  },
};

function AnimatedRoutes({ onMenuClick }: { onMenuClick: () => void }) {
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? { title: "ForgeSentinel", subtitle: "" };

  return (
    <>
      <TopBar title={meta.title} subtitle={meta.subtitle} onMenuClick={onMenuClick} />
      <div className="relative z-10 flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <Routes location={location}>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/telemetry" element={<TelemetryPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/assets" element={<AssetsPage />} />
              <Route path="/audit-log" element={<AuditLogPage />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </div>
    </>
  );
}

export function App() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const [lastPathname, setLastPathname] = useState(location.pathname);

  // Close the mobile nav drawer automatically whenever the route
  // changes, so picking a page also dismisses the overlay. Adjusted
  // during render (React's recommended pattern for state derived
  // from a prop/route change) rather than in an Effect, so it takes
  // effect in the same render instead of triggering an extra one.
  if (location.pathname !== lastPathname) {
    setLastPathname(location.pathname);
    setMobileNavOpen(false);
  }

  return (
    <div className="relative flex h-full overflow-hidden">
      <BackgroundFX />
      <Sidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
        <AnimatedRoutes onMenuClick={() => setMobileNavOpen(true)} />
      </div>
      <AlertToastStack />
    </div>
  );
}
