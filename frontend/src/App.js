import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import CommandCenter from "@/pages/CommandCenter";
import Vehicles from "@/pages/Vehicles";
import RoutesPage from "@/pages/Routes";
import LogisticsWorkspace from "@/pages/LogisticsWorkspace";
import FieldReporting from "@/pages/FieldReporting";
import PublicAdvisories from "@/pages/PublicAdvisories";
import GisMap from "@/pages/GisMap";
import Incidents from "@/pages/Incidents";
import Supply from "@/pages/Supply";
import Predictions from "@/pages/Predictions";
import Alerts from "@/pages/Alerts";
import Audit from "@/pages/Audit";
import { Toaster } from "sonner";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center text-[13px] text-neutral-500">
        Loading…
      </div>
    );
  }
  if (!user || typeof user !== "object") return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Toaster position="top-right" />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/command-center" element={<Protected><CommandCenter /></Protected>} />
            <Route path="/logistics" element={<Protected><LogisticsWorkspace /></Protected>} />
            <Route path="/field" element={<Protected><FieldReporting /></Protected>} />
            <Route path="/public" element={<Protected><PublicAdvisories /></Protected>} />
            <Route path="/map" element={<Protected><GisMap /></Protected>} />
            <Route path="/vehicles" element={<Protected><Vehicles /></Protected>} />
            <Route path="/routes" element={<Protected><RoutesPage /></Protected>} />
            <Route path="/incidents" element={<Protected><Incidents /></Protected>} />
            <Route path="/supply" element={<Protected><Supply /></Protected>} />
            <Route path="/predictions" element={<Protected><Predictions /></Protected>} />
            <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
            <Route path="/audit" element={<Protected><Audit /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
