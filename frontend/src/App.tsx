import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import ChatView from "./views/ChatView";
import CollectionsView from "./views/CollectionsView";
import DashboardView from "./views/DashboardView";
import DocumentsView from "./views/DocumentsView";

const LINKS = [
  { to: "/chats", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/collections", label: "Collections" },
  { to: "/dashboard", label: "Dashboard" },
];

export default function App() {
  return (
    <BrowserRouter>
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
            <Route path="/dashboard" element={<DashboardView />} />
            <Route path="*" element={<Navigate to="/chats" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
