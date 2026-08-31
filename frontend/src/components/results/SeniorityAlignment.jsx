'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Lightbulb, Pin } from 'lucide-react';

export const SeniorityAlignment = ({ alignment }) => {
    if (!alignment) return null;

    // Extract properties
    const summary = alignment.summary || "";
    const nextSteps = alignment.next_steps || [];
    const alignmentType = alignment.alignment_status || "minor_gap"; // match, minor_gap, significant_gap
    const badge = alignment.alignment_badge || "🟡 MINOR GAP";
    const yourLevel = alignment.your_level || "Unknown";
    const yourYears = alignment.your_years ?? 0;
    const requiredLevel = alignment.required_level || "Unknown";
    const requiredYears = alignment.required_years ?? 0;
    const gap = alignment.gap ?? 0;

    // Dynamic styling based on alignment type
    let badgeStyle = "bg-gray-50 text-gray-700 dark:bg-gray-900/50 dark:text-gray-300 border-gray-200 dark:border-gray-800";
    if (alignmentType === "match") {
        badgeStyle = "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-900";
    } else if (alignmentType === "minor_gap") {
        badgeStyle = "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-900";
    } else if (alignmentType === "significant_gap") {
        badgeStyle = "bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-900";
    }

    return (
        <div className="space-y-4">
            <h3 className="text-xl font-bold mb-4 flex items-center text-zinc-900 dark:text-zinc-100">
                Seniority Alignment
            </h3>
            
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="backdrop-blur-md bg-zinc-50/50 dark:bg-[#09090b]/50 border border-zinc-200 dark:border-zinc-800 rounded-lg p-6 shadow-sm transition-all duration-300"
            >
                {/* 3 Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <motion.div whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 bg-white dark:bg-zinc-900 shadow-sm flex flex-col justify-center items-center text-center">
                        <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-1">Your Level</div>
                        <div className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{yourLevel}</div>
                        <div className="text-sm text-zinc-600 dark:text-zinc-500">({yourYears} years)</div>
                    </motion.div>
                    
                    <motion.div whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 bg-white dark:bg-zinc-900 shadow-sm flex flex-col justify-center items-center text-center">
                        <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-1">Required</div>
                        <div className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{requiredLevel}</div>
                        <div className="text-sm text-zinc-600 dark:text-zinc-500">({requiredYears}+ years)</div>
                    </motion.div>
                    
                    <motion.div whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className={`border rounded-lg p-4 shadow-sm flex flex-col justify-center items-center text-center ${badgeStyle}`}>
                        <div className="text-sm font-medium opacity-80 mb-1">Gap</div>
                        <div className="text-lg font-bold">{gap} year(s)</div>
                        <div className="text-xs font-bold mt-1 tracking-wider">{badge}</div>
                    </motion.div>
                </div>

                {/* Summary Line */}
                {summary && (
                    <div className="mt-5 p-4 bg-zinc-100/80 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm text-zinc-800 dark:text-zinc-200 font-medium flex items-start gap-2">
                        <Lightbulb className="w-5 h-5 text-amber-500 flex-shrink-0" />
                        <span>{summary}</span>
                    </div>
                )}

                {/* Next Steps (max 3) */}
                {nextSteps && nextSteps.length > 0 && (
                    <div className="mt-5">
                        <div className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
                            <Pin className="w-4 h-4 text-rose-500" /> Next Steps
                        </div>
                        <ul className="space-y-2 text-sm text-zinc-700 dark:text-zinc-300">
                            {nextSteps.slice(0, 3).map((step, index) => (
                                <li key={index} className="flex items-start gap-2">
                                    <TrendingUp className="w-4 h-4 mt-0.5 text-zinc-400 flex-shrink-0" />
                                    <span>{step}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </motion.div>
        </div>
    );
};
