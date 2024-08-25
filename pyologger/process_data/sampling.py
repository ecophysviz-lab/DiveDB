import numpy as np

def upsample(data, upsampling_factor, original_length):
    """
    Upsamples the input data by repeating each value upsampling_factor times 
    and adjusts the length to match the original length.
    
    Parameters:
    - data: numpy array of the data to be upsampled.
    - upsampling_factor: int, the factor by which to upsample the data.
    - original_length: int, the length of the original data before downsampling.
    
    Returns:
    - numpy array of the upsampled data adjusted to the original length.
    """
    # Step 1: Repeat the data to upsample
    upsampled_data = np.repeat(data, upsampling_factor)
    
    # Step 2: Adjust the length to match the original length
    if len(upsampled_data) > original_length:
        upsampled_data = upsampled_data[:original_length]
    elif len(upsampled_data) < original_length:
        upsampled_data = np.pad(upsampled_data, (0, original_length - len(upsampled_data)), 'edge')
    
    return upsampled_data