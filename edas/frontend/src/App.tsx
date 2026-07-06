import { useEffect } from "react";
import Navbar from "./components/Navbar";
import DashboardPage from "./pages/DashboardPage";
import WorkspacePage from "./pages/WorkspacePage";
import { useSessionStore } from "./stores/sessionStore";
import { useUiStore } from "./stores/uiStore";

export default function App() {
  const view = useUiStore((s) => s.view);
  const bootstrap = useSessionStore((s) => s.bootstrap);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  return (
    <div className="flex flex-col h-screen bg-app text-text">
      <Navbar />
      {view === "dashboard" ? <DashboardPage /> : <WorkspacePage />}
    </div>
  );
}
