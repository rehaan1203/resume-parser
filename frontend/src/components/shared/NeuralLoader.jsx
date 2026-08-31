import React, { useState, useEffect } from 'react';
import { motion, animate } from 'framer-motion';

export const NeuralLoader = ({ progress = 0, message = "" }) => {
    const statusText = message || "Initializing...";
    const [displayProgress, setDisplayProgress] = useState(0);

    useEffect(() => {
        const controls = animate(displayProgress, progress, {
            duration: 1.5,
            ease: "easeOut",
            onUpdate: (value) => setDisplayProgress(value)
        });
        return () => controls.stop();
    }, [progress]);

    // Complex arrangement of 8 Orbital Nodes
    const core = { x: 100, y: 100 };
    const orbitals = [
        { x: 100, y: 15, size: 6, delay: 0 },
        { x: 160, y: 40, size: 8, delay: 0.2 },
        { x: 185, y: 100, size: 5, delay: 0.4 },
        { x: 160, y: 160, size: 7, delay: 0.6 },
        { x: 100, y: 185, size: 9, delay: 0.8 },
        { x: 40, y: 160, size: 6, delay: 1.0 },
        { x: 15, y: 100, size: 8, delay: 1.2 },
        { x: 40, y: 40, size: 5, delay: 1.4 },
    ];

    // Determine how many nodes are fully 'active' based on progress
    // Ensure at least index 0 is active at the start
    const activeIndex = Math.max(0, Math.floor((progress / 100) * (orbitals.length - 1)));

    return (
        <div className="flex flex-col items-center justify-center space-y-12 w-full py-8">
            <div className="relative w-64 h-64 flex items-center justify-center">
                
                {/* Ambient glowing background aura */}
                <motion.div 
                    className="absolute inset-0 bg-zinc-200/50 dark:bg-zinc-800/30 rounded-full blur-3xl"
                    animate={{
                        scale: [1, 1.2, 1],
                        opacity: [0.2, 0.5, 0.2],
                    }}
                    transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                />

                <motion.svg 
                    viewBox="0 0 200 200" 
                    className="w-full h-full overflow-visible relative z-10"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
                >
                    <defs>
                        {/* Dynamic Gradients for monochrome minimal style */}
                        <linearGradient id="coreGrad" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="currentColor" className="text-cyan-400 dark:text-zinc-500" />
                            <stop offset="100%" stopColor="currentColor" className="text-cyan-600 dark:text-zinc-300" />
                        </linearGradient>
                        <linearGradient id="activeLineGrad" x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stopColor="currentColor" className="text-cyan-400 dark:text-zinc-400" stopOpacity="0.8" />
                            <stop offset="100%" stopColor="currentColor" className="text-cyan-600 dark:text-zinc-200" stopOpacity="0.8" />
                        </linearGradient>
                        
                        {/* High-quality glow filter */}
                        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur stdDeviation="3.5" result="blur" />
                            <feComposite in="SourceGraphic" in2="blur" operator="over" />
                        </filter>
                    </defs>

                    {/* Outer Connecting Ring (Dashed, rotating) */}
                    {orbitals.map((node, i) => {
                        const nextNode = orbitals[(i + 1) % orbitals.length];
                        const isActive = i <= activeIndex;
                        return (
                            <motion.line
                                key={`ring-${i}`}
                                x1={node.x} y1={node.y}
                                x2={nextNode.x} y2={nextNode.y}
                                stroke="url(#activeLineGrad)"
                                strokeWidth="1.5"
                                opacity={0.8}
                                strokeDasharray="4 4"
                                animate={{ strokeDashoffset: [0, -24] }}
                                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                            />
                        );
                    })}

                    {/* Connections from Core to Orbitals with Data Particles */}
                    {orbitals.map((node, i) => {
                        const isActive = i <= activeIndex;
                        
                        return (
                            <g key={`connection-${i}`}>
                                <motion.line
                                    x1={core.x} y1={core.y}
                                    x2={node.x} y2={node.y}
                                    stroke="url(#activeLineGrad)"
                                    strokeWidth={1.5}
                                    opacity={0.8}
                                />
                                
                                {/* Flowing Data Particle (Only if path is active) */}
                                {isActive && (
                                    <motion.circle
                                        r="2.5"
                                        fill="currentColor"
                                        className="text-cyan-500 dark:text-white"
                                        filter="url(#glow)"
                                        animate={{
                                            cx: [core.x, node.x],
                                            cy: [core.y, node.y],
                                            opacity: [0, 1, 0]
                                        }}
                                        transition={{
                                            duration: 1.5 + (i * 0.1),
                                            repeat: Infinity,
                                            ease: "easeOut",
                                            delay: node.delay
                                        }}
                                    />
                                )}
                            </g>
                        );
                    })}

                    {/* Orbital Nodes */}
                    {orbitals.map((node, i) => {
                        const isActive = i <= activeIndex;
                        return (
                            <motion.circle
                                key={`node-${i}`}
                                cx={node.x} cy={node.y} r={node.size}
                                className="fill-cyan-500 dark:fill-zinc-300"
                                filter={isActive ? "url(#glow)" : ""}
                                opacity={isActive ? 1 : 0.25}
                                animate={isActive ? { scale: [1, 1.4, 1] } : {}}
                                transition={{ duration: 2, repeat: Infinity, delay: node.delay }}
                            />
                        );
                    })}

                    {/* Central Core Element */}
                    <motion.circle
                        cx={core.x} cy={core.y} r="18"
                        fill="url(#coreGrad)"
                        filter="url(#glow)"
                        animate={{ scale: [1, 1.15, 1] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    />
                    
                    {/* Intense Inner Core Pulse */}
                    <motion.circle
                        cx={core.x} cy={core.y} r="8"
                        fill="currentColor"
                        className="text-cyan-500 dark:text-white"
                        animate={{
                            opacity: [0.6, 1, 0.6],
                            scale: [0.8, 1.3, 0.8]
                        }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                    />
                </motion.svg>
            </div>

            <div className="w-full max-w-md space-y-6 text-center relative z-20">
                
                {/* Glowing Animated Progress Bar */}
                <div className="relative w-full h-1.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden shadow-inner">
                    <motion.div 
                        className="absolute top-0 left-0 h-full bg-cyan-500 dark:bg-zinc-100 rounded-full"
                        animate={{ width: `${Math.max(2, progress)}%` }}
                        transition={{ duration: 1.5, ease: 'easeOut' }}
                    />
                </div>
                
                {/* Subtitle pulse */}
                <motion.div 
                    className="flex justify-center"
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 2.5, repeat: Infinity }}
                >
                    <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 tracking-widest uppercase tabular-nums">
                        {Math.round(displayProgress)}% COMPLETED
                    </span>
                </motion.div>
            </div>
        </div>
    );
};
