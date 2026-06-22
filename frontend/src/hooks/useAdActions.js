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

    const downloadFile = useCallback(async (id, kind) => {
        const filename = `ad-${id}.${kind === "image" ? "png" : "mp4"}`;
        try {
            const res = await apiClient.get(`/ads/${id}/download/${kind}`, { responseType: "blob" });

            // ─── Android / iOS APK: save into the phone's public Downloads folder ───
            if (Capacitor.isNativePlatform()) {
                const base64 = await blobToBase64(res.data);
                await Filesystem.writeFile({
                    path: `Download/${filename}`,
                    data: base64,
                    directory: Directory.ExternalStorage,
                    recursive: true,
                });
                toast.success(`Saved to phone Downloads: ${filename}`);
                onChanged?.();
                return;
            }

            // ─── Web browser fallback: anchor + blob URL ───
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            toast.success(`Downloaded ${kind}`);
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
