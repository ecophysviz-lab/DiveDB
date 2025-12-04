/**
 * Global arrow key navigation for playhead control.
 * Left/Right arrows move playhead by 0.1 seconds.
 * 
 * This script works with Dash by:
 * 1. Listening for arrow key events globally (using capture phase to intercept before video player)
 * 2. Updating a hidden dcc.Input element with the direction
 * 3. Dash clientside callback responds to the input change and updates playhead-time
 */

(function() {
    'use strict';
    
    // Wait for Dash to be ready
    function init() {
        if (window._arrowKeyNavSetup) return;
        
        // Use capture phase (true) to intercept events before they reach video player
        document.addEventListener('keydown', handleArrowKey, true);
        window._arrowKeyNavSetup = true;
        console.log('Arrow key navigation initialized (±0.1s steps, capture mode)');
    }
    
    function handleArrowKey(e) {
        // Only handle left/right arrow keys
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') {
            return;
        }
        
        // Don't handle if user is typing in an input field (except our hidden one)
        const activeEl = document.activeElement;
        if (activeEl && activeEl.id !== 'arrow-key-input' && (
            activeEl.tagName === 'INPUT' || 
            activeEl.tagName === 'TEXTAREA' || 
            activeEl.isContentEditable ||
            activeEl.tagName === 'SELECT'
        )) {
            return;
        }
        
        // IMPORTANT: Prevent default and stop propagation to prevent video player from handling
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        // Determine direction: 1 for forward (right), -1 for backward (left)
        const direction = e.key === 'ArrowRight' ? 1 : -1;
        
        // Update the hidden input to trigger the Dash callback
        updateArrowKeyInput(direction);
    }
    
    function updateArrowKeyInput(direction) {
        // Find the hidden input element
        const hiddenInput = document.getElementById('arrow-key-input');
        if (!hiddenInput) {
            console.warn('Arrow key input element not found - waiting for Dash to render');
            return;
        }
        
        // Create a unique value that includes direction and timestamp
        // This ensures the callback fires even for repeated key presses
        const value = direction + ':' + Date.now();
        
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
                        console.log('Arrow key:', direction > 0 ? '→ +0.1s' : '← -0.1s');
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
            
            console.log('Arrow key (fallback):', direction > 0 ? '→ +0.1s' : '← -0.1s');
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
    window.arrowKeyNav = {
        init: init,
        trigger: updateArrowKeyInput
    };
})();
