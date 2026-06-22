import { useCallback } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { Capacitor } from "@capacitor/core";
import { Directory, Filesystem } from "@capacitor/filesystem";

/**
 * Convert an ArrayBuffer / Blob payload into a base64 string suitable for
 * `Filesystem.writeFile()`. Used only inside the Capacitor (Android APK) runtime.
 */
const blobToBase64 = (blob) =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            // strip "data:*/*;base64," prefix
            const result = reader.result;
            const idx = result.indexOf(",");
            resolve(idx >= 0 ? result.slice(idx + 1) : result);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });

/**
 * Hook returning ad-mutation actions that the gallery & detail modal can call.
 * `onChanged` is invoked after any successful mutation so the caller can refetch.
 */
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

    const downloadFile = useCallback(async (ad, kind) => {
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
            // ─── Native (Android APK / iOS): save to phone's Download folder ───
            if (Capacitor.isNativePlatform()) {
                const res = await fetch(mediaUrl);
                if (!res.ok) throw new Error(`Server returned ${res.status}`);
                const blob = await res.blob();
                const base64 = await blobToBase64(blob);
                await Filesystem.writeFile({
                    path: `Download/${filename}`,
                    data: base64,
                    directory: Directory.ExternalStorage,
                    recursive: true,
                });
                // Tell the server we downloaded it (status update + media-scan trigger)
                apiClient.get(`/ads/${id}/download/${kind}`).catch(() => {});
                toast.success(`Saved to Downloads: ${filename}`);
                onChanged?.();
                return;
            }

            // ─── Web browser: anchor + direct media URL (no JWT needed, files are public) ───
            const a = document.createElement("a");
            a.href = mediaUrl;
            a.download = filename;
            a.target = "_blank";
            a.rel = "noopener";
            document.body.appendChild(a);
            a.click();
            a.remove();
            // mark as downloaded server-side
            apiClient.get(`/ads/${id}/download/${kind}`).catch(() => {});
            toast.success(`Downloading ${kind}…`);
            onChanged?.();
        } catch (err) {
            console.error("Download failed", err);
            toast.error(err?.message || "Download failed");
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

    return { updateStatus, remove, downloadFile, copyCaption, publish, createVariant };
};
