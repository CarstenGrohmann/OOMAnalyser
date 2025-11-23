# Unit tests for OOMAnalyser
#
# Copyright (c) 2021-2025 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

import http.server
import inspect
import os
import re
import socketserver
import threading
import warnings
from typing import Any, Dict, Generator, List, Optional, Tuple

import pytest
from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import OOMAnalyser


class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(
        self,
        request: Any,
        client_address: Tuple[str, int],
        server: socketserver.BaseServer,
        directory: Optional[str] = None,
    ) -> None:
        self.directory = os.getcwd()
        super().__init__(request, client_address, server)

    # suppress all HTTP request messages
    def log_message(self, format: str, *args: Any) -> None:
        # super().log_message(format, *args)
        pass


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class BaseTests:
    text_alloc_failed_below_low_watermark = (
        "The request failed because the free memory would be below the memory low "
        "watermark after its completion."
    )
    text_alloc_failed_no_free_chunks = (
        "The request failed because there is no free chunk in the current or "
        "higher order."
    )
    text_alloc_failed_unknown_reason = "The request failed, but the reason is unknown."

    text_mem_not_heavily_fragmented = "The system memory is not heavily fragmented"
    text_mem_heavily_fragmented = "The system memory is heavily fragmented"

    text_oom_triggered_manually = "OOM killer was manually triggered"
    text_oom_triggered_automatically = "OOM killer was automatically triggered"

    text_cgroup_swap_activated = "Swap space is enabled for this cgroup."
    text_cgroup_swap_deactivated = "Swap space usage is disabled for this cgroup."
    text_kernel_swap_space_not_in_use = "physical memory and no system swap space"
    text_kernel_swap_space_are_in_use = "system swap space are in use"
    test_kernel_swap_no_space = "System swap space disabled."
    test_kernel_swap_swap_total = "Swap Total"

    text_with_an_oom_score_of = "with an OOM score of"

    def get_lines(self, text: str, count: int) -> str:
        """
        Return the number of lines specified by count from the given text

        @type text: str
        @type count: int
        """
        lines = text.splitlines()
        if count < 0:
            lines.reverse()
            count = count * -1
        lines = lines[:count]
        res = "\n".join(lines)
        return res

    def get_first_line(self, text: str) -> str:
        """
        Return the first line of the given text
        @type text: str
        """
        return self.get_lines(text, 1)

    def get_last_line(self, text: str) -> str:
        """
        Return the last line of the given text
        @type text: str
        """
        return self.get_lines(text, -1)

    def check_meminfo_format_rhel7(self, prefix: str, oom_text: str) -> None:
        """
        Check if the example contains a properly formatted "Mem-Info:" block

        @param str prefix: Prefix for error message
        @param str oom_text: Whole OOM block as text

        @see: OOMAnalyser.OOMDisplay.example_rhel7
        """
        found = False
        for line in oom_text.split("\n"):
            if "active_file:1263 " in line:
                found = True
                assert line.startswith(
                    " active_file:1263 "
                ), f'{prefix}: Unexpected prefix for third "Mem-Info:" block line: >>>{line}<<<'
        assert (
            found
        ), f'{prefix}: Missing content "active_file:1263 " in "Mem-Info:" block of\n{oom_text}'

    def to_continuous_text(self, text: str) -> str:
        """
        Convert the given text into a single continuous line.

        This function removes all line breaks and any whitespace before or after them,
        replacing them with a single space. Additionally, it corrects formatting issues
        where a space may be introduced before a closing parenthesis due to the replacement.

        @param text: The input string to be converted.
        @type text: str
        @return: The text as a single continuous line.
        @rtype: str
        """
        continuous = re.sub(r"\s*\n\s*", " ", text)
        # If a line ends with a closing parenthesis, the replacement of
        # LF by space character will add a space before the closing
        # parenthesis.
        # Remove this space character to match the original text.
        continuous = continuous.replace(" )", ")")
        return continuous


# Common test data for parametrized tests
LOG_PREFIXES = [
    "[11686.888109] ",
    "Apr 01 14:13:32 mysrv: ",
    "Apr 01 14:13:32 mysrv kernel: ",
    "Apr 01 14:13:32 mysrv <kern.warning> kernel: ",
    "Apr 01 14:13:32 mysrv kernel: [11686.888109] ",
    "kernel:",
    "Apr 01 14:13:32 mysrv <kern.warning> kernel:",
]

LOG_PREFIX_IDS = [
    "timestamp-only",
    "syslog-prefix",
    "syslog-kernel",
    "syslog-warning",
    "syslog-kernel-timestamp",
    "kernel-only",
    "syslog-warning-2",
]


