// frontend/src/lib/api-client.js

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
                errorMsg = error.detail || errorMsg;
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
    resetCache: async () => {
        const response = await fetch(`${API_BASE}/api/v1/cache/reset`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            console.error('Failed to reset cache');
        }
    },
    analyzeStream: async (data, onProgress) => {
        const response = await fetch(`${API_BASE}/api/v1/analyze/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
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
                errorMsg = error.detail || errorMsg;
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let finalResult = null;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            const lines = buffer.split('\n');
            // Keep the last partial line in the buffer
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
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
                        console.error("Failed to parse SSE line", e);
                    }
                }
            }
        }
        
        if (!finalResult) {
            throw new Error("Analysis failed: Stream ended without result.");
        }
        
        return finalResult;
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
                errorMsg = error.detail || errorMsg;
            } catch (e) {
                // Ignore parse error
            }
            throw new Error(errorMsg);
        }

        return await response.json();
    }
};
