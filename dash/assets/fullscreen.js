function plotZoom(el){
    if(document.fullscreenElement) {
        document.exitFullscreen();
    } else {
        el.closest('.js-plotly-plot').requestFullscreen();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const modeBarButtons = document.querySelectorAll('.modebar-btn.plotlyjsicon.modebar-btn--logo');
    modeBarButtons.forEach(button => {
        if (!button.closest('.fullscreen-btn')) { // Prevent adding multiple buttons
            const aTag = document.createElement('a');
            aTag.setAttribute('rel', 'tooltip');
            aTag.setAttribute('onclick', 'plotZoom(this);');
            aTag.className = 'modebar-btn fullscreen-btn';
            aTag.setAttribute('data-title', 'Full Screen');
            aTag.setAttribute('data-attr', 'zoom');
            aTag.setAttribute('data-val', 'auto');
            aTag.setAttribute('data-toggle', 'false');
            aTag.setAttribute('data-gravity', 'n');

            const iTag = document.createElement('i');
            iTag.className = 'fa-solid fa-maximize'; // Requires Font Awesome
            aTag.appendChild(iTag);

            button.replaceWith(aTag);
        }
    });
});