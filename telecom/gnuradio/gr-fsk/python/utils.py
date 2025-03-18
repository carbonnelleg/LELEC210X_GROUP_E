import atexit
import logging
import statistics as stats
from functools import wraps
from time import time
from typing import Any, Callable, List
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def get_measurements_logger(measurement_type: str ='main_app') -> logging.Logger:
    """
    Returns a Logger instance for logging measurement data.

    :param measurement_type: Type of measurement (e.g., 'main_app', 'eval_radio').
    :return: Configured Logger object.
    """
    log_dir = 'hands_on_measurements/data'
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('t%Y%m%d_%H%M%S')
    log_filename = f'../../../{log_dir}/{measurement_type}_measurements_{timestamp}.txt'

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


def timeit(fun: Callable[..., Any]) -> Callable[..., Any]:
    """
    Wrapper around a function and registers timing statistics about it.

    When the program exits (e.g., with CTRL + C), this utility
    will print short message with mean execution duration.

    Usage:

        Say you have a function definition:

        >>> def my_function(a, b):
        ...     pass

        You can simply use this utility as follows:

        >>> from .utils import timeit
        >>>
        >>> @timeit
        ... def my_function(a, b):
        ...     pass

    Note that you can use this decorator as many times as you want.
    """
    f_name = getattr(fun, "__name__", "<unnamed function>")
    data: List[float] = []

    def print_stats() -> None:
        mean = stats.mean(data)
        std = stats.stdev(data)
        print(
            f"{f_name} statistics: mean execution time of {mean:.2}s. (std: {std:.2}s.)"
        )

    @wraps(fun)
    def wrapper(*args, **kwargs):
        start = time()
        ret = fun(*args, **kwargs)
        end = time()
        data.append(end - start)
        return ret

    atexit.register(print_stats)

    return wrapper
