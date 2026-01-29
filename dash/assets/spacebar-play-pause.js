(function() {
    'use strict';

    function init() {
        if (window._spacebarPlayPauseSetup) return;

        document.addEventListener('keydown', handleSpacebar, true);
        window._spacebarPlayPauseSetup = true;
        console.log('Spacebar play/pause handler initialized');
    }

    function handleSpacebar(e) {
        if (e.code !== 'Space' && e.key !== ' ') {
            return;
        }

        const activeEl = document.activeElement;
        if (activeEl && (
            activeEl.tagName === 'INPUT' ||
            activeEl.tagName === 'TEXTAREA' ||
            activeEl.isContentEditable ||
            activeEl.tagName === 'SELECT'
        )) {
            return;
        }

        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            return;
        }

        const playBtn = document.getElementById('play-button');
        if (playBtn && !playBtn.disabled) {
            e.preventDefault();
            e.stopPropagation();
            playBtn.click();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(init, 500);
        });
    } else {
        setTimeout(init, 500);
    }

    setTimeout(init, 2000);

    window.spacebarPlayPause = {
        init: init
    };
})();
