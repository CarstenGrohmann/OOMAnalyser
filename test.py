# Unit tests for OOM Analyser
#
# This software is covered by the MIT License.
#
# Copyright (c) 2021 Carsten Grohmann <mail@carsten-grohmann.de>
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
import os
import socketserver
import threading
import unittest
from selenium import webdriver
from selenium.common.exceptions import *
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

        self.driver = webdriver.Chrome()
        self.driver.get("http://127.0.0.1:8000/OOMAnalyser.html")

    def tearDown(self):
        self.driver.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def assert_on_warn(self):
        notify_box = self.driver.find_element_by_id('notify_box')
        with self.assertRaises(NoSuchElementException):
            notify_box.find_element_by_class_name('js-notify_box__msg--warning')

    def assert_on_error(self):
        notify_box = self.driver.find_element_by_id('notify_box')
        with self.assertRaises(NoSuchElementException):
            notify_box.find_element_by_class_name('js-notify_box__msg--error')

    def click_analyse(self):
        analyse = self.driver.find_element_by_xpath('//button[text()="Analyse"]')
        analyse.click()

    def click_reset(self):
        reset = self.driver.find_element_by_xpath('//button[text()="Reset"]')
        reset.click()
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

    def assert_on_warn_error(self):
        self.assert_on_warn()
        self.assert_on_error()

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

        self.assert_on_warn_error()
        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

        trigger_proc_name = self.driver.find_element_by_class_name('trigger_proc_name')
        self.assertEqual(trigger_proc_name.text, 'sed', 'Unexpected trigger process name')
        trigger_proc_pid = self.driver.find_element_by_class_name('trigger_proc_pid')
        self.assertEqual(trigger_proc_pid.text, '29481', 'Unexpected trigger process pid')

        killed_proc_score = self.driver.find_element_by_class_name('killed_proc_score')
        self.assertEqual(killed_proc_score.text, '651', 'Unexpected OOM score of killed process')

    def test_004_begin_but_no_end(self):
        """Test incomplete OOM text - just the beginning"""
        example = """\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
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
        pass

    def test_007_kill_proc_space(self):
        """Test killed process name contains a space"""
        pass


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


if __name__ == "__main__":
    # import logging, sys
    # logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    unittest.main(verbosity=2)
