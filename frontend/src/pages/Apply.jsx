import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { Send, CheckCircle2, Globe } from "lucide-react";
import { toast } from "sonner";

const emptyForm = { name: "", phone: "", email: "", course: "", city: "", message: "" };

const Apply = () => {
    const { websiteId } = useParams();
    const [site, setSite] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [form, setForm] = useState(emptyForm);

    useEffect(() => {
        apiClient
            .get(`/public/websites/${websiteId}`)
            .then((r) => setSite(r.data))
            .catch(() => setSite(null))
            .finally(() => setLoading(false));
    }, [websiteId]);

    const submit = async (e) => {
        e.preventDefault();
        if (!form.name.trim() || !form.phone.trim()) {
            toast.error("Name and phone are required");
            return;
        }
        setSubmitting(true);
        try {
            await apiClient.post(`/public/leads/${websiteId}`, form);
            setSubmitted(true);
            toast.success("Got it! We'll reach out soon.");
        } catch (err) {
            toast.error(err.response?.data?.detail || "Submission failed");
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="nb-spinner" />
            </div>
        );
    }
    if (!site) {
        return (
            <div className="min-h-screen flex items-center justify-center p-6">
                <div className="nb-card p-10 text-center bg-white max-w-md">
                    <h2 className="font-display font-black text-3xl">404</h2>
                    <p className="text-sm mt-2 font-medium">This apply page doesn&apos;t exist or has been removed.</p>
                </div>
            </div>
        );
    }
    return (
        <div className="min-h-screen flex items-center justify-center p-4 md:p-8 bg-[#FFD84D]" data-testid="apply-page">
            <div className="nb-card !shadow-[8px_8px_0_0_#000] bg-white max-w-xl w-full p-6 md:p-10">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-[#FFD84D] border-2 border-black flex items-center justify-center">
                        <Globe size={20} strokeWidth={2.5} />
                    </div>
                    <div>
                        <p className="label-uppercase">Apply to</p>
                        <h1 className="font-display font-black text-2xl">{site.name}</h1>
                    </div>
                </div>
                {site.description && <p className="text-sm mt-4 font-medium">{site.description}</p>}

                {submitted ? (
                    <div className="mt-8 p-6 border-2 border-black bg-[#A7F3D0] text-center" data-testid="apply-success">
                        <CheckCircle2 size={36} strokeWidth={2.5} className="mx-auto" />
                        <h2 className="font-display font-black text-2xl mt-3">Thanks, {form.name.split(" ")[0]}!</h2>
                        <p className="text-sm font-medium mt-2">Our team will get in touch on <strong>{form.phone}</strong> within 24 hours.</p>
                        {site.cta_url && (
                            <a href={site.cta_url} target="_blank" rel="noreferrer" className="nb-btn nb-btn-primary mt-5 inline-flex" data-testid="apply-visit-site-btn">
                                Visit {site.name}
                            </a>
                        )}
                    </div>
                ) : (
                    <form onSubmit={submit} className="mt-6 space-y-4" data-testid="apply-form">
                        <div>
                            <label className="label-uppercase">Full Name *</label>
                            <input className="nb-input mt-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="apply-name-input" />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label className="label-uppercase">Phone *</label>
                                <input className="nb-input mt-2 font-mono" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="apply-phone-input" />
                            </div>
                            <div>
                                <label className="label-uppercase">Email</label>
                                <input className="nb-input mt-2 font-mono" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="apply-email-input" />
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label className="label-uppercase">Course / Interest</label>
                                <input className="nb-input mt-2" placeholder="e.g. B.Tech CSE" value={form.course} onChange={(e) => setForm({ ...form, course: e.target.value })} data-testid="apply-course-input" />
                            </div>
                            <div>
                                <label className="label-uppercase">City</label>
                                <input className="nb-input mt-2" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} data-testid="apply-city-input" />
                            </div>
                        </div>
                        <div>
                            <label className="label-uppercase">Message (optional)</label>
                            <textarea
                                className="nb-input mt-2 min-h-[90px]"
                                placeholder="Anything specific you want to know?"
                                value={form.message}
                                onChange={(e) => setForm({ ...form, message: e.target.value })}
                                data-testid="apply-message-input"
                            />
                        </div>
                        <button type="submit" className="nb-btn nb-btn-primary w-full !py-4" disabled={submitting} data-testid="apply-submit-btn">
                            {submitting ? <div className="nb-spinner" /> : <Send size={16} strokeWidth={2.5} />} Submit Application
                        </button>
                        <p className="text-xs text-center font-medium text-neutral-700">
                            Your info goes only to {site.name}&apos;s team. No spam.
                        </p>
                    </form>
                )}
            </div>
        </div>
    );
};

export default Apply;
