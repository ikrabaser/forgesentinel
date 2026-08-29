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

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "Overview",
    subtitle: "Plant-wide security posture at a glance",
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
};

function AnimatedRoutes() {
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? { title: "ForgeSentinel", subtitle: "" };

  return (
    <>
      <TopBar title={meta.title} subtitle={meta.subtitle} />
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
            </Routes>
          </motion.div>
        </AnimatePresence>
      </div>
    </>
  );
}

export function App() {
  return (
    <div className="relative flex h-full">
      <BackgroundFX />
      <Sidebar />
      <div className="relative z-10 flex flex-1 flex-col">
        <AnimatedRoutes />
      </div>
      <AlertToastStack />
    </div>
  );
}
