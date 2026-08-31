'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { Target, PlusCircle, Edit3, LayoutTemplate, Briefcase, GraduationCap, Award, FileText } from 'lucide-react';
import { cn } from '../../utils/cn';

export const ATSOptimizationTips = ({ tips }) => {
    if (!tips) return null;

    const isLegacy = Array.isArray(tips);
    const hasItems = isLegacy ? tips.length > 0 : Object.keys(tips).length > 0;
    
    if (!hasItems) return null;

    const getIcon = (type) => {
        switch (type.toLowerCase()) {
            case 'add_keyword': case 'keywords': case 'relevant_skills': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><PlusCircle className="w-5 h-5 text-emerald-500 drop-shadow-sm" /></motion.div>;
            case 'rephrase': case 'phrasing': case 'transferable_skills': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><Edit3 className="w-5 h-5 text-blue-500 drop-shadow-sm" /></motion.div>;
            case 'formatting': case 'formatting_tips': case 'resume_strategy': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><LayoutTemplate className="w-5 h-5 text-purple-500 drop-shadow-sm" /></motion.div>;
            case 'education': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><GraduationCap className="w-5 h-5 text-amber-500 drop-shadow-sm" /></motion.div>;
            case 'portfolio': case 'projects': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><Briefcase className="w-5 h-5 text-cyan-500 drop-shadow-sm" /></motion.div>;
            case 'certifications': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><Award className="w-5 h-5 text-yellow-500 drop-shadow-sm" /></motion.div>;
            case 'alternative_roles': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><Target className="w-5 h-5 text-rose-500 drop-shadow-sm" /></motion.div>;
            default: return <motion.div whileHover={{ y: -3, scale: 1.1 }}><FileText className="w-5 h-5 text-zinc-500 drop-shadow-sm" /></motion.div>;
        }
    };

    const getBadgeClass = (type) => {
        switch (type.toLowerCase()) {
            case 'add_keyword': case 'keywords': case 'relevant_skills': return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800";
            case 'rephrase': case 'phrasing': case 'transferable_skills': return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800";
            case 'formatting': case 'formatting_tips': case 'resume_strategy': return "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 border-purple-200 dark:border-purple-800";
            case 'education': return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-800";
            case 'portfolio': case 'projects': return "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400 border-cyan-200 dark:border-cyan-800";
            case 'certifications': return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800";
            case 'alternative_roles': return "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400 border-rose-200 dark:border-rose-800";
            default: return "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400 border-gray-200 dark:border-gray-800";
        }
    };

    let groupedTipsArray = [];

    if (isLegacy) {
        // Legacy grouping logic
        const groupedTips = tips.reduce((acc, tip) => {
            const type = tip.type.toLowerCase();
            if (!acc[type]) acc[type] = [];
            acc[type].push(tip.suggestion);
            return acc;
        }, {});
        groupedTipsArray = Object.entries(groupedTips).map(([type, suggestions]) => ({ type, suggestions }));
    } else {
        // Conditional generator logic (object with arrays)
        // filter out keys like 'type' if they exist inside data
        groupedTipsArray = Object.entries(tips)
            .filter(([k, v]) => Array.isArray(v) && v.length > 0 && k !== 'type')
            .map(([type, suggestions]) => ({ type, suggestions }));
    }

    if (groupedTipsArray.length === 0) return null;

    // Check if this is a transition/career gap focus
    const isTransition = !isLegacy && (tips.education !== undefined || tips.portfolio !== undefined);
    const title = isTransition ? "Career Transition Roadmap" : "ATS Optimization Tips";
    const titleCount = isLegacy ? tips.length : groupedTipsArray.reduce((acc, g) => acc + g.suggestions.length, 0);

    return (
        <div className="space-y-4">
            <h3 className="text-xl font-bold mb-4 flex items-center text-zinc-900 dark:text-zinc-100">
                {title} <span className="ml-2 px-2 py-0.5 text-sm bg-zinc-100 dark:bg-zinc-800 rounded-full">{titleCount}</span>
            </h3>
            
            {isTransition && (
                <div className="bg-rose-50 dark:bg-rose-900/10 border-l-4 border-rose-500 p-4 rounded-r-md mb-4 text-sm text-rose-800 dark:text-rose-200">
                    <strong>Note:</strong> Since this is a significant career pivot, standard ATS keyword stuffing won't be enough. Focus on the transition steps below to build verifiable experience first.
                </div>
            )}

            <div className="grid grid-cols-1 gap-3">
                {groupedTipsArray.map((group, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1, type: "spring", bounce: 0.3 }}
                        whileHover={{ scale: 1.01, transition: { duration: 0.2 } }}
                        className="backdrop-blur-md bg-zinc-50/50 dark:bg-[#09090b]/50 border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 flex gap-3 items-start shadow-sm hover:shadow-md transition-all duration-300"
                    >
                        <div className="mt-0.5">
                            {getIcon(group.type)}
                        </div>
                        <div className="flex-1">
                            <div className="mb-2">
                                <span className={cn("text-xs font-semibold px-2 py-0.5 rounded border capitalize", getBadgeClass(group.type))}>
                                    {group.type.replace(/_/g, ' ')}
                                </span>
                            </div>
                            {group.suggestions.length === 1 ? (
                                <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium mt-1 text-justify">
                                    {typeof group.suggestions[0] === 'object' && group.suggestions[0] !== null ? (
                                        group.suggestions[0].original ? (
                                            <span>
                                                <span className="line-through text-zinc-500 dark:text-zinc-400 mr-2">{group.suggestions[0].original}</span>
                                                <span className="text-emerald-600 dark:text-emerald-400 font-bold mr-2">→ {group.suggestions[0].suggested}</span>
                                                {group.suggestions[0].reason && <span className="text-sm text-zinc-500 dark:text-zinc-400 italic">({group.suggestions[0].reason})</span>}
                                            </span>
                                        ) : (
                                            JSON.stringify(group.suggestions[0])
                                        )
                                    ) : (
                                        group.suggestions[0]
                                    )}
                                </p>
                            ) : (
                                <ul className="list-disc list-outside ml-4 mt-1 space-y-2 text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium text-justify">
                                    {group.suggestions.map((suggestion, sIdx) => (
                                        <li key={sIdx} className="pl-1">
                                            {typeof suggestion === 'object' && suggestion !== null ? (
                                                suggestion.original ? (
                                                    <span>
                                                        <span className="line-through text-zinc-500 dark:text-zinc-400 mr-2">{suggestion.original}</span>
                                                        <span className="text-emerald-600 dark:text-emerald-400 font-bold mr-2">→ {suggestion.suggested}</span>
                                                        {suggestion.reason && <span className="text-sm text-zinc-500 dark:text-zinc-400 italic">({suggestion.reason})</span>}
                                                    </span>
                                                ) : (
                                                    JSON.stringify(suggestion)
                                                )
                                            ) : (
                                                suggestion
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
};
