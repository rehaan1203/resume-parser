import React from 'react';
import { motion } from 'framer-motion';

export default function QuickWinCard({ icon, title, description, duration, onClick }) {
    return (
        <motion.div 
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            onClick={onClick}
            className="bg-zinc-100/50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800 rounded-lg p-3 cursor-pointer hover:bg-zinc-200/50 dark:hover:bg-zinc-800 transition-colors"
        >
            <div className="flex items-center gap-3">
                <div className="text-zinc-700 dark:text-zinc-300">
                    {icon}
                </div>
                <div className="flex-1">
                    <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{title}</div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">{description}</div>
                </div>
                {duration && (
                    <div className="text-xs bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">
                        {duration}
                    </div>
                )}
            </div>
        </motion.div>
    );
}
