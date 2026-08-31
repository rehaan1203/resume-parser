'use client';
import React, { createContext, useContext, useState } from 'react';
import { api } from '../lib/api-client';
const AnalysisContext = createContext(undefined);
export const AnalysisProvider = ({ children }) => {
    const [state, setState] = useState('IDLE');
    const [formData, setFormData] = useState({ resume: '', jdText: '', jdUrl: '' });
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);
    const [hasUnanalyzedChanges, setHasUnanalyzedChanges] = useState(true);
    const [progress, setProgress] = useState(0);
    const [progressMsg, setProgressMsg] = useState("");
    const updateForm = (data) => {
        setFormData(prev => ({ ...prev, ...data }));
        setHasUnanalyzedChanges(true);
    };
    const submitAnalysis = async (forceFresh = false) => {
        setState('LOADING');
        setError(null);
        setProgress(0);
        setProgressMsg("");
        setHasUnanalyzedChanges(false);
        
        // Yield to the event loop so the UI updates to 'LOADING' immediately
        await new Promise(resolve => setTimeout(resolve, 0));

        try {
            if (forceFresh) {
                try {
                    await api.resetCache();
                } catch (e) {
                    console.error("Failed to reset cache", e);
                }
            }
            const res = await api.analyzeStream(formData, (prog, msg) => {
                setProgress(prog);
                setProgressMsg(msg);
            });
            setResults(res);
            setProgress(100);
            setState('RESULTS');
        }
        catch (err) {
            setError(err.message || 'An error occurred during analysis.');
            setState('ERROR');
            setHasUnanalyzedChanges(true); // Re-enable so they can try again on error
        }
    };
    const resetAnalysis = () => {
        setFormData({ resume: '', jdText: '', jdUrl: '' });
        setResults(null);
        setError(null);
        setState('IDLE');
        setHasUnanalyzedChanges(true);
        
        // Reset cache in the background without blocking UI
        api.resetCache().catch(e => console.error(e));
    };
    return (<AnalysisContext.Provider value={{ state, formData, results, setResults, error, updateForm, submitAnalysis, resetAnalysis, hasUnanalyzedChanges, progress, progressMsg }}>
      {children}
    </AnalysisContext.Provider>);
};
export const useAnalysisContext = () => {
    const context = useContext(AnalysisContext);
    if (context === undefined) {
        throw new Error('useAnalysisContext must be used within an AnalysisProvider');
    }
    return context;
};
