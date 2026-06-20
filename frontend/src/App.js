import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Websites from "@/pages/Websites";
import Generate from "@/pages/Generate";
import Gallery from "@/pages/Gallery";
import Leads from "@/pages/Leads";
import Login from "@/pages/Login";
import Apply from "@/pages/Apply";
import AdminUsers from "@/pages/AdminUsers";

const TOAST_OPTIONS = {
    style: {
        border: "2px solid #000",
        borderRadius: 0,
        boxShadow: "4px 4px 0 0 #000",
        background: "#fff",
        color: "#000",
        fontWeight: 600,
        zIndex: 9999,
    },
};

const Protected = ({ children }) => {
    const { user, loading } = useAuth();
    if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="nb-spinner" /></div>;
    if (!user) return <Navigate to="/login" replace />;
    return children;
};

function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <AuthProvider>
                    <Toaster position="top-right" toastOptions={TOAST_OPTIONS} />
                    <Routes>
                        <Route path="/login" element={<Login />} />
                        <Route path="/apply/:websiteId" element={<Apply />} />
                        <Route element={<Protected><Layout /></Protected>}>
                            <Route index element={<Dashboard />} />
                            <Route path="/websites" element={<Websites />} />
                            <Route path="/generate" element={<Generate />} />
                            <Route path="/gallery" element={<Gallery />} />
                            <Route path="/leads" element={<Leads />} />
                            <Route path="/admin/users" element={<AdminUsers />} />
                            <Route path="*" element={<Navigate to="/" replace />} />
                        </Route>
                    </Routes>
                </AuthProvider>
            </BrowserRouter>
        </div>
    );
}

export default App;
