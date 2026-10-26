import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { ProtectedRoute } from "./components/protected-route";
import { ChatPage } from "./pages/chat-page";
import { PerfilPage } from "./pages/perfil-page";
import { LoginPage } from "./pages/login-page";
import { MetricsPage } from "./pages/metrics-page";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat/:chatId"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/perfil"
          element={
            <ProtectedRoute>
              <PerfilPage />
            </ProtectedRoute>
          }
        />
        <Route path="/fluxo" element={<Navigate to="/chat" replace />} />
        <Route
          path="/metrics"
          element={
            <ProtectedRoute>
              <MetricsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
