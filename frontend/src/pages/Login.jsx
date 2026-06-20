import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LogIn, Sparkles } from "lucide-react";
import { toast } from "sonner";

const Login = () => {
    const { login, user, branding, loading } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center"><div className="nb-spinner" /></div>;
    }
    if (user) return <Navigate to="/" replace />;

    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await login(email, password);
            toast.success("Welcome back!");
        } catch (err) {
            toast.error(err.response?.data?.detail || "Login failed");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-[#FFD84D]" data-testid="login-page">
            <div className="nb-card !shadow-[8px_8px_0_0_#000] bg-white max-w-md w-full p-8">
                <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-[#FFD84D] border-2 border-black flex items-center justify-center font-display font-black text-2xl">A</div>
                    <div>
                        <h1 className="font-display font-black text-2xl leading-none">ADS.STUDIO</h1>
                        <p className="text-[0.65rem] tracking-[0.2em] uppercase font-bold text-neutral-700 mt-0.5">{branding.company || "AI Social Ad Engine"}</p>
                    </div>
                </div>
                <p className="label-uppercase">Sign in</p>
                <h2 className="font-display font-black text-3xl mt-1">Welcome back 👋</h2>
                <p className="text-sm mt-2 font-medium">Login to manage your ads, leads, and wallet.</p>

                <form onSubmit={submit} className="mt-6 space-y-4" data-testid="login-form">
                    <div>
                        <label className="label-uppercase">Email</label>
                        <input
                            className="nb-input mt-2"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            data-testid="login-email-input"
                        />
                    </div>
                    <div>
                        <label className="label-uppercase">Password</label>
                        <input
                            className="nb-input mt-2"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            data-testid="login-password-input"
                        />
                    </div>
                    <button type="submit" className="nb-btn nb-btn-primary w-full !py-4" disabled={submitting} data-testid="login-submit-btn">
                        {submitting ? <div className="nb-spinner" /> : <LogIn size={16} strokeWidth={2.5} />} Sign in
                    </button>
                </form>

                <p className="text-xs text-center mt-6 font-medium">
                    <Sparkles size={12} className="inline mr-1" /> By {branding.creator}
                </p>
            </div>
        </div>
    );
};

export default Login;
