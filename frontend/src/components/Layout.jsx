import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LayoutDashboard, Globe, Sparkles, ImagePlay, Users, ShieldCheck, Menu, X, Wallet, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const NAV_BASE = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
    { to: "/websites", label: "Websites", icon: Globe, testid: "nav-websites" },
    { to: "/generate", label: "Generate Ad", icon: Sparkles, testid: "nav-generate" },
    { to: "/gallery", label: "Ad Gallery", icon: ImagePlay, testid: "nav-gallery" },
    { to: "/leads", label: "Leads", icon: Users, testid: "nav-leads" },
];

const ADMIN_EXTRA = { to: "/admin/users", label: "Manage Users", icon: ShieldCheck, testid: "nav-admin" };

const MARQUEE_ITEMS = [
    "🔥 Peak student traffic: 8-10 AM",
    "📚 Lunch break: 1-2 PM",
    "🌙 Prime evening: 6-9 PM",
    "✨ Auto-generate ads for any website",
    "🎬 Image + Video ads supported",
    "🚀 GPT-5.2 + Nano Banana + Sora 2",
];

const Marquee = () => {
    const doubled = [...MARQUEE_ITEMS, ...MARQUEE_ITEMS];
    return (
        <div className="marquee" data-testid="header-marquee">
            <div className="marquee-track">
                {doubled.map((t, i) => <span key={`${t}-${i}`}>{t}</span>)}
            </div>
        </div>
    );
};

const WalletBadge = () => {
    const [balance, setBalance] = useState(null);
    const [unlimited, setUnlimited] = useState(false);
    useEffect(() => {
        const fetchBalance = () => {
            apiClient.get("/wallet").then((r) => {
                setBalance(r.data.balance);
                setUnlimited(!!r.data.unlimited);
            }).catch(() => {});
        };
        fetchBalance();
        const i = setInterval(fetchBalance, 30000);
        return () => clearInterval(i);
    }, []);
    return (
        <span className="nb-badge nb-badge-approved !text-sm" data-testid="wallet-badge">
            <Wallet size={12} strokeWidth={3} /> {unlimited ? "∞ Unlimited" : `${balance ?? "—"} cr`}
        </span>
    );
};

const Brand = ({ branding }) => (
    <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-[#FFD84D] border-2 border-black flex items-center justify-center font-display font-black text-xl">A</div>
        <div>
            <h1 className="font-display font-black text-xl leading-none" data-testid="app-title">ADS.STUDIO</h1>
            <p className="text-[0.65rem] tracking-[0.2em] uppercase font-bold text-neutral-700 mt-0.5">
                {branding.company || "AI Social Ad Engine"}
            </p>
        </div>
    </div>
);

const TopHeader = ({ openMobile, toggleMobile, user, branding, logout }) => (
    <header className="bg-white border-b-2 border-black flex items-center justify-between px-4 md:px-8 py-3 sticky top-0 z-30">
        <div className="flex items-center gap-3">
            <button data-testid="mobile-menu-toggle" className="md:hidden nb-btn !p-2" onClick={toggleMobile}>
                {openMobile ? <X size={18} /> : <Menu size={18} />}
            </button>
            <Brand branding={branding} />
        </div>
        <div className="flex items-center gap-2 md:gap-3">
            <WalletBadge />
            <span className="hidden sm:inline-block text-xs font-mono" data-testid="user-email">{user.email}</span>
            <button className="nb-btn nb-btn-danger !p-2" onClick={logout} title="Logout" data-testid="logout-btn">
                <LogOut size={14} />
            </button>
        </div>
    </header>
);

const getNavItemClass = (active) =>
    `flex items-center gap-3 px-4 py-3 border-2 border-black font-bold uppercase tracking-wider text-sm transition-all ${active ? "bg-black text-white shadow-[4px_4px_0_0_#000]" : "bg-white text-black hover:bg-[#FFD84D]"}`;

const isPathActive = (pathname, to) => pathname === to || (to !== "/" && pathname.startsWith(to));

const SidebarNav = ({ pathname, navItems, onItemClick }) => (
    <nav className="p-4 space-y-2">
        {navItems.map(({ to, label, icon: Icon, testid }) => (
            <NavLink key={to} to={to} data-testid={testid} onClick={onItemClick} className={() => getNavItemClass(isPathActive(pathname, to))}>
                <Icon size={18} strokeWidth={2.5} />
                {label}
            </NavLink>
        ))}
    </nav>
);

const FooterCredit = ({ branding }) => (
    <div className="px-4 py-2 mt-4">
        <div className="nb-card p-4 bg-[#A7F3D0]">
            <p className="label-uppercase">Built by</p>
            <p className="font-display font-black text-lg mt-1">{branding.creator}</p>
            <p className="text-xs font-bold">{branding.company}</p>
        </div>
    </div>
);

const Sidebar = ({ open, pathname, navItems, branding, onItemClick }) => (
    <aside className={`${open ? "block" : "hidden"} md:block w-full md:w-64 bg-[#DDD6FE] border-r-2 border-black md:sticky md:top-[65px] md:h-[calc(100vh-65px)] z-20 overflow-y-auto`} data-testid="sidebar">
        <SidebarNav pathname={pathname} navItems={navItems} onItemClick={onItemClick} />
        <FooterCredit branding={branding} />
    </aside>
);

const Layout = () => {
    const [openMobile, setOpenMobile] = useState(false);
    const { pathname } = useLocation();
    const { user, logout, branding } = useAuth();

    const navItems = user?.role === "admin" ? [...NAV_BASE, ADMIN_EXTRA] : NAV_BASE;

    return (
        <div className="min-h-screen flex flex-col" data-testid="app-root">
            <Marquee />
            <TopHeader
                openMobile={openMobile}
                toggleMobile={() => setOpenMobile(!openMobile)}
                user={user}
                branding={branding}
                logout={logout}
            />
            <div className="flex flex-1">
                <Sidebar
                    open={openMobile}
                    pathname={pathname}
                    navItems={navItems}
                    branding={branding}
                    onItemClick={() => setOpenMobile(false)}
                />
                <main className="flex-1 min-w-0 page-wrap" data-testid="main-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default Layout;
