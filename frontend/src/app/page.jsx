'use client';
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Hero } from '../components/layout/Hero';
import { AnalysisForm } from '../components/input/AnalysisForm';
import { ScoreCard } from '../components/results/ScoreCard';
import { FrictionVisualization } from '../components/results/FrictionVisualization';
import { SkillGapList, StrengthList } from '../components/results/Lists';
import { RoadmapDisplay } from '../components/results/RoadmapDisplay';
import { NeuralLoader } from '../components/shared/NeuralLoader';
import { useAnalysisContext } from '../context/AnalysisContext';
import { Button } from '../components/shared/Button';
import { Award, Briefcase, FileText, Send, User, Target, Zap, LayoutDashboard, Brain, AlertTriangle, RefreshCcw } from 'lucide-react';
import { ConfirmModal } from '../components/shared/ConfirmModal';
import { ExecutiveSummary } from '../components/results/ExecutiveSummary';
import { ATSOptimizationTips } from '../components/results/ATSOptimizationTips';
import { SeniorityAlignment } from '../components/results/SeniorityAlignment';
import { DomainMismatchCard } from '../components/results/DomainMismatchCard';
import { useState, useEffect, useRef } from 'react';

export default function Home() {
    const { state, results, resetAnalysis, submitAnalysis, progress, progressMsg } = useAnalysisContext();
    const [showConfirm, setShowConfirm] = useState(false);
    const topRef = useRef(null);
    const resultsRef = useRef(null);

    // Handle scrolling when state changes
    useEffect(() => {
        if (state === 'LOADING' || state === 'RESULTS' || state === 'ERROR') {
            requestAnimationFrame(() => {
                resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }
    }, [state]);

    const handleNewAnalysis = () => {
        setShowConfirm(false);
        resetAnalysis();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="w-full" ref={topRef}>
            <motion.div 
                initial={{ opacity: 0, y: 20 }} 
                animate={{ opacity: 1, y: 0 }} 
                transition={{ duration: 0.5 }}
                className="pb-12"
            >
                <Hero />
                <AnalysisForm />
            </motion.div>

            <div ref={resultsRef} className="scroll-mt-8">
                <AnimatePresence mode="wait">
                    {state === 'LOADING' && (
                        <motion.div 
                            key="loading" 
                            initial={{ opacity: 0, scale: 0.95, y: 20 }} 
                            animate={{ opacity: 1, scale: 1, y: 0 }} 
                            exit={{ opacity: 0, scale: 1.05, y: -20, transition: { duration: 0.3 } }} 
                            className="flex flex-col items-center justify-center py-20 space-y-8"
                        >
                            <NeuralLoader progress={progress} message={progressMsg} />
                        </motion.div>
                    )}

                    {state === 'RESULTS' && results && (
                        <motion.div 
                            key="results" 
                            initial={{ opacity: 0, y: 40 }} 
                            animate={{ opacity: 1, y: 0 }} 
                            transition={{ duration: 0.6, staggerChildren: 0.2 }} 
                            className="w-full pb-24"
                        >
                            <div className="flex justify-between items-center mb-8 border-t border-gray-200 dark:border-gray-800 pt-12">
                                <h1 className="text-3xl font-extrabold text-gray-900 dark:text-white flex items-center gap-3">
                                    Analysis Results
                                </h1>
                                <Button onClick={() => setShowConfirm(true)} variant="outline" size="sm">
                                    <RefreshCcw className="w-4 h-4 mr-2" /> New Analysis
                                </Button>
                            </div>

                            {results.status === 'domain_mismatch' ? (
                                <DomainMismatchCard result={results} />
                            ) : (
                                <>
                                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
                                        <div className="lg:col-span-4 space-y-8 sticky top-8 self-start">
                                            <ScoreCard score={results.overallScore || results.overall_score} breakdown={results.scoreBreakdown || results.score_breakdown} />
                                            <SkillGapList gaps={results.skillGaps || results.skill_gaps} />
                                            <StrengthList strengths={results.strengths} />
                                        </div>

                                        <div className="lg:col-span-8 space-y-8">
                                            <ExecutiveSummary summary={results.executiveSummary || results.executive_summary} />
                                            <FrictionVisualization points={results.frictionPoints || results.friction_points} />
                                            <ATSOptimizationTips tips={results.atsOptimization || results.atsOptimizationTips || results.ats_optimization} />
                                            <SeniorityAlignment alignment={results.seniorityAnalysis || results.seniorityAlignment || results.seniority_analysis} />
                                        </div>
                                    </div>
                                    
                                    <div className="w-full">
                                        {results.perfectMatch ? (
                                            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-4">
                                                <Award className="w-12 h-12 text-emerald-400" />
                                                <h3 className="text-xl font-bold text-emerald-400">Perfect Match</h3>
                                                <p className="text-zinc-400 max-w-lg">
                                                    You are a perfect match for this role! No upskilling roadmap is necessary.
                                                </p>
                                            </div>
                                        ) : (
                                            <RoadmapDisplay roadmap={results.roadmap} />
                                        )}
                                    </div>
                                </>
                            )}
                        </motion.div>
                    )}

                    {state === 'ERROR' && (
                        <motion.div 
                            key="error" 
                            initial={{ opacity: 0 }} 
                            animate={{ opacity: 1 }} 
                            className="flex flex-col items-center justify-center py-20 space-y-6"
                        >
                            <div className="text-red-500 flex items-center justify-center p-4 bg-red-100/10 rounded-full">
                                <AlertTriangle className="w-16 h-16 text-red-500" />
                            </div>
                            <h2 className="text-2xl font-bold">Something went wrong</h2>
                            <p className="text-gray-500">We couldn't complete the analysis. Please try again.</p>
                            <Button onClick={() => submitAnalysis(true)}>Try Again</Button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            <ConfirmModal
                isOpen={showConfirm}
                onClose={() => setShowConfirm(false)}
                onConfirm={handleNewAnalysis}
                title="Start New Analysis?"
                message="This will clear your current results and reset the AI cache. You will need to enter your details again."
            />
        </div>
    );
}
