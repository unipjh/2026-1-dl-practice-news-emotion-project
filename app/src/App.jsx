import { useState } from "react";
import { AppProvider } from "./context/AppContext";
import Header from "./components/Header";
import ControlBar from "./components/ControlBar";
import MonitoringView from "./components/MonitoringView";
import HeadlineExplorer from "./components/HeadlineExplorer";
import HeadlineDetail from "./components/HeadlineDetail";
import Toast from "./components/Toast";

function AppInner() {
  const [activeTab, setActiveTab] = useState("모니터링");

  return (
    <div className="min-h-screen bg-[#f5f4ed]">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      {activeTab === "모니터링" && <ControlBar />}
      {activeTab === "모니터링" ? (
        <MonitoringView />
      ) : (
        <HeadlineExplorer />
      )}
      <HeadlineDetail />
      <Toast />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppInner />
    </AppProvider>
  );
}
