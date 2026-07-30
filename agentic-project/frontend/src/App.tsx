import { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import LoginPage from "./components/LoginPage";
import LandingPage from "./components/LandingPage";
import { useSessionStore } from "./stores/sessionStore";
import { useUploadStore } from "./stores/uploadStore";
import { useAuthStore } from "./stores/authStore";
import ContextSection from "./sections/ContextSection";
import ChatSection from "./sections/ChatSection";
import OutputPanel from "./sections/OutputPanel";
import IotRegistryPage from "./sections/IotRegistryPage";
import { ToastContainer } from "./components/ToastContainer";
import ColumnClarifyView from "./components/ColumnClarifyView";
import ProcessingOverlay from "./components/ProcessingOverlay";
import AppTour from "./components/AppTour";

function Dashboard() {
  const isProcessing = useUploadStore((s) => s.isProcessing);
  return (
    <main
      className={`grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-[minmax(220px,20fr)_minmax(360px,50fr)_minmax(240px,30fr)] transition-[filter] duration-200 ${
        isProcessing ? "blur-sm pointer-events-none select-none" : ""
      }`}
    >
      <ContextSection />
      <ChatSection />
      <OutputPanel />
    </main>
  );
}

export default function App() {
  const bootstrap = useSessionStore((s) => s.bootstrap);
  const startPoller = useSessionStore((s) => s.startPoller);
  const stopPoller = useSessionStore((s) => s.stopPoller);
  const role = useAuthStore((s) => s.role);
  const viewingDashboard = useAuthStore((s) => s.viewingDashboard);
  const setViewingDashboard = useAuthStore((s) => s.setViewingDashboard);
  const [showLogin, setShowLogin] = useState(false);
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    if (role) startPoller();
    else stopPoller();
    return () => stopPoller();
  }, [role, startPoller, stopPoller]);

  useEffect(() => {
    if (role) bootstrap();
  }, [role, bootstrap]);

  if (!role) {
    return (
      <>
        <div className={`transition-[filter] duration-200 ${showLogin ? "blur-sm pointer-events-none select-none" : ""}`}>
          <LandingPage onGetStarted={() => setShowLogin(true)} />
        </div>
        {showLogin && <LoginPage onClose={() => setShowLogin(false)} />}
      </>
    );
  }

  if (role === "iot" && !viewingDashboard) {
    return <IotRegistryPage onViewDashboard={() => setViewingDashboard(true)} />;
  }

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <Navbar onBackToManage={role === "iot" ? () => setViewingDashboard(false) : undefined} onHelp={() => setShowTour(true)} />
      <Dashboard />
      <ToastContainer />
      <ColumnClarifyView />
      <ProcessingOverlay />
      <AppTour active={showTour} onClose={() => setShowTour(false)} />
    </div>
  );
}
