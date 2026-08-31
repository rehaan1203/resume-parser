import React from 'react';
import { motion } from 'framer-motion';

export default function RoleCard({ title, match, description }) {
    // Parse numeric match if possible
    const matchVal = parseInt(match);
    let matchColor = 'text-red-500 dark:text-red-400';
    if (!isNaN(matchVal)) {
        if (matchVal >= 80) matchColor = 'text-emerald-500 dark:text-emerald-400';
        else if (matchVal >= 60) matchColor = 'text-amber-500 dark:text-amber-400';
    }

    return (
        <motion.div 
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-zinc-100/50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800 rounded-lg p-3 hover:shadow-md transition-all hover:bg-zinc-200/50 dark:hover:bg-zinc-800"
        >
            <div className="flex items-center justify-between mb-1">
                <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{title}</div>
                <div className={`text-sm font-bold ${matchColor}`}>{match}</div>
            </div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400">{description}</div>
        </motion.div>
    );
}
