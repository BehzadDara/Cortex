import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import ChatView from "./views/ChatView";
import CollectionsView from "./views/CollectionsView";
import DashboardView from "./views/DashboardView";
import DocumentsView from "./views/DocumentsView";
import MemoriesView from "./views/MemoriesView";
import PreviewView from "./views/PreviewView";

const LINKS = [
  { to: "/chats", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/collections", label: "Collections" },
  { to: "/memories", label: "Memories" },
  { to: "/dashboard", label: "Dashboard" },
];

function Shell() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Cortex</span>
        <nav className="nav">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? "nav-item active" : "nav-item"
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/chats" replace />} />
          <Route path="/chats/:id?" element={<ChatView />} />
          <Route path="/documents" element={<DocumentsView />} />
          <Route path="/collections" element={<CollectionsView />} />
          <Route path="/memories" element={<MemoriesView />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="*" element={<Navigate to="/chats" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/preview/:id" element={<PreviewView />} />
        <Route path="*" element={<Shell />} />
      </Routes>
    </BrowserRouter>
  );
}
