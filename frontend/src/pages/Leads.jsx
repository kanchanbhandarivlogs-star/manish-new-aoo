import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, API } from "@/lib/api";
import { Users, Download, Trash2, RefreshCw, Mail, Phone, MapPin } from "lucide-react";
import { toast } from "sonner";

const LeadCard = ({ lead, onDelete }) => (
    <div className="nb-card nb-card-hover p-5" data-testid={`lead-card-${lead.id}`}>
        <div className="flex items-start justify-between">
            <div>
                <span className="nb-badge nb-badge-approved">{lead.website_name || "unknown"}</span>
                <h3 className="font-display font-black text-xl mt-2">{lead.name}</h3>
            </div>
            <button
                className="nb-btn nb-btn-danger !p-2 !shadow-[2px_2px_0_0_#000]"
                onClick={() => onDelete(lead.id)}
                data-testid={`delete-lead-${lead.id}`}
                title="Delete lead"
            >
                <Trash2 size={14} />
            </button>
        </div>
        <div className="mt-3 space-y-1 text-sm font-medium">
            <p className="flex items-center gap-2"><Phone size={14} strokeWidth={2.5} /> <a href={`tel:${lead.phone}`} className="font-mono underline">{lead.phone}</a></p>
            {lead.email && <p className="flex items-center gap-2"><Mail size={14} strokeWidth={2.5} /> <a href={`mailto:${lead.email}`} className="font-mono underline break-all">{lead.email}</a></p>}
            {lead.city && <p className="flex items-center gap-2"><MapPin size={14} strokeWidth={2.5} /> {lead.city}</p>}
            {lead.course && <p className="text-xs">📚 <strong>Course:</strong> {lead.course}</p>}
            {lead.message && <p className="text-xs italic">"{lead.message}"</p>}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
            <span className="font-mono text-neutral-700">{new Date(lead.created_at).toLocaleString()}</span>
            {lead.forwarded ? (
                <span className="nb-badge nb-badge-ready">✓ webhook sent</span>
            ) : (
                <span className="nb-badge">app only</span>
            )}
        </div>
    </div>
);

const FilterBar = ({ websites, websiteFilter, setWebsiteFilter, onExport, onRefresh, count }) => (
    <div className="nb-card p-4 flex flex-col md:flex-row md:items-center gap-3">
        <select
            className="nb-input md:max-w-xs !py-2"
            value={websiteFilter}
            onChange={(e) => setWebsiteFilter(e.target.value)}
            data-testid="leads-website-filter"
        >
            <option value="all">All websites</option>
            {websites.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
            ))}
        </select>
        <span className="text-sm font-bold">{count} leads</span>
        <div className="md:ml-auto flex gap-2">
            <button className="nb-btn nb-btn-mint" onClick={onExport} data-testid="export-leads-btn">
                <Download size={16} strokeWidth={2.5} /> Export CSV
            </button>
            <button className="nb-btn" onClick={onRefresh} data-testid="refresh-leads-btn">
                <RefreshCw size={16} strokeWidth={2.5} /> Refresh
            </button>
        </div>
    </div>
);

const Leads = () => {
    const [leads, setLeads] = useState([]);
    const [websites, setWebsites] = useState([]);
    const [websiteFilter, setWebsiteFilter] = useState("all");
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        try {
            const [leadsRes, sitesRes] = await Promise.all([
                apiClient.get("/leads"),
                apiClient.get("/websites"),
            ]);
            setLeads(leadsRes.data);
            setWebsites(sitesRes.data);
        } catch {
            toast.error("Could not load leads");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const filtered = useMemo(() => {
        if (websiteFilter === "all") return leads;
        return leads.filter((l) => l.website_id === websiteFilter);
    }, [leads, websiteFilter]);

    const onExport = () => {
        const qs = websiteFilter !== "all" ? `?website_id=${websiteFilter}` : "";
        window.open(`${API}/leads/export.csv${qs}`, "_blank");
    };

    const remove = async (id) => {
        if (!window.confirm("Delete this lead?")) return;
        try {
            await apiClient.delete(`/leads/${id}`);
            toast.success("Deleted");
            load();
        } catch {
            toast.error("Could not delete");
        }
    };

    return (
        <div className="space-y-6" data-testid="leads-page">
            <div>
                <p className="label-uppercase">Captured</p>
                <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Leads</h1>
                <p className="text-sm mt-2 max-w-xl font-medium">
                    Sare leads jo apply form se aaye. Same time पर आपकी website को भी forward हो रहे हैं (webhook configured पर).
                </p>
            </div>
            <FilterBar
                websites={websites}
                websiteFilter={websiteFilter}
                setWebsiteFilter={setWebsiteFilter}
                onExport={onExport}
                onRefresh={load}
                count={filtered.length}
            />
            {loading ? (
                <div className="nb-card p-10 text-center">
                    <div className="nb-spinner mx-auto" />
                </div>
            ) : filtered.length === 0 ? (
                <div className="nb-card p-10 text-center bg-white" data-testid="empty-leads">
                    <Users size={40} strokeWidth={2.5} className="mx-auto" />
                    <h3 className="font-display font-bold text-2xl mt-4">No leads yet</h3>
                    <p className="text-sm mt-2 font-medium">
                        Share your Apply Now link <code className="bg-[#FFD84D] px-2 border border-black">/apply/&lt;website-id&gt;</code> in your ads — leads will show up here.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="leads-grid">
                    {filtered.map((lead) => (
                        <LeadCard key={lead.id} lead={lead} onDelete={remove} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Leads;
