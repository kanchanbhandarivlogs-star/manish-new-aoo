import { useCallback } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { Capacitor } from "@capacitor/core";
import { Directory, Filesystem } from "@capacitor/filesystem";
import { Share } from "@capacitor/share";

/** ArrayBuffer / Blob → base64 string (for Filesystem.writeFile) */
const blobToBase64 = (blob) =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const r = reader.result;
            const i = r.indexOf(",");
            resolve(i >= 0 ? r.slice(i + 1) : r);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });

/** Download a media file to phone cache (Capacitor only). Returns the local file URI. */
const fetchToCache = async (mediaUrl, filename) => {
    const res = await fetch(mediaUrl);
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const blob = await res.blob();
    const base64 = await blobToBase64(blob);
    const written = await Filesystem.writeFile({
        path: filename,
        data: base64,
        directory: Directory.Cache,
    });
    return written.uri;
};

export const useAdActions = ({ onChanged, onDeleted } = {}) => {
    const updateStatus = useCallback(async (id, newStatus) => {
        try {
            await apiClient.patch(`/ads/${id}/status`, { status: newStatus });
            toast.success(`Marked ${newStatus}`);
            onChanged?.();
        } catch {
            toast.error("Could not update status");
        }
    }, [onChanged]);

    const remove = useCallback(async (id) => {
        if (!window.confirm("Delete this ad? Images/video files will be removed.")) return;
        try {
            await apiClient.delete(`/ads/${id}`);
            toast.success("Deleted");
            onDeleted?.();
            onChanged?.();
        } catch {
            toast.error("Could not delete");
        }
    }, [onChanged, onDeleted]);

    /**
     * Universal "share / download" action.
     * - On Android APK: opens native share-sheet (WhatsApp, Save to Gallery, Drive, etc.)
     *   with the actual image/video file attached.
     * - In a web browser: triggers a normal download via the public media URL.
     */
    const shareOrDownload = useCallback(async (ad, kind) => {
        if (!ad) return;
        const id = ad.id;
        const ext = kind === "image" ? "png" : "mp4";
        const filename = `ad-${id}.${ext}`;
        const relPath = kind === "image" ? ad.image_path : ad.video_path;
        if (!relPath) {
            toast.error(`No ${kind} available yet`);
            return;
        }
        const mediaUrl = `${process.env.REACT_APP_BACKEND_URL}/api/media/${relPath}`;

        try {
            if (Capacitor.isNativePlatform()) {
                toast.loading("Preparing file…", { id: "share-prep" });
                const localUri = await fetchToCache(mediaUrl, filename);
                toast.dismiss("share-prep");
                await Share.share({
                    title: kind === "image" ? "Ad image" : "Ad video",
                    text: (ad.caption || "Created with Ads Studio").slice(0, 240),
                    url: localUri,
                    dialogTitle: "Share or save",
                });
                // Tell the server we downloaded it (status → downloaded)
                apiClient.get(`/ads/${id}/download/${kind}`).catch(() => {});
                onChanged?.();
                return;
            }

            // Web browser path — direct anchor download
            const a = document.createElement("a");
            a.href = mediaUrl;
            a.download = filename;
            a.target = "_blank";
            a.rel = "noopener";
            document.body.appendChild(a);
            a.click();
            a.remove();
            apiClient.get(`/ads/${id}/download/${kind}`).catch(() => {});
            toast.success(`Downloading ${kind}…`);
            onChanged?.();
        } catch (err) {
            console.error("Share/download failed", err);
            toast.error(err?.message || "Could not share/download");
        }
    }, [onChanged]);

    const copyCaption = useCallback((ad) => {
        const text = `${ad.caption}\n\n${(ad.hashtags || []).join(" ")}`;
        navigator.clipboard.writeText(text);
        toast.success("Caption copied");
    }, []);

    const publish = useCallback(async (id, platforms) => {
        const t = toast.loading(`Publishing to ${platforms.join(" + ")}...`);
        try {
            const res = await apiClient.post(`/ads/${id}/publish`, { platforms });
            toast.success(`Published to ${(res.data.published_to || []).join(", ")}`, { id: t });
            onChanged?.();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Publish failed", { id: t });
        }
    }, [onChanged]);

    const createVariant = useCallback(async (id) => {
        const t = toast.loading("Cooking variant...");
        try {
            await apiClient.post(`/ads/${id}/variants`);
            toast.success("Variant generated", { id: t });
            onChanged?.();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Variant failed", { id: t });
        }
    }, [onChanged]);

    return { updateStatus, remove, downloadFile: shareOrDownload, shareOrDownload, copyCaption, publish, createVariant };
};
