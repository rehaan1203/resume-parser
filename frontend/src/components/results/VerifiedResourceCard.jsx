'use client';
import React from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Clock, BookOpen, Video, Award, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export const VerifiedResourceCard = ({ resource, className }) => {
    if (!resource) return null;

    // Lightweight non-blocking click telemetry
    const trackClick = () => {
        try {
            const isStr = typeof resource === 'string';
            const payload = JSON.stringify({
                resource_id: isStr ? undefined : resource.id,
                resource_url: isStr ? (resource.startsWith('http') ? resource : `https://google.com/search?q=${encodeURIComponent(resource)}`) : (resource.url || '#'),
                title: isStr ? resource : (resource.title || 'Verified Resource'),
                domain: isStr ? undefined : (resource.domain || 'tech'),
                source: 'roadmap_card'
            });

            const endpoint = '/api/v1/telemetry/resource-click';
            if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
                const blob = new Blob([payload], { type: 'application/json' });
                navigator.sendBeacon(endpoint, blob);
            } else if (typeof fetch !== 'undefined') {
                fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: payload,
                    keepalive: true
                }).catch(() => {});
            }
        } catch {
            // Non-blocking
        }
    };

    // Handle case where resource is just a plain URL or string
    if (typeof resource === 'string') {
        const isUrl = resource.startsWith('http');
        const href = isUrl ? resource : `https://google.com/search?q=${encodeURIComponent(resource)}`;
        const isVideo = resource.includes('youtube.com') || resource.includes('youtu.be') || resource.includes('vimeo');
        return (
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                onClick={trackClick}
                className={cn(
                    "inline-flex items-center text-xs px-2.5 py-1.5 bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800/80 dark:hover:bg-zinc-700/80 text-zinc-800 dark:text-zinc-200 rounded-md transition-colors border border-zinc-200 dark:border-zinc-700 font-medium group",
                    className
                )}
            >
                {isVideo ? (
                    <Video className="w-3.5 h-3.5 mr-1.5 text-red-500 shrink-0" />
                ) : (
                    <BookOpen className="w-3.5 h-3.5 mr-1.5 text-blue-500 shrink-0" />
                )}
                <span className="truncate max-w-[200px]">{resource.replace(/^https?:\/\/(www\.)?/, '')}</span>
                <ExternalLink className="w-3 h-3 ml-1.5 opacity-60 group-hover:opacity-100 transition-opacity" />
            </a>
        );
    }

    const {
        title = 'Verified Resource',
        url = '#',
        active_timestamp_url,
        matched_chapter,
        publication_year,
        platform = 'Resource',
        type = 'course',
        duration_hours,
        difficulty,
        is_free = true
    } = resource;

    const targetUrl = active_timestamp_url || url;

    // Icon mapping based on resource type
    const getIcon = () => {
        switch (type?.toLowerCase()) {
            case 'youtube_video':
            case 'video':
                return <Video className="w-3.5 h-3.5 text-red-500" />;
            case 'certification':
                return <Award className="w-3.5 h-3.5 text-amber-500" />;
            default:
                return <BookOpen className="w-3.5 h-3.5 text-blue-500" />;
        }
    };

    return (
        <motion.div
            whileHover={{ y: -2, transition: { duration: 0.15 } }}
            className={cn(
                "group relative flex flex-col justify-between p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800/80 bg-white/60 dark:bg-zinc-900/60 backdrop-blur-sm shadow-sm hover:shadow-md hover:border-zinc-300 dark:hover:border-zinc-700 transition-all",
                className
            )}
        >
            <div>
                {/* Header: Platform & Verified Badge */}
                <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200/60 dark:border-zinc-700/60">
                        {getIcon()}
                        {platform}
                    </span>

                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                        <ShieldCheck className="w-3 h-3" />
                        Verified
                    </span>
                </div>

                {/* Title */}
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors line-clamp-2">
                    {title}
                </h4>

                {/* Chapter Deep-Link Badge */}
                {matched_chapter && (
                    <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-900/50 flex items-center gap-1">
                        <span className="font-semibold">⏱️ Chapter:</span>
                        <span className="truncate">{matched_chapter}</span>
                    </div>
                )}
            </div>

            {/* Footer: Metadata & Direct Action */}
            <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-zinc-100 dark:border-zinc-800/60 text-xs text-zinc-500 dark:text-zinc-400">
                <div className="flex items-center gap-2.5">
                    {duration_hours && (
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {duration_hours}h
                        </span>
                    )}
                    {is_free && (
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">Free</span>
                    )}
                    {publication_year && (
                        <span className="text-zinc-400 font-mono text-[10px]">{publication_year}</span>
                    )}
                    {difficulty && (
                        <span className="capitalize">{difficulty}</span>
                    )}
                </div>

                <a
                    href={targetUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={trackClick}
                    className="inline-flex items-center gap-1 font-semibold text-zinc-700 dark:text-zinc-300 hover:text-amber-600 dark:hover:text-amber-400 transition-colors"
                >
                    Learn
                    <ExternalLink className="w-3 h-3 ml-0.5" />
                </a>
            </div>
        </motion.div>
    );
};

