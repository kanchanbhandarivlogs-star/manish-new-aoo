import { useCallback, useState } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

export const useWebsiteCrud = ({ onChanged } = {}) => {
    const [submitting, setSubmitting] = useState(false);

    const save = useCallback(async (editingId, form) => {
        if (!form.name.trim() || !form.url.trim()) {
            toast.error("Name and URL are required");
            return false;
        }
        setSubmitting(true);
        try {
            if (editingId) {
                await apiClient.patch(`/websites/${editingId}`, form);
                toast.success("Website updated");
            } else {
                await apiClient.post("/websites", form);
                toast.success("Website added");
            }
            onChanged?.();
            return true;
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed");
            return false;
        } finally {
            setSubmitting(false);
        }
    }, [onChanged]);

    const remove = useCallback(async (id) => {
        if (!window.confirm("Delete this website? Ads will remain but lose this link.")) return;
        try {
            await apiClient.delete(`/websites/${id}`);
            toast.success("Deleted");
            onChanged?.();
        } catch {
            toast.error("Could not delete");
        }
    }, [onChanged]);

    return { submitting, save, remove };
};
