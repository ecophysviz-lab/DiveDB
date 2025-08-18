window.dccFunctions = window.dccFunctions || {};
window.dccFunctions.formatTimestamp = function(value) {
    // if (typeof value !== "number" || isNaN(value)) return "";
    // return String(Math.floor(value)).slice(-3);

    const dateObject = new Date(value * 1000);

    const year = dateObject.getUTCFullYear();
    const month = dateObject.getUTCMonth();
    const day = dateObject.getUTCDate();
    const hours = dateObject.getUTCHours();
    const minutes = dateObject.getUTCMinutes();
    const seconds = dateObject.getUTCSeconds();
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
};