'use client';
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sun, Moon } from 'lucide-react';

const MatcherLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="4" y="4" width="14" height="14" rx="4" fill="currentColor" className="text-blue-500/80 dark:text-blue-400/80" />
    <rect x="10" y="10" width="14" height="14" rx="4" fill="url(#gradient_logo)" className="drop-shadow-lg" />
    <path d="M11 11L17 17" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-50" />
    <defs>
      <linearGradient id="gradient_logo" x1="10" y1="10" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop stopColor="#6366F1" />
        <stop offset="1" stopColor="#A855F7" />
      </linearGradient>
    </defs>
  </svg>
);

export const Header = () => {
    const [isDark, setIsDark] = useState(false);
    useEffect(() => {
        if (document.documentElement.classList.contains('dark') ||
            window.matchMedia('(prefers-color-scheme: dark)').matches) {
            setIsDark(true);
            document.documentElement.classList.add('dark');
        }
    }, []);
    const toggleDark = () => {
        setIsDark(!isDark);
        document.documentElement.classList.toggle('dark');
    };
    return (
      <header className="sticky top-0 z-50 w-full backdrop-blur-xl bg-white/70 dark:bg-[#09090b]/70 border-b border-zinc-200 dark:border-zinc-800 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          
          <motion.div className="flex items-center gap-3 cursor-pointer" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <MatcherLogo />
            <span className="font-extrabold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-zinc-900 to-zinc-600 dark:from-white dark:to-zinc-400">
              Friction Matcher
            </span>
          </motion.div>

          <motion.button 
            onClick={toggleDark} 
            whileHover={{ scale: 1.1, rotate: 15 }}
            whileTap={{ scale: 0.9 }}
            className="p-2.5 rounded-full bg-zinc-100 dark:bg-zinc-800/50 hover:bg-zinc-200 dark:hover:bg-zinc-700/50 border border-transparent dark:border-zinc-800 transition-colors" 
            aria-label="Toggle dark mode"
          >
            {isDark ? <Sun className="w-4 h-4 text-yellow-500"/> : <Moon className="w-4 h-4 text-zinc-700"/>}
          </motion.button>
        </div>
      </header>
    );
};
