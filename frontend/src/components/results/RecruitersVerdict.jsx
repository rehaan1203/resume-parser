'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { Briefcase, UserCheck } from 'lucide-react';
import { cn } from '../../utils/cn';

export const RecruitersVerdict = ({ reasoning, domainAnalysis }) => {
    if (!reasoning) return null;

    return (
        <div className="space-y-4">
            <h3 className="text-xl font-bold mb-4 flex items-center text-zinc-900 dark:text-zinc-100">
                Recruiter&apos;s Verdict
            </h3>
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="backdrop-blur-md bg-zinc-50/50 dark:bg-[#09090b]/50 border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden shadow-sm p-5 transition-all duration-300 hover:shadow-md hover:border-zinc-300 dark:hover:border-zinc-700"
            >
                <div className="flex items-start gap-4">
                    <motion.div 
                        whileHover={{ y: -3, scale: 1.1 }}
                        className="p-3 bg-blue-100/80 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-full mt-1 border border-blue-200 dark:border-blue-800/50"
                    >
                        <UserCheck className="w-6 h-6 drop-shadow-sm" />
                    </motion.div>
                    <div>
                        <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium text-justify">
                            {reasoning}
                        </p>
                        
                        {domainAnalysis && domainAnalysis.resume_domain && (
                            <div className="mt-4 pt-4 border-t border-zinc-200/50 dark:border-zinc-800/50 flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                                <motion.div whileHover={{ y: -2, scale: 1.1 }}><Briefcase className="w-4 h-4" /></motion.div>
                                <span>
                                    <strong>JD Domain:</strong> <span className="capitalize">{domainAnalysis.jd_domain}</span>
                                </span>
                                <span className="mx-2">•</span>
                                <span>
                                    <strong>Resume Domain:</strong> <span className="capitalize">{domainAnalysis.resume_domain}</span>
                                </span>
                                <span className="mx-2">•</span>
                                <span className={cn(
                                    "font-semibold", 
                                    domainAnalysis.match ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                                )}>
                                    {domainAnalysis.match ? "Domain Match" : "Domain Mismatch"}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </motion.div>
        </div>
    );
};
