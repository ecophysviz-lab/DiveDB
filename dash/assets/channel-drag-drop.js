/**
 * Channel Drag and Drop Functionality
 * Enables reordering of channel list items by dragging
 */

let draggedElement = null;
let draggedIndex = null;
let placeholder = null;
let isInitialized = false;
let lastPlacementInfo = null;  // Track last placement to prevent stuttering
let isDragging = false;
let observer = null;
let observedElement = null;
let reinitializeTimer = null;
let initRetryTimer = null;
let initRetryCount = 0;

const MAX_INIT_RETRIES = 10;
const INIT_RETRY_DELAY_MS = 150;

// Dead zone threshold - mouse must be this many pixels past center to trigger swap
const DRAG_THRESHOLD = 15;

function handleDragHandleMouseDown(e) {
    e.currentTarget.style.cursor = 'grabbing';
}

function handleDragHandleMouseUp(e) {
    e.currentTarget.style.cursor = 'grab';
}

function handleDragHandleMouseLeave(e) {
    e.currentTarget.style.cursor = 'grab';
}

function isPlaceholderNode(node) {
    return Boolean(
        node &&
        node.nodeType === Node.ELEMENT_NODE &&
        node.classList &&
        node.classList.contains('drag-placeholder')
    );
}

function shouldReinitializeForMutation(mutation) {
    if (mutation.type !== 'childList') {
        return false;
    }

    const addedNonPlaceholder = Array.from(mutation.addedNodes || []).some(
        (node) => !isPlaceholderNode(node)
    );
    if (addedNonPlaceholder) {
        return true;
    }

    return Array.from(mutation.removedNodes || []).some(
        (node) => !isPlaceholderNode(node)
    );
}

function scheduleDragHandlerSetup(channelList) {
    if (reinitializeTimer) {
        clearTimeout(reinitializeTimer);
    }

    reinitializeTimer = setTimeout(() => {
        reinitializeTimer = null;
        if (isDragging || !channelList || !document.body.contains(channelList)) {
            return;
        }
        setupDragHandlers(channelList);
    }, 100);
}

function initializeDragDrop() {
    const channelList = document.getElementById('graph-channel-list');
    if (!channelList) {
        // Channel list only exists while the popover is rendered/open.
        // Retry a bounded number of times for mount/animation timing, then stop.
        if (!initRetryTimer && initRetryCount < MAX_INIT_RETRIES) {
            initRetryCount += 1;
            initRetryTimer = setTimeout(() => {
                initRetryTimer = null;
                initializeDragDrop();
            }, INIT_RETRY_DELAY_MS);
        }
        return;
    }

    initRetryCount = 0;
    if (initRetryTimer) {
        clearTimeout(initRetryTimer);
        initRetryTimer = null;
    }

    console.log('Initializing drag and drop for channel list');
    setupDragHandlers(channelList);

    // If popover was closed/reopened, graph-channel-list may be a new DOM node.
    // Recreate observer for the new node and reset initialization state.
    if (observedElement && observedElement !== channelList) {
        if (observer) {
            observer.disconnect();
            observer = null;
        }
        isInitialized = false;
    }
    
    // Use MutationObserver to handle dynamically added channels
    if (!isInitialized) {
        observer = new MutationObserver((mutations) => {
            const shouldReinitialize = mutations.some(shouldReinitializeForMutation);
            if (shouldReinitialize) {
                scheduleDragHandlerSetup(channelList);
            }
        });
        
        observer.observe(channelList, {
            childList: true,
            subtree: false
        });
        
        observedElement = channelList;
        isInitialized = true;
    }
}

function setupDragHandlers(channelList) {
    if (isDragging) {
        return;
    }

    // Remove existing event listeners to prevent duplicates
    channelList.removeEventListener('dragstart', handleDragStart);
    channelList.removeEventListener('dragover', handleDragOver);
    channelList.removeEventListener('drop', handleDrop);
    channelList.removeEventListener('dragend', handleDragEnd);
    
    // Add event listeners
    channelList.addEventListener('dragstart', handleDragStart);
    channelList.addEventListener('dragover', handleDragOver);
    channelList.addEventListener('drop', handleDrop);
    channelList.addEventListener('dragend', handleDragEnd);
    
    // Make channel items draggable
    const channelItems = channelList.querySelectorAll('.list-group-item');
    channelItems.forEach((item, index) => {
        // Skip the "Add Graph" button (usually the last item)
        const hasAddButton = item.querySelector('#add-graph-btn');
        if (hasAddButton) {
            item.setAttribute('draggable', 'false');
            return;
        }
        
        // Only make items with drag handles draggable
        const dragHandle = item.querySelector('.drag-handle');
        if (dragHandle) {
            item.setAttribute('draggable', 'true');
            item.setAttribute('data-index', index);
            
            // Add drag handle styling
            dragHandle.style.cursor = 'grab';
            if (!dragHandle.dataset.dragCursorListenersAttached) {
                dragHandle.addEventListener('mousedown', handleDragHandleMouseDown);
                dragHandle.addEventListener('mouseup', handleDragHandleMouseUp);
                dragHandle.addEventListener('mouseleave', handleDragHandleMouseLeave);
                dragHandle.dataset.dragCursorListenersAttached = 'true';
            }
        } else {
            item.setAttribute('draggable', 'false');
        }
    });
}

