import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient, mediaUrl } from "@/lib/api";
import { useAdActions } from "@/hooks/useAdActions";
import {
    Download, Trash2, CheckCircle2, Copy, ImagePlay, RefreshCw, X, Filter, Film,
} from "lucide-react";

const STATUS_OPTIONS = [
    { value: "all", label: "All" },
    { value: "draft", label: "Drafts" },
    { value: "approved", label: "Approved" },
    { value: "downloaded", label: "Downloaded" },
];

const POLL_INTERVAL_MS = 20_000;

const getVideoBadgeVariant = (videoStatus) => {
    if (videoStatus === "ready") return "ready";
    if (videoStatus === "failed") return "failed";
    return "pending";
};

const filterAds = (ads, statusFilter, websiteFilter) =>
    ads.filter((ad) => {
        if (statusFilter !== "all" && ad.status !== statusFilter) return false;
        if (websiteFilter !== "all" && ad.website_id !== websiteFilter) return false;
        return true;
    });

const Filters = ({ status, setStatus, websiteFilter, setWebsiteFilter, websites }) => (
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
);

const AdCard = ({ ad, onFocus }) => (
    <div className="nb-card nb-card-hover overflow-hidden" data-testid={`ad-card-${ad.id}`}>
        <button onClick={() => onFocus(ad)} className="block w-full text-left">
            <div className="aspect-square bg-[#F3F4F6] border-b-2 border-black overflow-hidden flex items-center justify-center relative">
                {ad.image_path ? (
                    <img src={mediaUrl(ad.image_path)} alt={ad.topic} className="w-full h-full object-cover" />
                ) : (
                    <ImagePlay size={48} strokeWidth={2.5} className="text-neutral-400" />
                )}
                {ad.video_status !== "none" && (
                    <div className="absolute top-2 right-2">
                        <span className={`nb-badge nb-badge-${getVideoBadgeVariant(ad.video_status)}`}>
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
);

const VideoPreview = ({ ad }) => {
    if (ad.video_status === "ready" && ad.video_path) {
        return (
            <video
                src={mediaUrl(ad.video_path)}
                controls
                className="w-full mt-2 border-2 border-black"
                data-testid="detail-video"
            />
        );
    }
    if (ad.video_status === "pending") {
        return (
            <div className="mt-2 p-6 border-2 border-black bg-[#FFDBCB] text-center">
                <div className="nb-spinner mx-auto" />
                <p className="text-xs font-bold mt-2 uppercase tracking-wider">Generating video... (2-5 min)</p>
            </div>
        );
    }
    return (
        <div className="mt-2 p-6 border-2 border-black bg-red-200 text-center text-sm font-bold">
            Video failed
        </div>
    );
};

const AdDetailModal = ({ ad, onClose, onApprove, onDownload, onDelete, onCopyCaption }) => (
    <div
        className="fixed inset-0 bg-black/60 z-40 flex items-start justify-center p-4 md:p-8 overflow-y-auto"
        onClick={onClose}
        data-testid="ad-detail-overlay"
    >
        <div
            className="nb-card !shadow-[8px_8px_0_0_#000] bg-white max-w-3xl w-full my-auto"
            onClick={(e) => e.stopPropagation()}
            data-testid="ad-detail-modal"
        >
            <div className="flex items-start justify-between p-6 border-b-2 border-black">
                <div>
                    <span className={`nb-badge nb-badge-${ad.status}`}>{ad.status}</span>
                    <h2 className="font-display font-black text-2xl mt-2">{ad.topic}</h2>
                    {ad.website_name && <p className="text-xs font-mono mt-1">{ad.website_name}</p>}
                </div>
                <button className="nb-btn !p-2" onClick={onClose} data-testid="close-detail-btn">
                    <X size={16} />
                </button>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <p className="label-uppercase">Image</p>
                    {ad.image_path ? (
                        <img src={mediaUrl(ad.image_path)} alt={ad.topic} className="w-full mt-2 border-2 border-black" />
                    ) : (
                        <div className="mt-2 p-6 border-2 border-black bg-[#F3F4F6] text-center text-sm">No image</div>
                    )}
                    {ad.video_status !== "none" && (
                        <>
                            <p className="label-uppercase mt-4">Video</p>
                            <VideoPreview ad={ad} />
                        </>
                    )}
                </div>

                <div className="space-y-4">
                    <div>
                        <div className="flex items-center justify-between">
                            <p className="label-uppercase">Caption</p>
                            <button
                                className="nb-btn !p-2 !shadow-[2px_2px_0_0_#000]"
                                onClick={onCopyCaption}
                                data-testid="copy-caption-btn"
                                title="Copy caption + hashtags"
                            >
                                <Copy size={14} />
                            </button>
                        </div>
                        <p className="text-sm mt-2 whitespace-pre-wrap font-medium">{ad.caption}</p>
                    </div>
                    <div>
                        <p className="label-uppercase">Hashtags</p>
                        <div className="flex flex-wrap gap-1 mt-2">
                            {(ad.hashtags || []).map((h) => (
                                <span key={h} className="nb-badge !bg-[#DDD6FE]">{h}</span>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div className="border-t-2 border-black p-6 flex flex-wrap gap-2">
                {ad.status !== "approved" && ad.status !== "downloaded" && (
                    <button className="nb-btn nb-btn-mint" onClick={onApprove} data-testid="approve-btn">
                        <CheckCircle2 size={16} strokeWidth={2.5} /> Approve
                    </button>
                )}
                {ad.image_path && (
                    <button className="nb-btn nb-btn-primary" onClick={() => onDownload("image")} data-testid="download-image-btn">
                        <Download size={16} strokeWidth={2.5} /> Download Image
                    </button>
                )}
                {ad.video_status === "ready" && (
                    <button className="nb-btn nb-btn-lavender" onClick={() => onDownload("video")} data-testid="download-video-btn">
                        <Download size={16} strokeWidth={2.5} /> Download Video
                    </button>
                )}
                <button className="nb-btn nb-btn-danger ml-auto" onClick={onDelete} data-testid="delete-btn">
                    <Trash2 size={16} strokeWidth={2.5} /> Delete
                </button>
            </div>
        </div>
    </div>
);

const GalleryBody = ({ loading, filtered, onFocus }) => {
    if (loading) {
        return (
            <div className="nb-card p-10 text-center">
                <div className="nb-spinner mx-auto" />
            </div>
        );
    }
    if (filtered.length === 0) {
        return (
            <div className="nb-card p-10 text-center bg-white" data-testid="empty-gallery">
                <ImagePlay size={40} strokeWidth={2.5} className="mx-auto" />
                <h3 className="font-display font-bold text-2xl mt-4">No ads match your filters</h3>
                <p className="text-sm mt-2 font-medium">Generate a new one to see it here.</p>
            </div>
        );
    }
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="ads-grid">
            {filtered.map((ad) => (
                <AdCard key={ad.id} ad={ad} onFocus={onFocus} />
            ))}
        </div>
    );
};

const GalleryPageHeader = ({ onRefresh }) => (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
            <p className="label-uppercase">Library</p>
            <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Ad Gallery</h1>
            <p className="text-sm mt-2 max-w-xl font-medium">
                Review, approve, copy captions, download images & videos. Post to Instagram / Facebook manually.
            </p>
        </div>
        <button className="nb-btn" onClick={onRefresh} data-testid="refresh-btn">
            <RefreshCw size={16} strokeWidth={2.5} /> Refresh
        </button>
    </div>
);

const Gallery = () => {
    const [ads, setAds] = useState([]);
    const [websites, setWebsites] = useState([]);
    const [status, setStatus] = useState("all");
    const [websiteFilter, setWebsiteFilter] = useState("all");
    const [loading, setLoading] = useState(true);
    const [focusAd, setFocusAd] = useState(null);
    const [searchParams] = useSearchParams();

    const load = useCallback(async () => {
        try {
            const [adsRes, sitesRes] = await Promise.all([
                apiClient.get("/ads"),
                apiClient.get("/websites"),
            ]);
            setAds(adsRes.data);
            setWebsites(sitesRes.data);
            const fid = searchParams.get("focus");
            if (fid) {
                const focused = adsRes.data.find((a) => a.id === fid);
                if (focused) setFocusAd(focused);
            }
        } finally {
            setLoading(false);
        }
    }, [searchParams]);

    const refreshSilent = useCallback(async () => {
        try {
            const r = await apiClient.get("/ads");
            setAds(r.data);
            setFocusAd((curr) => (curr ? r.data.find((a) => a.id === curr.id) || curr : curr));
        } catch (err) {
            console.warn("Background ads poll failed", err);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(() => {
        const interval = setInterval(refreshSilent, POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [refreshSilent]);

    const filtered = useMemo(
        () => filterAds(ads, status, websiteFilter),
        [ads, status, websiteFilter]
    );

    const { updateStatus, remove, downloadFile, copyCaption } = useAdActions({
        onChanged: load,
        onDeleted: () => setFocusAd(null),
    });

    return (
        <div className="space-y-6" data-testid="gallery-page">
            <GalleryPageHeader onRefresh={load} />
            <Filters
                status={status}
                setStatus={setStatus}
                websiteFilter={websiteFilter}
                setWebsiteFilter={setWebsiteFilter}
                websites={websites}
            />
            <GalleryBody loading={loading} filtered={filtered} onFocus={setFocusAd} />
            {focusAd && (
                <AdDetailModal
                    ad={focusAd}
                    onClose={() => setFocusAd(null)}
                    onApprove={() => updateStatus(focusAd.id, "approved")}
                    onDownload={(kind) => downloadFile(focusAd.id, kind)}
                    onDelete={() => remove(focusAd.id)}
                    onCopyCaption={() => copyCaption(focusAd)}
                />
            )}
        </div>
    );
};

export default Gallery;
