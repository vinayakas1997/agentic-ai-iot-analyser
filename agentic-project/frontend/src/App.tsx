import { useEffect } from "react";
import Navbar from "./components/Navbar";
import { useSessionStore } from "./stores/sessionStore";
import ContextSection from "./sections/ContextSection";
import ChatSection from "./sections/ChatSection";
import OutputPanel from "./sections/OutputPanel";
import { ToastContainer } from "./components/ToastContainer";

export default function App() {
  const bootstrap = useSessionStore((s) => s.bootstrap);
  const startPoller = useSessionStore((s) => s.startPoller);
  const stopPoller = useSessionStore((s) => s.stopPoller);

  useEffect(() => {
    bootstrap();
    startPoller();
    return () => stopPoller();
  }, [bootstrap, startPoller, stopPoller]);

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <Navbar />
      <main className="grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-[minmax(220px,20fr)_minmax(360px,50fr)_minmax(240px,30fr)]">
        <ContextSection />
        <ChatSection />
        <OutputPanel />
      </main>
      <ToastContainer />
    </div>
  );
}
