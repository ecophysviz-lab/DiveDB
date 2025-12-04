window.dccFunctions = window.dccFunctions || {};
window.dccFunctions.formatTimestamp = function(value) {
    if (typeof value !== "number" || isNaN(value)) return "";
    
    // Convert Unix timestamp (seconds) to Date object
    // Handle fractional seconds for millisecond precision
    const dateObject = new Date(value * 1000);
    
    const year = dateObject.getUTCFullYear();
    const month = (dateObject.getUTCMonth() + 1).toString().padStart(2, '0');
    const day = dateObject.getUTCDate().toString().padStart(2, '0');
    const hours = dateObject.getUTCHours().toString().padStart(2, '0');
    const minutes = dateObject.getUTCMinutes().toString().padStart(2, '0');
    const seconds = dateObject.getUTCSeconds().toString().padStart(2, '0');
    const milliseconds = dateObject.getUTCMilliseconds().toString().padStart(3, '0');
    
    // Format: YYYY-MM-DD HH:MM:SS.mmm
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
};