'use client';
import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, Upload, Clipboard } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '../shared/Card';
import { Button } from '../shared/Button';
import { cn } from '../../utils/cn';
export const ResumeInput = ({ value, onChange, error }) => {
    const [isFocused, setIsFocused] = useState(false);
    const onDrop = useCallback(async (acceptedFiles) => {
        let combinedText = '';
        for (const file of acceptedFiles) {
            if (file.name.endsWith('.pdf')) {
                combinedText += `\n--- ${file.name} ---\n[PDF Content Mock: ${file.name}]\n`;
            } else {
                const text = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = (e) => resolve(e.target?.result);
                    reader.readAsText(file);
                });
                if (typeof text === 'string') {
                    combinedText += `\n--- ${file.name} ---\n${text}\n`;
                }
            }
        }
        if (combinedText) {
            onChange(combinedText.trim());
        }
    }, [onChange]);
    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'text/plain': ['.txt'],
            'application/pdf': ['.pdf']
        }
    });
    const handlePasteFromClipboard = async () => {
        try {
            const text = await navigator.clipboard.readText();
            onChange(text);
        }
        catch (err) {
            console.error('Failed to read clipboard', err);
        }
    };
    
    const handleFileUpload = async (e) => {
        const files = Array.from(e.target.files || []);
        let combinedText = '';
        for (const file of files) {
            if (file.name.endsWith('.pdf')) {
                combinedText += `\n--- ${file.name} ---\n[PDF Content Mock: ${file.name}]\n`;
            } else {
                const text = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = (ev) => resolve(ev.target?.result);
                    reader.readAsText(file);
                });
                if (typeof text === 'string') {
                    combinedText += `\n--- ${file.name} ---\n${text}\n`;
                }
            }
        }
        if (combinedText) {
            const currentVal = value ? value + '\n' : '';
            onChange((currentVal + combinedText).trim());
        }
        e.target.value = '';
    };

    return (<Card className={cn("relative overflow-hidden transition-all duration-300", (isFocused || isDragActive) && "ring-2 ring-zinc-900 dark:ring-zinc-50 border-transparent")}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
          <FileText className="w-5 h-5 text-zinc-700 dark:text-zinc-300"/>
          Resume
        </h2>
        <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={handlePasteFromClipboard} className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
            <Clipboard className="w-4 h-4 mr-2"/>
            Paste
            </Button>
        </div>
      </div>

      <div {...getRootProps()} className="relative">
        <input {...getInputProps()}/>
        <textarea value={value} onChange={(e) => onChange(e.target.value)} onFocus={() => setIsFocused(true)} onBlur={() => setIsFocused(false)} placeholder="Paste your resume here, or drag & drop .txt/.pdf files..." className="w-full h-64 p-5 text-sm bg-zinc-50/50 dark:bg-[#09090b]/50 border border-zinc-200 dark:border-zinc-800 rounded-lg resize-none focus:outline-none z-10 relative transition-colors shadow-inner" onClick={(e) => e.stopPropagation()} 
    />

        <AnimatePresence>
          {isDragActive && (<motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-zinc-100/90 dark:bg-zinc-900/90 backdrop-blur-md rounded-lg border-2 border-dashed border-zinc-900 dark:border-zinc-50 flex flex-col items-center justify-center z-20 pointer-events-none">
              <Upload className="w-8 h-8 text-zinc-800 dark:text-zinc-200 mb-2 animate-bounce"/>
              <p className="text-zinc-800 dark:text-zinc-200 font-medium">Drop file here</p>
            </motion.div>)}
        </AnimatePresence>
      </div>

      <div className="mt-2 flex justify-between items-center text-xs">
        <span className={cn(error ? "text-red-500" : "text-gray-500")}>
          {error || 'Supports pasting text or uploading .txt / .pdf files'}
        </span>
        <span className={cn("font-medium", value.length > 10000 ? "text-red-500" : "text-gray-400")}>
          {value.length}/10000
        </span>
      </div>
    </Card>);
};