class BaseInBrowserTests(BaseTests):
    """Base class for all tests that run in a browser"""

    # Instance attributes (initialized by setup_browser fixture)
    driver: Optional[webdriver.Chrome]

    # --- Begin: generic result check configuration ---
    # For each test variant, set these in the child class. An empty value
    # disables the corresponding check.
    check_results: Dict[str, str] = {
        "gfp_mask": "",  # Expected text in the GFP mask field
        "proc_name": "",  # Expected text in the process name field
        "proc_pid": "",  # Expected text in the process pid field
        "killed_proc_score": "",  # Expected OOM score of killed process
        "swap_cache_kb": "",  # Expected swap cache size
        "swap_used_kb": "",  # Expected swap used size
        "swap_free_kb": "",  # Expected swap free size
        "swap_total_kb": "",  # Expected swap total size
        "swap_active": "no check",  # Set to "check" to verify swap is active
        "swap_inactive": "no check",  # Set to "check" to verify swap is inactive
        "mem_node_info_start": "",  # Expected start text in memory node info
        "mem_node_info_end": "",  # Expected end text in memory node info
        "mem_watermarks_start": "",  # Expected start text in watermarks
        "mem_watermarks_end": "",  # Expected end text in watermarks
        "column_header": "",  # Expected column header in process table
    }
    """Dictionary of expected values for result validation. Empty string disables check."""
    check_explanation_expected_statements: List[str] = []
    """List of text patterns that must be found in the summary/explanation section"""
    check_explanation_unexpected_statements: List[str] = []
    """List of text patterns that must not be found in the summary/explanation section"""
    check_results_result_table_expected: List[str] = []
    """List of text patterns that must be found in the result table"""
    check_results_result_table_unexpected: List[str] = []
    """List of text patterns that must not be found in the result table"""
    check_explanation_section: Dict[str, str] = {}
    """Dictionary with category and text pattern to check the summary/explanation section"""
    # --- End: generic result check configuration ---

    def check_all_results(self) -> None:
        """
        Generic result checker for OOM analysis results.
        Skips tests if the corresponding check_results value is empty.
        """
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be displayed"

        # Mapping of check_results keys to CSS class names and error messages
        simple_checks = {
            "proc_name": ("trigger_proc_name", "Unexpected trigger process name"),
            "proc_pid": (
                "trigger_proc_pid",
                "Unexpected trigger process pid: --{actual}--",
            ),
            "gfp_mask": (
                "trigger_proc_gfp_mask",
                'Unexpected GFP Mask: got: "{actual}", expect: "{expected}"',
            ),
            "killed_proc_score": (
                "killed_proc_score",
                "Unexpected OOM score of killed process",
            ),
            "swap_cache_kb": ("system_swap_cache_kb", "Unexpected swap cache size"),
            "swap_used_kb": ("system_swap_used_kb", "Unexpected swap used size"),
            "swap_free_kb": ("system_swap_free_kb", "Unexpected swap free size"),
            "swap_total_kb": ("system_swap_total_kb", "Unexpected swap total size"),
        }

        # Generic loop for simple equality checks
        for key, (css_class, error_msg) in simple_checks.items():
            expected_value = self.check_results.get(key, "")
            if expected_value:
                element = self.driver.find_element(By.CLASS_NAME, css_class)
                actual_value = element.text
                assert actual_value == expected_value, error_msg.format(
                    actual=actual_value, expected=expected_value
                )

        continuous_explanation_text = self.to_continuous_text(
            self.driver.find_element(By.ID, "explanation").text
        )
        for expected in self.check_explanation_expected_statements:
            assert (
                expected in continuous_explanation_text
            ), f'Missing statement "{expected}" in summary section: >{continuous_explanation_text}<'
        for unexpected in self.check_explanation_unexpected_statements:
            assert (
                unexpected not in continuous_explanation_text
            ), f'Unexpected statement "{unexpected}" in summary section: >{continuous_explanation_text}<'

        result_table = self.driver.find_element(By.CLASS_NAME, "result__table")
        if self.check_results_result_table_expected:
            for expected in self.check_results_result_table_expected:
                assert (
                    expected in result_table.text
                ), f'Missing statement in result table: "{expected}"'
        if self.check_results_result_table_unexpected:
            for unexpected in self.check_results_result_table_unexpected:
                assert (
                    unexpected not in result_table.text
                ), f'Unexpected statement in result table: "{unexpected}"'

        # check text pattern in summary section
        for category in self.check_explanation_section:
            pattern = self.check_explanation_section[category]
            assert (
                pattern in continuous_explanation_text
            ), f'{category}: Pattern "{pattern}" not found in summary section: >{continuous_explanation_text}<'

        mem_node_info = self.driver.find_element(By.CLASS_NAME, "mem_node_info")
        if self.check_results.get("mem_node_info_start"):
            expected_start = self.check_results["mem_node_info_start"]
            assert (
                mem_node_info.text[: len(expected_start)] == expected_start
            ), "Unexpected memory chunks"
        if self.check_results.get("mem_node_info_end"):
            expected_end = self.check_results["mem_node_info_end"]
            assert (
                mem_node_info.text[-len(expected_end) :] == expected_end
            ), "Unexpected memory information about hugepages"

        mem_watermarks = self.driver.find_element(By.CLASS_NAME, "mem_watermarks")
        if self.check_results.get("mem_watermarks_start"):
            expected_start = self.check_results["mem_watermarks_start"]
            assert (
                mem_watermarks.text[: len(expected_start)] == expected_start
            ), "Unexpected memory watermarks"
        if self.check_results.get("mem_watermarks_end"):
            expected_end = self.check_results["mem_watermarks_end"]
            assert (
                mem_watermarks.text[-len(expected_end) :] == expected_end
            ), "Unexpected lowmem_reserve values"

        if self.check_results.get("column_header"):
            header = self.driver.find_element(By.ID, "pstable_header")
            assert (
                self.check_results["column_header"] in header.text
            ), f'Missing column header "{self.check_results["column_header"]}"'

        if self.check_results.get("swap_active", "not set") == "check":
            self.check_swap_active()
        if self.check_results.get("swap_inactive", "not set") == "check":
            self.check_swap_inactive()

    @pytest.fixture(autouse=True)
    def setup_browser(self) -> Generator[None, None, None]:
        """Setup browser and HTTP server for tests"""
        warnings.simplefilter("ignore", ResourceWarning)

        ThreadedTCPServer.allow_reuse_address = True
        # Use port 0 for automatic port assignment to enable parallel test execution
        http_srv = ThreadedTCPServer(("127.0.0.1", 0), MyRequestHandler)
        server_thread = threading.Thread(target=http_srv.serve_forever, args=(0.1,))
        server_thread.daemon = True
        server_thread.start()

        # Get actual assigned port for parallel execution
        actual_port = http_srv.server_address[1]

        # silent Webdriver Manager
        os.environ["WDM_LOG_LEVEL"] = "0"

        # store driver locally
        os.environ["WDM_LOCAL"] = "1"

        # Configure Chrome for performance
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.page_load_strategy = "eager"

        s = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=s, options=chrome_options)
        self.driver.set_page_load_timeout(10)
        self.driver.get(f"http://127.0.0.1:{actual_port}/OOMAnalyser.html")

        yield  # Test runs here

        # Teardown
        self.driver.close()
        http_srv.shutdown()
        http_srv.server_close()

    def assert_on_warn(self) -> None:
        notify_box = self.driver.find_element(By.ID, "notify_box")
        try:
            warning = notify_box.find_element(
                By.CLASS_NAME, "js-notify_box__msg--warning"
            )
        except NoSuchElementException:
            pass
        else:
            pytest.fail(f'Unexpected warning message: "{warning.text}"')

    def assert_on_error(self) -> None:
        error = self.get_first_error_msg()
        if error:
            pytest.fail(f'Unexpected error message: "{error}"')

        for event in self.driver.get_log("browser"):
            # ignore favicon.ico errors
            if "favicon.ico" in event["message"]:
                continue
            pytest.fail(f'Error on browser console reported: "{event}"')

    def assert_on_warn_error(self) -> None:
        self.assert_on_warn()
        self.assert_on_error()

    def click_analyse_button(self) -> None:
        analyse = self.driver.find_element(
            By.XPATH, '//button[text()="Analyse OOM block"]'
        )
        analyse.click()

    def click_reset_button(self) -> None:
        reset = self.driver.find_element(By.XPATH, '//button[text()="Reset form"]')
        if reset.is_displayed():
            reset.click()
        else:
            new_analysis = self.driver.find_element(
                By.XPATH, '//a[contains(text(), "Step 1 - Enter your OOM message")]'
            )
            new_analysis.click()
        self.assert_on_warn_error()

    def clear_notification_box(self) -> None:
        """Clear notification box"""
        # Selenium doesn't provide an interface to delete objects.
        # Remove all notification entries with JS.
        self.driver.execute_script(
            """
            var element = document.getElementById ('notify_box');
            while (element.firstChild) {
                element.removeChild (element.firstChild);
            }
            """
        )

    def get_first_error_msg(self) -> str:
        """
        Return the first (oldest) error message from error notification box or an empty
        string if no error message exists.

        @rtype: str
        """
        notify_box = self.driver.find_element(By.ID, "notify_box")
        try:
            first_error_msg = notify_box.find_element(
                By.CLASS_NAME, "js-notify_box__msg--error"
            )
            return first_error_msg.text
        except NoSuchElementException:
            return ""

    def insert_example(self, select_value: str) -> None:
        """
        Select and insert an example from the combobox

        @param str select_value: Option value to specify the example
        """
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        assert textarea.get_attribute("value") == "", "Empty textarea expected"
        select_element = self.driver.find_element(By.ID, "examples")
        select = Select(select_element)
        option_values = [o.get_attribute("value") for o in select.options]
        assert (
            select_value in option_values
        ), f"Missing proper option for example {select_value}"
        select.select_by_value(select_value)
        assert textarea.get_attribute("value") != "", "Missing OOM text in textarea"
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            not h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be not displayed"

    def analyse_oom(self, text: str) -> None:
        """
        Insert text and run analysis

        :param str text: OOM text to analyse
        """
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        assert textarea.get_attribute("value") == "", "Empty textarea expected"
        textarea.send_keys(text)

        assert textarea.get_attribute("value") != "", "Missing OOM text in textarea"

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            not h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be not displayed"

        self.clear_notification_box()
        self.click_analyse_button()

    def check_swap_inactive(self) -> None:
        explanation = self.driver.find_element(By.ID, "explanation")
        continuous_text = self.to_continuous_text(explanation.text)
        assert (
            self.text_kernel_swap_space_not_in_use in continuous_text
        ), f'Missing statement "{self.text_kernel_swap_space_not_in_use}"'
        assert (
            self.text_kernel_swap_space_are_in_use not in continuous_text
        ), f'Unexpected statement "{self.text_kernel_swap_space_are_in_use}"'

    def check_swap_active(self) -> None:
        explanation = self.driver.find_element(By.ID, "explanation")
        continuous_text = self.to_continuous_text(explanation.text)
        assert (
            self.text_kernel_swap_space_are_in_use in continuous_text
        ), f'Missing statement "{self.text_kernel_swap_space_are_in_use}"'


