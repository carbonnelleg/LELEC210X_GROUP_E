import logging
import os
from datetime import datetime

def get_measurements_logger(measurement_type: str ='main_app') -> logging.Logger:
    """
    Returns a Logger instance for logging measurement data.

    :param measurement_type: Type of measurement (e.g., 'main_app', 'eval_radio').
    :return: Configured Logger object.
    """
    log_dir = 'data'
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('t%Y%m%d_%H%M%S')
    log_filename = f'{log_dir}/{measurement_type}_measurements_{timestamp}.txt'

    logger = logging.getLogger(f'measurements_{measurement_type}')
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent duplicate logging if another logger is configured

    file_handler = logging.FileHandler(log_filename, mode='w')
    file_handler.setLevel(logging.INFO)
    
    # Remove existing handlers if already set (prevents duplicate logging in new calls)
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(file_handler)
    
    return logger
