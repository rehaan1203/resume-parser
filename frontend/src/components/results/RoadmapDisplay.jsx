'use client';
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Calendar, ExternalLink, ChevronDown, Map, Compass } from 'lucide-react';
import { Card } from '../shared/Card';
import { cn } from '../../utils/cn';

export const RoadmapDisplay = ({ roadmap }) => {
    const [expandedSections, setExpandedSections] = useState([1]);
    
    if (!roadmap) return null;

    const toggleSection = (id) => {
        setExpandedSections(prev => prev.includes(id) ? prev.filter(w => w !== id) : [...prev, id]);
    };

    // Determine the type of roadmap payload
    const isLegacy = Array.isArray(roadmap);
    const data = isLegacy ? null : (roadmap.data || roadmap.content || roadmap);
    const ai_note = isLegacy ? null : roadmap.ai_note;
    
    let renderType = '30_day';
    if (!isLegacy) {
        if (data.phases || roadmap.type === 'transition' || roadmap.type === 'career_change') {
            renderType = 'transition';
        } else if (data.months) {
            renderType = '90_day';
        } else {
            renderType = '30_day';
        }
    }

    const renderHeader = (title, icon) => (
        <div className="flex items-center gap-3 border-b border-zinc-200 dark:border-zinc-800 pb-4">
            {icon}
            <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{title}</h2>
        </div>
    );

    const renderResources = (resources) => (
        resources && resources.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
                {resources.map((res, rIdx) => (
                    <a key={rIdx} href={res.startsWith('http') ? res : `https://google.com/search?q=${res}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-xs px-2 py-1 bg-zinc-200/80 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded hover:bg-zinc-300 dark:hover:bg-zinc-700 transition-colors border border-zinc-300 dark:border-zinc-700">
                        {res.substring(0, 30)}{res.length > 30 ? '...' : ''} <ExternalLink className="w-3 h-3 ml-1"/>
                    </a>
                ))}
            </div>
        )
    );

    // ==========================================
    // LEGACY / 30 DAY RENDERER
    // ==========================================
    if (renderType === '30_day') {
        let flatItems = [];
        if (isLegacy) {
            flatItems = roadmap;
        } else if (data.days) {
            data.days.forEach(d => {
                flatItems.push({ week: 1, day: d.day || 1, action: d.action, resources: d.resources || [] });
            });
        } else if (data.weeks) {
            data.weeks.forEach(w => {
                if (w.days) {
                    w.days.forEach(d => {
                        flatItems.push({ week: w.week || 1, day: d.day || 1, action: d.action, resources: d.resources || [] });
                    });
                } else if (w.activities) {
                    w.activities.forEach(a => {
                        flatItems.push({ week: w.week || 1, day: a.day || 1, action: a.action, resources: a.resources || [] });
                    });
                }
            });
        }

        const weeks = Array.from(new Set(flatItems.map(item => item.week))).sort();

        return (
            <div className="mt-12 space-y-6">
                {renderHeader((roadmap.title || "30-Day Learning Roadmap").replace(/[^\x00-\x7F]/g, "").trim(), <Calendar className="w-6 h-6 text-zinc-900 dark:text-zinc-100"/>)}
                <div className="space-y-4">
                    {weeks.map(week => {
                        const isExpanded = expandedSections.includes(week);
                        const weekItems = flatItems.filter(item => item.week === week).sort((a, b) => a.day - b.day);
                        return (
                            <Card key={`week-${week}`} hoverLift={false} className="p-0 overflow-hidden bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 shadow-sm">
                                <button onClick={() => toggleSection(week)} className="w-full flex items-center justify-between p-4 bg-zinc-100/50 hover:bg-zinc-200/50 dark:bg-zinc-900/50 dark:hover:bg-zinc-800/50 transition-colors">
                                    <h3 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">Week {week}</h3>
                                    <ChevronDown className={cn("w-5 h-5 text-zinc-500 transition-transform", isExpanded ? "rotate-180" : "")}/>
                                </button>
                                <AnimatePresence>
                                    {isExpanded && (
                                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-zinc-200 dark:border-zinc-800">
                                            <div className="p-4 relative">
                                                <div className="absolute left-4 top-6 bottom-4 w-0.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden shadow-[0_0_5px_rgba(139,92,246,0.15)]">
                                                    <motion.div className="absolute w-full h-[40%] bg-gradient-to-b from-transparent via-violet-500 dark:via-violet-400 to-transparent opacity-90 blur-[1px]" animate={{ top: ["-40%", "100%"] }} transition={{ repeat: Infinity, duration: 3, ease: "linear" }} />
                                                </div>
                                                <motion.div className="space-y-6" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
                                                    {weekItems.map((item, idx) => (
                                                        <motion.div key={idx} className="relative pl-6 group" variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0, transition: { type: "spring", stiffness: 100 } } }} whileHover={{ x: 4, transition: { duration: 0.2 } }}>
                                                            <div className="absolute w-3 h-3 bg-zinc-400 dark:bg-zinc-600 rounded-full -left-1.5 top-1.5 ring-4 ring-zinc-50/50 dark:ring-[#09090b]/50 group-hover:scale-125 group-hover:bg-violet-500 dark:group-hover:bg-violet-400 group-hover:ring-violet-100 transition-all duration-300"/>
                                                            <div className="mb-1 text-sm font-semibold text-zinc-600 dark:text-zinc-400">Day {item.day}</div>
                                                            <div className="font-medium text-zinc-900 dark:text-zinc-200 mb-2">{item.action}</div>
                                                            {renderResources(item.resources)}
                                                        </motion.div>
                                                    ))}
                                                </motion.div>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </Card>
                        );
                    })}
                </div>
            </div>
        );
    }

    // ==========================================
    // 90 DAY RENDERER
    // ==========================================
    if (renderType === '90_day') {
        const months = data.months || [];
        return (
            <div className="mt-12 space-y-6">
                {renderHeader(`Extended ${data.total_days}-Day Roadmap`, <Map className="w-6 h-6 text-zinc-900 dark:text-zinc-100"/>)}
                <div className="space-y-4">
                    {months.map(month => {
                        const isExpanded = expandedSections.includes(month.month);
                        return (
                            <Card key={`month-${month.month}`} hoverLift={false} className="p-0 overflow-hidden bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 shadow-sm">
                                <button onClick={() => toggleSection(month.month)} className="w-full flex items-center justify-between p-4 bg-zinc-100/50 hover:bg-zinc-200/50 dark:bg-zinc-900/50 transition-colors">
                                    <div className="flex flex-col items-start">
                                        <h3 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">Month {month.month}</h3>
                                        <p className="text-sm text-zinc-500">{month.focus}</p>
                                    </div>
                                    <ChevronDown className={cn("w-5 h-5 text-zinc-500 transition-transform", isExpanded ? "rotate-180" : "")}/>
                                </button>
                                <AnimatePresence>
                                    {isExpanded && (
                                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-zinc-200 dark:border-zinc-800">
                                            <div className="p-4 relative">
                                                <div className="absolute left-4 top-6 bottom-4 w-0.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden shadow-[0_0_5px_rgba(59,130,246,0.15)]">
                                                    <motion.div className="absolute w-full h-[40%] bg-gradient-to-b from-transparent via-blue-500 to-transparent opacity-90 blur-[1px]" animate={{ top: ["-40%", "100%"] }} transition={{ repeat: Infinity, duration: 3, ease: "linear" }} />
                                                </div>
                                                <motion.div className="space-y-6" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
                                                    {month.activities.map((item, idx) => (
                                                        <motion.div key={idx} className="relative pl-6 group" variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0, transition: { type: "spring", stiffness: 100 } } }} whileHover={{ x: 4, transition: { duration: 0.2 } }}>
                                                            <div className="absolute w-3 h-3 bg-zinc-400 dark:bg-zinc-600 rounded-full -left-1.5 top-1.5 ring-4 ring-zinc-50/50 dark:ring-[#09090b]/50 group-hover:scale-125 group-hover:bg-blue-500 group-hover:ring-blue-100 transition-all duration-300"/>
                                                            <div className="mb-1 text-sm font-semibold text-zinc-600 dark:text-zinc-400">Week {item.week}</div>
                                                            <div className="font-medium text-zinc-900 dark:text-zinc-200 mb-2">{item.action}</div>
                                                            {renderResources(item.resources)}
                                                        </motion.div>
                                                    ))}
                                                </motion.div>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </Card>
                        );
                    })}
                </div>
            </div>
        );
    }

    // ==========================================
    // TRANSITION RENDERER
    // ==========================================
    if (renderType === 'transition') {
        const phases = data.phases || [];
        return (
            <div className="mt-12 space-y-6">
                {renderHeader(`Career Transition Feasibility (${data.total_months} months)`, <Compass className="w-6 h-6 text-zinc-900 dark:text-zinc-100"/>)}
                
                {ai_note && (
                    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
                        <p className="text-sm font-medium text-blue-800 dark:text-blue-300">
                            {ai_note}
                        </p>
                    </div>
                )}
                
                {data.alternative_roles && data.alternative_roles.length > 0 && (
                    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 mb-6">
                        <h4 className="font-bold text-amber-800 dark:text-amber-300 mb-2 text-sm uppercase tracking-wider">Alternative Bridge Roles</h4>
                        <div className="flex flex-wrap gap-2">
                            {data.alternative_roles.map((role, idx) => (
                                <span key={idx} className="bg-amber-100 dark:bg-amber-800/50 text-amber-700 dark:text-amber-200 px-3 py-1 rounded-full text-sm font-medium">
                                    {role}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                <div className="space-y-4">
                    {phases.map(phase => {
                        const isExpanded = expandedSections.includes(phase.phase);
                        return (
                            <Card key={`phase-${phase.phase}`} hoverLift={false} className="p-0 overflow-hidden bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 shadow-sm">
                                <button onClick={() => toggleSection(phase.phase)} className="w-full flex items-center justify-between p-4 bg-zinc-100/50 hover:bg-zinc-200/50 dark:bg-zinc-900/50 transition-colors">
                                    <div className="flex flex-col items-start text-left">
                                        <div className="flex items-center gap-2">
                                            <span className="bg-zinc-800 text-white dark:bg-zinc-200 dark:text-black text-xs font-bold px-2 py-0.5 rounded">PHASE {phase.phase}</span>
                                            <span className="text-sm font-medium text-zinc-500">({phase.duration})</span>
                                        </div>
                                        <h3 className="font-bold text-lg text-zinc-900 dark:text-zinc-100 mt-1">{phase.focus}</h3>
                                    </div>
                                    <ChevronDown className={cn("w-5 h-5 text-zinc-500 transition-transform", isExpanded ? "rotate-180" : "")}/>
                                </button>
                                <AnimatePresence>
                                    {isExpanded && (
                                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-zinc-200 dark:border-zinc-800">
                                            <div className="p-4 relative">
                                                <div className="absolute left-4 top-6 bottom-4 w-0.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden shadow-[0_0_5px_rgba(245,158,11,0.15)]">
                                                    <motion.div className="absolute w-full h-[40%] bg-gradient-to-b from-transparent via-amber-500 to-transparent opacity-90 blur-[1px]" animate={{ top: ["-40%", "100%"] }} transition={{ repeat: Infinity, duration: 3, ease: "linear" }} />
                                                </div>
                                                <motion.div className="space-y-6" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
                                                    {phase.activities.map((act, idx) => (
                                                        <motion.div key={idx} className="relative pl-6 group" variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0, transition: { type: "spring", stiffness: 100 } } }} whileHover={{ x: 4, transition: { duration: 0.2 } }}>
                                                            <div className="absolute w-3 h-3 bg-zinc-400 dark:bg-zinc-600 rounded-full -left-1.5 top-2 ring-4 ring-zinc-50/50 dark:ring-[#09090b]/50 group-hover:scale-125 group-hover:bg-amber-500 group-hover:ring-amber-100 transition-all duration-300"/>
                                                            <div className="font-medium text-zinc-900 dark:text-zinc-200 pt-0.5">{act}</div>
                                                        </motion.div>
                                                    ))}
                                                    {phase.resources && phase.resources.length > 0 && (
                                                        <div className="pl-6 pt-2">
                                                            {renderResources(phase.resources)}
                                                        </div>
                                                    )}
                                                </motion.div>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </Card>
                        );
                    })}
                </div>
            </div>
        );
    }

    return null;
};
