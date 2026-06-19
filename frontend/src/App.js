import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Websites from "@/pages/Websites";
import Generate from "@/pages/Generate";
import Gallery from "@/pages/Gallery";
import Settings from "@/pages/Settings";

function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <Toaster
                    position="top-right"
                    toastOptions={{
                        style: {
                            border: "2px solid #000",
                            borderRadius: 0,
                            boxShadow: "4px 4px 0 0 #000",
                            background: "#fff",
                            color: "#000",
                            fontWeight: 600,
                        },
                    }}
                />
                <Routes>
                    <Route element={<Layout />}>
                        <Route index element={<Dashboard />} />
                        <Route path="/websites" element={<Websites />} />
                        <Route path="/generate" element={<Generate />} />
                        <Route path="/gallery" element={<Gallery />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </div>
    );
}

export default App;
