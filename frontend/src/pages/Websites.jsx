import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Plus, Trash2, Pencil, Globe, X, Check } from "lucide-react";
import { toast } from "sonner";

const emptyForm = { name: "", url: "", description: "" };

const Websites = () => {
    const [websites, setWebsites] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState(emptyForm);
    const [editingId, setEditingId] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    const load = async () => {
        try {
            const res = await apiClient.get("/websites");
            setWebsites(res.data);
        } catch (e) {
            toast.error("Could not load websites");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const startEdit = (w) => {
        setEditingId(w.id);
        setForm({ name: w.name, url: w.url, description: w.description || "" });
        setShowForm(true);
    };

    const reset = () => {
        setShowForm(false);
        setEditingId(null);
        setForm(emptyForm);
    };

    const submit = async (e) => {
        e.preventDefault();
        if (!form.name.trim() || !form.url.trim()) {
            toast.error("Name and URL are required");
            return;
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
            reset();
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        } finally {
            setSubmitting(false);
        }
    };

    const remove = async (id) => {
        if (!window.confirm("Delete this website? Ads will remain but lose this link.")) return;
        try {
            await apiClient.delete(`/websites/${id}`);
            toast.success("Deleted");
            load();
        } catch (e) {
            toast.error("Could not delete");
        }
    };

    return (
        <div className="space-y-6" data-testid="websites-page">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                    <p className="label-uppercase">Manage</p>
                    <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Your Websites</h1>
                    <p className="text-sm mt-2 max-w-xl font-medium">
                        Add any number of websites. We&apos;ll scrape content and generate ads on demand. Delete or rename anytime.
                    </p>
                </div>
                <button
                    className="nb-btn nb-btn-primary"
                    onClick={() => {
                        reset();
                        setShowForm(true);
                    }}
                    data-testid="add-website-btn"
                >
                    <Plus size={16} strokeWidth={2.5} /> Add Website
                </button>
            </div>

            {showForm && (
                <div className="nb-card p-6" data-testid="website-form">
                    <div className="flex items-start justify-between">
                        <h2 className="font-display font-bold text-2xl">{editingId ? "Edit website" : "Add a website"}</h2>
                        <button className="nb-btn !p-2" onClick={reset} data-testid="form-close-btn">
                            <X size={16} />
                        </button>
                    </div>
                    <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                        <div>
                            <label className="label-uppercase">Name *</label>
                            <input
                                className="nb-input mt-2"
                                placeholder="e.g. CollegeOp"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                data-testid="form-name-input"
                            />
                        </div>
                        <div>
                            <label className="label-uppercase">URL *</label>
                            <input
                                className="nb-input mt-2"
                                placeholder="https://collegeop.com"
                                value={form.url}
                                onChange={(e) => setForm({ ...form, url: e.target.value })}
                                data-testid="form-url-input"
                            />
                        </div>
                        <div className="md:col-span-2">
                            <label className="label-uppercase">Description (optional)</label>
                            <input
                                className="nb-input mt-2"
                                placeholder="Short brand brief or audience notes"
                                value={form.description}
                                onChange={(e) => setForm({ ...form, description: e.target.value })}
                                data-testid="form-desc-input"
                            />
                        </div>
                        <div className="md:col-span-2 flex gap-3">
                            <button type="submit" className="nb-btn nb-btn-mint" disabled={submitting} data-testid="form-submit-btn">
                                {submitting ? <div className="nb-spinner" /> : <Check size={16} />}
                                {editingId ? "Save" : "Add"}
                            </button>
                            <button type="button" className="nb-btn" onClick={reset} data-testid="form-cancel-btn">
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {loading ? (
                <div className="nb-card p-10 text-center">
                    <div className="nb-spinner mx-auto" />
                </div>
            ) : websites.length === 0 ? (
                <div className="nb-card p-10 text-center bg-white" data-testid="empty-websites">
                    <Globe size={40} strokeWidth={2.5} className="mx-auto" />
                    <h3 className="font-display font-bold text-2xl mt-4">No websites yet</h3>
                    <p className="text-sm mt-2 font-medium max-w-md mx-auto">
                        Add your first website to start generating AI ads. You can add multiple, edit or delete them anytime — no code changes ever needed.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="websites-grid">
                    {websites.map((w, idx) => (
                        <div
                            key={w.id}
                            className={`nb-card nb-card-hover p-6 ${["bg-white", "bg-[#FFDBCB]", "bg-[#BAE6FD]", "bg-[#A7F3D0]", "bg-[#DDD6FE]"][idx % 5]}`}
                            data-testid={`website-card-${w.id}`}
                        >
                            <div className="flex items-start justify-between">
                                <div className="w-10 h-10 bg-white border-2 border-black flex items-center justify-center">
                                    <Globe size={18} strokeWidth={2.5} />
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        className="nb-btn !p-2 !shadow-[2px_2px_0_0_#000]"
                                        onClick={() => startEdit(w)}
                                        data-testid={`edit-website-${w.id}`}
                                        title="Edit"
                                    >
                                        <Pencil size={14} />
                                    </button>
                                    <button
                                        className="nb-btn nb-btn-danger !p-2 !shadow-[2px_2px_0_0_#000]"
                                        onClick={() => remove(w.id)}
                                        data-testid={`delete-website-${w.id}`}
                                        title="Delete"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            </div>
                            <h3 className="font-display font-black text-xl mt-4 break-words">{w.name}</h3>
                            <a href={w.url} target="_blank" rel="noreferrer" className="text-sm font-mono underline break-all mt-1 block" data-testid={`website-url-${w.id}`}>
                                {w.url}
                            </a>
                            {w.description && <p className="text-sm mt-3 font-medium">{w.description}</p>}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default Websites;
