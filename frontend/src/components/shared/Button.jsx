'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';
export const Button = React.forwardRef(({ className, variant = 'primary', size = 'md', isLoading = false, children, disabled, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center rounded-lg font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 disabled:pointer-events-none disabled:opacity-50';
    const variants = {
        primary: 'bg-zinc-900 text-zinc-50 hover:bg-zinc-800 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 shadow-sm',
        secondary: 'bg-zinc-100 text-zinc-900 hover:bg-zinc-200 dark:bg-zinc-800/50 dark:text-zinc-100 dark:hover:bg-zinc-800',
        outline: 'border border-zinc-200 bg-transparent hover:bg-zinc-100 text-zinc-900 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-900',
        ghost: 'bg-transparent hover:bg-zinc-100 text-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-900',
    };
    const sizes = {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4 py-2 text-sm',
        lg: 'h-12 px-8 text-base',
    };
    return (<motion.button ref={ref} whileTap={{ scale: 0.95 }} whileHover={!disabled && !isLoading ? { y: -2 } : {}} className={cn(baseStyles, variants[variant], sizes[size], className)} disabled={disabled || isLoading} {...props}>
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin"/>}
        {children}
      </motion.button>);
});
Button.displayName = 'Button';
