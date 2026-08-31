export const truncateText = (text, maxLength = 100) => {
    if (text.length <= maxLength)
        return text;
    return text.slice(0, maxLength) + '...';
};
export const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
};
