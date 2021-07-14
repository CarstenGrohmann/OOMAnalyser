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


class TestHTTPOOMAnalyser(unittest.TestCase):
    """Test OOM web page"""

    @classmethod
    def setUpClass(cls):
        ThreadedTCPServer.allow_reuse_address = True
        cls.httpd = ThreadedTCPServer(('127.0.0.1', 8000), MyRequestHandler)
        # cls.httpd.allow_reuse_address = True
        server_thread = threading.Thread(target=cls.httpd.serve_forever, args=(0.1,))
        server_thread.daemon = True
        server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.get("http://127.0.0.1:8000/OOMAnalyser.html")

    def tearDown(self):
        self.driver.close()

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

        analyse = self.driver.find_element_by_xpath('//button[text()="Analyse"]')
        analyse.click()

        self.assertTrue(h3_summary.is_displayed(), "Analysis details incl. <h3>Summary</h3> should be displayed")

        trigger_proc_name = self.driver.find_element_by_class_name('trigger_proc_name')
        self.assertEqual(trigger_proc_name.text, 'sed', 'Unexpected trigger process name')
        trigger_proc_pid = self.driver.find_element_by_class_name('trigger_proc_pid')
        self.assertEqual(trigger_proc_pid.text, '29481', 'Unexpected trigger process pid')

        killed_proc_score = self.driver.find_element_by_class_name('killed_proc_score')
        self.assertEqual(killed_proc_score.text, '651', 'Unexpected OOM score of killed process')


if __name__ == "__main__":
    # import logging, sys
    # logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    unittest.main(verbosity=2)
