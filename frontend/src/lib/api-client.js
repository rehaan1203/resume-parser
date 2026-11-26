// frontend/src/lib/api-client.js

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function extractErrorMessage(error, fallback = 'Analysis failed') {
    if (!error) return fallback;
    if (typeof error === 'string') return error;
    if (Array.isArray(error.detail)) {
        return error.detail.map(d => {
            const field = Array.isArray(d.loc) ? d.loc.filter(k => k !== 'body').join('.') : '';
            return field ? `${field}: ${d.msg}` : d.msg;
        }).join('; ');
    }
    if (typeof error.detail === 'string') return error.detail;
    if (error.message) return error.message;
    return fallback;
}

export const api = {
    analyze: async (data) => {
        // data contains: { resume, jdText, jdUrl, includeRoadmap }
        // Send to backend with camelCase (Pydantic handles conversion)
        
        const response = await fetch(`${API_BASE}/api/v1/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                resume: data.resume,
                jdText: data.jdText,      // camelCase - accepted via alias
                jdUrl: data.jdUrl,        // camelCase - accepted via alias
                includeRoadmap: data.includeRoadmap !== undefined ? data.includeRoadmap : true,
            }),
        });

        if (!response.ok) {
            let errorMsg = 'Analysis failed';
            try {
                const error = await response.json();
                errorMsg = extractErrorMessage(error, errorMsg);
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }

        const result = await response.json();
        
        // Backend returns camelCase due to populate_by_name=True
        // Matches frontend expectations: overallScore, frictionPoints, etc.
        return result;
    },
    uploadResume: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/api/v1/upload/resume`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            let errorMsg = 'Failed to upload and parse resume PDF';
            try {
                const error = await response.json();
                errorMsg = extractErrorMessage(error, errorMsg);
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }
        return await response.json();
    },
    fetchJdFromUrl: async (url) => {
        const response = await fetch(`${API_BASE}/api/v1/upload/jd?url=${encodeURIComponent(url)}`, {
            method: 'POST',
        });
        if (!response.ok) {
            let errorMsg = 'Failed to extract job description from URL';
            try {
                const error = await response.json();
                errorMsg = extractErrorMessage(error, errorMsg);
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }
        return await response.json();
    },
    resetCache: async () => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/cache/reset`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                // Non-blocking if admin key required in prod
            }
        } catch (e) {
            // Ignore network or admin header notice on local reset
        }
    },
    analyzeStream: async (data, onProgress) => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000);

        try {
            const response = await fetch(`${API_BASE}/api/v1/analyze/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                signal: controller.signal,
                body: JSON.stringify({
                    resume: data.resume,
                    jdText: data.jdText,
                    jdUrl: data.jdUrl,
                    includeRoadmap: data.includeRoadmap !== undefined ? data.includeRoadmap : true,
                }),
            });

            if (!response.ok) {
                let errorMsg = 'Analysis failed';
                try {
                    const error = await response.json();
                    errorMsg = extractErrorMessage(error, errorMsg);
                } catch (e) {
                    // Ignore parse error
                }
                throw new Error(errorMsg);
            }

            if (!response.body) {
                throw new Error('Streaming response body unavailable.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";
            let finalResult = null;

            const processLine = (line) => {
                if (!line.startsWith('data: ')) return;
                try {
                    const eventData = JSON.parse(line.slice(6));
                    if (eventData.type === 'progress') {
                        if (onProgress) {
                            onProgress(eventData.progress, eventData.message);
                        }
                    } else if (eventData.type === 'complete') {
                        finalResult = eventData.result;
                    } else if (eventData.type === 'error') {
                        throw new Error(eventData.message);
                    }
                } catch (e) {
                    if (e instanceof SyntaxError) {
                        console.error("Failed to parse SSE line", e);
                    } else {
                        throw e;
                    }
                }
            };

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || "";

                for (const line of lines) {
                    processLine(line);
                }
            }

            if (buffer.trim()) {
                processLine(buffer.trim());
            }

            if (!finalResult) {
                throw new Error("Analysis failed: Stream ended without result.");
            }

            return finalResult;
        } catch (err) {
            if (err?.name === 'AbortError') {
                throw new Error('Analysis request timed out. Please try again.');
            }
            throw err;
        } finally {
            clearTimeout(timeoutId);
        }
    },
    transitionPlan: async (data) => {
        const response = await fetch(`${API_BASE}/api/v1/transition-plan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            let errorMsg = 'Failed to generate transition plan.';
            try {
                const error = await response.json();
                errorMsg = extractErrorMessage(error, errorMsg);
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }

        return await response.json();
    }
};
