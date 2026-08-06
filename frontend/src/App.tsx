import { useState } from "react";
import ChatView from "./views/ChatView";
import CollectionsView from "./views/CollectionsView";
import DashboardView from "./views/DashboardView";
import DocumentsView from "./views/DocumentsView";

const VIEWS = ["Chat", "Documents", "Collections", "Dashboard"] as const;
type View = (typeof VIEWS)[number];

export default function App() {
  const [view, setView] = useState<View>("Chat");

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Cortex</span>
        <nav className="nav">
          {VIEWS.map((name) => (
            <button
              key={name}
              className={view === name ? "nav-item active" : "nav-item"}
              onClick={() => setView(name)}
            >
              {name}
            </button>
          ))}
        </nav>
      </header>
      <main className="content">
        {view === "Chat" && <ChatView />}
        {view === "Documents" && <DocumentsView />}
        {view === "Collections" && <CollectionsView />}
        {view === "Dashboard" && <DashboardView />}
      </main>
    </div>
  );
}
