import time
import logging

class TimingContext:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start_time = time.time()
        logging.info(f"Starting {self.name}...")

    def __exit__(self, exc_type, exc_value, traceback):
        end_time = time.time()
        elapsed_time = end_time - self.start_time
        logging.info(f"Finished {self.name} in {elapsed_time:.2f} seconds.")