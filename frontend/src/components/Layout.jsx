import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LayoutDashboard, Globe, Sparkles, ImagePlay, Settings as SettingsIcon, Menu, X } from "lucide-react";
import { useState } from "react";

const NAV = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
    { to: "/websites", label: "Websites", icon: Globe, testid: "nav-websites" },
    { to: "/generate", label: "Generate Ad", icon: Sparkles, testid: "nav-generate" },
    { to: "/gallery", label: "Ad Gallery", icon: ImagePlay, testid: "nav-gallery" },
    { to: "/settings", label: "Settings", icon: SettingsIcon, testid: "nav-settings" },
];

const Marquee = () => {
    const items = [
        "🔥 Peak student traffic: 8-10 AM",
        "📚 Lunch break window: 1-2 PM",
        "🌙 Prime evening slot: 6-9 PM",
        "✨ Auto-generate ads for any website",
        "🎬 Image + Video ads supported",
        "🚀 Powered by GPT-5.2 + Nano Banana + Sora 2",
    ];
    const doubled = [...items, ...items];
    return (
        <div className="marquee" data-testid="header-marquee">
            <div className="marquee-track">
                {doubled.map((t, i) => (
                    <span key={`${t}-${i}`}>{t}</span>
                ))}
            </div>
        </div>
    );
};

const Layout = () => {
    const [openMobile, setOpenMobile] = useState(false);
    const location = useLocation();

    return (
        <div className="min-h-screen flex flex-col" data-testid="app-root">
            <Marquee />

            {/* Top header */}
            <header className="bg-white border-b-2 border-black flex items-center justify-between px-4 md:px-8 py-4 sticky top-0 z-30">
                <div className="flex items-center gap-3">
                    <button
                        data-testid="mobile-menu-toggle"
                        className="md:hidden nb-btn !p-2"
                        onClick={() => setOpenMobile(!openMobile)}
                        aria-label="Menu"
                    >
                        {openMobile ? <X size={18} /> : <Menu size={18} />}
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#FFD84D] border-2 border-black flex items-center justify-center font-display font-black text-xl">
                            A
                        </div>
                        <div>
                            <h1 className="font-display font-black text-xl leading-none" data-testid="app-title">
                                ADS.STUDIO
                            </h1>
                            <p className="text-[0.65rem] tracking-[0.2em] uppercase font-bold text-neutral-700 mt-0.5">
                                AI Social Ad Engine
                            </p>
                        </div>
                    </div>
                </div>
                <div className="hidden md:flex items-center gap-3">
                    <span className="nb-badge nb-badge-ready" data-testid="header-status-badge">
                        <span className="w-2 h-2 rounded-full bg-black inline-block" /> LIVE
                    </span>
                </div>
            </header>

            <div className="flex flex-1">
                {/* Sidebar */}
                <aside
                    className={`${openMobile ? "block" : "hidden"} md:block w-full md:w-64 bg-[#DDD6FE] border-r-2 border-black md:sticky md:top-[73px] md:h-[calc(100vh-73px)] z-20`}
                    data-testid="sidebar"
                >
                    <nav className="p-4 space-y-2">
                        {NAV.map(({ to, label, icon: Icon, testid }) => {
                            const active = location.pathname === to || (to !== "/" && location.pathname.startsWith(to));
                            return (
                                <NavLink
                                    key={to}
                                    to={to}
                                    data-testid={testid}
                                    onClick={() => setOpenMobile(false)}
                                    className={() =>
                                        `flex items-center gap-3 px-4 py-3 border-2 border-black font-bold uppercase tracking-wider text-sm transition-all ${
                                            active
                                                ? "bg-black text-white shadow-[4px_4px_0_0_#000]"
                                                : "bg-white text-black hover:bg-[#FFD84D]"
                                        }`
                                    }
                                >
                                    <Icon size={18} strokeWidth={2.5} />
                                    {label}
                                </NavLink>
                            );
                        })}
                    </nav>
                    <div className="px-4 py-2 mt-4">
                        <div className="nb-card p-4 bg-[#A7F3D0]">
                            <p className="label-uppercase">Pro Tip</p>
                            <p className="text-sm mt-2 font-medium">
                                Generate ads during peak student hours (8-10 AM, 6-9 PM) for max engagement.
                            </p>
                        </div>
                    </div>
                </aside>

                {/* Main content */}
                <main className="flex-1 min-w-0 page-wrap" data-testid="main-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default Layout;
