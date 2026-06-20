import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";

const AuthContext = createContext(null);

const TOKEN_KEY = "ads_studio_token";

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [branding, setBranding] = useState({ creator: "Admin", company: "" });

    // attach interceptor once
    useMemo(() => {
        apiClient.interceptors.request.use((config) => {
            const token = localStorage.getItem(TOKEN_KEY);
            if (token) config.headers.Authorization = `Bearer ${token}`;
            return config;
        });
        apiClient.interceptors.response.use(
            (r) => r,
            (err) => {
                if (err.response?.status === 401) {
                    localStorage.removeItem(TOKEN_KEY);
                    setUser(null);
                }
                return Promise.reject(err);
            }
        );
        return null;
    }, []);

    const refresh = useCallback(async () => {
        try {
            const res = await apiClient.get("/auth/me");
            setUser(res.data);
        } catch {
            setUser(null);
        }
    }, []);

    useEffect(() => {
        const token = localStorage.getItem(TOKEN_KEY);
        if (token) {
            refresh().finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
        apiClient.get("/branding").then((r) => setBranding(r.data)).catch(() => {});
    }, [refresh]);

    const login = async (email, password) => {
        const res = await apiClient.post("/auth/login", { email, password });
        localStorage.setItem(TOKEN_KEY, res.data.token);
        setUser(res.data.user);
    };

    const logout = () => {
        localStorage.removeItem(TOKEN_KEY);
        setUser(null);
    };

    const value = { user, loading, login, logout, branding, refresh };
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
};
