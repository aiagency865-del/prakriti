import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import PostLoginStub from "@/pages/PostLoginStub";
import CommandCenter from "@/pages/CommandCenter";
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
            <Route path="/logistics" element={<Protected><PostLoginStub pageTitle="Logistics Workspace" /></Protected>} />
            <Route path="/field" element={<Protected><PostLoginStub pageTitle="Field Reporting" /></Protected>} />
            <Route path="/public" element={<Protected><PostLoginStub pageTitle="Public Advisories" /></Protected>} />
            <Route path="/map" element={<Protected><PostLoginStub pageTitle="GIS Map" /></Protected>} />
            <Route path="/vehicles" element={<Protected><PostLoginStub pageTitle="Fleet Tracking" /></Protected>} />
            <Route path="/routes" element={<Protected><PostLoginStub pageTitle="Route Calculation" /></Protected>} />
            <Route path="/incidents" element={<Protected><PostLoginStub pageTitle="Incidents" /></Protected>} />
            <Route path="/supply" element={<Protected><PostLoginStub pageTitle="Supply Intelligence" /></Protected>} />
            <Route path="/predictions" element={<Protected><PostLoginStub pageTitle="Hazard Predictions" /></Protected>} />
            <Route path="/alerts" element={<Protected><PostLoginStub pageTitle="Alerts" /></Protected>} />
            <Route path="/audit" element={<Protected><PostLoginStub pageTitle="Audit Log" /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
