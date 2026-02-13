class Options:
    def __init__(self, *, filename: str,
                         collapse_single_pages: bool,
                         strict: bool,
                         maximum_file_homepage: int,
                         maximum_days_ahead: int,
                         ai_report_path_prefix: str = "",
                         ai_report_recent_limit: int = 0,
                         ai_report_pin_to_top: bool = False):
        self.filename = filename
        self.collapse_single_pages = collapse_single_pages
        self.strict = strict
        self.maximum_file_homepage = maximum_file_homepage
        self.maximum_days_ahead = maximum_days_ahead
        self.ai_report_path_prefix = ai_report_path_prefix
        self.ai_report_recent_limit = ai_report_recent_limit
        self.ai_report_pin_to_top = ai_report_pin_to_top
        
