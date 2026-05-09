import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { Toaster } from "./components/ui/sonner";
import "./App.css";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import AuthCallback from "./pages/AuthCallback";
import Dashboard from "./pages/Dashboard";
import LicensePage from "./pages/LicensePage";
import DownloadsPage from "./pages/DownloadsPage";
import ScansPage from "./pages/ScansPage";
import CouponsPage from "./pages/CouponsPage";
import AdminStats from "./pages/AdminStats";
import AdminUsers from "./pages/AdminUsers";
import AdminCoupons from "./pages/AdminCoupons";
import AdminBuilds from "./pages/AdminBuilds";
import BillingPage from "./pages/BillingPage";
import BillingSuccess from "./pages/BillingSuccess";
import BillingCancel from "./pages/BillingCancel";
import VerifyEmail from "./pages/VerifyEmail";
import ProtectedRoute from "./components/ProtectedRoute";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

function AppRouter() {
  // Detect Emergent OAuth callback synchronously
  if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/verify-email" element={<VerifyEmail />} />

        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/dashboard/license" element={<ProtectedRoute><LicensePage /></ProtectedRoute>} />
        <Route path="/dashboard/downloads" element={<ProtectedRoute><DownloadsPage /></ProtectedRoute>} />
        <Route path="/dashboard/scans" element={<ProtectedRoute><ScansPage /></ProtectedRoute>} />
        <Route path="/dashboard/coupons" element={<ProtectedRoute><CouponsPage /></ProtectedRoute>} />
        <Route path="/dashboard/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} />
        <Route path="/billing/success" element={<ProtectedRoute><BillingSuccess /></ProtectedRoute>} />
        <Route path="/billing/cancel" element={<ProtectedRoute><BillingCancel /></ProtectedRoute>} />

        <Route path="/admin" element={<ProtectedRoute adminOnly><AdminStats /></ProtectedRoute>} />
        <Route path="/admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />
        <Route path="/admin/coupons" element={<ProtectedRoute adminOnly><AdminCoupons /></ProtectedRoute>} />
        <Route path="/admin/builds" element={<ProtectedRoute adminOnly><AdminBuilds /></ProtectedRoute>} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster richColors position="top-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
