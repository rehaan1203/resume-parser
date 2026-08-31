'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { ResumeInput } from './ResumeInput';
import { JDInput } from './JDInput';
import { Button } from '../shared/Button';
import { useAnalysisContext } from '../../context/AnalysisContext';
import { api } from '../../lib/api-client';

export const AnalysisForm = () => {
    const { formData, updateForm, submitAnalysis, state, hasUnanalyzedChanges } = useAnalysisContext();
    const [forceFresh, setForceFresh] = React.useState(false);
    
    const isFormValid = formData.resume.length >= 100 && (formData.jdText?.length >= 100 || formData.jdUrl?.length > 5);
    const isAnalyzing = state === 'LOADING';
    const isReadyToAnalyze = isFormValid && !isAnalyzing && hasUnanalyzedChanges;

    const handleAnalyzeClick = () => {
        if (isReadyToAnalyze) {
            submitAnalysis(forceFresh);
        }
    };
    return (<div className="flex flex-col space-y-8 max-w-6xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResumeInput value={formData.resume} onChange={(val) => updateForm({ resume: val })}/>
        <JDInput jdText={formData.jdText || ''} jdUrl={formData.jdUrl || ''} onTextChange={(val) => updateForm({ jdText: val })} onUrlChange={(val) => updateForm({ jdUrl: val })}/>
      </div>

      <div className="flex flex-col items-center pt-4 space-y-4">
        <motion.div 
            animate={isReadyToAnalyze ? { scale: [1, 1.02, 1] } : {}} 
            transition={isReadyToAnalyze ? { repeat: Infinity, duration: 3, ease: "easeInOut" } : {}} 
            className="rounded-full"
        >
          <Button size="lg" onClick={handleAnalyzeClick} disabled={!isReadyToAnalyze} isLoading={isAnalyzing} className="rounded-full px-10 py-7 text-lg font-medium bg-zinc-900 dark:bg-zinc-50 text-white dark:text-zinc-900 hover:scale-[1.02] active:scale-[0.98] transition-transform shadow-lg hover:shadow-xl">
            {!isAnalyzing && <Sparkles className="w-5 h-5 mr-3"/>}
            {isAnalyzing ? 'Analyzing Match...' : 'Analyze Match'}
          </Button>
        </motion.div>
        
        <label className="flex items-center space-x-2 text-sm text-zinc-600 dark:text-zinc-400 cursor-pointer">
          <input 
            type="checkbox" 
            checked={forceFresh} 
            onChange={(e) => setForceFresh(e.target.checked)}
            className="rounded border-zinc-300 dark:border-zinc-700 text-zinc-900 dark:text-zinc-50 focus:ring-zinc-900 dark:focus:ring-zinc-50"
          />
          <span>Force fresh analysis (ignore cache)</span>
        </label>
      </div>
    </div>);
};
