from datetime import datetime
import logging
import os.path
import sys

from django.conf import settings


_logging_setup = False
_profile_log = None


class LoggingMiddleware(object):
    """
    A piece of middleware that sets up logging.

    This a few settings to configure.

    LOGGING_ENABLED
    ---------------

    Default: False

    Sets whether or not logging is enabled.


    LOGGING_DIRECTORY
    -----------------

    Default: None

    Specifies the directory that log files should be stored in.
    This directory must be writable by the process running Django.


    LOGGING_NAME
    ------------

    Default: None

    The name of the log files, excluding the extension and path. This will
    usually be the name of the website or web application. The file extension
    will be automatically appended when the file is written.


    LOGGING_ALLOW_PROFILING
    -----------------------

    Default: False

    Specifies whether or not code profiling is allowed. If True, visiting
    any page with a ``?profiling=1`` parameter in the URL will cause the
    request to be profiled and stored in a ``.prof`` file using the defined
    ``LOGGING_DIRECTORY`` and ``LOGGING_NAME``.


    LOGGING_LINE_FORMAT
    -------------------

    Default: "%(asctime)s - %(levelname)s - %(message)s"

    The format for lines in the log file. See Python's logging documentation
    for possible values in the format string.


    LOGGING_LEVEL
    -------------

    Default: "DEBUG"

    The minimum level to log. Possible values are ``DEBUG``, ``INFO``,
    ``WARNING``, ``ERROR`` and ``CRITICAL``.
    """

    DEFAULT_LOG_LEVEL = "DEBUG"
    DEFAULT_LINE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

    def process_request(self, request):
        """
        Processes an incoming request. This will set up logging.
        """
        self.ensure_loggers()

    def process_view(self, request, callback, callback_args, callback_kwargs):
        """
        Handler for processing a view. This will run the profiler on the view
        if profiling is allowed in the settings and the user specified the
        profiling parameter on the URL.
        """
        if ('profiling' in request.GET and
            getattr(settings, "LOGGING_ALLOW_PROFILING", False)):
            import cProfile
            self.profiler = cProfile.Profile()
            args = (request,) + callback_args
            return self.profiler.runcall(callback, *args, **callback_kwargs)

    def process_response(self, request, response):
        """
        Handler for processing a response. Dumps the profiling information
        to the profile log file.
        """
        if ('profiling' in request.GET and
            getattr(settings, "LOGGING_ALLOW_PROFILING", False)):

            self.ensure_profile_logger()

            from cStringIO import StringIO
            self.profiler.create_stats()

            # Capture the stats
            out = StringIO()
            old_stdout, sys.stdout = sys.stdout, out
            self.profiler.print_stats(1)
            sys.stdout = old_stdout

            _profile_log.log(logging.INFO,
                             "Profiling results for %s (HTTP %s):",
                             request.path, request.method)
            _profile_log.log(logging.INFO, out.getvalue().strip())

        return response

    def ensure_loggers(self):
        """
        Sets up the main loggers, if they haven't already been set up.
        """
        global _logging_setup

        if _logging_setup:
            return

        enabled = getattr(settings, 'LOGGING_ENABLED', False)
        log_directory = getattr(settings, 'LOGGING_DIRECTORY', None)
        log_name = getattr(settings, 'LOGGING_NAME', None)

        if not enabled or not log_directory or not log_name:
            return

        log_level_name = getattr(settings, 'LOGGING_LEVEL',
                                 self.DEFAULT_LOG_LEVEL)
        log_level = logging.getLevelName(log_level_name)
        format_str = getattr(settings, 'LOGGING_LINE_FORMAT',
                             self.DEFAULT_LINE_FORMAT)

        log_path = os.path.join(log_directory, log_name + ".log")

        logging.basicConfig(
            level=log_level,
            format=format_str,
            filename=log_path,
            filemode='a'
        )

        if settings.DEBUG:
            # In DEBUG mode, log to the console as well.
            console_log = logging.StreamHandler()
            console_log.setLevel(log_level)
            console_log.setFormatter(logging.Formatter(format_str))
            logging.getLogger('').addHandler(console_log)

        logging.info("Logging to %s with a minimum level of %s",
                     log_path, log_level_name)

        _logging_setup = True

    def ensure_profile_logger(self):
        """
        Sets up the profiling logger, if it hasn't already been set up.
        """
        global _profile_log

        enabled = getattr(settings, 'LOGGING_ENABLED', False)
        log_directory = getattr(settings, 'LOGGING_DIRECTORY', None)
        log_name = getattr(settings, 'LOGGING_NAME', None)

        if (enabled and log_directory and log_name and not _profile_log and
            getattr(settings, "LOGGING_ALLOW_PROFILING", False)):
            handler = logging.FileHandler(
                os.path.join(log_directory, log_name + ".prof"))
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

            _profile_log = logging.getLogger("profile")
            _profile_log.addHandler(handler)