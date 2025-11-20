/**
 * Channel Drag and Drop Functionality
 * Enables reordering of channel list items by dragging
 */

let draggedElement = null;
let draggedIndex = null;
let placeholder = null;
let isInitialized = false;

function initializeDragDrop() {
    const channelList = document.getElementById('graph-channel-list');
    if (!channelList) {
        console.log('Channel list not found, retrying...');
        setTimeout(initializeDragDrop, 1000);
        return;
    }
    
    console.log('Initializing drag and drop for channel list');
    setupDragHandlers(channelList);
    
    // Use MutationObserver to handle dynamically added channels
    if (!isInitialized) {
        const observer = new MutationObserver((mutations) => {
            let shouldReinitialize = false;
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    shouldReinitialize = true;
                }
            });
            
            if (shouldReinitialize) {
                setTimeout(() => setupDragHandlers(channelList), 100);
            }
        });
        
        observer.observe(channelList, {
            childList: true,
            subtree: true
        });
        
        isInitialized = true;
    }
}

function setupDragHandlers(channelList) {
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
            dragHandle.addEventListener('mousedown', () => {
                dragHandle.style.cursor = 'grabbing';
            });
            dragHandle.addEventListener('mouseup', () => {
                dragHandle.style.cursor = 'grab';
            });
            dragHandle.addEventListener('mouseleave', () => {
                dragHandle.style.cursor = 'grab';
            });
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
    draggedIndex = parseInt(draggedElement.getAttribute('data-index'));
    
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
    
    // Skip the "Add Graph" button
    const hasAddButton = targetItem.querySelector('#add-graph-btn');
    if (hasAddButton) {
        return;
    }
    
    // Remove existing placeholder
    if (placeholder) {
        placeholder.remove();
        placeholder = null;
    }
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.className = 'drag-placeholder list-group-item';
    // placeholder.style.height = draggedElement.offsetHeight + 'px';
    placeholder.innerHTML = '<div></div>';
    
    const rect = targetItem.getBoundingClientRect();
    const mouseY = e.clientY;
    const targetY = rect.top + rect.height / 2;
    
    if (mouseY < targetY) {
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
    
    // Trigger a custom event to notify Dash about the reorder
    const channelList = document.getElementById('graph-channel-list');
    const reorderEvent = new CustomEvent('channelReorder', {
        detail: {
            originalIndex: draggedIndex,
            newIndex: Array.from(channelList.children).indexOf(draggedElement)
        }
    });
    channelList.dispatchEvent(reorderEvent);
    
    console.log('Drop completed, reorder event dispatched');
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
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDragDrop);
} else {
    initializeDragDrop();
}