# Unit tests for OOMAnalyser
#
# Copyright (c) 2021-2022 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

import http.server
import os
import re
import socketserver
import threading
import unittest
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
        res = '\n'.join(lines)
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


class TestInBrowser(TestBase):
    """Test OOM web page in a browser"""

    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)

        ThreadedTCPServer.allow_reuse_address = True
        self.httpd = ThreadedTCPServer(('127.0.0.1', 8000), MyRequestHandler)
        server_thread = threading.Thread(target=self.httpd.serve_forever, args=(0.1,))
        server_thread.daemon = True
        server_thread.start()

        # silent Webdriver Manager
        os.environ['WDM_LOG_LEVEL'] = '0'

        # store driver locally
        os.environ['WDM_LOCAL'] = '1'

        s=Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=s)
        self.driver.get("http://127.0.0.1:8000/OOMAnalyser.html")

    def tearDown(self):
        self.driver.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def assert_on_warn(self):
        notify_box = self.driver.find_element(By.ID, 'notify_box')
        try:
            warning = notify_box.find_element(By.CLASS_NAME, 'js-notify_box__msg--warning')
        except NoSuchElementException:
            pass
        else:
            self.fail('Unexpected warning message: "%s"' % warning.text)

    def assert_on_error(self):
        error = self.get_error_text()
        if error:
            self.fail('Unexpected error message: "%s"' % error)

        for event in self.driver.get_log('browser'):
            # ignore favicon.ico errors
            if 'favicon.ico' in event['message']:
                continue
            self.fail('Error on browser console reported: "%s"' % event)

    def assert_on_warn_error(self):
        self.assert_on_warn()
        self.assert_on_error()

    def click_analyse(self):
        analyse = self.driver.find_element(By.XPATH, '//button[text()="Analyse"]')
        analyse.click()

    def get_error_text(self):
        """
        Return text from error notification box or an empty string if no error message exists

        @rtype: str
        """
        notify_box = self.driver.find_element(By.ID, 'notify_box')
        try:
            notify_box.find_element(By.CLASS_NAME, 'js-notify_box__msg--error')
        except NoSuchElementException:
            return ""
        return notify_box.text

    def click_reset(self):
        reset = self.driver.find_element(By.XPATH, '//button[text()="Reset"]')
        if reset.is_displayed():
            reset.click()
        else:
            new_analysis = self.driver.find_element(By.XPATH, '//a[contains(text(), "Step 1 - Enter your OOM message")]')
            new_analysis.click()
        self.assert_on_warn_error()

    def analyse_oom(self, text):
        """
        Insert text and run analysis

        :param str text: OOM text to analyse
        """
        textarea = self.driver.find_element(By.ID, 'textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        textarea.send_keys(text)

        self.assertNotEqual(textarea.get_attribute('value'), '', 'Missing OOM text in textarea')

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()

    def check_results_rhel7(self):
        """Check the results of the analysis of the RHEL7 example"""
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

        trigger_proc_name = self.driver.find_element(By.CLASS_NAME, 'trigger_proc_name')
        self.assertEqual(trigger_proc_name.text, 'sed', 'Unexpected trigger process name')
        trigger_proc_pid = self.driver.find_element(By.CLASS_NAME, 'trigger_proc_pid')
        self.assertEqual(trigger_proc_pid.text, '29481', 'Unexpected trigger process pid')

        killed_proc_score = self.driver.find_element(By.CLASS_NAME, 'killed_proc_score')
        self.assertEqual(killed_proc_score.text, '651', 'Unexpected OOM score of killed process')

        swap_cache_kb = self.driver.find_element(By.CLASS_NAME, 'swap_cache_kb')
        self.assertEqual(swap_cache_kb.text, '45368 kBytes')
        swap_used_kb = self.driver.find_element(By.CLASS_NAME, 'swap_used_kb')
        self.assertEqual(swap_used_kb.text, '8343236 kBytes')
        swap_free_kb = self.driver.find_element(By.CLASS_NAME, 'swap_free_kb')
        self.assertEqual(swap_free_kb.text, '0 kBytes')
        swap_total_kb = self.driver.find_element(By.CLASS_NAME, 'swap_total_kb')
        self.assertEqual(swap_total_kb.text, '8388604 kBytes')

        explanation = self.driver.find_element(By.ID, 'explanation')
        self.assertTrue('OOM killer was automatically triggered' in explanation.text,
                        'Missing text "OOM killer was automatically triggered"')

        head = self.driver.find_element(By.ID, 'pstable_header')
        self.assertTrue('Page Table Entries' in head.text, 'Missing column head line "Page Table Entries"')

        self.check_swap_active()

    def check_results_ubuntu2110(self):
        """Check the results of the analysis of the Ubuntu example"""
        dirty_pages = self.driver.find_element(By.CLASS_NAME, 'dirty_pages')
        self.assertEqual(dirty_pages.text, '633 pages', 'Unexpected number of dirty pages')

        ram_pages = self.driver.find_element(By.CLASS_NAME, 'ram_pages')
        self.assertEqual(ram_pages.text, '524158 pages', 'Unexpected number of RAM pages')

        explanation = self.driver.find_element(By.ID, 'explanation')
        self.assertTrue('OOM killer was manually triggered' in explanation.text,
                        'Missing text "OOM killer was manually triggered"')

        self.assertFalse('with an OOM score of' in explanation.text,
                         'No OOM score but text "with an OOM score of"')

        head = self.driver.find_element(By.ID, 'pstable_header')
        self.assertTrue('Page Table Bytes' in head.text, 'Missing column head line "Page Table Bytes"')

        self.check_swap_inactive()

    def check_swap_inactive(self):
        explanation = self.driver.find_element(By.ID, 'explanation')
        self.assertTrue('physical memory and no swap space' in explanation.text,
                        'Missing text "physical memory and no swap space"')
        self.assertFalse('swap space are in use' in explanation.text,
                         'No swap space but text "swap space are in use"')

    def check_swap_active(self):
        explanation = self.driver.find_element(By.ID, 'explanation')
        self.assertTrue('swap space are in use' in explanation.text,
                        'Swap space active but no text "swap space are in use"')

    def test_010_load_page(self):
        """Test if the page is loading"""
        assert "OOMAnalyser" in self.driver.title

    def test_020_load_js(self):
        """Test if JS is loaded"""
        elem = self.driver.find_element(By.ID, "version")
        self.assertIsNotNone(elem.text, "Version statement not set - JS not loaded")

    def test_030_insert_and_analyse_rhel7_example(self):
        """Test loading and analysing RHEL7 example"""
        textarea = self.driver.find_element(By.ID, 'textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        insert_example = self.driver.find_element(By.XPATH, '//button[contains(text(), "RHEL7" )]')
        insert_example.click()
        self.assertNotEqual(textarea.get_attribute('value'), '', 'Missing OOM text in textarea')

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()
        self.check_results_rhel7()

    def test_031_insert_and_analyse_ubuntu_example(self):
        """Test loading and analysing Ubuntu 21.10 example"""
        textarea = self.driver.find_element(By.ID, 'textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        insert_example = self.driver.find_element(By.XPATH, '//button[contains(text(), "Ubuntu" )]')
        insert_example.click()
        self.assertNotEqual(textarea.get_attribute('value'), '', 'Missing OOM text in textarea')

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()
        self.check_results_ubuntu2110()

    def test_032_empty_textarea(self):
        """Test "Analyse" with empty textarea"""
        textarea = self.driver.find_element(By.ID, 'textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        # textarea.send_keys(text)

        self.assertEqual(textarea.get_attribute('value'), '', 'Expected empty text area, but text found')

        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()
        self.assertEqual(self.get_error_text(), "ERROR: Empty OOM text. Please insert an OOM message block.")
        self.click_reset()

    def test_033_begin_but_no_end(self):
        """Test incomplete OOM text - just the beginning"""
        example = """\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        """
        self.analyse_oom(example)
        self.assertEqual(self.get_error_text(), "ERROR: The inserted OOM is incomplete! The initial pattern was "
                                                "found but not the final.")
        self.click_reset()

    def test_034_no_begin_but_end(self):
        """Test incomplete OOM text - just the end"""
        example = """\
Out of memory: Kill process 6576 (java) score 651 or sacrifice child
Killed process 6576 (java) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
        """
        self.analyse_oom(example)
        self.assertEqual(self.get_error_text(), "ERROR: Failed to extract kernel version from OOM text")
        self.click_reset()

    def test_035_leading_journalctl_input(self):
        """Test loading input from journalctl """
        # prepare example
        example_lines = OOMAnalyser.OOMDisplay.example_rhel7.split('\n')
        res = []

        # unescape #012 - see OOMAnalyser.OOMEntity._rsyslog_unescape_lf()
        for line in example_lines:
            if '#012' in line:
                res.extend(line.split('#012'))
            else:
                res.append(line)
        example_lines = res
        res = []

        # add date/time prefix except for "Mem-Info:" block
        pattern = r'^ (active_file|unevictable|slab_reclaimable|mapped|free):.+$'
        rec = re.compile(pattern)
        for line in example_lines:
            match = rec.search(line)
            if match:
                line = "                                             {}".format(line)
            else:
                line = "Apr 01 14:13:32 mysrv <kern.warning> kernel: {}".format(line)
            res.append(line)
        example = "\n".join(res)

        self.analyse_oom(example)
        self.check_results_rhel7()
        self.click_reset()

    def test_040_trigger_proc_space(self):
        """Test trigger process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace('sed', 'VM Monitoring Task')

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

    def test_050_kill_proc_space(self):
        """Test killed process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace('mysqld', 'VM Monitoring Task')

        self.analyse_oom(example)
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element(By.XPATH, '//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

    def test_060_removal_of_leading_but_useless_columns(self):
        """Test removal of leading but useless columns"""
        self.analyse_oom(OOMAnalyser.OOMDisplay.example_rhel7)
        self.check_results_rhel7()
        self.click_reset()
        for prefix in ["[11686.888109] ",
                       "Apr 01 14:13:32 mysrv: ",
                       "Apr 01 14:13:32 mysrv kernel: ",
                       "Apr 01 14:13:32 mysrv <kern.warning> kernel: ",
                       "Apr 01 14:13:32 mysrv kernel: [11686.888109] ",
                       "kernel:",
                       "Apr 01 14:13:32 mysrv <kern.warning> kernel:",
                       ]:
            lines = OOMAnalyser.OOMDisplay.example_rhel7.split('\n')
            lines = ["{}{}".format(prefix, line) for line in lines]
            oom_text = "\n".join(lines)
            self.analyse_oom(oom_text)

            self.check_results_rhel7()
            self.click_reset()

    def test_070_manually_triggered_OOM(self):
        """Test for manually triggered OOM"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace('order=0', 'order=-1')
        self.analyse_oom(example)
        self.assert_on_warn_error()

        explanation = self.driver.find_element(By.ID, 'explanation')
        self.assertTrue('OOM killer was manually triggered' in explanation.text,
                        'Missing text "OOM killer was manually triggered"')

    def test_080_swap_deactivated(self):
        """Test w/o swap or with deactivated swap"""
        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = example.replace('Total swap = 8388604kB', 'Total swap = 0kB')
        self.analyse_oom(example)
        self.assert_on_warn_error()

        self.check_swap_inactive()
        self.click_reset()

        example = OOMAnalyser.OOMDisplay.example_rhel7
        example = re.sub(r'\d+ pages in swap cac.*\n*', '', example, re.MULTILINE)
        example = re.sub(r'Swap cache stats.*\n*', '', example)
        example = re.sub(r'Free swap.*\n*', '', example)
        example = re.sub(r'Total swap.*\n*', '', example)

        self.analyse_oom(example)
        self.assert_on_warn_error()
        self.check_swap_inactive()


class TestPython(TestBase):

    def test_001_trigger_proc_space(self):
        """Test RE to find name of trigger process"""
        first = self.get_first_line(OOMAnalyser.OOMDisplay.example_rhel7)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN['invoked oom-killer'][0]
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(first)
        self.assertTrue(match, "Error: re.search('invoked oom-killer') failed for simple process name")

        first = first.replace('sed', 'VM Monitoring Task')
        match = rec.search(first)
        self.assertTrue(match, "Error: re.search('invoked oom-killer') failed for process name with space")

    def test_002_killed_proc_space(self):
        """Test RE to find name of killed process"""
        text = self.get_lines(OOMAnalyser.OOMDisplay.example_rhel7, -2)
        pattern = OOMAnalyser.OOMAnalyser.oom_result.kconfig.EXTRACT_PATTERN['Process killed by OOM'][0]
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(text)
        self.assertTrue(match, "Error: re.search('Process killed by OOM') failed for simple process name")

        text = text.replace('sed', 'VM Monitoring Task')
        match = rec.search(text)
        self.assertTrue(match, "Error: re.search('Process killed by OOM') failed for process name with space")

    def test_003_OOMEntity_number_of_columns_to_strip(self):
        """Test stripping useless / leading columns"""
        oom_entity = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        for pos, line in [
            (1, '[11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1'),
            (5, 'Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1'),
            (6, 'Apr 01 14:13:32 mysrv kernel: [11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1'),
        ]:
            to_strip = oom_entity._number_of_columns_to_strip(line)
            self.assertEqual(to_strip, pos, 'Calc wrong number of columns to strip for "%s": got: %d, expect: %d' % (
                line, to_strip, pos))

    def test_004_extract_block_from_next_pos(self):
        """Test extracting a single block (all lines till the next line with a colon)"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        text = analyser._extract_block_from_next_pos('Hardware name:')
        expected = '''\
Hardware name: HP ProLiant DL385 G7, BIOS A18 12/08/2012
 ffff880182272f10 00000000021dcb0a ffff880418207938 ffffffff816861ac
 ffff8804182079c8 ffffffff81681157 ffffffff810eab9c ffff8804182fe910
 ffff8804182fe928 0000000000000202 ffff880182272f10 ffff8804182079b8
'''
        self.assertEqual(text, expected)

    def test_005_extract_kernel_version(self):
        """Test extracting kernel version"""
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example_rhel7)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        for text, kversion in [
            ('CPU: 0 PID: 19163 Comm: kworker/0:0 Tainted: G           OE     5.4.0-80-lowlatency #90~18.04.1-Ubuntu', '5.4.0-80-lowlatency'),
            ('CPU: 4 PID: 1 Comm: systemd Not tainted 3.10.0-1062.9.1.el7.x86_64 #1', '3.10.0-1062.9.1.el7.x86_64'),
        ]:
            analyser.oom_entity.text = text
            success = analyser._identify_kernel_version()
            self.assertTrue(analyser._identify_kernel_version(), analyser.oom_result.error_msg)
            self.assertEqual(analyser.oom_result.kversion, kversion)

    def test_006_choosing_kernel_config(self):
        """Test choosing the right kernel configuration"""
        for kcfg, kversion in [
            (OOMAnalyser.KernelConfig_5_8(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 5.13.0-514 #1'),
            (OOMAnalyser.KernelConfig_5_8(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 5.8.0-514 #1'),
            (OOMAnalyser.KernelConfig_4_6(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 4.6.0-514 #1'),
            (OOMAnalyser.KernelConfigRhel7(), 'CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-1062.9.1.el7.x86_64 #1'),
            (OOMAnalyser.KernelConfig_5_0(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 5.5.1 #1'),
            (OOMAnalyser.KernelConfig_5_8(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 5.23.0 #1'),
            (OOMAnalyser.KernelConfig_5_8(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 6.12.0 #1'),
            (OOMAnalyser.BaseKernelConfig(),  'CPU: 4 PID: 29481 Comm: sed Not tainted 2.33.0 #1'),
        ]:
            oom = OOMAnalyser.OOMEntity(kversion)
            analyser = OOMAnalyser.OOMAnalyser(oom)
            analyser._identify_kernel_version()
            analyser._choose_kernel_config()
            result = analyser.oom_result.kconfig
            self.assertEqual(
                type(result), type(kcfg),
                'Mismatch between expected kernel config "%s" and chosen config "%s" for kernel version "%s"' % (
                    type(kcfg), type(result), kversion
                )
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
