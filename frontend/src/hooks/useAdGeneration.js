import { useCallback, useRef, useState } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

const PROGRESS_TICK_MS = 5000;
const MAX_PROGRESS_STEP = 3;
const TOPIC_MAX_LEN = 400;

const buildScrapedTopic = (data) => {
    const title = data.title || data.description || "";
    if (!title) return "";
    const suffix = data.description ? ` — ${data.description}` : "";
    return `${title}${suffix}`.slice(0, TOPIC_MAX_LEN);
};

export const useAdGeneration = ({ websites, navigate }) => {
    const [scraping, setScraping] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [progressStep, setProgressStep] = useState(0);
    const stepTimerRef = useRef(null);

    const handleScrape = useCallback(async (selectedWebsiteId, setTopic) => {
        const site = websites.find((w) => w.id === selectedWebsiteId);
        if (!site) {
            toast.error("Select a website first");
            return;
        }
        setScraping(true);
        try {
            const res = await apiClient.post("/scrape", { url: site.url });
            const newTopic = buildScrapedTopic(res.data);
            if (newTopic) {
                setTopic(newTopic);
                toast.success("Scraped! Topic auto-filled");
            } else {
                toast.message("Page scraped, but no clear topic. Type one manually.");
            }
        } catch {
            toast.error("Could not scrape. Try a different URL.");
        } finally {
            setScraping(false);
        }
    }, [websites]);

    const startProgress = () => {
        setProgressStep(1);
        stepTimerRef.current = setInterval(() => {
            setProgressStep((s) => (s < MAX_PROGRESS_STEP ? s + 1 : s));
        }, PROGRESS_TICK_MS);
    };

    const stopProgress = () => {
        if (stepTimerRef.current) clearInterval(stepTimerRef.current);
        stepTimerRef.current = null;
        setGenerating(false);
        setProgressStep(0);
    };

    const handleGenerate = useCallback(async (payload) => {
        if (!payload.topic.trim()) {
            toast.error("Topic / product is required");
            return;
        }
        setGenerating(true);
        startProgress();
        try {
            const res = await apiClient.post("/ads/generate", payload);
            toast.success("Ad generated! Review it now.");
            navigate(`/gallery?focus=${res.data.id}`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "Generation failed");
        } finally {
            stopProgress();
        }
    }, [navigate]);

    return { scraping, generating, progressStep, handleScrape, handleGenerate };
};
