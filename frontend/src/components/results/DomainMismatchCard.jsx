import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    AlertOctagon, Loader2, BookOpen, Search, 
    Scale, Bot, RefreshCcw, Link, FileText, 
    ClipboardList, BarChart, AlertTriangle,
    Award, FolderGit2, Rocket
} from 'lucide-react';
import { useAnalysisContext } from '../../context/AnalysisContext';
import { api } from '../../lib/api-client';
import DomainCard from './DomainCard';

export function DomainMismatchCard({ result }) {
    const { formData } = useAnalysisContext();
    const [expanded, setExpanded] = useState(false);
    const [loading, setLoading] = useState(false);
    const [transitionPlan, setTransitionPlan] = useState(null);
    const [error, setError] = useState(null);

    const handleTransitionClick = async () => {
        if (transitionPlan) {
            setExpanded(!expanded);
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const fallbackText = "Text unavailable. " + " ".repeat(100);
            
            const data = await api.transitionPlan({
                resume: formData?.resume || result.resume || result.resume_text || fallbackText,
                jd: formData?.jdText || formData?.jdUrl || result.jd || result.jd_text || fallbackText,
                resume_domain: result.resume_domain,
                jd_domain: result.jd_domain
            });
            
            setTransitionPlan(data);
            setExpanded(true);
        } catch (err) {
            console.error('Failed to fetch transition plan:', err);
            setError(err.message || "Failed to generate transition plan.");
        } finally {
            setLoading(false);
        }
    };

    // Helper to map domain names to icons
    const getDomainIcon = (domainName, fallbackIcon) => {
        const d = (domainName || '').toLowerCase();
        if (d.includes('law') || d.includes('legal')) return <Scale className="w-6 h-6" />;
        if (d.includes('ai') || d.includes('ml') || d.includes('data') || d.includes('software')) return <Bot className="w-6 h-6" />;
        return fallbackIcon;
    };

    return (
        <div className="w-full">
            <div className="bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-xl p-8 max-w-4xl mx-auto">
                {/* Header */}
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 gap-4">
                    <div className="flex items-center gap-3">
                        <div className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2">
                            <RefreshCcw className="w-4 h-4" />
                            <span>DOMAIN MISMATCH DETECTED</span>
                        </div>
                    </div>
                </div>

                {/* 3-Column Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                    <DomainCard 
                        icon={getDomainIcon(result.resume_domain, <Scale className="w-6 h-6" />)} 
                        label="Your Domain" 
                        value={result.resume_domain} 
                        sub="Current Background"
                    />
                    <DomainCard 
                        icon={getDomainIcon(result.jd_domain, <Bot className="w-6 h-6" />)} 
                        label="Target Domain" 
                        value={result.jd_domain} 
                        sub="Required Background"
                    />
                    <DomainCard 
                        icon={<RefreshCcw className="w-6 h-6" />} 
                        label="Gap" 
                        value="Complete Career Change" 
                        sub="12-18 months estimated"
                    />
                </div>

                {/* Score & Message */}
                <div className="bg-zinc-100/50 dark:bg-zinc-800/50 rounded-xl p-6 mb-8 border border-zinc-200 dark:border-zinc-800">
                    <div className="flex flex-col md:flex-row items-center gap-6">
                        <div className="text-center flex-shrink-0">
                            <div className="text-4xl font-bold text-red-500 dark:text-red-400">0%</div>
                            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 uppercase tracking-wider font-semibold">Match Score</div>
                        </div>
                        <div className="w-px h-16 bg-zinc-300 dark:bg-zinc-700 hidden md:block"></div>
                        <div className="text-zinc-700 dark:text-zinc-300 text-lg text-justify flex items-start gap-3">
                            <AlertTriangle className="w-6 h-6 text-amber-500 shrink-0 mt-0.5" />
                            <span>{result.message}</span>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg border border-red-200 dark:border-red-800/30 flex items-start gap-2">
                        <AlertOctagon className="w-5 h-5 shrink-0 mt-0.5" />
                        <span>{error}</span>
                    </div>
                )}

                {/* Action Buttons */}
                <div className="flex justify-center w-full">
                    <button
                        onClick={handleTransitionClick}
                        disabled={loading}
                        className="w-full max-w-lg py-4 px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl text-center transition-all shadow-md hover:shadow-lg disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span>Generating Transition Plan...</span>
                            </>
                        ) : (
                            <>
                                <ClipboardList className="w-5 h-5" />
                                <span>{expanded ? 'Hide Transition Plan' : 'See Career Transition Plan'}</span>
                            </>
                        )}
                    </button>
                </div>
                
                {/* Transition Plan - Inline Expandable */}
                <AnimatePresence>
                    {expanded && transitionPlan && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden mt-8 border-t border-zinc-200 dark:border-zinc-800 pt-8"
                        >
                            <div className="mb-6">
                                <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                                    <Rocket className="w-6 h-6 text-blue-500 shrink-0" />
                                    <span>{transitionPlan.roadmap.title.replace(/^🚀\s*/, '')}</span>
                                </h3>
                                <div className="text-sm font-semibold text-blue-600 dark:text-blue-400 mt-1">
                                    Estimated Timeline: {transitionPlan.roadmap.estimated_timeline}
                                </div>
                            </div>

                            {/* Roadmap Phases */}
                            <div className="space-y-4 mb-8">
                                <h4 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100">Transition Roadmap</h4>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {transitionPlan.roadmap.phases.map((phase, index) => (
                                        <div key={index} className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-5 border border-zinc-200 dark:border-zinc-700/50">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                                                    Phase {phase.phase}
                                                </div>
                                                <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                                                    {phase.duration}
                                                </div>
                                            </div>
                                            <div className="text-base font-bold text-zinc-900 dark:text-zinc-100 mb-3">
                                                {phase.focus}
                                            </div>
                                            <ul className="space-y-3">
                                                {phase.activities.map((activity, i) => (
                                                    <li key={i} className="flex gap-2 text-sm text-zinc-600 dark:text-zinc-300">
                                                        <span className="text-blue-500 shrink-0 mt-1">•</span>
                                                        <span className="text-justify w-full leading-relaxed">{activity}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Transition Resources */}
                            <div className="space-y-4 mb-6">
                                <h4 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100">Transition Resources</h4>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <ResourceCard 
                                        icon={<BookOpen size={18} className="text-blue-500" />} 
                                        title="Education" 
                                        items={transitionPlan.transition_tips.education} 
                                        isLink={true}
                                    />
                                    <ResourceCard 
                                        icon={<Award size={18} className="text-emerald-500" />} 
                                        title="Certifications" 
                                        items={transitionPlan.transition_tips.certifications} 
                                        isLink={true}
                                    />
                                    <ResourceCard 
                                        icon={<FolderGit2 size={18} className="text-purple-500" />} 
                                        title="Portfolio" 
                                        items={transitionPlan.transition_tips.portfolio} 
                                        isLink={true}
                                    />
                                    <ResourceCard 
                                        icon={<FileText size={18} className="text-amber-500" />} 
                                        title="Resume Strategy" 
                                        items={transitionPlan.transition_tips.resume_strategy} 
                                        isLink={false}
                                    />
                                </div>
                            </div>

                            {/* Seniority Message */}
                            <div className="mt-8 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800/50 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                                <div className="text-sm font-medium text-amber-800 dark:text-amber-400 mt-0.5">
                                    {transitionPlan.seniority.message}
                                </div>
                            </div>
                            
                            <div className="mt-6 flex justify-center">
                                <button 
                                    onClick={() => setExpanded(false)}
                                    className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300 transition-colors"
                                >
                                    Close Transition Plan
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

// Helper Component
function ResourceCard({ icon, title, items, isLink = false }) {
    return (
        <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-5 border border-zinc-200 dark:border-zinc-700/50">
            <div className="flex items-center gap-2 text-base font-bold text-zinc-900 dark:text-zinc-100 mb-3">
                {icon} {title}
            </div>
            <ul className="space-y-3 text-sm text-zinc-600 dark:text-zinc-300">
                {items.map((item, i) => (
                    <li key={i} className="flex gap-2">
                        <span className="text-zinc-400 shrink-0 mt-1">•</span>
                        <span className="text-justify w-full leading-relaxed">
                            {isLink && item.url ? (
                                <a 
                                    href={item.url} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
                                >
                                    {item.name || item}
                                    {(item.platform || item.provider) && ` (${item.platform || item.provider})`}
                                </a>
                            ) : typeof item === 'string' ? (
                                item
                            ) : (
                                <>
                                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{item.name || item}</span>
                                    {item.description && <span className="block text-xs text-zinc-500 mt-0.5 text-justify">{item.description}</span>}
                                </>
                            )}
                        </span>
                    </li>
                ))}
            </ul>
        </div>
    );
}
