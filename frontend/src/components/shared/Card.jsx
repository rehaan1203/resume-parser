'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../utils/cn';
export const Card = React.forwardRef(({ className, hoverLift = true, children, ...props }, ref) => {
    return (<motion.div ref={ref} whileHover={hoverLift ? { y: -4 } : {}} className={cn('rounded-xl border border-gray-200 bg-white/50 backdrop-blur-sm p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900/50', hoverLift && 'transition-shadow hover:shadow-md dark:hover:shadow-gray-800', className)} {...props}>
        {children}
      </motion.div>);
});
Card.displayName = 'Card';
