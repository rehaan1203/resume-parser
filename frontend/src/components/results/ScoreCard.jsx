'use client';
import React, { useEffect, useState } from 'react';
import { motion, animate } from 'framer-motion';
import { Card } from '../shared/Card';

export const ScoreCard = ({ score, breakdown }) => {
    const isScoreAvailable = typeof score === 'number' && !isNaN(score);
    const [animatedScore, setAnimatedScore] = useState(0);

    useEffect(() => {
        if (!isScoreAvailable) return;
        const controls = animate(0, score, {
            duration: 1.5,
            type: "tween",
            ease: "easeOut",
            onUpdate: (latest) => setAnimatedScore(Math.round(latest))
        });
        return () => controls.stop();
    }, [score, isScoreAvailable]);

    const colorClass = "text-zinc-900 dark:text-zinc-50";
    const strokeClass = "stroke-zinc-900 dark:stroke-zinc-50";

    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = isScoreAvailable 
        ? circumference - (score / 100) * circumference 
        : circumference;

    return (
        <Card className="flex flex-col items-center justify-center p-8 bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm transition-all duration-300">
          <div className="relative w-40 h-40 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 140 140">
              <circle cx="70" cy="70" r={radius} className="stroke-zinc-200 dark:stroke-zinc-800" strokeWidth="8" fill="transparent"/>
              {isScoreAvailable && (
                <motion.circle 
                  cx="70" 
                  cy="70" 
                  r={radius} 
                  className={strokeClass} 
                  strokeWidth="8" 
                  fill="transparent" 
                  strokeDasharray={circumference} 
                  initial={{ strokeDashoffset: circumference }} 
                  animate={{ strokeDashoffset }} 
                  transition={{ duration: 1.5, type: "tween", ease: "easeOut" }} 
                  strokeLinecap="round"
                />
              )}
            </svg>
            <div className="absolute inset-0 flex items-center justify-center flex-col">
              <span className={`text-4xl sm:text-5xl font-semibold tracking-tighter ${colorClass}`}>
                {isScoreAvailable ? `${animatedScore}%` : 'N/A'}
              </span>
            </div>
          </div>
          <p className="mt-4 text-sm font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Match Score</p>
          
          {breakdown && isScoreAvailable && (
              <div className="w-full mt-6 space-y-3 pt-4 border-t border-zinc-200 dark:border-zinc-800">
                  <div className="flex justify-between items-center text-sm">
                      <span className="text-zinc-500 dark:text-zinc-400">Skills Match</span>
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">{breakdown.skills_match ?? breakdown.skillsMatch ?? 0}%</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                      <span className="text-zinc-500 dark:text-zinc-400">Seniority Match</span>
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">{breakdown.seniority_match ?? breakdown.seniorityMatch ?? 0}%</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                      <span className="text-zinc-500 dark:text-zinc-400">Domain Match</span>
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">{breakdown.domain_match ?? breakdown.domainMatch ?? 0}%</span>
                  </div>
              </div>
          )}
        </Card>
    );
};

