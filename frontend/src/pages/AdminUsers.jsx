import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Users, Plus, Trash2, X, Wallet, Send } from "lucide-react";
import { toast } from "sonner";

const TopUpRow = ({ user, onTopUp }) => {
    const [amount, setAmount] = useState(100);
    const [note, setNote] = useState("");
    return (
        <div className="flex flex-col md:flex-row gap-2 mt-3 p-3 border-2 border-black bg-[#FFD84D]">
            <input
                type="number"
                className="nb-input md:max-w-[120px]"
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                data-testid={`topup-amount-${user.id}`}
                placeholder="Credits"
            />
            <input
                className="nb-input flex-1"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Note (optional)"
                data-testid={`topup-note-${user.id}`}
            />
            <button
                className="nb-btn nb-btn-mint"
                onClick={() => { onTopUp(user.id, amount, note); setNote(""); }}
                data-testid={`topup-btn-${user.id}`}
            >
                <Send size={14} strokeWidth={2.5} /> Top-up
            </button>
        </div>
    );
};

const UserCard = ({ user, onTopUp, onDelete }) => (
    <div className="nb-card nb-card-hover p-5" data-testid={`user-card-${user.id}`}>
        <div className="flex items-start justify-between">
            <div>
                <span className={`nb-badge ${user.role === "admin" ? "!bg-black !text-white" : "nb-badge-approved"}`}>{user.role}</span>
                <h3 className="font-display font-black text-xl mt-2">{user.name || user.email}</h3>
                <p className="text-xs font-mono break-all">{user.email}</p>
            </div>
            {user.role !== "admin" && (
                <button
                    className="nb-btn nb-btn-danger !p-2"
                    onClick={() => onDelete(user.id)}
                    data-testid={`delete-user-${user.id}`}
                >
                    <Trash2 size={14} />
                </button>
            )}
        </div>
        <div className="mt-3 p-3 border-2 border-black bg-[#A7F3D0] flex items-center justify-between">
            <span className="label-uppercase">Wallet</span>
            <span className="font-display font-black text-2xl" data-testid={`wallet-balance-${user.id}`}>{user.wallet_balance} cr</span>
        </div>
        <TopUpRow user={user} onTopUp={onTopUp} />
    </div>
);

const CreateUserForm = ({ onCreate, onCancel }) => {
    const [form, setForm] = useState({ email: "", password: "", name: "" });
    const [submitting, setSubmitting] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await onCreate(form);
            setForm({ email: "", password: "", name: "" });
        } finally {
            setSubmitting(false);
        }
    };
    return (
        <form onSubmit={submit} className="nb-card p-6 space-y-3" data-testid="create-user-form">
            <div className="flex items-center justify-between">
                <h2 className="font-display font-bold text-xl">Add new user</h2>
                <button type="button" className="nb-btn !p-2" onClick={onCancel}><X size={14} /></button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input className="nb-input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="new-user-name" />
                <input className="nb-input" type="email" required placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="new-user-email" />
                <input className="nb-input" type="password" required placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="new-user-password" />
            </div>
            <button type="submit" className="nb-btn nb-btn-primary" disabled={submitting} data-testid="create-user-submit">
                {submitting ? <div className="nb-spinner" /> : <Plus size={14} strokeWidth={2.5} />} Create user
            </button>
        </form>
    );
};

const AdminUsers = () => {
    const { user } = useAuth();
    const [users, setUsers] = useState([]);
    const [showForm, setShowForm] = useState(false);

    const load = useCallback(async () => {
        try {
            const res = await apiClient.get("/admin/users");
            setUsers(res.data);
        } catch {
            toast.error("Could not load users");
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (user?.role !== "admin") {
        return (
            <div className="nb-card p-10 text-center bg-white">
                <h2 className="font-display font-bold text-2xl">Admin only 🔒</h2>
                <p className="text-sm font-medium mt-2">Sirf admin is page ko dekh sakta hai.</p>
            </div>
        );
    }

    const createUser = async (form) => {
        try {
            await apiClient.post("/admin/users", form);
            toast.success("User created");
            load();
            setShowForm(false);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    const topUp = async (uid, amount, note) => {
        try {
            await apiClient.post("/admin/wallet/topup", { user_id: uid, amount, note });
            toast.success(`+${amount} credits added`);
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Top-up failed");
        }
    };

    const remove = async (uid) => {
        if (!window.confirm("Delete this user? Their websites/ads/leads stay but become orphaned.")) return;
        try {
            await apiClient.delete(`/admin/users/${uid}`);
            toast.success("Deleted");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    return (
        <div className="space-y-6" data-testid="admin-users-page">
            <div className="flex justify-between items-end">
                <div>
                    <p className="label-uppercase">Admin</p>
                    <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1 flex items-center gap-3"><Users size={36} strokeWidth={2.5} /> Users</h1>
                    <p className="text-sm mt-2 font-medium">Sirf aap (admin) hi users add aur unke wallet me credits dal sakte ho.</p>
                </div>
                <button className="nb-btn nb-btn-primary" onClick={() => setShowForm(true)} data-testid="show-create-user-btn">
                    <Plus size={16} strokeWidth={2.5} /> Add user
                </button>
            </div>
            {showForm && <CreateUserForm onCreate={createUser} onCancel={() => setShowForm(false)} />}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="users-grid">
                {users.map((u) => (
                    <UserCard key={u.id} user={u} onTopUp={topUp} onDelete={remove} />
                ))}
            </div>
            <div className="nb-card p-6 bg-[#BAE6FD]">
                <div className="flex items-center gap-2">
                    <Wallet size={18} strokeWidth={2.5} />
                    <h3 className="font-display font-bold text-lg">Credit Pricing (per action)</h3>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3 text-sm font-bold">
                    <div className="p-3 border-2 border-black bg-white text-center">🖼️ Image<br/><span className="font-display text-2xl">5</span></div>
                    <div className="p-3 border-2 border-black bg-white text-center">🎬 Video 4s<br/><span className="font-display text-2xl">30</span></div>
                    <div className="p-3 border-2 border-black bg-white text-center">🎬 Video 8s<br/><span className="font-display text-2xl">60</span></div>
                    <div className="p-3 border-2 border-black bg-white text-center">🔁 Variant<br/><span className="font-display text-2xl">5</span></div>
                    <div className="p-3 border-2 border-black bg-white text-center">🤖 Auto-gen<br/><span className="font-display text-2xl">5</span></div>
                </div>
            </div>
        </div>
    );
};

export default AdminUsers;
