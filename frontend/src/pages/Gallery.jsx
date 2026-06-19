import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient, mediaUrl, API } from "@/lib/api";
import { Download, Trash2, CheckCircle2, Copy, ImagePlay, RefreshCw, X, Filter, Film } from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTIONS = [
    { value: "all", label: "All" },
    { value: "draft", label: "Drafts" },
    { value: "approved", label: "Approved" },
    { value: "downloaded", label: "Downloaded" },
];

const Gallery = () => {
    const [ads, setAds] = useState([]);
    const [websites, setWebsites] = useState([]);
    const [status, setStatus] = useState("all");
    const [websiteFilter, setWebsiteFilter] = useState("all");
    const [loading, setLoading] = useState(true);
    const [focusAd, setFocusAd] = useState(null);
    const [searchParams, setSearchParams] = useSearchParams();

    const load = async () => {
        try {
            const [adsRes, sitesRes] = await Promise.all([apiClient.get("/ads"), apiClient.get("/websites")]);
            setAds(adsRes.data);
            setWebsites(sitesRes.data);
            const fid = searchParams.get("focus");
            if (fid) {
                const f = adsRes.data.find((a) => a.id === fid);
                if (f) setFocusAd(f);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        // Auto-refresh pending videos every 20 seconds
        const interval = setInterval(() => {
            apiClient.get("/ads").then((r) => {
                setAds(r.data);
                setFocusAd((curr) => {
                    if (!curr) return curr;
                    return r.data.find((a) => a.id === curr.id) || curr;
                });
            });
        }, 20000);
        return () => clearInterval(interval);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const filtered = useMemo(() => {
        return ads.filter((a) => {
            if (status !== "all" && a.status !== status) return false;
            if (websiteFilter !== "all" && a.website_id !== websiteFilter) return false;
            return true;
        });
    }, [ads, status, websiteFilter]);

    const updateStatus = async (id, newStatus) => {
        try {
            await apiClient.patch(`/ads/${id}/status`, { status: newStatus });
            toast.success(`Marked ${newStatus}`);
            load();
        } catch {
            toast.error("Could not update status");
        }
    };

    const remove = async (id) => {
        if (!window.confirm("Delete this ad? Images/video files will be removed.")) return;
        try {
            await apiClient.delete(`/ads/${id}`);
            toast.success("Deleted");
            setFocusAd(null);
            load();
        } catch {
            toast.error("Could not delete");
        }
    };

    const downloadFile = async (id, kind) => {
        try {
            const res = await apiClient.get(`/ads/${id}/download/${kind}`, { responseType: "blob" });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement("a");
            a.href = url;
            a.download = `ad-${id}.${kind === "image" ? "png" : "mp4"}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            toast.success(`Downloaded ${kind}`);
            load();
        } catch {
            toast.error("Download failed");
        }
    };

    const copyCaption = (ad) => {
        const text = `${ad.caption}\n\n${(ad.hashtags || []).join(" ")}`;
        navigator.clipboard.writeText(text);
        toast.success("Caption copied");
    };

    return (
        <div className="space-y-6" data-testid="gallery-page">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                    <p className="label-uppercase">Library</p>
                    <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Ad Gallery</h1>
                    <p className="text-sm mt-2 max-w-xl font-medium">
                        Review, approve, copy captions, download images & videos. Post to Instagram / Facebook manually.
                    </p>
                </div>
                <button className="nb-btn" onClick={load} data-testid="refresh-btn">
                    <RefreshCw size={16} strokeWidth={2.5} /> Refresh
                </button>
            </div>

            {/* Filters */}
            <div className="nb-card p-4 flex flex-col md:flex-row md:items-center gap-3">
                <div className="flex items-center gap-2">
                    <Filter size={16} strokeWidth={2.5} />
                    <p className="label-uppercase">Filters</p>
                </div>
                <div className="flex gap-2 flex-wrap">
                    {STATUS_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            className={`nb-btn !py-2 !px-3 !text-xs ${status === opt.value ? "nb-btn-primary" : ""}`}
                            onClick={() => setStatus(opt.value)}
                            data-testid={`filter-status-${opt.value}`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
                <select
                    className="nb-input md:max-w-xs !py-2"
                    value={websiteFilter}
                    onChange={(e) => setWebsiteFilter(e.target.value)}
                    data-testid="filter-website-select"
                >
                    <option value="all">All websites</option>
                    {websites.map((w) => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                </select>
            </div>

            {loading ? (
                <div className="nb-card p-10 text-center">
                    <div className="nb-spinner mx-auto" />
                </div>
            ) : filtered.length === 0 ? (
                <div className="nb-card p-10 text-center bg-white" data-testid="empty-gallery">
                    <ImagePlay size={40} strokeWidth={2.5} className="mx-auto" />
                    <h3 className="font-display font-bold text-2xl mt-4">No ads match your filters</h3>
                    <p className="text-sm mt-2 font-medium">Generate a new one to see it here.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="ads-grid">
                    {filtered.map((ad) => (
                        <div key={ad.id} className="nb-card nb-card-hover overflow-hidden" data-testid={`ad-card-${ad.id}`}>
                            <button onClick={() => setFocusAd(ad)} className="block w-full text-left">
                                <div className="aspect-square bg-[#F3F4F6] border-b-2 border-black overflow-hidden flex items-center justify-center relative">
                                    {ad.image_path ? (
                                        <img src={mediaUrl(ad.image_path)} alt={ad.topic} className="w-full h-full object-cover" />
                                    ) : (
                                        <ImagePlay size={48} strokeWidth={2.5} className="text-neutral-400" />
                                    )}
                                    {ad.video_status !== "none" && (
                                        <div className="absolute top-2 right-2">
                                            <span className={`nb-badge nb-badge-${ad.video_status === "ready" ? "ready" : ad.video_status === "failed" ? "failed" : "pending"}`}>
                                                <Film size={10} strokeWidth={3} /> {ad.video_status}
                                            </span>
                                        </div>
                                    )}
                                </div>
                                <div className="p-4">
                                    <div className="flex items-center justify-between">
                                        <span className={`nb-badge nb-badge-${ad.status}`}>{ad.status}</span>
                                        {ad.website_name && (
                                            <span className="text-xs font-mono truncate max-w-[120px]">{ad.website_name}</span>
                                        )}
                                    </div>
                                    <h3 className="font-display font-bold text-lg mt-2 line-clamp-2">{ad.topic}</h3>
                                    <p className="text-xs mt-2 line-clamp-2 text-neutral-700">{ad.caption}</p>
                                </div>
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Detail drawer */}
            {focusAd && (
                <div className="fixed inset-0 bg-black/60 z-40 flex items-start justify-center p-4 md:p-8 overflow-y-auto" onClick={() => setFocusAd(null)} data-testid="ad-detail-overlay">
                    <div
                        className="nb-card !shadow-[8px_8px_0_0_#000] bg-white max-w-3xl w-full my-auto"
                        onClick={(e) => e.stopPropagation()}
                        data-testid="ad-detail-modal"
                    >
                        <div className="flex items-start justify-between p-6 border-b-2 border-black">
                            <div>
                                <span className={`nb-badge nb-badge-${focusAd.status}`}>{focusAd.status}</span>
                                <h2 className="font-display font-black text-2xl mt-2">{focusAd.topic}</h2>
                                {focusAd.website_name && (
                                    <p className="text-xs font-mono mt-1">{focusAd.website_name}</p>
                                )}
                            </div>
                            <button className="nb-btn !p-2" onClick={() => setFocusAd(null)} data-testid="close-detail-btn">
                                <X size={16} />
                            </button>
                        </div>

                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <p className="label-uppercase">Image</p>
                                {focusAd.image_path ? (
                                    <img src={mediaUrl(focusAd.image_path)} alt={focusAd.topic} className="w-full mt-2 border-2 border-black" />
                                ) : (
                                    <div className="mt-2 p-6 border-2 border-black bg-[#F3F4F6] text-center text-sm">No image</div>
                                )}
                                {focusAd.video_status !== "none" && (
                                    <>
                                        <p className="label-uppercase mt-4">Video</p>
                                        {focusAd.video_status === "ready" && focusAd.video_path ? (
                                            <video src={mediaUrl(focusAd.video_path)} controls className="w-full mt-2 border-2 border-black" data-testid="detail-video"/>
                                        ) : focusAd.video_status === "pending" ? (
                                            <div className="mt-2 p-6 border-2 border-black bg-[#FFDBCB] text-center">
                                                <div className="nb-spinner mx-auto" />
                                                <p className="text-xs font-bold mt-2 uppercase tracking-wider">Generating video... (2-5 min)</p>
                                            </div>
                                        ) : (
                                            <div className="mt-2 p-6 border-2 border-black bg-red-200 text-center text-sm font-bold">Video failed</div>
                                        )}
                                    </>
                                )}
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <div className="flex items-center justify-between">
                                        <p className="label-uppercase">Caption</p>
                                        <button className="nb-btn !p-2 !shadow-[2px_2px_0_0_#000]" onClick={() => copyCaption(focusAd)} data-testid="copy-caption-btn" title="Copy caption + hashtags">
                                            <Copy size={14} />
                                        </button>
                                    </div>
                                    <p className="text-sm mt-2 whitespace-pre-wrap font-medium">{focusAd.caption}</p>
                                </div>
                                <div>
                                    <p className="label-uppercase">Hashtags</p>
                                    <div className="flex flex-wrap gap-1 mt-2">
                                        {(focusAd.hashtags || []).map((h, i) => (
                                            <span key={i} className="nb-badge !bg-[#DDD6FE]">{h}</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="border-t-2 border-black p-6 flex flex-wrap gap-2">
                            {focusAd.status !== "approved" && focusAd.status !== "downloaded" && (
                                <button className="nb-btn nb-btn-mint" onClick={() => updateStatus(focusAd.id, "approved")} data-testid="approve-btn">
                                    <CheckCircle2 size={16} strokeWidth={2.5} /> Approve
                                </button>
                            )}
                            {focusAd.image_path && (
                                <button className="nb-btn nb-btn-primary" onClick={() => downloadFile(focusAd.id, "image")} data-testid="download-image-btn">
                                    <Download size={16} strokeWidth={2.5} /> Download Image
                                </button>
                            )}
                            {focusAd.video_status === "ready" && (
                                <button className="nb-btn nb-btn-lavender" onClick={() => downloadFile(focusAd.id, "video")} data-testid="download-video-btn">
                                    <Download size={16} strokeWidth={2.5} /> Download Video
                                </button>
                            )}
                            <button className="nb-btn nb-btn-danger ml-auto" onClick={() => remove(focusAd.id)} data-testid="delete-btn">
                                <Trash2 size={16} strokeWidth={2.5} /> Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Gallery;
