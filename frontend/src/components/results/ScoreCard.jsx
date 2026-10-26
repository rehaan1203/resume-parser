'use client';
import React, { useEffect, useState } from 'react';
import { motion, animate } from 'framer-motion';
import { AlertCircle } from 'lucide-react';
import { Card } from '../shared/Card';

export const ScoreCard = ({ 
    score, 
    breakdown, 
    seniorityReason, 
    seniorityStatus,
    lowConfidence,
    low_confidence
}) => {
    const isScoreAvailable = typeof score === 'number' && !isNaN(score);
    const [animatedScore, setAnimatedScore] = useState(0);
    const isLowConfidence = Boolean(lowConfidence ?? low_confidence);

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
    const strokeClass = isLowConfidence 
        ? "stroke-amber-600 dark:stroke-amber-400" 
        : "stroke-zinc-900 dark:stroke-zinc-50";

    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = isScoreAvailable 
        ? circumference - (score / 100) * circumference 
        : circumference;

    const getBreakdownValue = (val1, val2) => {
        const val = val1 !== undefined ? val1 : val2;
        if (val === null || val === undefined) return null;
        const num = Number(val);
        return !isNaN(num) ? num : null;
    };

    const skillsVal = breakdown ? getBreakdownValue(breakdown.skills_match, breakdown.skillsMatch) : null;
    const seniorityVal = breakdown ? getBreakdownValue(breakdown.seniority_match, breakdown.seniorityMatch) : null;
    const domainVal = breakdown ? getBreakdownValue(breakdown.domain_match, breakdown.domainMatch) : null;

    const effectiveReason = seniorityReason || (breakdown && (breakdown.seniority_reason || breakdown.seniorityReason));
    const effectiveStatus = seniorityStatus || (breakdown && (breakdown.seniority_status || breakdown.seniorityStatus));

    const normReason = String(effectiveReason || '').toLowerCase();
    const normStatus = String(effectiveStatus || '').toLowerCase();

    let seniorityBadgeText = 'Seniority not assessed';
    if (
        normReason === 'not_specified' ||
        normStatus === 'not_specified' ||
        normReason.includes('job description does not specify') ||
        normReason.includes('no experience requirement')
    ) {
        seniorityBadgeText = 'Seniority not assessed: no experience requirement stated';
    } else if (
        normReason === 'unconfirmed' ||
        normStatus === 'unconfirmed' ||
        normReason.includes('unconfirmed') ||
        normReason.includes('not explicitly stated') ||
        normReason.includes("couldn't find")
    ) {
        seniorityBadgeText = "Seniority not assessed: we couldn't find years of experience in your resume";
    }

    return (
        <Card className="flex flex-col items-center justify-center p-8 bg-zinc-50/50 dark:bg-[#09090b]/50 backdrop-blur-md rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm transition-all duration-300">
          <div className={`relative w-40 h-40 flex items-center justify-center ${isLowConfidence ? 'rounded-full border-2 border-dashed border-amber-500/40 dark:border-amber-400/40 p-1' : ''}`}>
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 140 140">
              <circle 
                cx="70" 
                cy="70" 
                r={radius} 
                className={isLowConfidence ? "stroke-amber-500/20 dark:stroke-amber-500/20" : "stroke-zinc-200 dark:stroke-zinc-800"} 
                strokeWidth="8" 
                fill="transparent"
                strokeDasharray={isLowConfidence ? "6 6" : undefined}
              />
              {isLowConfidence && (
                <circle 
                  cx="70" 
                  cy="70" 
                  r={radius + 5} 
                  className="stroke-amber-500/70 dark:stroke-amber-400/70" 
                  strokeWidth="2" 
                  strokeDasharray="5 5" 
                  fill="transparent"
                />
              )}
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
              <span className={`text-4xl sm:text-5xl font-semibold tracking-tighter ${colorClass}`} aria-hidden={isLowConfidence ? "true" : undefined}>
                {isScoreAvailable ? `${animatedScore}%` : 'N/A'}
              </span>
              {isLowConfidence && (
                <span className="sr-only">
                  Provisional score: {isScoreAvailable ? `${score}%` : 'N/A'}. Estimated from limited recognized JD requirements.
                </span>
              )}
            </div>
          </div>
          <p className="mt-4 text-sm font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Match Score</p>
          
          {isLowConfidence && (
            <div 
              className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30"
              role="status"
              aria-label="Provisional score"
            >
              <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0" aria-hidden="true" />
              <span>PROVISIONAL SCORE</span>
            </div>
          )}

          {breakdown && isScoreAvailable && (
              <div className="w-full mt-6 space-y-3 pt-4 border-t border-zinc-200 dark:border-zinc-800">
                  {skillsVal !== null && (
                      <div className="flex justify-between items-center text-sm">
                          <span className="text-zinc-500 dark:text-zinc-400">Skills Match</span>
                          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{skillsVal}%</span>
                      </div>
                  )}
                  {seniorityVal !== null ? (
                      <div className="flex justify-between items-center text-sm">
                          <span className="text-zinc-500 dark:text-zinc-400">Seniority Match</span>
                          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{seniorityVal}%</span>
                      </div>
                  ) : (
                      <div className="pt-1">
                          <span className="inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
                              {seniorityBadgeText}
                          </span>
                      </div>
                  )}
                  {domainVal !== null && (
                      <div className="flex justify-between items-center text-sm">
                          <span className="text-zinc-500 dark:text-zinc-400">Domain Match</span>
                          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{domainVal}%</span>
                      </div>
                  )}
              </div>
          )}

          {isLowConfidence && (
            <p className="mt-4 text-xs text-center text-zinc-500 dark:text-zinc-400 italic">
              Estimated from limited recognized JD requirements
            </p>
          )}
        </Card>
    );
};