@pytest.mark.browser
class TestInBrowser(BaseInBrowserTests):
    """Test OOM web page in a browser"""

    def test_010_load_page(self) -> None:
        """Test if the page is loading"""
        assert "OOMAnalyser" in self.driver.title

    def test_020_load_js(self) -> None:
        """Test if JS is loaded"""
        elem = self.driver.find_element(By.ID, "version")
        assert elem.text is not None, "Version statement not set - JS not loaded"

    def test_033_empty_textarea(self) -> None:
        """Test "Analyse OOM block" with an empty textarea"""
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        assert textarea.get_attribute("value") == "", "Empty textarea expected"
        # textarea.send_keys(text)

        assert (
            textarea.get_attribute("value") == ""
        ), "Expected empty text area, but text found"

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            not h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be not displayed"

        self.clear_notification_box()
        self.click_analyse_button()
        assert (
            self.get_first_error_msg()
            == "ERROR: Empty OOM text. Please insert an OOM message block."
        )
        self.click_reset_button()

    def test_034_begin_but_no_end(self) -> None:
        """Test incomplete OOM text - just the beginning"""
        example = """\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        """
        self.analyse_oom(example)
        assert (
            self.get_first_error_msg()
            == "ERROR: The inserted OOM is incomplete! The initial pattern was "
            "found but not the final."
        )
        self.click_reset_button()

    def test_035_no_begin_but_end(self) -> None:
        """Test incomplete OOM text - just the end"""
        example = """\
Out of memory: Kill process 6576 (java) score 651 or sacrifice child
Killed process 6576 (java) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
        """
        self.analyse_oom(example)
        assert (
            self.get_first_error_msg()
            == "ERROR: Failed to extract kernel version from OOM text"
        )
        self.click_reset_button()

    def test_090_scroll_to_top(self) -> None:
        """Test scrolling to the top of the page"""
        # scroll to the bottom of the page
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        initial_position = self.driver.execute_script("return window.scrollY;")

        self.analyse_oom(OOMAnalyser.OOMDisplay.example_rhel7)

        # Wait briefly for smooth scroll to be initiated, then verify scroll started
        # Under parallel execution, smooth scroll animations are unreliable due to resource
        # contention, so we verify scroll was initiated then force completion
        wait = WebDriverWait(self.driver, 5)
        wait.until(
            lambda driver: driver.execute_script("return window.scrollY;")
            < initial_position,
            message="Scroll to top should have been initiated within 5 seconds",
        )

        # Force instant scroll to top to complete the test reliably
        # (smooth scroll animation may be too slow/interrupted in parallel execution)
        self.driver.execute_script("window.scrollTo(0, 0);")

        # Verify final position
        final_position = self.driver.execute_script("return window.scrollY;")
        assert (
            final_position == 0
        ), f"Page should be at top (0), but is at {final_position}"


