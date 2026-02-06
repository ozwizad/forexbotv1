"""
Walk-Forward Analysis Infrastructure
Provides data splitting for out-of-sample testing to avoid overfitting.
"""


def walk_forward_splits(data_length, n_splits=5, train_ratio=0.7):
    """
    Generate walk-forward analysis splits for avoiding overfitting.
    
    Creates overlapping windows that slide forward through the data,
    with each window split into training and testing periods.
    
    Args:
        data_length: Total length of the dataset
        n_splits: Number of walk-forward windows (default 5)
        train_ratio: Ratio of training data in each window (default 0.7)
        
    Returns:
        List of tuples: (train_start, train_end, test_start, test_end)
    """
    window_size = data_length // n_splits
    splits = []
    
    for i in range(n_splits):
        # Sliding window with 50% overlap
        start = i * (window_size // 2)
        end = min(start + window_size, data_length)
        
        # Skip if window too small
        if end - start < 100:
            continue
        
        # Split point between train and test
        split_point = start + int((end - start) * train_ratio)
        
        splits.append((start, split_point, split_point, end))
    
    return splits
