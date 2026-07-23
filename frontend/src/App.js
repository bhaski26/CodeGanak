import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import RepositoryDetail from "@/pages/RepositoryDetail";
import ProtectedRoute from "@/components/ProtectedRoute";
import CommandPalette from "@/components/CommandPalette";

function App() {
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="App min-h-screen text-foreground">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard onOpenCommand={() => setCmdOpen(true)} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/repositories/:repoId"
            element={
              <ProtectedRoute>
                <RepositoryDetail onOpenCommand={() => setCmdOpen(true)} />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <CommandPalette open={cmdOpen} setOpen={setCmdOpen} />
      </BrowserRouter>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "bg-card border border-border text-foreground rounded-md shadow-lg",
            description: "text-muted-foreground",
          },
        }}
      />
    </div>
  );
}

export default App;
