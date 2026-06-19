import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Key, Save, ExternalLink, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const Settings = () => {
    const [form, setForm] = useState({ fb_access_token: "", fb_page_id: "", ig_account_id: "" });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const load = async () => {
        try {
            const res = await apiClient.get("/meta-settings");
            setForm({
                fb_access_token: res.data.fb_access_token || "",
                fb_page_id: res.data.fb_page_id || "",
                ig_account_id: res.data.ig_account_id || "",
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const save = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await apiClient.put("/meta-settings", form);
            toast.success("Settings saved");
        } catch {
            toast.error("Could not save");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-6 max-w-3xl" data-testid="settings-page">
            <div>
                <p className="label-uppercase">Configure</p>
                <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Meta Settings</h1>
                <p className="text-sm mt-2 max-w-xl font-medium">
                    Save your Facebook / Instagram credentials here. You can update them anytime — no code changes needed.
                </p>
            </div>

            <div className="nb-card p-6 bg-[#A7F3D0]">
                <div className="flex items-start gap-3">
                    <ShieldCheck size={22} strokeWidth={2.5} />
                    <div>
                        <h2 className="font-display font-bold text-lg">Use a permanent System User token</h2>
                        <p className="text-sm font-medium mt-1">
                            Regular tokens expire in 1-2 hours. From{" "}
                            <a className="underline font-bold" href="https://business.facebook.com" target="_blank" rel="noreferrer">business.facebook.com</a>{" "}
                            → Settings → Users → System Users, generate a token with permissions:{" "}
                            <code className="bg-white px-1 border border-black">pages_manage_posts</code>,{" "}
                            <code className="bg-white px-1 border border-black">pages_read_engagement</code>,{" "}
                            <code className="bg-white px-1 border border-black">instagram_basic</code>,{" "}
                            <code className="bg-white px-1 border border-black">instagram_content_publish</code>.
                        </p>
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="nb-card p-10 text-center">
                    <div className="nb-spinner mx-auto" />
                </div>
            ) : (
                <form onSubmit={save} className="nb-card p-6 space-y-4" data-testid="settings-form">
                    <div className="flex items-center gap-2">
                        <Key size={18} strokeWidth={2.5} />
                        <h2 className="font-display font-bold text-xl">Credentials</h2>
                    </div>

                    <div>
                        <label className="label-uppercase">FB Access Token (System User)</label>
                        <input
                            className="nb-input mt-2 font-mono text-xs"
                            type="password"
                            placeholder="EAAxxx... (paste here)"
                            value={form.fb_access_token}
                            onChange={(e) => setForm({ ...form, fb_access_token: e.target.value })}
                            data-testid="fb-token-input"
                        />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="label-uppercase">Facebook Page ID</label>
                            <input
                                className="nb-input mt-2 font-mono"
                                placeholder="123456789012345"
                                value={form.fb_page_id}
                                onChange={(e) => setForm({ ...form, fb_page_id: e.target.value })}
                                data-testid="fb-page-input"
                            />
                        </div>
                        <div>
                            <label className="label-uppercase">Instagram Business Account ID</label>
                            <input
                                className="nb-input mt-2 font-mono"
                                placeholder="17841412345678"
                                value={form.ig_account_id}
                                onChange={(e) => setForm({ ...form, ig_account_id: e.target.value })}
                                data-testid="ig-account-input"
                            />
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3 pt-2">
                        <button type="submit" className="nb-btn nb-btn-primary" disabled={saving} data-testid="save-settings-btn">
                            {saving ? <div className="nb-spinner" /> : <Save size={16} strokeWidth={2.5} />} Save
                        </button>
                        <a
                            className="nb-btn"
                            href="https://developers.facebook.com/tools/explorer/"
                            target="_blank"
                            rel="noreferrer"
                            data-testid="open-graph-explorer"
                        >
                            <ExternalLink size={14} /> Open Graph API Explorer
                        </a>
                    </div>

                    <p className="text-xs text-neutral-700 font-medium pt-2">
                        Tokens are stored in your private MongoDB. Set an Ad Account spending limit in Meta Ads Manager
                        (Billing → Account Spending Limit) for budget safety.
                    </p>
                </form>
            )}
        </div>
    );
};

export default Settings;
