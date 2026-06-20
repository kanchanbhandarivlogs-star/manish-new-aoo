import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Key, Save, ExternalLink, ShieldCheck, Bell } from "lucide-react";
import { toast } from "sonner";

const PageHeader = () => (
    <div>
        <p className="label-uppercase">Configure</p>
        <h1 className="font-display font-black text-4xl sm:text-5xl uppercase mt-1">Meta Settings</h1>
        <p className="text-sm mt-2 max-w-xl font-medium">
            Save your Facebook / Instagram credentials here. You can update them anytime — no code changes needed.
        </p>
    </div>
);

const TokenGuideCard = () => (
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
);

const CredentialField = ({ label, value, onChange, type = "text", placeholder, testid, mono = false }) => (
    <div>
        <label className="label-uppercase">{label}</label>
        <input
            className={`nb-input mt-2 ${mono ? "font-mono" : ""} ${type === "password" ? "text-xs" : ""}`}
            type={type}
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            data-testid={testid}
        />
    </div>
);

const TelegramSection = ({ form, setForm }) => (
    <div className="border-2 border-black p-4 bg-[#BAE6FD]">
        <div className="flex items-center gap-2">
            <Bell size={18} strokeWidth={2.5} />
            <h3 className="font-display font-bold text-lg">Real-time Lead Alerts (Telegram)</h3>
        </div>
        <p className="text-xs mt-2 font-medium">
            जैसे ही कोई नया lead आए, instantly Telegram पर ping मिलेगा। Steps:
        </p>
        <ol className="text-xs mt-2 list-decimal list-inside font-medium space-y-1">
            <li>Telegram पर <strong>@BotFather</strong> को message करें → /newbot → token लें</li>
            <li>उस bot को अपने chat में add करें और एक message भेजें</li>
            <li><code className="bg-white px-1 border border-black">api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> खोलें → `chat.id` copy करें</li>
            <li>नीचे दोनों paste करें ↓</li>
        </ol>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
            <CredentialField
                label="Bot Token"
                mono
                type="password"
                placeholder="1234567890:ABCdef..."
                value={form.telegram_bot_token}
                onChange={(v) => setForm({ ...form, telegram_bot_token: v })}
                testid="tg-token-input"
            />
            <CredentialField
                label="Chat ID"
                mono
                placeholder="123456789 (or -100123 for group)"
                value={form.telegram_chat_id}
                onChange={(v) => setForm({ ...form, telegram_chat_id: v })}
                testid="tg-chat-input"
            />
        </div>
    </div>
);

const SettingsForm = ({ form, setForm, saving, onSubmit }) => (
    <form onSubmit={onSubmit} className="nb-card p-6 space-y-4" data-testid="settings-form">
        <div className="flex items-center gap-2">
            <Key size={18} strokeWidth={2.5} />
            <h2 className="font-display font-bold text-xl">Credentials</h2>
        </div>

        <CredentialField
            label="FB Access Token (System User)"
            type="password"
            mono
            placeholder="EAAxxx... (paste here)"
            value={form.fb_access_token}
            onChange={(v) => setForm({ ...form, fb_access_token: v })}
            testid="fb-token-input"
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CredentialField
                label="Facebook Page ID"
                mono
                placeholder="123456789012345"
                value={form.fb_page_id}
                onChange={(v) => setForm({ ...form, fb_page_id: v })}
                testid="fb-page-input"
            />
            <CredentialField
                label="Instagram Business Account ID"
                mono
                placeholder="17841412345678"
                value={form.ig_account_id}
                onChange={(v) => setForm({ ...form, ig_account_id: v })}
                testid="ig-account-input"
            />
        </div>

        <TelegramSection form={form} setForm={setForm} />

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
);

const Settings = () => {
    const [form, setForm] = useState({
        fb_access_token: "",
        fb_page_id: "",
        ig_account_id: "",
        telegram_bot_token: "",
        telegram_chat_id: "",
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        try {
            const res = await apiClient.get("/meta-settings");
            setForm({
                fb_access_token: res.data.fb_access_token || "",
                fb_page_id: res.data.fb_page_id || "",
                ig_account_id: res.data.ig_account_id || "",
                telegram_bot_token: res.data.telegram_bot_token || "",
                telegram_chat_id: res.data.telegram_chat_id || "",
            });
        } catch {
            toast.error("Could not load settings");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

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
            <PageHeader />
            <TokenGuideCard />
            {loading ? (
                <div className="nb-card p-10 text-center">
                    <div className="nb-spinner mx-auto" />
                </div>
            ) : (
                <SettingsForm form={form} setForm={setForm} saving={saving} onSubmit={save} />
            )}
        </div>
    );
};

export default Settings;
