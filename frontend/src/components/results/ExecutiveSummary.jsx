import React from 'react';
import { FileText } from 'lucide-react';
import { motion } from 'framer-motion';

export function ExecutiveSummary({ summary, isDegraded }) {
    if (!summary) return null;

    return (
        <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm mb-8"
        >
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/10 rounded-xl">
                        <FileText className="w-5 h-5 text-blue-500" />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">Executive Summary</h2>
                </div>
                {isDegraded && (
                    <span className="text-xs px-2.5 py-1 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                        Generic suggestions shown: automated suggestions were unavailable
                    </span>
                )}
            </div>
            <div className="text-gray-600 dark:text-zinc-400 leading-relaxed text-lg font-medium text-justify">
                {summary}
            </div>
        </motion.div>
    );
}
