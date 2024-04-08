# Unit tests for OOMAnalyser
#
# Copyright (c) 2021-2024 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

import http.server
import os
import re
import socketserver
import threading
import unittest

from selenium.webdriver.support.ui import Select
from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import warnings

import OOMAnalyser


class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server, directory=None):
        self.directory = os.getcwd()
        super().__init__(request, client_address, server)

    # suppress all HTTP request messages
    def log_message(self, format, *args):
        # super().log_message(format, *args)
        pass


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class TestBase(unittest.TestCase):
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

    text_swap_space_not_in_use = "physical memory and no swap space"
    text_swap_space_are_in_use = "swap space are in use"
    test_swap_no_space = "No swap space available"
    test_swap_swap_total = "Swap Total"

    text_with_an_oom_score_of = "with an OOM score of"

    def get_lines(self, text, count):
        """
        Return the number of lines specified by count from given text

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

    def get_first_line(self, text):
        """
        Return the first line of the given text
        @type text: str
        """
        return self.get_lines(text, 1)

    def get_last_line(self, text):
        """
        Return the last line of the given text
        @type text: str
        """
        return self.get_lines(text, -1)

    def check_meminfo_format_rhel7(self, prefix, oom_text):
        """
        Check if the example contains a proper formatted "Mem-Info:" block

        @param str prefix: Prefix for error message
        @param str oom_text: Whole OOM block as text

        @see: OOMAnalyser.OOMDisplay.example_rhel7
        """
        found = False
        for line in oom_text.split("\n"):
            if "active_file:1263 " in line:
                found = True
                self.assertTrue(
                    line.startswith(" active_file:1263 "),
                    f'{prefix}: Unexpected prefix for third "Mem-Info:" block line: >>>{line}<<<',
                )
        self.assertTrue(
            found,
            f'{prefix}: Missing content "active_file:1263 " in "Mem-Info:" block of\n{oom_text}',
        )


class TestInBrowser(TestBase):
    """Test OOM web page in a browser"""

    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)

        ThreadedTCPServer.allow_reuse_address = True
        self.httpd = ThreadedTCPServer(("127.0.0.1", 8000), MyRequestHandler)
        server_thread = threading.Thread(target=self.httpd.serve_forever, args=(0.1,))
        server_thread.daemon = True
        server_thread.start()

        # silent Webdriver Manager
        os.environ["WDM_LOG_LEVEL"] = "0"

        # store driver locally
        os.environ["WDM_LOCAL"] = "1"

        s = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=s)
        self.driver.get("http://127.0.0.1:8000/OOMAnalyser.html")

    def tearDown(self):
        self.driver.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def assert_on_warn(self):
        notify_box = self.driver.find_element(By.ID, "notify_box")
        try:
            warning = notify_box.find_element(
                By.CLASS_NAME, "js-notify_box__msg--warning"
            )
        except NoSuchElementException:
            pass
        else:
            self.fail('Unexpected warning message: "%s"' % warning.text)

    def assert_on_error(self):
        error = self.get_first_error_msg()
        if error:
            self.fail('Unexpected error message: "%s"' % error)

        for event in self.driver.get_log("browser"):
            # ignore favicon.ico errors
            if "favicon.ico" in event["message"]:
                continue
            self.fail('Error on browser console reported: "%s"' % event)

    def assert_on_warn_error(self):
        self.assert_on_warn()
        self.assert_on_error()

    def click_analyse_button(self):
        analyse = self.driver.find_element(
            By.XPATH, '//button[text()="Analyse OOM block"]'
        )
        analyse.click()

    def click_reset_button(self):
        reset = self.driver.find_element(By.XPATH, '//button[text()="Reset form"]')
        if reset.is_displayed():
            reset.click()
        else:
            new_analysis = self.driver.find_element(
                By.XPATH, '//a[contains(text(), "Step 1 - Enter your OOM message")]'
            )
            new_analysis.click()
        self.assert_on_warn_error()

    def get_first_error_msg(self):
        """
        Return first (oldest) error message from error notification box or an empty
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
        return notify_box.text

    def insert_example(self, select_value):
        """
        Select and insert example from the combobox

        @param str select_value: Option value to specify the example
        """
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        self.assertEqual(textarea.get_attribute("value"), "", "Empty textarea expected")
        select_element = self.driver.find_element(By.ID, "examples")
        select = Select(select_element)
        option_values = [o.get_attribute("value") for o in select.options]
        self.assertTrue(
            select_value in option_values,
            "Missing proper option for example %s" % select_value,
        )
        select.select_by_value(select_value)
        self.assertNotEqual(
            textarea.get_attribute("value"), "", "Missing OOM text in textarea"
        )
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be not displayed",
        )

    def analyse_oom(self, text):
        """
        Insert text and run analysis

        :param str text: OOM text to analyse
        """
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        self.assertEqual(textarea.get_attribute("value"), "", "Empty textarea expected")
        textarea.send_keys(text)

        self.assertNotEqual(
            textarea.get_attribute("value"), "", "Missing OOM text in textarea"
        )

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be not displayed",
        )

        self.click_analyse_button()

    def check_results_archlinux_6_1_1(self):
        """Check the results of the analysis of the ArchLinux 6.1.1 example"""
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be displayed",
        )
        trigger_proc_name = self.driver.find_element(By.CLASS_NAME, "trigger_proc_name")
        self.assertEqual(
            trigger_proc_name.text, "doxygen", "Unexpected trigger process name"
        )
        trigger_proc_pid = self.driver.find_element(By.CLASS_NAME, "trigger_proc_pid")
        self.assertEqual(
            trigger_proc_pid.text,
            "473206",
            "Unexpected trigger process pid: --%s--" % trigger_proc_pid.text,
        )
        trigger_proc_gfp_mask = self.driver.find_element(
            By.CLASS_NAME, "trigger_proc_gfp_mask"
        )
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
        self.assertEqual(
            trigger_proc_gfp_mask.text,
            "0x140dca (GFP_HIGHUSER_MOVABLE|__GFP_COMP|__GFP_ZERO)",
            "Unexpected GFP Mask",
        )

        killed_proc_score = self.driver.find_element(By.CLASS_NAME, "killed_proc_score")
        self.assertTrue(
            not killed_proc_score.text,
            "Unexpected statement for OOM score of killed process",
        )

        swap_cache_kb = self.driver.find_element(By.CLASS_NAME, "swap_cache_kb")
        self.assertEqual(swap_cache_kb.text, "99452 kBytes")
        swap_used_kb = self.driver.find_element(By.CLASS_NAME, "swap_used_kb")
        self.assertEqual(swap_used_kb.text, "25066284 kBytes")
        swap_free_kb = self.driver.find_element(By.CLASS_NAME, "swap_free_kb")
        self.assertEqual(swap_free_kb.text, "84 kBytes")
        swap_total_kb = self.driver.find_element(By.CLASS_NAME, "swap_total_kb")
        self.assertEqual(swap_total_kb.text, "25165820 kBytes")

        explanation = self.driver.find_element(By.ID, "explanation")
        for expected in [
            self.text_alloc_failed_below_low_watermark,
            self.text_mem_not_heavily_fragmented,
            self.text_oom_triggered_automatically,
            self.text_swap_space_are_in_use,
        ]:
            self.assertTrue(
                expected in explanation.text,
                'Missing statement in OOM summary: "%s"' % expected,
            )
        for unexpected in [
            self.text_alloc_failed_no_free_chunks,
            self.text_alloc_failed_unknown_reason,
            self.text_mem_heavily_fragmented,
            self.text_oom_triggered_manually,
            self.text_swap_space_not_in_use,
            self.text_with_an_oom_score_of,
        ]:
            self.assertTrue(
                unexpected not in explanation.text,
                'Unexpected statement in OOM summary: "%s"' % unexpected,
            )

        result_table = self.driver.find_element(By.CLASS_NAME, "result__table")
        for expected in [
            self.test_swap_swap_total,
        ]:
            self.assertTrue(
                expected in result_table.text,
                'Missing statement in result table: "%s"' % expected,
            )
        for unexpected in [
            self.test_swap_no_space,
        ]:
            self.assertTrue(
                unexpected not in result_table.text,
                'Unexpected statement in result table: "%s"' % unexpected,
            )

        self.assertTrue(
            "system has 16461600 kBytes physical memory and 25165820 kBytes swap space."
            in explanation.text,
            "Physical and swap memory in summary not found",
        )
        self.assertTrue(
            "That's 41627420 kBytes total." in explanation.text,
            "Total memory in summary not found",
        )
        self.assertTrue(
            "69 % (11513452 kBytes out of 16461600 kBytes) physical memory"
            in explanation.text,
            "Used physical memory in summary not found",
        )
        self.assertTrue(
            "99 % (25066284 kBytes out of 25165820 kBytes) swap space"
            in explanation.text,
            "Used swap space in summary not found",
        )

        mem_node_info = self.driver.find_element(By.CLASS_NAME, "mem_node_info")
        self.assertEqual(
            mem_node_info.text[:44],
            "Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 0*64kB",
            "Unexpected memory chunks",
        )
        self.assertEqual(
            mem_node_info.text[-80:],
            "Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
            "Unexpected memory information about hugepages",
        )

        mem_watermarks = self.driver.find_element(By.CLASS_NAME, "mem_watermarks")
        self.assertEqual(
            mem_watermarks.text[:51],
            "Node 0 DMA free:13312kB boost:0kB min:64kB low:80kB",
            "Unexpected memory watermarks",
        )
        self.assertEqual(
            mem_watermarks.text[-27:],
            "lowmem_reserve[]: 0 0 0 0 0",
            "Unexpected lowmem_reserve values",
        )

        header = self.driver.find_element(By.ID, "pstable_header")
        self.assertTrue(
            "Page Table Bytes" in header.text,
            'Missing column header "Page Table Bytes"',
        )

        self.check_swap_active()

    def check_results_rhel7(self):
        """Check the results of the analysis of the RHEL7 example"""
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be displayed",
        )

        trigger_proc_name = self.driver.find_element(By.CLASS_NAME, "trigger_proc_name")
        self.assertEqual(
            trigger_proc_name.text, "sed", "Unexpected trigger process name"
        )
        trigger_proc_pid = self.driver.find_element(By.CLASS_NAME, "trigger_proc_pid")
        self.assertEqual(
            trigger_proc_pid.text, "29481", "Unexpected trigger process pid"
        )
        trigger_proc_gfp_mask = self.driver.find_element(
            By.CLASS_NAME, "trigger_proc_gfp_mask"
        )
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
        self.assertEqual(
            trigger_proc_gfp_mask.text,
            "0x201da (GFP_HIGHUSER_MOVABLE | __GFP_COLD)",
            "Unexpected GFP Mask",
        )

        killed_proc_score = self.driver.find_element(By.CLASS_NAME, "killed_proc_score")
        self.assertEqual(
            killed_proc_score.text, "651", "Unexpected OOM score of killed process"
        )

        swap_cache_kb = self.driver.find_element(By.CLASS_NAME, "swap_cache_kb")
        self.assertEqual(swap_cache_kb.text, "45368 kBytes")
        swap_used_kb = self.driver.find_element(By.CLASS_NAME, "swap_used_kb")
        self.assertEqual(swap_used_kb.text, "8343236 kBytes")
        swap_free_kb = self.driver.find_element(By.CLASS_NAME, "swap_free_kb")
        self.assertEqual(swap_free_kb.text, "0 kBytes")
        swap_total_kb = self.driver.find_element(By.CLASS_NAME, "swap_total_kb")
        self.assertEqual(swap_total_kb.text, "8388604 kBytes")

        explanation = self.driver.find_element(By.ID, "explanation")
        for expected in [
            self.text_alloc_failed_below_low_watermark,
            self.text_mem_not_heavily_fragmented,
            self.text_oom_triggered_automatically,
            self.text_swap_space_are_in_use,
            self.text_with_an_oom_score_of,
        ]:
            self.assertTrue(
                expected in explanation.text,
                'Missing statement in OOM summary: "%s"' % expected,
            )
        for unexpected in [
            self.text_alloc_failed_no_free_chunks,
            self.text_alloc_failed_unknown_reason,
            self.text_mem_heavily_fragmented,
            self.text_oom_triggered_manually,
            self.text_swap_space_not_in_use,
        ]:
            self.assertTrue(
                unexpected not in explanation.text,
                'Unexpected statement in OOM summary: "%s"' % unexpected,
            )

        result_table = self.driver.find_element(By.CLASS_NAME, "result__table")
        for expected in [
            self.test_swap_swap_total,
        ]:
            self.assertTrue(
                expected in result_table.text,
                'Missing statement in result table: "%s"' % expected,
            )
        for unexpected in [
            self.test_swap_no_space,
        ]:
            self.assertTrue(
                unexpected not in result_table.text,
                'Unexpected statement in result table: "%s"' % unexpected,
            )

        self.assertTrue(
            "system has 33519336 kBytes physical memory and 8388604 kBytes swap space."
            in explanation.text,
            "Physical and swap memory in summary not found",
        )
        self.assertTrue(
            "That's 41907940 kBytes total." in explanation.text,
            "Total memory in summary not found",
        )
        self.assertTrue(
            "94 % (31705788 kBytes out of 33519336 kBytes) physical memory"
            in explanation.text,
            "Used physical memory in summary not found",
        )
        self.assertTrue(
            "99 % (8343236 kBytes out of 8388604 kBytes) swap space"
            in explanation.text,
            "Used swap space in summary not found",
        )

        mem_node_info = self.driver.find_element(By.CLASS_NAME, "mem_node_info")
        self.assertEqual(
            mem_node_info.text[:44],
            "Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 2*64kB",
            "Unexpected memory chunks",
        )
        self.assertEqual(
            mem_node_info.text[-80:],
            "Node 1 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
            "Unexpected memory information about hugepages",
        )

        mem_watermarks = self.driver.find_element(By.CLASS_NAME, "mem_watermarks")
        self.assertEqual(
            mem_watermarks.text[:51],
            "Node 0 DMA free:15872kB min:40kB low:48kB high:60kB",
            "Unexpected memory watermarks",
        )
        self.assertEqual(
            mem_watermarks.text[-25:],
            "lowmem_reserve[]: 0 0 0 0",
            "Unexpected lowmem_reserve values",
        )

        header = self.driver.find_element(By.ID, "pstable_header")
        self.assertTrue(
            "Page Table Entries" in header.text,
            'Missing column header "Page Table Entries"',
        )

        self.check_swap_active()

    def check_results_ubuntu2110(self):
        """Check the results of the analysis of the Ubuntu example"""
        trigger_proc_gfp_mask = self.driver.find_element(
            By.CLASS_NAME, "trigger_proc_gfp_mask"
        )
        # 0xcc0 will split into
        #  GFP_KERNEL             (__GFP_RECLAIM | __GFP_IO | __GFP_FS)
        #    __GFP_RECLAIM        (___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM)
        #        ___GFP_DIRECT_RECLAIM   0x400
        #        ___GFP_KSWAPD_RECLAIM   0x800
        #    __GFP_IO                    0x40
        #    __GFP_FS                    0x80
        #                  sum:          0xCC0
        self.assertEqual(
            trigger_proc_gfp_mask.text, "0xcc0 (GFP_KERNEL)", "Unexpected GFP Mask"
        )

        dirty_pages = self.driver.find_element(By.CLASS_NAME, "dirty_pages")
        self.assertEqual(
            dirty_pages.text, "633 pages", "Unexpected number of dirty pages"
        )

        ram_pages = self.driver.find_element(By.CLASS_NAME, "ram_pages")
        self.assertEqual(
            ram_pages.text, "524158 pages", "Unexpected number of RAM pages"
        )

        explanation = self.driver.find_element(By.ID, "explanation")
        for expected in [
            self.text_oom_triggered_manually,
            self.text_swap_space_not_in_use,
        ]:
            self.assertTrue(
                expected in explanation.text,
                'Missing statement in OOM summary: "%s"' % expected,
            )
        for unexpected in [
            self.text_alloc_failed_below_low_watermark,
            self.text_alloc_failed_no_free_chunks,
            self.text_alloc_failed_unknown_reason,
            self.text_mem_heavily_fragmented,
            self.text_mem_not_heavily_fragmented,
            self.text_oom_triggered_automatically,
            self.text_with_an_oom_score_of,
        ]:
            self.assertTrue(
                unexpected not in explanation.text,
                'Unexpected statement in OOM summary: "%s"' % unexpected,
            )

        result_table = self.driver.find_element(By.CLASS_NAME, "result__table")
        for expected in [
            self.test_swap_no_space,
        ]:
            self.assertTrue(
                expected in result_table.text,
                'Missing statement in result table: "%s"' % expected,
            )
        for unexpected in [
            self.test_swap_swap_total,
        ]:
            self.assertTrue(
                unexpected not in result_table.text,
                'Unexpected statement in result table: "%s"' % unexpected,
            )

        self.assertTrue(
            "system has 2096632 kBytes physical memory" in explanation.text,
            "Physical memory in summary not found",
        )
        self.assertTrue(
            "9 % (209520 kBytes out of 2096632 kBytes) physical memory"
            in explanation.text,
            "Used physical memory in summary not found",
        )

        mem_node_info = self.driver.find_element(By.CLASS_NAME, "mem_node_info")
        self.assertEqual(
            mem_node_info.text[:49],
            "Node 0 DMA: 1*4kB (U) 1*8kB (U) 1*16kB (U) 1*32kB",
            "Unexpected memory chunks",
        )
        self.assertEqual(
            mem_node_info.text[-80:],
            "Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB",
            "Unexpected memory information about hugepages",
        )

        mem_watermarks = self.driver.find_element(By.CLASS_NAME, "mem_watermarks")
        self.assertEqual(
            mem_watermarks.text[:54],
            "Node 0 DMA free:15036kB min:352kB low:440kB high:528kB",
            "Unexpected memory watermarks",
        )
        self.assertEqual(
            mem_watermarks.text[-27:],
            "lowmem_reserve[]: 0 0 0 0 0",
            "Unexpected lowmem_reserve values",
        )

        header = self.driver.find_element(By.ID, "pstable_header")
        self.assertTrue(
            "Page Table Bytes" in header.text,
            'Missing column header "Page Table Bytes"',
        )

        self.check_swap_inactive()

    def check_swap_inactive(self):
        explanation = self.driver.find_element(By.ID, "explanation")
        self.assertTrue(
            self.text_swap_space_not_in_use in explanation.text,
            'Missing statement "%s"' % self.text_swap_space_not_in_use,
        )
        self.assertTrue(
            self.text_swap_space_are_in_use not in explanation.text,
            'Unexpected statement "%s"' % self.text_swap_space_are_in_use,
        )

    def check_swap_active(self):
        explanation = self.driver.find_element(By.ID, "explanation")
        self.assertTrue(
            self.text_swap_space_are_in_use in explanation.text,
            'Missing statement "%s"' % self.text_swap_space_are_in_use,
        )

    def test_010_load_page(self):
        """Test if the page is loading"""
        assert "OOMAnalyser" in self.driver.title

    def test_020_load_js(self):
        """Test if JS is loaded"""
        elem = self.driver.find_element(By.ID, "version")
        self.assertIsNotNone(elem.text, "Version statement not set - JS not loaded")

    def test_030_insert_and_analyse_rhel7_example(self):
        """Test loading and analysing RHEL7 example"""
        self.insert_example("RHEL7")
        self.click_analyse_button()
        self.check_results_rhel7()

    def test_031_insert_and_analyse_ubuntu_example(self):
        """Test loading and analysing Ubuntu 21.10 example"""
        self.insert_example("Ubuntu_2110")
        self.click_analyse_button()
        self.check_results_ubuntu2110()

    def test_032_insert_and_analyse_archlinux_example(self):
        """Test loading and analysing ArchLinux 6.1.1 example"""
        self.insert_example("ArchLinux")
        self.click_analyse_button()
        self.check_results_archlinux_6_1_1()

    def test_033_empty_textarea(self):
        """Test "Analyse" with empty textarea"""
        textarea = self.driver.find_element(By.ID, "textarea_oom")
        self.assertEqual(textarea.get_attribute("value"), "", "Empty textarea expected")
        # textarea.send_keys(text)

        self.assertEqual(
            textarea.get_attribute("value"),
            "",
            "Expected empty text area, but text found",
        )

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be not displayed",
        )

        self.click_analyse_button()
        self.assertEqual(
            self.get_first_error_msg(),
            "ERROR: Empty OOM text. Please insert an OOM message block.",
        )
        self.click_reset_button()

    def test_034_begin_but_no_end(self):
        """Test incomplete OOM text - just the beginning"""
        example = """\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        """
        self.analyse_oom(example)
        self.assertEqual(
            self.get_first_error_msg(),
            "ERROR: The inserted OOM is incomplete! The initial pattern was "
            "found but not the final.",
        )
        self.click_reset_button()

    def test_035_no_begin_but_end(self):
        """Test incomplete OOM text - just the end"""
        example = """\
Out of memory: Kill process 6576 (java) score 651 or sacrifice child
Killed process 6576 (java) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
        """
        self.analyse_oom(example)
        self.assertEqual(
            self.get_first_error_msg(),
            "ERROR: Failed to extract kernel version from OOM text",
        )
        self.click_reset_button()

    def test_036_loading_journalctl_input(self):
        """Test loading input from journalctl

        The second part of the "Mem-Info:" block as starting with the third
        line has not a prefix like the lines before and after it. It is
        indented only by a single space.
        """
        for prefix in [
            "Apr 01 14:13:32 mysrv <kern.warning> kernel:",
            "[1234567.654321]",
        ]:
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
                if not OOMAnalyser.OOMEntity.REC_MEMINFO_INDENTED_LINES.search(line):
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
            self.check_results_rhel7()
            self.click_reset_button()

    def test_040_trigger_proc_space(self):
        """Test trigger process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("sed", "VM Monitoring Task")

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be displayed",
        )

    def test_050_kill_proc_space(self):
        """Test killed process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("mysqld", "VM Monitoring Task")

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(
            h3_summary.is_displayed(),
            "Analysis details incl. <h3>Summary</h3> should be displayed",
        )

    def test_060_removal_of_leading_but_useless_columns(self):
        """Test removal of leading but useless columns"""
        self.analyse_oom(OOMAnalyser.OOMDisplay.example_rhel7)
        self.check_results_rhel7()
        self.click_reset_button()
        for prefix in [
            "[11686.888109] ",
            "Apr 01 14:13:32 mysrv: ",
            "Apr 01 14:13:32 mysrv kernel: ",
            "Apr 01 14:13:32 mysrv <kern.warning> kernel: ",
            "Apr 01 14:13:32 mysrv kernel: [11686.888109] ",
            "kernel:",
            "Apr 01 14:13:32 mysrv <kern.warning> kernel:",
        ]:
            lines = OOMAnalyser.OOMDisplay.example_rhel7.split("\n")
            lines = ["{}{}".format(prefix, line) for line in lines]
            oom_text = "\n".join(lines)
            self.analyse_oom(oom_text)

            self.check_results_rhel7()
            self.click_reset_button()

    def test_070_manually_triggered_OOM(self):
        """Test for manually triggered OOM"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace("order=0", "order=-1")
        self.analyse_oom(example)
        self.assert_on_warn_error()

        explanation = self.driver.find_element(By.ID, "explanation")
        self.assertTrue(
            self.text_oom_triggered_manually in explanation.text,
            'Missing statement "%s"' % self.text_oom_triggered_manually,
        )
        self.assertTrue(
            self.text_oom_triggered_automatically not in explanation.text,
            'Unexpected statement "%s"' % self.text_oom_triggered_automatically,
        )

    def test_080_swap_deactivated(self):
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


class TestPython(TestBase):
    def test_001_trigger_proc_space(self):
        """Test RE to find name of trigger process"""
        first = self.get_first_line(OOMAnalyser.OOMDisplay.example_rhel7)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN[
            "invoked oom-killer"
        ][0]
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(first)
        self.assertTrue(
            match,
            "Error: re.search('invoked oom-killer') failed for simple process name",
        )

        first = first.replace("sed", "VM Monitoring Task")
        match = rec.search(first)
        self.assertTrue(
            match,
            "Error: re.search('invoked oom-killer') failed for process name with space",
        )

    def test_002_killed_proc_space(self):
        """Test RE to find name of killed process"""
        text = self.get_lines(OOMAnalyser.OOMDisplay.example_rhel7, -2)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN[
            "Process killed by OOM"
        ][0]
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(text)
        self.assertTrue(
            match,
            "Error: re.search('Process killed by OOM') failed for simple process name",
        )

        text = text.replace("sed", "VM Monitoring Task")
        match = rec.search(text)
        self.assertTrue(
            match,
            "Error: re.search('Process killed by OOM') failed for process name with space",
        )

    def test_003_OOMEntity_number_of_columns_to_strip(self):
        """Test stripping useless / leading columns"""
        oom_entity = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        for pos, line in [
            (
                1,
                "[11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
            ),
            (
                5,
                "Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
            ),
            (
                6,
                "Apr 01 14:13:32 mysrv kernel: [11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1",
            ),
        ]:
            to_strip = oom_entity._number_of_columns_to_strip(line)
            self.assertEqual(
                to_strip,
                pos,
                'Calc wrong number of columns to strip for "%s": got: %d, expect: %d'
                % (line, to_strip, pos),
            )

    def test_004_extract_block_from_next_pos(self):
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
        self.assertEqual(text, expected)

    def test_005_extract_kernel_version(self):
        """Test extracting kernel version"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        for text, kversion in [
            (
                "CPU: 0 PID: 19163 Comm: kworker/0:0 Tainted: G           OE     5.4.0-80-lowlatency #90~18.04.1-Ubuntu",
                "5.4.0-80-lowlatency",
            ),
            (
                "CPU: 4 PID: 1 Comm: systemd Not tainted 3.10.0-1062.9.1.el7.x86_64 #1",
                "3.10.0-1062.9.1.el7.x86_64",
            ),
        ]:
            analyser.oom_entity.text = text
            success = analyser._identify_kernel_version()
            self.assertTrue(
                analyser._identify_kernel_version(), analyser.oom_result.error_msg
            )
            self.assertEqual(analyser.oom_result.kversion, kversion)

    def test_006_choosing_kernel_config(self):
        """Test choosing the right kernel configuration"""
        for kcfg, kversion in [
            (
                OOMAnalyser.KernelConfig_5_8(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.13.0-514 #1",
            ),
            (
                OOMAnalyser.KernelConfig_5_8(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.8.0-514 #1",
            ),
            (
                OOMAnalyser.KernelConfig_4_6(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 4.6.0-514 #1",
            ),
            (
                OOMAnalyser.KernelConfig_3_10_EL7(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-1062.9.1.el7.x86_64 #1",
            ),
            (
                OOMAnalyser.KernelConfig_5_4(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.5.1 #1",
            ),
            (
                OOMAnalyser.KernelConfig_5_18(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 5.23.0 #1",
            ),
            (
                OOMAnalyser.KernelConfig_6_1(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 6.12.0 #1",
            ),
            (
                OOMAnalyser.BaseKernelConfig(),
                "CPU: 4 PID: 29481 Comm: sed Not tainted 2.33.0 #1",
            ),
        ]:
            oom = OOMAnalyser.OOMEntity(kversion)
            analyser = OOMAnalyser.OOMAnalyser(oom)
            analyser._identify_kernel_version()
            analyser._choose_kernel_config()
            result = analyser.oom_result.kconfig
            self.assertEqual(
                type(result),
                type(kcfg),
                'Mismatch between expected kernel config "%s" and chosen config "%s" for kernel version "%s"'
                % (type(kcfg), type(result), kversion),
            )

    def test_007_gfp_processing(self):
        """Test processing GFP flags"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.kconfig.release,
            (3, 10, ".el7."),
            "Wrong KernelConfig release",
        )

        for flag, hex_value in [
            ("__GFP_DMA", 0x01),
            ("__GFP_WAIT", 0x10),
            ("__GFP_IO", 0x40),
            ("__GFP_FS", 0x80),
            ("GFP_KERNEL", 0xD0),  # __GFP_WAIT | __GFP_IO | __GFP_FS
            ("__GFP_UNKNOWN", 0x00),  # unknown GFP flag
        ]:
            self.assertEqual(
                analyser.oom_result.kconfig._gfp_flag2decimal(flag),
                hex_value,
                "Invalid decimal value for %s" % flag,
            )

        for hex_value, flags_expected, unknown_expected in [
            (
                "0x01",
                ["__GFP_DMA"],
                0,
            ),
            ("0x05", ["__GFP_DMA", "__GFP_DMA32"], 0),
            (
                "0x5000000",  # 0x1000000 (__GFP_WRITE) + 0x4000000  (no flag - unused)
                ["__GFP_WRITE"],
                0x4000000,
            ),
            ("0x201da", ["GFP_HIGHUSER_MOVABLE", "__GFP_COLD"], 0),
        ]:
            flags_calculated, unknown_calculated = analyser._gfp_hex2flags(hex_value)
            self.assertEqual(
                flags_calculated,
                flags_expected,
                "Invalid flag(s) for hex value %s" % hex_value,
            )
            self.assertEqual(
                unknown_calculated,
                unknown_expected,
                "Invalid remaining / not resolved decimal flag value",
            )

        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_ubuntu2110)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.kconfig.release,
            (5, 8, ""),
            "Wrong KernelConfig release",
        )

        for flag, hex_value in [
            ("__GFP_DMA", 0x01),
            ("__GFP_IO", 0x40),
            ("__GFP_FS", 0x80),
            ("__GFP_UNKNOWN", 0x00),  # unknown GFP flag
        ]:
            self.assertEqual(
                analyser.oom_result.kconfig._gfp_flag2decimal(flag),
                hex_value,
                "Invalid decimal value for %s" % flag,
            )

        for hex_value, flags_expected, unknown_expected in [
            (
                "0x01",
                ["__GFP_DMA"],
                0,
            ),
            ("0x05", ["__GFP_DMA", "__GFP_DMA32"], 0),
            (
                "0x4001000",  # 0x1000 (__GFP_WRITE) + 0x4000000 (no flag - unused)
                ["__GFP_WRITE"],
                0x4000000,
            ),
            (
                "0xCC0",
                ["GFP_KERNEL"],
                0,
            ),
        ]:
            flags_calculated, unknown_calculated = analyser._gfp_hex2flags(hex_value)
            self.assertEqual(
                flags_calculated,
                flags_expected,
                "Invalid flag(s) for hex value %s" % hex_value,
            )
            self.assertEqual(
                unknown_calculated,
                unknown_expected,
                "Invalid remaining / not resolved decimal flag value",
            )

        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_archlinux_6_1_1)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.kconfig.release,
            (6, 1, ""),
            "Wrong KernelConfig release",
        )

        for flag, hex_value in [
            ("__GFP_DMA", 0x01),
            ("__GFP_IO", 0x40),
            ("__GFP_FS", 0x80),
            (
                "GFP_KERNEL",
                0xCC0,
            ),  # (__GFP_RECLAIM (___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM) | __GFP_IO | __GFP_FS)
            ("__GFP_UNKNOWN", 0x00),  # unknown GFP flag
        ]:
            self.assertEqual(
                analyser.oom_result.kconfig._gfp_flag2decimal(flag),
                hex_value,
                "Invalid decimal value for %s" % flag,
            )

        for hex_value, flags_expected, unknown_expected in [
            (
                "0x01",
                ["__GFP_DMA"],
                0,
            ),
            ("0x05", ["__GFP_DMA", "__GFP_DMA32"], 0),
            (
                "0x201000",  # 0x1000 (__GFP_WRITE) + 0x200000 (no flag - unused)
                ["__GFP_WRITE"],
                0x200000,
            ),
            ("0x140dca", ["GFP_HIGHUSER_MOVABLE", "__GFP_COMP", "__GFP_ZERO"], 0),
        ]:
            flags_calculated, unknown_calculated = analyser._gfp_hex2flags(hex_value)
            self.assertEqual(
                flags_calculated,
                flags_expected,
                "Invalid flag(s) for hex value %s" % hex_value,
            )
            self.assertEqual(
                unknown_calculated,
                unknown_expected,
                "Invalid remaining / not resolved decimal flag value",
            )

    def test_008_kversion_check(self):
        """Test check for minimum kernel version"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)

        for kversion, min_version, expected_result in (
            ("5.19-rc6", (5, 16, ""), True),
            ("5.19-rc6", (5, 19, ""), True),
            ("5.19-rc6", (5, 20, ""), False),
            ("5.18.6-arch1-1", (5, 18, ""), True),
            ("5.18.6-arch1-1", (5, 1, ""), True),
            ("5.18.6-arch1-1", (5, 19, ""), False),
            ("5.13.0-1028-aws #31~20.04.1-Ubuntu", (5, 14, ""), False),
            ("5.13.0-1028-aws #31~20.04.1-Ubuntu", (5, 13, ""), True),
            ("5.13.0-1028-aws #31~20.04.1-Ubuntu", (5, 13, "-aws"), True),
            ("5.13.0-1028-aws #31~20.04.1-Ubuntu", (5, 13, "not_in_version"), False),
            ("5.13.0-1028-aws #31~20.04.1-Ubuntu", (5, 12, ""), True),
            ("4.14.288", (5, 0, ""), False),
            ("4.14.288", (4, 14, ""), True),
            ("3.10.0-514.6.1.el7.x86_64 #1", (3, 11, ""), False),
            ("3.10.0-514.6.1.el7.x86_64 #1", (3, 10, ".el7."), True),
            ("3.10.0-514.6.1.el7.x86_64 #1", (3, 10, ""), True),
            ("3.10.0-514.6.1.el7.x86_64 #1", (3, 9, ""), True),
        ):
            self.assertEqual(
                analyser._check_kversion_greater_equal(kversion, min_version),
                expected_result,
                'Failed to compare kernel version "%s" with minimum version "%s"'
                % (kversion, min_version),
            )

    def test_009_extract_zoneinfo(self):
        """Test extracting zone usage information"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.kconfig.release,
            (3, 10, ".el7."),
            "Wrong KernelConfig release",
        )
        buddyinfo = analyser.oom_result.buddyinfo
        for zone, order, node, except_count in [
            ("Normal", 6, 0, 0),  # order 6 - page size 256kB
            ("Normal", 6, 1, 2),  # order 6 - page size 256kB
            ("Normal", 6, "free_chunks_total", 0 + 2),  # order 6 - page size 256kB
            ("Normal", 0, 0, 1231),  # order 0 - page size 4kB
            ("Normal", 0, 1, 2245),  # order 0 - page size 4kB
            ("Normal", 0, "free_chunks_total", 1231 + 2245),  # order 0 - page size 4kB
            ("DMA", 5, 0, 1),  # order 5 - page size 128kB
            ("DMA", 5, "free_chunks_total", 1),  # order 5 - page size 128kB
            ("DMA32", 4, 0, 157),  # order 4 - page size 64k
            ("DMA32", 4, "free_chunks_total", 157),  # order 4 - page size 64k
            ("Normal", "total_free_kb_per_node", 0, 38260),
            ("Normal", "total_free_kb_per_node", 1, 50836),
        ]:
            self.assertTrue(
                zone in buddyinfo, "Missing details for zone %s in buddy info" % zone
            )
            self.assertTrue(
                order in buddyinfo[zone],
                'Missing details for order "%s" in buddy info' % order,
            )
            count = buddyinfo[zone][order][node]
            self.assertTrue(
                count == except_count,
                'Wrong chunk count for order %s in zone "%s" for node "%s" (got: %d, expect %d)'
                % (order, zone, node, count, except_count),
            )

    def test_010_extract_zoneinfo(self):
        """Test extracting watermark information"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.kconfig.release,
            (3, 10, ".el7."),
            "Wrong KernelConfig release",
        )
        watermarks = analyser.oom_result.watermarks
        for zone, node, level, except_level in [
            ("Normal", 0, "free", 36692),
            ("Normal", 0, "min", 36784),
            ("Normal", 1, "low", 56804),
            ("Normal", 1, "high", 68164),
            ("DMA", 0, "free", 15872),
            ("DMA", 0, "high", 60),
            ("DMA32", 0, "free", 59728),
            ("DMA32", 0, "low", 9788),
        ]:
            self.assertTrue(
                zone in watermarks,
                "Missing details for zone %s in memory watermarks" % zone,
            )
            self.assertTrue(
                node in watermarks[zone],
                'Missing details for node "%s" in memory watermarks' % node,
            )
            self.assertTrue(
                level in watermarks[zone][node],
                'Missing details for level "%s" in memory watermarks' % level,
            )
            level = watermarks[zone][node][level]
            self.assertTrue(
                level == except_level,
                'Wrong watermark level for node %s in zone "%s" (got: %d, expect %d)'
                % (node, zone, level, except_level),
            )
        node = analyser.oom_result.details["trigger_proc_numa_node"]
        self.assertTrue(
            node == 0, "Wrong node with memory shortage (got: %s, expect: 0)" % node
        )
        self.assertEqual(
            analyser.oom_result.kconfig.MAX_ORDER,
            11,  # This is a hard coded value as extracted from kernel 6.2.0
            "Unexpected number of chunk sizes (got: %s, expect: 11 (kernel 6.2.0))"
            % analyser.oom_result.kconfig.MAX_ORDER,
        )

    def test_011_alloc_failure(self):
        """Test analysis why the memory allocation could be failed"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        self.assertEqual(
            analyser.oom_result.oom_type,
            OOMAnalyser.OOMEntityType.automatic,
            "OOM triggered manually",
        )
        self.assertTrue(analyser.oom_result.buddyinfo, "Missing buddyinfo")
        self.assertTrue(
            "trigger_proc_order" in analyser.oom_result.details
            and "trigger_proc_mem_zone" in analyser.oom_result.details,
            "Missing trigger_proc_order and/or trigger_proc_mem_zone",
        )
        self.assertTrue(analyser.oom_result.watermarks, "Missing watermark information")

        for zone, order, node, expected_result in [
            ("DMA", 0, 0, True),
            ("DMA", 6, 0, True),
            ("DMA32", 0, 0, True),
            ("DMA32", 10, 0, False),
            ("Normal", 0, 0, True),
            ("Normal", 0, 1, True),
            ("Normal", 6, 0, False),
            ("Normal", 6, 1, True),
            ("Normal", 7, 0, False),
            ("Normal", 7, 1, True),
            ("Normal", 9, 0, False),
            ("Normal", 9, 1, False),
        ]:
            result = analyser._check_free_chunks(order, zone, node)
            self.assertEqual(
                result,
                expected_result,
                "Wrong result of the check for free chunks with the same or higher order for Node %d, "
                'Zone "%s" and order %d (got: %s, expected %s)'
                % (node, zone, order, result, expected_result),
            )

        # Search node with memory shortage: watermark "free" < "min"
        for zone, expected_node in [
            ("DMA", None),
            ("DMA32", None),
            ("Normal", 0),
        ]:
            # override zone with test data and trigger extracting node
            analyser.oom_result.details["trigger_proc_mem_zone"] = zone
            analyser._search_node_with_memory_shortage()
            node = analyser.oom_result.details["trigger_proc_numa_node"]
            self.assertEqual(
                node,
                expected_node,
                'Wrong result if a node has memory shortage in zone "%s" (got: %s, expected %s)'
                % (zone, node, expected_node),
            )

        self.assertEqual(
            analyser.oom_result.mem_alloc_failure,
            OOMAnalyser.OOMMemoryAllocFailureType.failed_below_low_watermark,
            "Unexpected reason why the memory allocation has failed.",
        )

    def test_012_fragmentation(self):
        """Test memory fragmentation"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")
        zone = analyser.oom_result.details["trigger_proc_mem_zone"]
        node = analyser.oom_result.details["trigger_proc_numa_node"]
        mem_fragmented = not analyser._check_free_chunks(
            analyser.oom_result.kconfig.PAGE_ALLOC_COSTLY_ORDER, zone, node
        )
        self.assertFalse(
            mem_fragmented,
            'Memory of Node %d, Zone "%s" is not fragmented, but reported as fragmented'
            % (node, zone),
        )

    def test_013_page_size(self):
        """Test determination of the page size"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        success = analyser.analyse()
        self.assertTrue(success, "OOM analysis failed")

        page_size_kb = analyser.oom_result.details["page_size_kb"]
        self.assertEqual(
            page_size_kb,
            4,
            "Unexpected page size (got %s, expect: 4)" % page_size_kb,
        )
        self.assertEqual(
            analyser.oom_result.details["_page_size_guessed"],
            False,
            "Page size guessed and not determinated",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
