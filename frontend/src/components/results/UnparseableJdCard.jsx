'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { AlertCircle, Edit3, ArrowUp, HelpCircle, FileSearch } from 'lucide-react';
import { Button } from '../shared/Button';

export function UnparseableJdCard({ onEditJd, message }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-4xl mx-auto"
        >
            <div className="bg-zinc-50/80 dark:bg-[#09090b]/80 backdrop-blur-md border border-amber-500/30 dark:border-amber-500/20 rounded-2xl p-8 sm:p-10 shadow-lg text-center flex flex-col items-center space-y-6">
                <div className="w-16 h-16 rounded-2xl bg-amber-500/10 dark:bg-amber-500/15 border border-amber-500/20 flex items-center justify-center text-amber-600 dark:text-amber-400">
                    <FileSearch className="w-8 h-8" />
                </div>

                <div className="space-y-3 max-w-2xl">
                    <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">
                        We couldn't recognize specific requirements in this job description
                    </h2>
                    <p className="text-sm sm:text-base text-zinc-600 dark:text-zinc-400 leading-relaxed">
                        This version works best with skill-based postings and has limited coverage for some fields, such as healthcare, law and trades, so your job description may be fine. You can paste the requirements section or edit the text below.
                    </p>
                </div>

                <div className="w-full max-w-xl bg-zinc-100/80 dark:bg-zinc-900/60 rounded-xl p-5 border border-zinc-200 dark:border-zinc-800 text-left space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                        <HelpCircle className="w-4 h-4 text-amber-500" />
                        <span>Suggestions to try</span>
                    </div>
                    <ul className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 space-y-2 list-disc list-inside">
                        <li>Paste or highlight the explicit <strong>Requirements</strong>, <strong>Qualifications</strong>, or <strong>Skills</strong> section of the posting.</li>
                        <li>Ensure concrete competencies, licenses, degrees, or tools are explicitly mentioned in the text.</li>
                    </ul>
                </div>

                <div className="pt-2 flex flex-col sm:flex-row gap-3">
                    <Button 
                        size="lg" 
                        onClick={onEditJd}
                        className="rounded-xl px-6 py-3 bg-zinc-900 dark:bg-zinc-50 text-white dark:text-zinc-900 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-md"
                    >
                        <Edit3 className="w-4 h-4 mr-2" />
                        Edit Job Description
                    </Button>
                </div>
            </div>
        </motion.div>
    );
}
