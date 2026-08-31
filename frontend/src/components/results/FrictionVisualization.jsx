'use client';
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, AlertTriangle, Info, ChevronDown } from 'lucide-react';
import { cn } from '../../utils/cn';
export const FrictionVisualization = ({ points }) => {
    const [expandedIds, setExpandedIds] = useState([]);
    const toggleExpand = (id) => {
        setExpandedIds(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]);
    };
    const getIcon = (severity) => {
        switch (severity) {
            case 'critical': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><AlertCircle className="w-5 h-5 text-red-500 drop-shadow-md"/></motion.div>;
            case 'warning': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><AlertTriangle className="w-5 h-5 text-yellow-500 drop-shadow-md"/></motion.div>;
            case 'info': return <motion.div whileHover={{ y: -3, scale: 1.1 }}><Info className="w-5 h-5 text-blue-500 drop-shadow-md"/></motion.div>;
            default: return null;
        }
    };
    const getBadgeClass = (severity) => {
        switch (severity) {
            case 'critical': return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-800";
            case 'warning': return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800";
            case 'info': return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800";
            default: return "";
        }
    };
    return (<div className="space-y-4">
      <h3 className="text-xl font-bold mb-4 flex items-center text-zinc-900 dark:text-zinc-100">
        Friction Points <span className="ml-2 px-2 py-0.5 text-sm bg-zinc-100 dark:bg-zinc-800 rounded-full">{points.length}</span>
      </h3>
      <motion.div variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } }} initial="hidden" animate="show">
        {points.map((point) => (<motion.div key={point.id} variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="mb-3">
            <div className={cn("border rounded-lg overflow-hidden transition-all duration-200 cursor-pointer backdrop-blur-md bg-zinc-50/50 dark:bg-[#09090b]/50 hover:bg-white/80 dark:hover:bg-[#111113]/80", expandedIds.includes(point.id) ? "border-zinc-300 dark:border-zinc-700 shadow-sm" : "border-zinc-200 dark:border-zinc-800")} onClick={() => toggleExpand(point.id)}>
              <div className="p-4 flex items-start justify-between">
                <div className="flex items-start gap-3 flex-1">
                  <div className="mt-0.5">{getIcon(point.severity)}</div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn("text-xs font-semibold px-2 py-0.5 rounded border capitalize", getBadgeClass(point.severity))}>
                        {point.severity}
                      </span>
                      <span className="text-xs text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-medium">{point.category}</span>
                    </div>
                    <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium text-justify">{point.description}</p>
                  </div>
                </div>
                <ChevronDown className={cn("w-5 h-5 text-zinc-400 transition-transform", expandedIds.includes(point.id) ? "rotate-180" : "")}/>
              </div>

              <AnimatePresence>
                {expandedIds.includes(point.id) && (<motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="p-4 pt-0 border-t border-zinc-200/50 dark:border-zinc-800/50 bg-white/30 dark:bg-black/20">
                      <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium mt-3 text-justify">
                        <span className="font-semibold text-zinc-900 dark:text-zinc-100">Suggestion: </span>
                        {point.suggestion}
                      </p>
                    </div>
                  </motion.div>)}
              </AnimatePresence>
            </div>
          </motion.div>))}
      </motion.div>
    </div>);
};
