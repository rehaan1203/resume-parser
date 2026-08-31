'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { XCircle, CheckCircle } from 'lucide-react';
import { Card } from '../shared/Card';
export const SkillGapList = ({ gaps }) => {
    return (<Card className="bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 shadow-sm">
      <h3 className="text-sm font-semibold tracking-wide uppercase mb-4 text-zinc-900 dark:text-zinc-50 border-b border-zinc-200 dark:border-zinc-800 pb-2">Skill Gaps</h3>
      <ul className="space-y-3 mt-1">
        {gaps.map((gap, i) => (<motion.li key={i} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1, type: "spring", bounce: 0.3 }} className="flex items-start gap-3 text-zinc-700 dark:text-zinc-300 group">
            <XCircle className="w-5 h-5 shrink-0 mt-[1px] text-zinc-400 group-hover:scale-110 group-hover:text-zinc-900 dark:group-hover:text-zinc-50 transition-all"/>
            <span className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium">{gap}</span>
          </motion.li>))}
      </ul>
    </Card>);
};
export const StrengthList = ({ strengths }) => {
    return (<Card className="bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md border border-zinc-200 dark:border-zinc-800 shadow-sm">
      <h3 className="text-sm font-semibold tracking-wide uppercase mb-4 text-zinc-900 dark:text-zinc-50 border-b border-zinc-200 dark:border-zinc-800 pb-2">Strengths</h3>
      <ul className="space-y-3 mt-1">
        {strengths.map((strength, i) => (<motion.li key={i} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1, type: "spring", bounce: 0.3 }} className="flex items-start gap-3 text-zinc-700 dark:text-zinc-300 group">
            <CheckCircle className="w-5 h-5 shrink-0 mt-[1px] text-zinc-400 group-hover:scale-110 group-hover:text-zinc-900 dark:group-hover:text-zinc-50 transition-all"/>
            <span className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium">{strength}</span>
          </motion.li>))}
      </ul>
    </Card>);
};
