import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient, mediaUrl } from "@/lib/api";
import { Sparkles, Globe, ImagePlay, CheckCircle2, Download, Clock, ArrowRight, Image as ImageIcon } from "lucide-react";

const StatCard = ({ label, value, color, icon: Icon, testid }) => (
    <div className={`nb-card nb-card-hover p-6 ${color}`} data-testid={testid}>
        <div className="flex items-start justify-between">
            <p className="label-uppercase">{label}</p>
            <Icon size={20} strokeWidth={2.5} />
        </div>
        <p className="font-display font-black text-5xl md:text-6xl mt-3 leading-none">{value}</p>
    </div>
);

const PEAK_SLOTS = [
    { label: "Morning rush", time: "8:00 - 10:00 AM", reason: "Students before class scroll Instagram heavily" },
    { label: "Lunch break", time: "1:00 - 2:00 PM", reason: "Cafeteria scroll time, high reel views" },
    { label: "Evening prime", time: "6:00 - 9:00 PM", reason: "Highest engagement, peak shareability" },
];

const Dashboard = () => {
    const [stats, setStats] = useState({ total_ads: 0, drafts: 0, approved: 0, downloaded: 0, websites: 0, pending_videos: 0 });
    const [recent, setRecent] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        try {
            const [s, ads] = await Promise.all([apiClient.get("/stats"), apiClient.get("/ads")]);
            setStats(s.data);
            setRecent(ads.data.slice(0, 6));
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    return (
        <div className="space-y-8" data-testid="dashboard-page">
            {/* Hero */}
            <div className="nb-card p-6 md:p-10 bg-[#FFD84D]" data-testid="hero-card">
                <p className="label-uppercase">Welcome back, marketer</p>
                <h1 className="font-display font-black text-4xl sm:text-5xl lg:text-6xl uppercase mt-2 leading-[0.95]">
                    Ship scroll-stopping
                    <br />
                    ads. <span className="bg-black text-white px-3">Every day.</span>
                </h1>
                <p className="text-base md:text-lg font-medium mt-4 max-w-2xl">
                    Plug in any website, let the AI engine cook captions, banner images and short video ads — you review,
                    download, and post.
                </p>
                <div className="flex flex-wrap gap-3 mt-6">
                    <Link to="/generate" className="nb-btn nb-btn-primary" data-testid="hero-generate-btn">
                        <Sparkles size={16} strokeWidth={2.5} /> Generate New Ad
                    </Link>
                    <Link to="/websites" className="nb-btn" data-testid="hero-websites-btn">
                        <Globe size={16} strokeWidth={2.5} /> Manage Websites
                    </Link>
                </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6" data-testid="stats-grid">
                <StatCard label="Total Ads" value={stats.total_ads} color="bg-white" icon={ImagePlay} testid="stat-total" />
                <StatCard label="Drafts" value={stats.drafts} color="bg-[#F3F4F6]" icon={Clock} testid="stat-drafts" />
                <StatCard label="Approved" value={stats.approved} color="bg-[#A7F3D0]" icon={CheckCircle2} testid="stat-approved" />
                <StatCard label="Downloaded" value={stats.downloaded} color="bg-[#DDD6FE]" icon={Download} testid="stat-downloaded" />
            </div>

            {/* Peak times */}
            <div>
                <div className="flex items-end justify-between mb-4">
                    <div>
                        <p className="label-uppercase">When to post</p>
                        <h2 className="font-display font-bold text-2xl md:text-3xl mt-1">Peak Student Traffic Hours</h2>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6" data-testid="peak-times-grid">
                    {PEAK_SLOTS.map((slot, i) => (
                        <div key={slot.label} className={`nb-card p-6 ${["bg-[#FFDBCB]", "bg-[#BAE6FD]", "bg-[#A7F3D0]"][i]}`} data-testid={`peak-slot-${i}`}>
                            <p className="label-uppercase">{slot.label}</p>
                            <p className="font-display font-black text-3xl mt-2">{slot.time}</p>
                            <p className="text-sm mt-3 font-medium">{slot.reason}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Recent ads */}
            <div>
                <div className="flex items-end justify-between mb-4">
                    <div>
                        <p className="label-uppercase">Latest output</p>
                        <h2 className="font-display font-bold text-2xl md:text-3xl mt-1">Recent Ads</h2>
                    </div>
                    <Link to="/gallery" className="nb-btn nb-btn-lavender hidden sm:inline-flex" data-testid="view-all-ads-btn">
                        View all <ArrowRight size={16} />
                    </Link>
                </div>

                {loading ? (
                    <div className="nb-card p-10 text-center">
                        <div className="nb-spinner mx-auto" />
                        <p className="mt-3 font-bold uppercase tracking-wider text-sm">Loading...</p>
                    </div>
                ) : recent.length === 0 ? (
                    <div className="nb-card p-10 text-center bg-white" data-testid="empty-recent">
                        <ImageIcon size={40} strokeWidth={2.5} className="mx-auto" />
                        <h3 className="font-display font-bold text-xl mt-4">No ads yet</h3>
                        <p className="text-sm mt-2 font-medium">Generate your first AI ad to see it here.</p>
                        <Link to="/generate" className="nb-btn nb-btn-primary mt-5 inline-flex" data-testid="empty-generate-btn">
                            <Sparkles size={16} /> Get Started
                        </Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        {recent.map((ad) => (
                            <div key={ad.id} className="nb-card nb-card-hover overflow-hidden" data-testid={`recent-ad-${ad.id}`}>
                                <div className="aspect-square bg-[#F3F4F6] border-b-2 border-black overflow-hidden flex items-center justify-center">
                                    {ad.image_path ? (
                                        <img src={mediaUrl(ad.image_path)} alt={ad.topic} className="w-full h-full object-cover" />
                                    ) : (
                                        <ImageIcon size={48} strokeWidth={2.5} className="text-neutral-400" />
                                    )}
                                </div>
                                <div className="p-4">
                                    <span className={`nb-badge nb-badge-${ad.status}`}>{ad.status}</span>
                                    <h3 className="font-display font-bold text-lg mt-2 line-clamp-2">{ad.topic}</h3>
                                    <p className="text-xs mt-2 line-clamp-3 text-neutral-700">{ad.caption}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
