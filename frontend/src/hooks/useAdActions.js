import { useCallback } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

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
            onChanged?.();
        } catch {
            toast.error("Download failed");
        }
    }, [onChanged]);

    const copyCaption = useCallback((ad) => {
        const text = `${ad.caption}\n\n${(ad.hashtags || []).join(" ")}`;
        navigator.clipboard.writeText(text);
        toast.success("Caption copied");
    }, []);

    return { updateStatus, remove, downloadFile, copyCaption };
};
