import { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import LoginPage from "./components/LoginPage";
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
  const [viewingDashboard, setViewingDashboard] = useState(false);

  useEffect(() => {
    bootstrap();
    startPoller();
    return () => stopPoller();
  }, [bootstrap, startPoller, stopPoller]);

  if (!role) {
    return <LoginPage />;
  }

  if (role === "iot" && !viewingDashboard) {
    return <IotRegistryPage onViewDashboard={() => setViewingDashboard(true)} />;
  }

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <Navbar onBackToManage={role === "iot" ? () => setViewingDashboard(false) : undefined} />
      <Dashboard />
      <ToastContainer />
      <ColumnClarifyView />
      <ProcessingOverlay />
    </div>
  );
}
