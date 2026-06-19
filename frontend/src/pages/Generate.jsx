import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { Sparkles, Globe, FileSearch, Wand2, ChevronRight, AlertCircle } from "lucide-react";
import { toast } from "sonner";

const DEFAULTS = {
    audience: "Indian college students (17-24)",
    tone: "energetic, fun, Gen Z, hinglish-friendly",
};

const PROGRESS_STEPS = ["Crafting caption", "Painting image", "Queueing video"];

const getStepClass = (active, current) => {
    if (active) return "bg-white";
    if (current) return "bg-[#FFD84D]";
    return "bg-white/60";
};

const WebsitePicker = ({ websites, selectedWebsite, onChange, onScrape, scraping }) => (
    <div className="nb-card p-6" data-testid="website-picker-card">
        <div className="flex items-center gap-2">
            <Globe size={18} strokeWidth={2.5} />
            <h2 className="font-display font-bold text-xl">Source Website (optional)</h2>
        </div>
        <p className="text-sm mt-2 font-medium">
            Choose a saved website to auto-scrape its latest content into the topic field.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 mt-4">
            <select
                className="nb-input"
                value={selectedWebsite}
                onChange={(e) => onChange(e.target.value)}
                data-testid="website-select"
            >
                <option value="">— Select a website —</option>
                {websites.map((w) => (
                    <option key={w.id} value={w.id}>
                        {w.name} ({w.url})
                    </option>
                ))}
            </select>
            <button
                className="nb-btn nb-btn-lavender"
                onClick={onScrape}
                disabled={!selectedWebsite || scraping}
                data-testid="scrape-btn"
            >
                {scraping ? <div className="nb-spinner" /> : <FileSearch size={16} strokeWidth={2.5} />}
                {scraping ? "Scraping..." : "Auto-fill Topic"}
            </button>
        </div>
        {websites.length === 0 && (
            <div className="mt-4 p-3 border-2 border-black bg-[#FFDBCB] flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5" strokeWidth={2.5} />
                <p className="text-sm font-medium">
                    No websites yet. You can still type a topic below, or add a website first.
                </p>
            </div>
        )}
    </div>
);

const BriefSection = ({ topic, setTopic, audience, setAudience, tone, setTone }) => (
    <div className="nb-card p-6">
        <h2 className="font-display font-bold text-xl">Brief</h2>
        <div className="mt-4 space-y-4">
            <div>
                <label className="label-uppercase">Topic / Product *</label>
                <textarea
                    className="nb-input mt-2 min-h-[110px]"
                    placeholder="e.g. New B.Tech admission open for 2026 batch with 100% placement guarantee"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    data-testid="topic-input"
                />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label className="label-uppercase">Audience</label>
                    <input
                        className="nb-input mt-2"
                        value={audience}
                        onChange={(e) => setAudience(e.target.value)}
                        data-testid="audience-input"
                    />
                </div>
                <div>
                    <label className="label-uppercase">Tone</label>
                    <input
                        className="nb-input mt-2"
                        value={tone}
                        onChange={(e) => setTone(e.target.value)}
                        data-testid="tone-input"
                    />
                </div>
            </div>
        </div>
    </div>
);

const VideoOptions = ({ duration, setDuration, size, setSize }) => (
    <div className="grid grid-cols-2 gap-3 pt-2">
        <div>
            <label className="label-uppercase">Duration</label>
            <select
                className="nb-input mt-2"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                data-testid="video-duration-select"
            >
                <option value={4}>4 seconds</option>
                <option value={8}>8 seconds</option>
                <option value={12}>12 seconds</option>
            </select>
        </div>
        <div>
            <label className="label-uppercase">Format</label>
            <select
                className="nb-input mt-2"
                value={size}
                onChange={(e) => setSize(e.target.value)}
                data-testid="video-size-select"
            >
                <option value="1024x1792">Portrait (Reels)</option>
                <option value="1280x720">Landscape (YouTube)</option>
                <option value="1024x1024">Square (Feed)</option>
            </select>
        </div>
    </div>
);

const OutputSection = ({
    includeImage, setIncludeImage,
    includeVideo, setIncludeVideo,
    videoDuration, setVideoDuration,
    videoSize, setVideoSize,
}) => (
    <div className="nb-card p-6">
        <h2 className="font-display font-bold text-xl">Output</h2>
        <div className="mt-4 space-y-3">
            <label className="flex items-center gap-3 p-3 border-2 border-black bg-[#FFD84D] cursor-pointer" data-testid="toggle-image">
                <input
                    type="checkbox"
                    checked={includeImage}
                    onChange={(e) => setIncludeImage(e.target.checked)}
                    className="w-5 h-5 accent-black"
                />
                <div>
                    <p className="font-bold uppercase tracking-wider text-sm">Image Ad</p>
                    <p className="text-xs">Banner for Instagram / Facebook posts (Nano Banana)</p>
                </div>
            </label>
            <label className="flex items-center gap-3 p-3 border-2 border-black bg-[#BAE6FD] cursor-pointer" data-testid="toggle-video">
                <input
                    type="checkbox"
                    checked={includeVideo}
                    onChange={(e) => setIncludeVideo(e.target.checked)}
                    className="w-5 h-5 accent-black"
                />
                <div>
                    <p className="font-bold uppercase tracking-wider text-sm">Video Ad (Reel)</p>
                    <p className="text-xs">4-12 sec short cinematic video (Sora 2). Generated in background.</p>
                </div>
            </label>
            {includeVideo && (
                <VideoOptions
                    duration={videoDuration}
                    setDuration={setVideoDuration}
                    size={videoSize}
                    setSize={setVideoSize}
                />
            )}
        </div>
    </div>
);

