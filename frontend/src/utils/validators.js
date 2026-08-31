export const isValidUrl = (urlString) => {
    try {
        return Boolean(new URL(urlString));
    }
    catch (e) {
        return false;
    }
};
export const validateResumeLength = (text) => {
    if (text.length < 100)
        return 'Resume must be at least 100 characters long.';
    if (text.length > 10000)
        return 'Resume cannot exceed 10,000 characters.';
    return null;
};