@pytest.mark.python_only
class TestPython(BaseTests):
    def test_000_configured(self) -> None:
        """Check if all kernel classes are instantiated in OOMAnalyser.AllKernelConfigs"""
        all_kernel_classes = {
            cls.__name__
            for name, cls in inspect.getmembers(OOMAnalyser, inspect.isclass)
            if issubclass(cls, OOMAnalyser.BaseKernelConfig)
        }
        all_configured_kernels = {
            inst.__class__.__name__ for inst in OOMAnalyser.AllKernelConfigs
        }
        missing = all_kernel_classes - all_configured_kernels
        assert not missing, f"Missing kernel instances in AllKernelConfigs: {missing}"

    def test_010_trigger_proc_space(self) -> None:
        """Test RE to find the name of the trigger process"""
        first = self.get_first_line(OOMAnalyser.OOMDisplay.example_rhel7)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN[
            "invoked oom-killer"
        ][0]
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(first)
        assert (
            match
        ), "Error: re.search('invoked oom-killer') failed for simple process name"

        first = first.replace("sed", "VM Monitoring Task")
        match = rec.search(first)
        assert (
            match
        ), "Error: re.search('invoked oom-killer') failed for process name with space"

    @pytest.mark.parametrize(
        "process_name,description",
        [
            pytest.param("sed", "simple process name", id="simple"),
            pytest.param(
                "VM Monitoring Task", "process name with spaces", id="with-spaces"
            ),
            pytest.param(
                "kworker/0:1",
                "process name with special characters (slash and colon)",
                id="special-chars",
            ),
            pytest.param("php-fpm", "process name with hyphen", id="hyphen"),
        ],
    )
    def test_020_killed_proc_space(self, process_name, description) -> None:
        """Test RE to find name of the killed process"""
        pattern_key = "global oom: kill process - pid, name and score"
        original_process_name = "sed"
        original_text = self.get_lines(OOMAnalyser.OOMDisplay.example_rhel7, -2)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN[
            pattern_key
        ][0]
        rec = re.compile(pattern, re.MULTILINE)

        text = original_text.replace(original_process_name, process_name)
        match = rec.search(text)
        assert (
            match
        ), f'Error: Search for process names failed for {description}: "{process_name}"'

    @pytest.mark.parametrize(
        "expected_pos,line",
        [
            pytest.param(
                1,
                "[11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
                id="timestamp-only",
            ),
            pytest.param(
                5,
                "Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
                id="syslog-prefix",
            ),
            pytest.param(
                6,
                "Apr 01 14:13:32 mysrv kernel: [11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
                id="syslog-timestamp",
            ),
        ],
    )
    def test_030_OOMEntity_number_of_columns_to_strip(self, expected_pos, line) -> None:
        """Test stripping useless / leading columns"""
        oom_entity = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        to_strip = oom_entity._number_of_columns_to_strip(line)
        assert (
            to_strip == expected_pos
        ), f'Calc wrong number of columns to strip for "{line}": got: {to_strip}, expect: {expected_pos}'

    @pytest.mark.parametrize(
        "input_lines,expected,description",
        [
            pytest.param(
                ["Apr 01 14:13:32 mysrv kernel:CPU: 4 PID: 29481 Comm: sed"],
                ["Apr 01 14:13:32 mysrv CPU: 4 PID: 29481 Comm: sed"],
                "kernel: without space (edge case)",
                id="no-space",
            ),
            pytest.param(
                ["Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481 Comm: sed"],
                ["Apr 01 14:13:32 mysrv  CPU: 4 PID: 29481 Comm: sed"],
                "kernel: with space (standard case)",
                id="with-space",
            ),
            pytest.param(
                ["Apr 01 14:13:32 mysrv kernel:[11686.888109] Out of memory"],
                ["Apr 01 14:13:32 mysrv [11686.888109] Out of memory"],
                "kernel: before timestamp pattern",
                id="before-timestamp",
            ),
            pytest.param(
                ["[11686.888109] CPU: 4 PID: 29481 Comm: sed"],
                ["[11686.888109] CPU: 4 PID: 29481 Comm: sed"],
                "no kernel: pattern (unchanged)",
                id="no-kernel-pattern",
            ),
            pytest.param(
                [
                    "Apr 01 14:13:32 mysrv kernel:Out of memory: Killed process 29481",
                    "Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481",
                    "[11686.888109] Hardware name: HP ProLiant",
                ],
                [
                    "Apr 01 14:13:32 mysrv Out of memory: Killed process 29481",
                    "Apr 01 14:13:32 mysrv  CPU: 4 PID: 29481",
                    "[11686.888109] Hardware name: HP ProLiant",
                ],
                "multiple lines with mixed patterns",
                id="multiple-lines",
            ),
            pytest.param(
                [],
                [],
                "empty list",
                id="empty",
            ),
            pytest.param(
                ["kernel:kernel: This is unusual but possible"],
                [" This is unusual but possible"],
                "multiple kernel: occurrences (edge case)",
                id="multiple-occurrences",
            ),
        ],
    )
    def test_031_OOMEntity_remove_kernel_colon(
        self, input_lines, expected, description
    ) -> None:
        """Test removal of kernel: pattern from OOM log lines"""
        oom_entity = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        result = oom_entity._remove_kernel_colon(input_lines)
        assert (
            result == expected
        ), f"Failed test: {description}. Got: {result}, expected: {expected}"

    def test_040_extract_block_from_next_pos(self) -> None:
        """Test extracting a single block (all lines till the next line with a colon)"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        text = analyser._extract_block_from_next_pos("Hardware name:")
        expected = """\
Hardware name: HP ProLiant DL385 G7, BIOS A18 12/08/2012
 ffff880182272f10 00000000021dcb0a ffff880418207938 ffffffff816861ac
 ffff8804182079c8 ffffffff81681157 ffffffff810eab9c ffff8804182fe910
 ffff8804182fe928 0000000000000202 ffff880182272f10 ffff8804182079b8
