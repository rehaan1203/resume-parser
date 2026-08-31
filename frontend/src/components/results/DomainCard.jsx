import React from 'react';
import { motion } from 'framer-motion';

export default function DomainCard({ icon, label, value, sub }) {
    return (
        <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-xl border bg-zinc-50/50 dark:bg-[#09090b]/50 border-zinc-200 dark:border-zinc-800 text-center flex flex-col items-center justify-center transition-colors"
        >
            <div className="mb-2 text-zinc-700 dark:text-zinc-300">
                {icon}
            </div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-1">
                {label}
            </div>
            <div className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                {value}
            </div>
            {sub && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    {sub}
                </div>
            )}
        </motion.div>
    );
}
