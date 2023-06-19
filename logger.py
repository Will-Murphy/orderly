import logging

class Logger:
    def __init__(self, name, level=logging.DEBUG):
        # Create a logger with the specified name
        self.logger = logging.getLogger(name)
        # Set the log level to DEBUG so all log messages are recorded
        self.logger.setLevel(level)

        # Create console handler with a higher log level
        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(level)

        # Create formatter and add it to the handler
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.console_handler.setFormatter(formatter)

        # Add the handler to the logger
        self.logger.addHandler(self.console_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def error(self, message):
        self.logger.error(message)

    def set_level(self, level: int):
        map_int_to_level = {
            1: logging.DEBUG,
            2: logging.INFO,
            3: logging.ERROR
        }
        log_level = map_int_to_level.get(level, logging.DEBUG)
        self.logger.setLevel(log_level)
        self.console_handler.setLevel(log_level)