"""
        assert text == expected

    @pytest.mark.parametrize(
        "text,kversion",
        [
            pytest.param(
                "CPU: 0 PID: 19163 Comm: kworker/0:0 Tainted: G           OE     5.4.0-80-lowlatency #90~18.04.1-Ubuntu",
                "5.4.0-80-lowlatency",
                id="ubuntu-5.4",
            ),
            pytest.param(
                "CPU: 4 PID: 1 Comm: systemd Not tainted 3.10.0-1062.9.1.el7.x86_64 #1",
                "3.10.0-1062.9.1.el7.x86_64",
                id="rhel7-3.10",
            ),
        ],
    )
    def test_050_extract_kernel_version(self, text, kversion) -> None:
        """Test extracting the kernel version"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        analyser.oom_entity.text = text
        assert analyser._identify_kernel_version(), analyser.oom_result.error_msg
        assert analyser.oom_result.kversion == kversion

    @pytest.mark.parametrize(
        "kcfg,kversion",
        [
            pytest.param(
                OOMAnalyser.KernelConfig_6_11(),
                "CPU: 4 UID: 123456 PID: 29481 Comm: sed Not tainted 6.12.0 #1",
                id="6.11",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_5_18(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.23.0 #1",
                id="5.18",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_5_12(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.13.0-514 #1",
                id="5.12",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_5_8(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.8.0-514 #1",
                id="5.8",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_5_4(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.5.1 #1",
                id="5.4",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_4_6(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 4.6.0-514 #1",
                id="4.6",
            ),
            pytest.param(
                OOMAnalyser.KernelConfig_3_10_EL7(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-1062.9.1.el7.x86_64 #1",
                id="3.10-el7",
            ),
            pytest.param(
                OOMAnalyser.BaseKernelConfig(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 2.33.0 #1",
                id="2.33-base",
            ),
        ],
    )
    def test_060_choosing_kernel_config(self, kcfg, kversion) -> None:
        """Test choosing the right kernel configuration"""
        oom = OOMAnalyser.OOMEntity(kversion)
        analyser = OOMAnalyser.OOMAnalyser(oom)

        kernel_found = analyser._identify_kernel_version()
        assert kernel_found, f'Failed to identify kernel from string "{kversion}"'

        analyser._choose_kernel_config()
        result = analyser.oom_result.kconfig
        assert type(result) == type(kcfg), (
            f'Mismatch between expected kernel config "{type(kcfg)}" and chosen '
            f'config "{type(result)}" for kernel version "{kversion}"'
        )

    @pytest.mark.parametrize(
        "kversion,min_version,expected_result",
        [
            pytest.param("5.19-rc6", (5, 16, ""), True, id="5.19-rc6-ge-5.16"),
            pytest.param("5.19-rc6", (5, 19, ""), True, id="5.19-rc6-ge-5.19"),
            pytest.param("5.19-rc6", (5, 20, ""), False, id="5.19-rc6-lt-5.20"),
            pytest.param("5.18.6-arch1-1", (5, 18, ""), True, id="5.18-arch-ge-5.18"),
            pytest.param("5.18.6-arch1-1", (5, 1, ""), True, id="5.18-arch-ge-5.1"),
            pytest.param("5.18.6-arch1-1", (5, 19, ""), False, id="5.18-arch-lt-5.19"),
            pytest.param(
                "5.13.0-1028-aws #31~20.04.1-Ubuntu",
                (5, 14, ""),
                False,
                id="5.13-aws-lt-5.14",
            ),
            pytest.param(
                "5.13.0-1028-aws #31~20.04.1-Ubuntu",
                (5, 13, ""),
                True,
                id="5.13-aws-ge-5.13",
            ),
            pytest.param(
                "5.13.0-1028-aws #31~20.04.1-Ubuntu",
                (5, 13, "-aws"),
                True,
                id="5.13-aws-with-string",
            ),
            pytest.param(
                "5.13.0-1028-aws #31~20.04.1-Ubuntu",
                (5, 13, "not_in_version"),
                False,
                id="5.13-aws-wrong-string",
            ),
            pytest.param(
                "5.13.0-1028-aws #31~20.04.1-Ubuntu",
                (5, 12, ""),
                True,
                id="5.13-aws-ge-5.12",
            ),
            pytest.param("4.14.288", (5, 0, ""), False, id="4.14-lt-5.0"),
            pytest.param("4.14.288", (4, 14, ""), True, id="4.14-ge-4.14"),
            pytest.param(
                "3.10.0-514.6.1.el7.x86_64 #1",
                (3, 11, ""),
                False,
                id="3.10-el7-lt-3.11",
            ),
            pytest.param(
                "3.10.0-514.6.1.el7.x86_64 #1",
                (3, 10, ".el7."),
                True,
                id="3.10-el7-with-string",
            ),
            pytest.param(
                "3.10.0-514.6.1.el7.x86_64 #1", (3, 10, ""), True, id="3.10-el7-ge-3.10"
            ),
            pytest.param(
                "3.10.0-514.6.1.el7.x86_64 #1", (3, 9, ""), True, id="3.10-el7-ge-3.9"
            ),
        ],
    )
    def test_080_kversion_check(self, kversion, min_version, expected_result) -> None:
        """Test check for the minimum kernel version"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        assert (
            analyser._check_kversion_greater_equal(kversion, min_version)
            == expected_result
        ), f'Failed to compare kernel version "{kversion}" with minimum version "{min_version}"'

    @pytest.mark.parametrize(
        "zone,order,node,expect_count",
        [
            pytest.param("Normal", 6, 0, 0, id="Normal-order6-node0"),
            pytest.param("Normal", 6, 1, 2, id="Normal-order6-node1"),
            pytest.param("Normal", 6, "free_chunks_total", 2, id="Normal-order6-total"),
            pytest.param("Normal", 0, 0, 1231, id="Normal-order0-node0"),
            pytest.param("Normal", 0, 1, 2245, id="Normal-order0-node1"),
            pytest.param(
                "Normal", 0, "free_chunks_total", 3476, id="Normal-order0-total"
            ),
            pytest.param("DMA", 5, 0, 1, id="DMA-order5-node0"),
            pytest.param("DMA", 5, "free_chunks_total", 1, id="DMA-order5-total"),
            pytest.param("DMA32", 4, 0, 157, id="DMA32-order4-node0"),
            pytest.param("DMA32", 4, "free_chunks_total", 157, id="DMA32-order4-total"),
            pytest.param(
                "Normal", "total_free_kb_per_node", 0, 38260, id="Normal-total_kb-node0"
            ),
            pytest.param(
                "Normal", "total_free_kb_per_node", 1, 50836, id="Normal-total_kb-node1"
            ),
        ],
    )
    def test_090_extract_zoneinfo(self, zone, order, node, expect_count) -> None:
        """Test extracting zone usage information"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        assert analyser.oom_result.kconfig.release == (
            3,
            10,
            ".el7.",
        ), "Wrong KernelConfig release"
        buddyinfo = analyser.oom_result.buddyinfo
        assert zone in buddyinfo, f"Missing details for zone {zone} in buddy info"
        assert (
            order in buddyinfo[zone]
        ), f'Missing details for order "{order}" in buddy info'
        count = buddyinfo[zone][order][node]
        assert (
            count == expect_count
        ), f'Wrong chunk count for order {order} in zone "{zone}" for node "{node}" (got: {count}, expect {expect_count})'

    @pytest.mark.parametrize(
        "zone,node,level_name,expect_level",
        [
            pytest.param("Normal", 0, "free", 36692, id="Normal-node0-free"),
            pytest.param("Normal", 0, "min", 36784, id="Normal-node0-min"),
            pytest.param("Normal", 1, "low", 56804, id="Normal-node1-low"),
            pytest.param("Normal", 1, "high", 68164, id="Normal-node1-high"),
            pytest.param("DMA", 0, "free", 15872, id="DMA-node0-free"),
            pytest.param("DMA", 0, "high", 60, id="DMA-node0-high"),
            pytest.param("DMA32", 0, "free", 59728, id="DMA32-node0-free"),
            pytest.param("DMA32", 0, "low", 9788, id="DMA32-node0-low"),
        ],
    )
    def test_100_extract_zoneinfo(self, zone, node, level_name, expect_level) -> None:
        """Test extracting watermark information"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        assert analyser.oom_result.kconfig.release == (
            3,
            10,
            ".el7.",
        ), "Wrong KernelConfig release"
        watermarks = analyser.oom_result.watermarks
        assert (
            zone in watermarks
        ), f"Missing details for zone {zone} in memory watermarks"
        assert (
            node in watermarks[zone]
        ), f'Missing details for node "{node}" in memory watermarks'
        assert (
            level_name in watermarks[zone][node]
        ), f'Missing details for level "{level_name}" in memory watermarks'
        level = watermarks[zone][node][level_name]
        assert (
            level == expect_level
        ), f'Wrong watermark level for node {node} in zone "{zone}" (got: {level}, expect {expect_level})'
        numa_node = analyser.oom_result.details["trigger_proc_numa_node"]
        assert (
            numa_node == 0
        ), f"Wrong node with memory shortage (got: {numa_node}, expect: 0)"

    def test_105_max_order(self):
        """Check that the kernel configuration MAX_ORDER matches the expected value."""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        assert analyser.oom_result.kconfig.MAX_ORDER == 11, (
            f"Unexpected number of chunk sizes (got: {analyser.oom_result.kconfig.MAX_ORDER}, "
            f"expect: 11 (kernel 6.2.0))"
        )

    @pytest.mark.parametrize(
        "zone,order,node,expected_result",
        [
            pytest.param("DMA", 0, 0, True, id="DMA-order0-node0"),
            pytest.param("DMA", 6, 0, True, id="DMA-order6-node0"),
            pytest.param("DMA32", 0, 0, True, id="DMA32-order0-node0"),
            pytest.param("DMA32", 10, 0, False, id="DMA32-order10-node0"),
            pytest.param("Normal", 0, 0, True, id="Normal-order0-node0"),
            pytest.param("Normal", 0, 1, True, id="Normal-order0-node1"),
            pytest.param("Normal", 6, 0, False, id="Normal-order6-node0"),
            pytest.param("Normal", 6, 1, True, id="Normal-order6-node1"),
            pytest.param("Normal", 7, 0, False, id="Normal-order7-node0"),
            pytest.param("Normal", 7, 1, True, id="Normal-order7-node1"),
            pytest.param("Normal", 9, 0, False, id="Normal-order9-node0"),
            pytest.param("Normal", 9, 1, False, id="Normal-order9-node1"),
        ],
    )
    def test_110a_check_free_chunks(self, zone, order, node, expected_result) -> None:
        """Test checking for free memory chunks"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        assert (
            analyser.oom_result.oom_type == OOMAnalyser.OOMType.KERNEL_AUTOMATIC
        ), "OOM triggered manually"
        assert analyser.oom_result.buddyinfo, "Missing buddyinfo"
        assert (
            "trigger_proc_order" in analyser.oom_result.details
            and "trigger_proc_mem_zone" in analyser.oom_result.details
        ), "Missing trigger_proc_order and/or trigger_proc_mem_zone"
        assert analyser.oom_result.watermarks, "Missing watermark information"

        result = analyser._check_free_chunks(order, zone, node)
        assert result == expected_result, (
            f"Wrong result of the check for free chunks with the same or higher order for Node {node}, "
            f'Zone "{zone}" and order {order} (got: {result}, expected {expected_result})'
        )

    @pytest.mark.parametrize(
        "zone,expected_node",
        [
            pytest.param("DMA", None, id="DMA"),
            pytest.param("DMA32", None, id="DMA32"),
            pytest.param("Normal", 0, id="Normal"),
        ],
    )
    def test_110b_search_node_with_memory_shortage(self, zone, expected_node) -> None:
        """Test searching for node with memory shortage"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        assert (
            analyser.oom_result.oom_type == OOMAnalyser.OOMType.KERNEL_AUTOMATIC
        ), "OOM triggered manually"
        assert analyser.oom_result.buddyinfo, "Missing buddyinfo"
        assert (
            "trigger_proc_order" in analyser.oom_result.details
            and "trigger_proc_mem_zone" in analyser.oom_result.details
        ), "Missing trigger_proc_order and/or trigger_proc_mem_zone"
        assert analyser.oom_result.watermarks, "Missing watermark information"

        # override zone with test data and trigger extracting node
        analyser.oom_result.details["trigger_proc_mem_zone"] = zone
        analyser._search_node_with_memory_shortage()
        node = analyser.oom_result.details["trigger_proc_numa_node"]
        assert node == expected_node, (
            f'Wrong result if a node has memory shortage in zone "{zone}" (got: {node}, '
            f"expected {expected_node})"
        )

        assert (
            analyser.oom_result.mem_alloc_failure
            == OOMAnalyser.OOMAllocationFailureReason.FAILED_BELOW_LOW_WATERMARK
        ), "Unexpected reason why the memory allocation has failed."

    def test_120_fragmentation(self) -> None:
        """Test memory fragmentation"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"
        zone = analyser.oom_result.details["trigger_proc_mem_zone"]
        node = analyser.oom_result.details["trigger_proc_numa_node"]
        mem_fragmented = not analyser._check_free_chunks(
            analyser.oom_result.kconfig.PAGE_ALLOC_COSTLY_ORDER, zone, node
        )
        assert (
            not mem_fragmented
        ), f'Memory of Node {node}, Zone "{zone}" is not fragmented, but reported as fragmented'

    def test_130_page_size(self) -> None:
        """Test determination of the page size"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        assert success, "OOM analysis failed"

        page_size_kb = analyser.oom_result.details["page_size_kb"]
        assert (
            page_size_kb == 4
        ), f"Unexpected page size (got {page_size_kb}, expect: 4)"
        assert (
            analyser.oom_result.details["_page_size_guessed"] == False
        ), "Page size is guessed and not determined"

    @pytest.mark.parametrize(
        "value,expected",
        [
            pytest.param(0, "0 Bytes", id="0-bytes"),
            pytest.param(123, "123 Bytes", id="123-bytes"),
            pytest.param(1234567, "1.2 MB", id="1.2-mb"),
            pytest.param(9876543210, "9.2 GB", id="9.2-gb"),
            pytest.param(12345678901234, "11.2 TB", id="11.2-tb"),
        ],
    )
    def test_014_size_to_human_readable(self, value, expected) -> None:
        """Test convertion of size in bytes to a human-readable value"""
        formatted = OOMAnalyser.OOMDisplay._size_to_human_readable(value)
        assert (
            formatted == expected
        ), f"Unexpected human readable output of size {value} (got {formatted}, expect: {expected})"


@pytest.mark.browser
class TestBroswerArchLinux(BaseInBrowserTests):
    """Test ArchLinux 6.1.1 OOM web page in a browser"""

    # 0x140dca will split into
    #  GFP_HIGHUSER_MOVABLE -> 0x100cca
    #                         (GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN_POISON | __GFP_SKIP_KASAN_UNPOISON)
    #      GFP_HIGHUSER
    #          GFP_USER
    #              __GFP_RECLAIM
    #                   ___GFP_DIRECT_RECLAIM       0x400
    #                   ___GFP_KSWAPD_RECLAIM       0x800
    #              __GFP_IO                          0x40
    #              __GFP_FS                          0x80
    #              __GFP_HARDWALL                0x100000
    #          __GFP_HIGHMEM                         0x02
    #      __GFP_MOVABLE                             0x08
    #      __GFP_SKIP_KASAN_POISON                   0x00
    #      __GFP_SKIP_KASAN_UNPOISON                 0x00
    #  __GFP_COMP                                 0x40000
    #  __GFP_ZERO                                   0x100
    #                                       sum: 0x140dca
    check_results = {
        "gfp_mask": "0x140dca (GFP_HIGHUSER_MOVABLE|__GFP_COMP|__GFP_ZERO)",
        "proc_name": "doxygen",
        "proc_pid": "473206",
        "swap_cache_kb": "99452 kBytes",
        "swap_used_kb": "25066284 kBytes",
        "swap_free_kb": "84 kBytes",
        "swap_total_kb": "25165820 kBytes",
        "swap_active": "check",
        "mem_node_info_start": "Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 0*64kB",
        "mem_node_info_end": "Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
        "mem_watermarks_start": "Node 0 DMA free:13312kB boost:0kB min:64kB low:80kB",
        "mem_watermarks_end": "lowmem_reserve[]: 0 0 0 0 0",
        "column_header": "Page Table Bytes",
    }
    check_explanation_expected_statements = [
        BaseTests.text_alloc_failed_below_low_watermark,
        BaseTests.text_mem_not_heavily_fragmented,
        BaseTests.text_oom_triggered_automatically,
        BaseTests.text_kernel_swap_space_are_in_use,
    ]
    check_explanation_unexpected_statements = [
        BaseTests.text_alloc_failed_no_free_chunks,
        BaseTests.text_alloc_failed_unknown_reason,
        BaseTests.text_mem_heavily_fragmented,
        BaseTests.text_oom_triggered_manually,
        BaseTests.text_kernel_swap_space_not_in_use,
        BaseTests.text_with_an_oom_score_of,
    ]
    check_results_result_table_expected = [BaseTests.test_kernel_swap_swap_total]
    check_results_result_table_unexpected = [BaseTests.test_kernel_swap_no_space]

    check_explanation_section = {
        "Physical and swap memory": "system has 16461600 kBytes physical memory and 25165820 kBytes system swap space.",
        "Total memory": "That's 41627420 kBytes total.",
        "Use physical memory": "69 % (11513452 kBytes out of 16461600 kBytes) physical memory",
        "Use swap space": "99 % (25066284 kBytes out of 25165820 kBytes) system swap space",
    }

    def test_020_insert_and_analyse_example(self) -> None:
        """Test loading and analysing ArchLinux 6.1.1 example"""
        self.clear_notification_box()
        self.insert_example("ArchLinux")
        self.click_analyse_button()
        self.check_all_results()

    @pytest.mark.parametrize("prefix", LOG_PREFIXES, ids=LOG_PREFIX_IDS)
    def test_030_removal_of_leading_but_useless_columns(self, prefix: str) -> None:
        """
        Test removal of leading but useless columns with an ArchLinux example

        In this test, the lines of the "Mem-Info:" block are joined
        together with #012 to form a single line. Therefore, the prefix
        test must handle the additional leading spaces in these lines.
        The selected example tests this behavior.

        @see: TestRhel7.test_030_removal_of_leading_but_useless_columns()
        """
        self.analyse_oom(OOMAnalyser.OOMDisplay.example_archlinux_6_1_1)
        self.check_all_results()
        self.click_reset_button()

        lines = OOMAnalyser.OOMDisplay.example_archlinux_6_1_1.split("\n")
        new_lines = []
        for line in lines:
            if OOMAnalyser.OOMEntity.REC_MEMINFO_BLOCK_SECOND_PART.search(line):
                new_line = f'{" " * len(prefix)}{line}'
            else:
                new_line = f"{prefix}{line}"
            new_lines.append(new_line)
        oom_text = "\n".join(new_lines)
        self.analyse_oom(oom_text)
        self.check_all_results()
        self.click_reset_button()


@pytest.mark.browser
class TestBrowserRhel7(BaseInBrowserTests):
    """Test RHEL7 OOM web page in a browser"""

    # 0x201da will split into
    #  GFP_HIGHUSER_MOVABLE   0x200da
    #                         (__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM | __GFP_MOVABLE)
    #    __GFP_WAIT              0x10
    #    __GFP_IO                0x40
    #    __GFP_FS                0x80
    #    __GFP_HARDWALL       0x20000
    #    __GFP_HIGHMEM           0x02
    #    __GFP_MOVABLE           0x08
    #  __GFP_COLD               0x100
    #                    sum: 0x201da
    check_results = {
        "gfp_mask": "0x201da (GFP_HIGHUSER_MOVABLE | __GFP_COLD)",
        "proc_name": "sed",
        "proc_pid": "29481",
        "killed_proc_score": "651",
        "swap_cache_kb": "45368 kBytes",
        "swap_used_kb": "8343236 kBytes",
        "swap_free_kb": "0 kBytes",
        "swap_total_kb": "8388604 kBytes",
        "swap_active": "check",
        "mem_node_info_start": "Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 2*64kB",
        "mem_node_info_end": "Node 1 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
        "mem_watermarks_start": "Node 0 DMA free:15872kB min:40kB low:48kB high:60kB",
        "mem_watermarks_end": "lowmem_reserve[]: 0 0 0 0",
        "column_header": "Page Table Entries",
    }
    check_explanation_expected_statements = [
        BaseTests.text_alloc_failed_below_low_watermark,
        BaseTests.text_mem_not_heavily_fragmented,
        BaseTests.text_oom_triggered_automatically,
        BaseTests.text_kernel_swap_space_are_in_use,
        BaseTests.text_with_an_oom_score_of,
    ]
    check_explanation_unexpected_statements = [
        BaseTests.text_alloc_failed_no_free_chunks,
        BaseTests.text_alloc_failed_unknown_reason,
        BaseTests.text_mem_heavily_fragmented,
        BaseTests.text_oom_triggered_manually,
        BaseTests.text_kernel_swap_space_not_in_use,
    ]
    check_results_result_table_expected = [BaseTests.test_kernel_swap_swap_total]
    check_results_result_table_unexpected = [BaseTests.test_kernel_swap_no_space]

    check_explanation_section = {
        "Physical and swap memory": "system has 33519336 kBytes physical memory and 8388604 kBytes system swap space.",
        "Total memory": "That's 41907940 kBytes total.",
        "Use physical memory": "94 % (31705788 kBytes out of 33519336 kBytes) physical memory",
        "Use swap space": "99 % (8343236 kBytes out of 8388604 kBytes) system swap space",
    }

    def test_020_insert_and_analyse_example(self) -> None:
        """Test loading and analysing RHEL7 example"""
        self.clear_notification_box()
        self.insert_example("RHEL7")
        self.click_analyse_button()
        self.check_all_results()

    @pytest.mark.parametrize("prefix", LOG_PREFIXES, ids=LOG_PREFIX_IDS)
    def test_030_removal_of_leading_but_useless_columns(self, prefix: str) -> None:
        """
        Test removal of leading but useless columns with RHEL7 example

        In this test, the lines of the "Mem-Info:" block are joined
        together with #012 to form a single line. Therefore, the prefix
        test must handle the additional leading spaces in these lines.
        The selected example tests this behavior.

        @see: TestArchLinux.test_030_removal_of_leading_but_useless_columns()
        """
        self.analyse_oom(OOMAnalyser.OOMDisplay.example_rhel7)
        self.check_all_results()
        self.click_reset_button()

        lines = OOMAnalyser.OOMDisplay.example_rhel7.split("\n")
        lines = [f"{prefix}{line}" for line in lines]
        oom_text = "\n".join(lines)
        self.analyse_oom(oom_text)
        self.check_all_results()
        self.click_reset_button()

    @pytest.mark.parametrize(
        "prefix",
        [
            pytest.param(
                "Apr 01 14:13:32 mysrv <kern.warning> kernel:", id="syslog-warning"
            ),
            pytest.param("[1234567.654321]", id="timestamp-only"),
        ],
    )
    def test_040_loading_journalctl_input(self, prefix: str) -> None:
        """Test loading input from journalctl

        The second part of the "Mem-Info:" block as starting with the third
        line has not a prefix like the lines before and after it. It is
        indented only by a single space.
        """
        # prepare example
        example_lines = OOMAnalyser.OOMDisplay.example_rhel7.split("\n")
        res = []

        # unescape #012 - see OOMAnalyser.OOMEntity._rsyslog_unescape_lf()
        for line in example_lines:
            if "#012" in line:
                res.extend(line.split("#012"))
            else:
                res.append(line)
        example_lines = res
        res = []

        # add date/time prefix except for "Mem-Info:" block
        for line in example_lines:
            if not OOMAnalyser.OOMEntity.REC_MEMINFO_BLOCK_SECOND_PART.search(line):
                line = f"{prefix} {line}"
            res.append(line)
        example = "\n".join(res)

        self.check_meminfo_format_rhel7(
            f'Unprocessed example with prefix "{prefix}"', example
        )
        oom = OOMAnalyser.OOMEntity(example)
        self.check_meminfo_format_rhel7(
            f'Processed example after OOMEntity() with prefix "{prefix}"', oom.text
        )

        self.analyse_oom(example)
        self.check_all_results()
        self.click_reset_button()

    def test_050_trigger_proc_space(self) -> None:
        """Test trigger process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("sed", "VM Monitoring Task")

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be displayed"

    def test_060_kill_proc_space(self) -> None:
        """Test killed process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("mysqld", "VM Monitoring Task")

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        assert (
            h3_summary.is_displayed()
        ), "Analysis details incl. <h3>Summary</h3> should be displayed"

    def test_070_manually_triggered_OOM(self) -> None:
        """Test for manually triggered OOM"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("order=0", "order=-1")
        self.analyse_oom(example)
        self.assert_on_warn_error()

        explanation = self.driver.find_element(By.ID, "explanation")
        continuous_text = self.to_continuous_text(explanation.text)
        assert (
            self.text_oom_triggered_manually in continuous_text
        ), f'Missing statement "{self.text_oom_triggered_manually}"'
        assert (
            self.text_oom_triggered_automatically not in continuous_text
        ), f'Unexpected statement "{self.text_oom_triggered_automatically}"'

    def test_080_swap_deactivated(self) -> None:
        """Test w/o swap or with deactivated swap"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("Total swap = 8388604kB", "Total swap = 0kB")
        self.analyse_oom(example)
        self.assert_on_warn_error()

        self.check_swap_inactive()
        self.click_reset_button()

        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = re.sub(r"\d+ pages in swap cac.*\n*", "", example, re.MULTILINE)
        example = re.sub(r"Swap cache stats.*\n*", "", example)
        example = re.sub(r"Free swap.*\n*", "", example)
        example = re.sub(r"Total swap.*\n*", "", example)

        self.analyse_oom(example)
        self.assert_on_warn_error()
        self.check_swap_inactive()


@pytest.mark.browser
class TestBrowserUbuntu2110(BaseInBrowserTests):
    """Test Ubuntu 21.10 OOM web page in a browser"""

    # 0xcc0 will split into
    #  GFP_KERNEL             (__GFP_RECLAIM | __GFP_IO | __GFP_FS)
    #    __GFP_RECLAIM        (___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM)
    #        ___GFP_DIRECT_RECLAIM   0x400
    #        ___GFP_KSWAPD_RECLAIM   0x800
    #    __GFP_IO                    0x40
    #    __GFP_FS                    0x80
    #                  sum:          0xCC0
    check_results = {
        "gfp_mask": "0xcc0 (GFP_KERNEL)",
        "swap_inactive": "check",
        "mem_node_info_start": "Node 0 DMA: 1*4kB (U) 1*8kB (U) 1*16kB (U) 1*32kB",
        "mem_node_info_end": "Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
        "mem_watermarks_start": "Node 0 DMA free:15036kB min:352kB low:440kB high:528kB",
        "mem_watermarks_end": "lowmem_reserve[]: 0 0 0 0 0",
        "column_header": "Page Table Bytes",
    }
    check_explanation_expected_statements = [
        BaseTests.text_oom_triggered_manually,
        BaseTests.text_kernel_swap_space_not_in_use,
    ]
    check_explanation_unexpected_statements = [
        BaseTests.text_alloc_failed_below_low_watermark,
        BaseTests.text_alloc_failed_no_free_chunks,
        BaseTests.text_alloc_failed_unknown_reason,
        BaseTests.text_mem_heavily_fragmented,
        BaseTests.text_mem_not_heavily_fragmented,
        BaseTests.text_oom_triggered_automatically,
        BaseTests.text_with_an_oom_score_of,
    ]
    check_results_result_table_expected = [BaseTests.test_kernel_swap_no_space]
    check_results_result_table_unexpected = [BaseTests.test_kernel_swap_swap_total]

    check_explanation_section = {
        "Physical and swap memory": "system has 2096632 kBytes physical memory",
        "Use physical memory": "9 % (209520 kBytes out of 2096632 kBytes) physical memory",
    }

    def test_020_insert_and_analyse_example(self) -> None:
        """Test loading and analysing Ubuntu 21.10 example"""
        self.clear_notification_box()
        self.insert_example("Ubuntu_2110")
        self.click_analyse_button()
        self.check_all_results()


@pytest.mark.browser
class TestBrowserProxmoxCgroupOom(BaseInBrowserTests):
    """Test cases for Proxmox Cgroup OOM example"""

    text_oom_triggered_automatically = (
        "The cgroup-local OOM killer was automatically triggered"
    )

    check_explanation_unexpected_statements = [
        BaseTests.text_oom_triggered_manually,
        BaseTests.text_cgroup_swap_activated,
        BaseTests.text_kernel_swap_space_not_in_use,
        BaseTests.text_alloc_failed_below_low_watermark,
        BaseTests.text_alloc_failed_no_free_chunks,
        BaseTests.text_alloc_failed_unknown_reason,
        BaseTests.text_mem_heavily_fragmented,
        BaseTests.text_mem_not_heavily_fragmented,
        BaseTests.text_with_an_oom_score_of,
    ]

    check_explanation_expected_statements = [
        text_oom_triggered_automatically,
        BaseTests.text_cgroup_swap_deactivated,
    ]

    check_explanation_section = {
        "Terminated process": 'The process "php-fpm" (PID 3902942) has been terminated.',
        "Resident memory": "It uses 12781340 kBytes of the resident memory.",
    }

    def test_020_insert_and_analyse_example(self) -> None:
        """Test loading and analysing Proxmox cgroup OOM example"""
        self.clear_notification_box()
        self.insert_example("Proxmox_cgroup_oom")
        self.click_analyse_button()
        self.check_all_results()


# Tests are now run using pytest
# Run with: pytest test.py
