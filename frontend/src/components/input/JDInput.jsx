'use client';
import React, { useState } from 'react';
import { Briefcase, Link as LinkIcon, FileText } from 'lucide-react';
import { Card } from '../shared/Card';
import { Button } from '../shared/Button';
import { cn } from '../../utils/cn';
export const JDInput = ({ jdText, jdUrl, onTextChange, onUrlChange, error }) => {
    const [activeTab, setActiveTab] = useState('text');
    const [isFocused, setIsFocused] = useState(false);
    const [isFetching, setIsFetching] = useState(false);
    const handleFetchUrl = async () => {
        if (!jdUrl)
            return;
        setIsFetching(true);
        // Mock fetch delay
        setTimeout(() => {
            onTextChange("Mock fetched job description from " + jdUrl + "\n\nRequirements:\n- Python\n- Docker\n- Kubernetes");
            setActiveTab('text');
            setIsFetching(false);
        }, 1500);
    };
    return (<Card className={cn("relative overflow-hidden flex flex-col h-full transition-all duration-300", isFocused && "ring-2 ring-zinc-900 dark:ring-zinc-50 border-transparent")}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
          <Briefcase className="w-5 h-5 text-zinc-700 dark:text-zinc-300"/>
          Job Description
        </h2>
        
        <div className="flex bg-zinc-100 dark:bg-zinc-900 rounded-md p-1 shadow-inner">
          <button onClick={() => setActiveTab('text')} className={cn("px-3 py-1 text-xs font-medium rounded-sm transition-all", activeTab === 'text' ? "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50 shadow-sm" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300")}>
            <FileText className="w-3 h-3 inline mr-1"/> Text
          </button>
          <button onClick={() => setActiveTab('url')} className={cn("px-3 py-1 text-xs font-medium rounded-sm transition-all", activeTab === 'url' ? "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50 shadow-sm" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300")}>
            <LinkIcon className="w-3 h-3 inline mr-1"/> URL
          </button>
        </div>
      </div>

      <div className="flex-1 relative">
        {activeTab === 'text' ? (<textarea value={jdText} onChange={(e) => onTextChange(e.target.value)} onFocus={() => setIsFocused(true)} onBlur={() => setIsFocused(false)} placeholder="Paste the job description here..." className="w-full h-64 p-5 text-sm bg-zinc-50/50 dark:bg-[#09090b]/50 border border-zinc-200 dark:border-zinc-800 rounded-lg resize-none focus:outline-none transition-colors shadow-inner"/>) : (<div className="w-full h-64 flex flex-col justify-center items-center space-y-4 border border-zinc-200 dark:border-zinc-800 rounded-lg p-6 bg-zinc-50/50 dark:bg-[#09090b]/50">
            <div className="w-full max-w-sm">
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Job Posting URL</label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input type="url" value={jdUrl} onChange={(e) => onUrlChange(e.target.value)} placeholder="https://linkedin.com/jobs/..." className="flex-1 rounded-md border-zinc-300 dark:border-zinc-700 bg-white dark:bg-[#09090b] px-3 py-2 text-sm focus:ring-2 focus:ring-zinc-900 dark:focus:ring-zinc-50 focus:outline-none transition-all"/>
                <Button onClick={handleFetchUrl} isLoading={isFetching} disabled={!jdUrl} size="sm">
                  Fetch JD
                </Button>
              </div>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 text-center">
              Our AI will visit the URL and extract the job requirements.
            </p>
          </div>)}
      </div>

      <div className="mt-2 flex justify-between items-center text-xs">
        <span className={cn(error ? "text-red-500" : "text-gray-500")}>
          {error || ' '}
        </span>
        {activeTab === 'text' && (<span className={cn("font-medium", jdText.length > 10000 ? "text-red-500" : "text-gray-400")}>
            {jdText.length}/10000
          </span>)}
      </div>
    </Card>);
};
