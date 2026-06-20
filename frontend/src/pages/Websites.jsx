import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { useWebsiteCrud } from "@/hooks/useWebsiteCrud";
import { Plus, Trash2, Pencil, Globe, X, Check, Zap } from "lucide-react";
import { toast } from "sonner";

const emptyForm = { name: "", url: "", description: "", auto_generate: false };

const CARD_COLORS = ["bg-white", "bg-[#FFDBCB]", "bg-[#BAE6FD]", "bg-[#A7F3D0]", "bg-[#DDD6FE]"];

const WebsiteForm = ({ editingId, form, setForm, submitting, onSubmit, onClose }) => (
    <div className="nb-card p-6" data-testid="website-form">
        <div className="flex items-start justify-between">
            <h2 className="font-display font-bold text-2xl">{editingId ? "Edit website" : "Add a website"}</h2>
            <button className="nb-btn !p-2" onClick={onClose} data-testid="form-close-btn">
                <X size={16} />
            </button>
        </div>
        <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
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
            <label className="md:col-span-2 flex items-center gap-3 p-3 border-2 border-black bg-[#FFD84D] cursor-pointer" data-testid="form-auto-generate">
                <input
                    type="checkbox"
                    checked={!!form.auto_generate}
                    onChange={(e) => setForm({ ...form, auto_generate: e.target.checked })}
                    className="w-5 h-5 accent-black"
                />
                <div>
                    <p className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                        <Zap size={14} strokeWidth={3} /> Auto-generate at peak hours
                    </p>
                    <p className="text-xs">9 AM, 1 PM, 6 PM UTC — fresh Draft ad every peak window.</p>
                </div>
            </label>
            <div className="md:col-span-2 flex gap-3">
                <button type="submit" className="nb-btn nb-btn-mint" disabled={submitting} data-testid="form-submit-btn">
                    {submitting ? <div className="nb-spinner" /> : <Check size={16} />}
                    {editingId ? "Save" : "Add"}
                </button>
                <button type="button" className="nb-btn" onClick={onClose} data-testid="form-cancel-btn">
                    Cancel
                </button>
            </div>
        </form>
    </div>
);

const WebsiteCard = ({ website, color, onEdit, onDelete }) => (
    <div className={`nb-card nb-card-hover p-6 ${color}`} data-testid={`website-card-${website.id}`}>
        <div className="flex items-start justify-between">
            <div className="w-10 h-10 bg-white border-2 border-black flex items-center justify-center">
                <Globe size={18} strokeWidth={2.5} />
            </div>
            <div className="flex gap-2">
                <button
                    className="nb-btn !p-2 !shadow-[2px_2px_0_0_#000]"
                    onClick={onEdit}
                    data-testid={`edit-website-${website.id}`}
                    title="Edit"
                >
                    <Pencil size={14} />
                </button>
                <button
                    className="nb-btn nb-btn-danger !p-2 !shadow-[2px_2px_0_0_#000]"
                    onClick={onDelete}
                    data-testid={`delete-website-${website.id}`}
                    title="Delete"
                >
                    <Trash2 size={14} />
                </button>
            </div>
        </div>
        <h3 className="font-display font-black text-xl mt-4 break-words">{website.name}</h3>
        <a
            href={website.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-mono underline break-all mt-1 block"
            data-testid={`website-url-${website.id}`}
        >
            {website.url}
        </a>
        {website.description && <p className="text-sm mt-3 font-medium">{website.description}</p>}
        {website.auto_generate && (
            <span className="nb-badge !bg-black !text-white mt-3 inline-flex" data-testid={`auto-gen-${website.id}`}>
                <Zap size={10} strokeWidth={3} /> Auto-gen ON
            </span>
        )}
    </div>
);

const renderWebsiteContent = (loading, websites, onEdit, onDelete) => {
    if (loading) {
        return (
            <div className="nb-card p-10 text-center">
                <div className="nb-spinner mx-auto" />
            </div>
        );
    }
    if (websites.length === 0) {
        return (
            <div className="nb-card p-10 text-center bg-white" data-testid="empty-websites">
                <Globe size={40} strokeWidth={2.5} className="mx-auto" />
                <h3 className="font-display font-bold text-2xl mt-4">No websites yet</h3>
                <p className="text-sm mt-2 font-medium max-w-md mx-auto">
                    Add your first website to start generating AI ads. You can add multiple, edit or delete them anytime — no code changes ever needed.
                </p>
            </div>
        );
    }
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="websites-grid">
            {websites.map((w, idx) => (
                <WebsiteCard
                    key={w.id}
                    website={w}
                    color={CARD_COLORS[idx % CARD_COLORS.length]}
                    onEdit={() => onEdit(w)}
                    onDelete={() => onDelete(w.id)}
                />
            ))}
        </div>
    );
};

const WebsitesPageHeader = ({ onAdd }) => (
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
            onClick={onAdd}
            data-testid="add-website-btn"
        >
            <Plus size={16} strokeWidth={2.5} /> Add Website
        </button>
    </div>
);

const Websites = () => {
    const [websites, setWebsites] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState(emptyForm);
    const [editingId, setEditingId] = useState(null);

    const load = useCallback(async () => {
        try {
            const res = await apiClient.get("/websites");
            setWebsites(res.data);
        } catch {
            toast.error("Could not load websites");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const reset = () => {
        setShowForm(false);
        setEditingId(null);
        setForm(emptyForm);
    };

    const startEdit = (w) => {
        setEditingId(w.id);
        setForm({
            name: w.name,
            url: w.url,
            description: w.description || "",
            auto_generate: !!w.auto_generate,
        });
        setShowForm(true);
    };

    const { submitting, save, remove } = useWebsiteCrud({ onChanged: load });

    const submit = async (e) => {
        e.preventDefault();
        const ok = await save(editingId, form);
        if (ok) reset();
    };

    return (
        <div className="space-y-6" data-testid="websites-page">
            <WebsitesPageHeader
                onAdd={() => {
                    reset();
                    setShowForm(true);
                }}
            />
            {showForm && (
                <WebsiteForm
                    editingId={editingId}
                    form={form}
                    setForm={setForm}
                    submitting={submitting}
                    onSubmit={submit}
                    onClose={reset}
                />
            )}
            {renderWebsiteContent(loading, websites, startEdit, remove)}
        </div>
    );
};

export default Websites;