function handleDragStart(e) {
    // Only allow dragging from drag handles
    if (!e.target.closest('.drag-handle')) {
        e.preventDefault();
        return;
    }
    
    draggedElement = e.target.closest('.list-group-item');
    if (!draggedElement) {
        e.preventDefault();
        return;
    }

    isDragging = true;
    draggedIndex = parseInt(draggedElement.getAttribute('data-index'));
    lastPlacementInfo = null;  // Reset placement tracking
    
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', draggedElement.outerHTML);
    
    // Add visual feedback
    setTimeout(() => {
        draggedElement.style.opacity = '0.5';
    }, 0);
    
    console.log('Drag started:', draggedIndex);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const targetItem = e.target.closest('.list-group-item');
    if (!targetItem || targetItem === draggedElement) {
        return;
    }
    
    // Skip the header (contains Add button) and non-channel items
    const hasAddButton = targetItem.querySelector('#add-graph-btn');
    const hasChannelSelect = targetItem.querySelector('select');
    if (hasAddButton || !hasChannelSelect) {
        return;
    }
    
    const rect = targetItem.getBoundingClientRect();
    const mouseY = e.clientY;
    const targetCenterY = rect.top + rect.height / 2;
    const distanceFromCenter = mouseY - targetCenterY;
    
    // Determine placement position with dead zone threshold
    // Only place above if mouse is significantly above center
    // Only place below if mouse is significantly below center
    let placeBefore;
    if (distanceFromCenter < -DRAG_THRESHOLD) {
        placeBefore = true;  // Place above target
    } else if (distanceFromCenter > DRAG_THRESHOLD) {
        placeBefore = false;  // Place below target
    } else {
        // Within dead zone - keep current placement or don't move
        return;
    }
    
    // Check if this would be the same placement as before (prevent redundant DOM updates)
    const targetIndex = targetItem.getAttribute('data-index');
    const newPlacementInfo = `${targetIndex}-${placeBefore ? 'before' : 'after'}`;
    
    if (lastPlacementInfo === newPlacementInfo) {
        return;  // No change needed
    }
    lastPlacementInfo = newPlacementInfo;
    
    // Remove existing placeholder
    if (placeholder) {
        placeholder.remove();
        placeholder = null;
    }
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.className = 'drag-placeholder list-group-item';
    placeholder.innerHTML = '<div></div>';
    
    if (placeBefore) {
        targetItem.parentNode.insertBefore(placeholder, targetItem);
    } else {
        targetItem.parentNode.insertBefore(placeholder, targetItem.nextSibling);
    }
}

function handleDrop(e) {
    e.preventDefault();
    
    if (!placeholder || !draggedElement) {
        return;
    }
    
    // Insert the dragged element at the placeholder position
    placeholder.parentNode.insertBefore(draggedElement, placeholder);
    placeholder.remove();
    placeholder = null;
    
    // Reset opacity
    draggedElement.style.opacity = '1';
    
    // Log the new order for debugging
    // The actual order will be read from DOM when "Update Graph" is clicked
    const channelList = document.getElementById('graph-channel-list');
    const channelOrder = [];
    
    const listItems = channelList.querySelectorAll('.list-group-item');
    listItems.forEach((item) => {
        const select = item.querySelector('select');
        if (select && select.id && select.id.includes('channel-select')) {
            channelOrder.push(select.value);
        }
    });
    
    console.log('Drag reorder completed. New visual order:', channelOrder);
    console.log('Click "Update Graph" to apply this order to the graph.');
}

function handleDragEnd(e) {
    if (draggedElement) {
        draggedElement.style.opacity = '1';
    }
    
    if (placeholder) {
        placeholder.remove();
        placeholder = null;
    }
    
    // Reset cursor
    const dragHandle = e.target.closest('.drag-handle');
    if (dragHandle) {
        dragHandle.style.cursor = 'grab';
    }
    
    draggedElement = null;
    draggedIndex = null;
    lastPlacementInfo = null;  // Reset placement tracking
    isDragging = false;

    // If mutations were queued while dragging, safely re-run setup now.
    if (reinitializeTimer) {
        clearTimeout(reinitializeTimer);
        reinitializeTimer = null;
        const channelList = document.getElementById('graph-channel-list');
        if (channelList) {
            setupDragHandlers(channelList);
        }
    }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDragDrop);
} else {
    initializeDragDrop();
}