const ProgressPanel = ({ generating, progressStep }) => (
    <div className="nb-card p-6 bg-[#A7F3D0] sticky top-24">
        <div className="flex items-center gap-2">
            <Wand2 size={18} strokeWidth={2.5} />
            <h3 className="font-display font-bold text-lg">How it works</h3>
        </div>
        <ol className="space-y-3 mt-4">
            {PROGRESS_STEPS.map((step, i) => {
                const active = generating && progressStep > i;
                const current = generating && progressStep === i + 1;
                return (
                    <li
                        key={step}
                        className={`flex items-center gap-3 p-3 border-2 border-black ${getStepClass(active, current)}`}
                        data-testid={`progress-step-${i}`}
                    >
                        <div className="w-6 h-6 border-2 border-black bg-white flex items-center justify-center font-display font-black text-sm">
                            {active ? "✓" : i + 1}
                        </div>
                        <p className="font-bold text-sm">{step}</p>
                        {current && <div className="nb-spinner ml-auto" />}
                    </li>
                );
            })}
        </ol>
        <p className="text-xs mt-4 font-medium">
            Caption + image take 10-30 sec. Video runs in background (2-5 min) — you can leave this page once started.
        </p>
    </div>
);

const PageIntro = () => (
    <div>
        <p className="label-uppercase">Create</p>
        <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Generate Ad</h1>
        <p className="text-sm mt-2 max-w-xl font-medium">
            Pick a website (optional), drop a topic, and let the AI cook captions, banner image & short video ad.
        </p>
    </div>
);

const GenerateButton = ({ generating, onClick }) => (
    <button
        className="nb-btn nb-btn-primary w-full !py-5 !text-base"
        onClick={onClick}
        disabled={generating}
        data-testid="generate-btn"
    >
        {generating ? (
            <>
                <div className="nb-spinner" /> Generating...
            </>
        ) : (
            <>
                <Sparkles size={18} strokeWidth={2.5} /> Generate Ad
                <ChevronRight size={18} />
            </>
        )}
    </button>
);

const Generate = () => {
    const navigate = useNavigate();
    const [websites, setWebsites] = useState([]);
    const [selectedWebsite, setSelectedWebsite] = useState("");
    const [topic, setTopic] = useState("");
    const [audience, setAudience] = useState(DEFAULTS.audience);
    const [tone, setTone] = useState(DEFAULTS.tone);
    const [includeImage, setIncludeImage] = useState(true);
    const [includeVideo, setIncludeVideo] = useState(false);
    const [videoDuration, setVideoDuration] = useState(4);
    const [videoSize, setVideoSize] = useState("1024x1792");
    const [scraping, setScraping] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [progressStep, setProgressStep] = useState(0);

    const loadWebsites = useCallback(async () => {
        try {
            const r = await apiClient.get("/websites");
            setWebsites(r.data);
        } catch (err) {
            console.warn("Failed to load websites for picker", err);
        }
    }, []);

    useEffect(() => {
        loadWebsites();
    }, [loadWebsites]);

    const handleScrape = async () => {
        const site = websites.find((w) => w.id === selectedWebsite);
        if (!site) {
            toast.error("Select a website first");
            return;
        }
        setScraping(true);
        try {
            const res = await apiClient.post("/scrape", { url: site.url });
            const title = res.data.title || res.data.description || "";
            if (title) {
                setTopic(`${title}${res.data.description ? " — " + res.data.description : ""}`.slice(0, 400));
                toast.success("Scraped! Topic auto-filled");
            } else {
                toast.message("Page scraped, but no clear topic. Type one manually.");
            }
        } catch {
            toast.error("Could not scrape. Try a different URL.");
        } finally {
            setScraping(false);
        }
    };

    const handleGenerate = async () => {
        if (!topic.trim()) {
            toast.error("Topic / product is required");
            return;
        }
        setGenerating(true);
        setProgressStep(1);
        const stepTimer = setInterval(() => {
            setProgressStep((s) => (s < 3 ? s + 1 : s));
        }, 5000);
        try {
            const res = await apiClient.post("/ads/generate", {
                website_id: selectedWebsite || null,
                topic,
                audience,
                tone,
                include_image: includeImage,
                include_video: includeVideo,
                video_duration: videoDuration,
                video_size: videoSize,
            });
            toast.success("Ad generated! Review it now.");
            navigate(`/gallery?focus=${res.data.id}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "Generation failed");
        } finally {
            clearInterval(stepTimer);
            setGenerating(false);
            setProgressStep(0);
        }
    };

    return (
        <div className="space-y-6" data-testid="generate-page">
            <PageIntro />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                    <WebsitePicker
                        websites={websites}
                        selectedWebsite={selectedWebsite}
                        onChange={setSelectedWebsite}
                        onScrape={handleScrape}
                        scraping={scraping}
                    />
                    <BriefSection
                        topic={topic} setTopic={setTopic}
                        audience={audience} setAudience={setAudience}
                        tone={tone} setTone={setTone}
                    />
                    <OutputSection
                        includeImage={includeImage} setIncludeImage={setIncludeImage}
                        includeVideo={includeVideo} setIncludeVideo={setIncludeVideo}
                        videoDuration={videoDuration} setVideoDuration={setVideoDuration}
                        videoSize={videoSize} setVideoSize={setVideoSize}
                    />
                    <GenerateButton generating={generating} onClick={handleGenerate} />
                </div>
                <div className="lg:col-span-1">
                    <ProgressPanel generating={generating} progressStep={progressStep} />
                </div>
            </div>
        </div>
    );
};

export default Generate;
