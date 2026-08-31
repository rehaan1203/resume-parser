'use client';
import React from 'react';
import { motion } from 'framer-motion';

export const Hero = () => {
    return (
        <div className="text-center py-16 px-4 sm:px-6 lg:px-8">
            <motion.div 
                initial={{ opacity: 0, y: 30, filter: "blur(10px)" }} 
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} 
                transition={{ duration: 0.8, type: "spring", bounce: 0.4 }} 
                className="max-w-4xl mx-auto"
            >

                <h1 className="text-5xl sm:text-7xl font-semibold tracking-tighter text-zinc-900 dark:text-zinc-50 mb-6 leading-[1.1]">
                    Bridge the gap to your <br className="hidden sm:block"/>
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-zinc-500 to-zinc-900 dark:from-zinc-100 dark:to-zinc-500">
                        dream role.
                    </span>
                </h1>
                
                <p className="text-lg sm:text-xl text-zinc-500 dark:text-zinc-400 max-w-2xl mx-auto leading-relaxed">
                    Instantly analyze semantic friction between your resume and job description. Get a tailored, actionable roadmap to land the interview.
                </p>
            </motion.div>
        </div>
    );
};
