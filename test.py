# Unit tests for OOM Analyser
#
# This software is covered by the MIT License.
#
# Copyright (c) 2021 Carsten Grohmann <mail@carstengrohmann.de>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import http.server
import logging
import os
import socketserver
import threading
import unittest
from selenium import webdriver
from selenium.common.exceptions import *
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
        lines = text.splitlines()[:count]
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

        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        self.driver.get("http://127.0.0.1:8000/OOMAnalyser.html")

    def tearDown(self):
        self.driver.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def assert_on_warn(self):
        notify_box = self.driver.find_element_by_id('notify_box')
        try:
            warning = notify_box.find_element_by_class_name('js-notify_box__msg--warning')
        except NoSuchElementException:
            pass
        else:
            self.fail('Unexpected warning message: %s' % warning.text)

    def assert_on_error(self):
        notify_box = self.driver.find_element_by_id('notify_box')
        try:
            error = notify_box.find_element_by_class_name('js-notify_box__msg--error')
        except NoSuchElementException:
            pass
        else:
            self.fail('Unexpected error message: %s' % error.text)

        for event in self.driver.get_log('browser'):
            # ignore favicon.ico errors
            if 'favicon.ico' in event['message']:
                continue
            self.fail('Error on browser console reported: %s' % event)

    def assert_on_warn_error(self):
        self.assert_on_warn()
        self.assert_on_error()

    def click_analyse(self):
        analyse = self.driver.find_element_by_xpath('//button[text()="Analyse"]')
        analyse.click()

    def click_reset(self):
        # OOMAnalyser.OOMDisplayInstance.reset_form()
        reset = self.driver.find_element_by_xpath('//button[text()="Reset"]')
        if reset.is_displayed():
            reset.click()
        else:
            new_analysis = self.driver.find_element_by_xpath('//a[contains(text(), "Step 1 - Enter your OOM message")]')
            # new_analysis = self.driver.find_element_by_link_text('Run a new analysis')
            new_analysis.click()
        self.assert_on_warn_error()

    def analyse_oom(self, text):
        """
        Insert text and run analysis

        :param str text: OOM text to analyse
        """
        textarea = self.driver.find_element_by_id('textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        textarea.send_keys(text)

        self.assertNotEqual(textarea.get_attribute('value'), '', 'Missing OOM text in textarea')

        h3_summary = self.driver.find_element_by_xpath('//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()

    def check_results(self):
        """Check the results of the analysis of the default example"""
        self.assert_on_warn_error()
        h3_summary = self.driver.find_element_by_xpath('//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

        trigger_proc_name = self.driver.find_element_by_class_name('trigger_proc_name')
        self.assertEqual(trigger_proc_name.text, 'sed', 'Unexpected trigger process name')
        trigger_proc_pid = self.driver.find_element_by_class_name('trigger_proc_pid')
        self.assertEqual(trigger_proc_pid.text, '29481', 'Unexpected trigger process pid')

        killed_proc_score = self.driver.find_element_by_class_name('killed_proc_score')
        self.assertEqual(killed_proc_score.text, '651', 'Unexpected OOM score of killed process')

        swap_cache_kb = self.driver.find_element_by_class_name('swap_cache_kb')
        self.assertEqual(swap_cache_kb.text, '45368 kBytes')
        swap_used_kb = self.driver.find_element_by_class_name('swap_used_kb')
        self.assertEqual(swap_used_kb.text, '8343236 kBytes')
        swap_free_kb = self.driver.find_element_by_class_name('swap_free_kb')
        self.assertEqual(swap_free_kb.text, '0 kBytes')
        swap_total_kb = self.driver.find_element_by_class_name('swap_total_kb')
        self.assertEqual(swap_total_kb.text, '8388604 kBytes')

    def test_001_load_page(self):
        """Test if the page is loading"""
        assert "OOM Analyser" in self.driver.title

    def test_002_load_js(self):
        """Test if JS is loaded"""
        elem = self.driver.find_element_by_id("version")
        self.assertIsNotNone(elem.text, "Version statement not set - JS not loaded")

    def test_003_insert_and_analyse_example(self):
        """Test loading and analysing example"""
        textarea = self.driver.find_element_by_id('textarea_oom')
        self.assertEqual(textarea.get_attribute('value'), '', 'Empty textarea expected')
        insert_example = self.driver.find_element_by_xpath('//button[text()="Insert example"]')
        insert_example.click()
        self.assertNotEqual(textarea.get_attribute('value'), '', 'Missing OOM text in textarea')

        h3_summary = self.driver.find_element_by_xpath('//h3[text()="Summary"]')
        self.assertFalse(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be not displayed")

        self.click_analyse()
        self.check_results()

    def test_004_begin_but_no_end(self):
        """Test incomplete OOM text - just the beginning"""
        example = """\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        """
        self.analyse_oom(example)

        notify_box = self.driver.find_element_by_id('notify_box')
        notify_box.find_element_by_class_name('js-notify_box__msg--warning')
        self.assertTrue(notify_box.text.startswith("WARNING: The inserted OOM is incomplete!"))

        self.click_reset()

    def test_005_no_begin_but_end(self):
        """Test incomplete OOM text - just the end"""
        example = """\
Out of memory: Kill process 6576 (java) score 651 or sacrifice child
Killed process 6576 (java) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
        """
        self.analyse_oom(example)

        notify_box = self.driver.find_element_by_id('notify_box')
        notify_box.find_element_by_class_name('js-notify_box__msg--error')
        self.assertTrue(notify_box.text.startswith("ERROR: The inserted text is not a valid OOM block!"))

        self.click_reset()

    def test_006_trigger_proc_space(self):
        """Test trigger process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example
        example = example.replace('sed', 'VM Monitoring Task')

        self.analyse_oom(example)

        self.assert_on_warn_error()

        h3_summary = self.driver.find_element_by_xpath('//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

    def test_007_kill_proc_space(self):
        """Test killed process name contains a space"""
        example = OOMAnalyser.OOMDisplay.example
        example = example.replace('mysqld', 'VM Monitoring Task')

        self.analyse_oom(example)

        self.assert_on_warn_error()

        h3_summary = self.driver.find_element_by_xpath('//h3[text()="Summary"]')
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

    def test_removal_of_leading_but_useless_columns(self):
        """Test removal of leading but useless columns"""
        self.analyse_oom(OOMAnalyser.OOMDisplay.example)
        self.check_results()
        self.click_reset()
        for prefix in ["[11686.888109] ",
                       "Apr 01 14:13:32 mysrv: ",
                       "Apr 01 14:13:32 mysrv kernel: ",
                       "Apr 01 14:13:32 mysrv <kern.warning> kernel: ",
                       "Apr 01 14:13:32 mysrv kernel: [11686.888109] ",
                       "kernel:",
                       "Apr 01 14:13:32 mysrv <kern.warning> kernel:",
                       ]:
            lines = OOMAnalyser.OOMDisplay.example.split('\n')
            lines = ["{}{}".format(prefix, line) for line in lines]
            oom_text = "\n".join(lines)
            self.analyse_oom(oom_text)

            self.check_results()
            self.click_reset()


class TestPython(TestBase):

    def test_001_trigger_proc_space(self):
        """Test RE to find name of trigger process"""
        first = self.get_first_line(OOMAnalyser.OOMDisplay.example)
        rec = OOMAnalyser.OOMAnalyser.REC_INVOKED_OOMKILLER
        match = rec.search(first)
        self.assertTrue(match, 'Error: re.search(REC_INVOKED_OOMKILLER) failed for simple '
                               'process name')

        first = first.replace('sed', 'VM Monitoring Task')
        match = rec.search(first)
        self.assertTrue(match, 'Error: re.search(REC_INVOKED_OOMKILLER) failed for process name '
                               'with space')

    def test_002_killed_proc_space(self):
        """Test RE to find name of killed process"""
        last = self.get_last_line(OOMAnalyser.OOMDisplay.example)
        rec = OOMAnalyser.OOMAnalyser.REC_OOM_KILL_PROCESS
        match = rec.search(last)
        self.assertTrue(match, 'Error: re.search(REC_OOM_KILL_PROCESS) failed for simple '
                               'process name')

        last = last.replace('sed', 'VM Monitoring Task')
        match = rec.search(last)
        self.assertTrue(match, 'Error: re.search(REC_OOM_KILL_PROCESS) failed for process name '
                               'with space')

    def test_003_OOMEntity_number_of_columns_to_strip(self):
        """Test stripping useless / leading columns"""
        oom_entity = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example)
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
        oom = OOMAnalyser.OOMEntity(OOMAnalyser.OOMDisplay.example)
        analyser = OOMAnalyser.OOMAnalyser(oom)
        text = analyser._extract_block_from_next_pos('Hardware name:')
        expected = '''\
Hardware name: HP ProLiant DL385 G7, BIOS A18 12/08/2012
 ffff880182272f10 00000000021dcb0a ffff880418207938 ffffffff816861ac
 ffff8804182079c8 ffffffff81681157 ffffffff810eab9c ffff8804182fe910
 ffff8804182fe928 0000000000000202 ffff880182272f10 ffff8804182079b8
'''
        self.assertEqual(text, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
