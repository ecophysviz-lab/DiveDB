/**
 * Global B key handler for event bookmark creation.
 * Press 'B' to open the event creation modal at the current playhead position.
 * 
 * This script works with Dash by:
 * 1. Listening for 'B' key events globally (using capture phase)
 * 2. Updating a hidden dcc.Input element with a timestamp
 * 3. Dash callback responds to the input change and opens the event modal
 */

(function() {
    'use strict';
    
    // Wait for Dash to be ready
    function init() {
        if (window._bKeyBookmarkSetup) return;
        
        // Use capture phase (true) to intercept events before they reach other handlers
        document.addEventListener('keydown', handleBKey, true);
        window._bKeyBookmarkSetup = true;
        console.log('B-key bookmark handler initialized');
    }
    
    function handleBKey(e) {
        // Only handle 'B' or 'b' key
        if (e.key !== 'b' && e.key !== 'B') {
            return;
        }
        
        // Don't handle if user is typing in an input field
        const activeEl = document.activeElement;
        if (activeEl && (
            activeEl.tagName === 'INPUT' || 
            activeEl.tagName === 'TEXTAREA' || 
            activeEl.isContentEditable ||
            activeEl.tagName === 'SELECT'
        )) {
            return;
        }
        
        // Don't handle if a modal is already open
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            return;
        }
        
        // Prevent default behavior
        e.preventDefault();
        e.stopPropagation();
        
        // Update the hidden input to trigger the Dash callback
        updateBookmarkTrigger();
    }
    
    function updateBookmarkTrigger() {
        // Find the hidden input element
        const hiddenInput = document.getElementById('bookmark-trigger');
        if (!hiddenInput) {
            console.warn('Bookmark trigger element not found - waiting for Dash to render');
            return;
        }
        
        // Create a unique value with timestamp to ensure callback fires
        const value = 'open:' + Date.now();
        
        // Try to find the React component and use setProps
        const reactKey = Object.keys(hiddenInput).find(key => 
            key.startsWith('__reactFiber$') || key.startsWith('__reactInternalInstance$')
        );
        
        if (reactKey) {
            try {
                let fiber = hiddenInput[reactKey];
                // Traverse up to find the component with setProps
                while (fiber) {
                    if (fiber.memoizedProps && typeof fiber.memoizedProps.setProps === 'function') {
                        // Found the Dash component - update the value
                        fiber.memoizedProps.setProps({ value: value });
                        console.log('B key pressed - opening event modal');
                        return;
                    }
                    fiber = fiber.return;
                }
            } catch (err) {
                console.warn('Could not update via React fiber:', err);
            }
        }
        
        // Fallback: try native value change with event dispatch
        try {
            // Set the value using native setter
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeInputValueSetter.call(hiddenInput, value);
            
            // Dispatch input event to trigger React's onChange
            const inputEvent = new Event('input', { bubbles: true });
            hiddenInput.dispatchEvent(inputEvent);
            
            // Also dispatch change event as backup
            const changeEvent = new Event('change', { bubbles: true });
            hiddenInput.dispatchEvent(changeEvent);
            
            console.log('B key pressed (fallback) - opening event modal');
        } catch (err) {
            console.warn('Fallback input update failed:', err);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(init, 500);
        });
    } else {
        // Small delay to ensure Dash components are rendered
        setTimeout(init, 500);
    }
    
    // Also try to init after a longer delay in case Dash is slow to load
    setTimeout(init, 2000);
    
    // Expose for debugging
    window.bKeyBookmark = {
        init: init,
        trigger: updateBookmarkTrigger
    };
})();
