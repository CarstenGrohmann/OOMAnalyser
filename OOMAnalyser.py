# -*- coding: Latin-1 -*-
#
# Linux OOMAnalyser
#
# Copyright (c) 2017-2022 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY
import math
import re

DEBUG = False
"""Show additional information during the development cycle"""

VERSION = "0.5.0 (devel)"
"""Version number"""

# __pragma__ ('skip')
# MOC objects to satisfy statical checker and imports in unit tests
js_undefined = 0


class classList:

    def add(self, *args, **kwargs):
        pass

    def remove(self, *args, **kwargs):
        pass


class document:

    def querySelectorAll(self, *args, **kwargs):
        return [Node()]

    def getElementById(self, *arg, **kwargs):
        return Node()

    def createElementNS(self, *arg, **kwargs):
        return Node()

    def createElement(self, *args, **kwargs):
        return Node()


class Node:

    classList = classList()
    offsetWidth = 0
    textContent = ""

    def __init__(self, nr_children=1):
        self.nr_children = nr_children

    @property
    def firstChild(self):
        if self.nr_children:
            self.nr_children -= 1
            return Node(self.nr_children)
        else:
            return None

    def removeChild(self, *args, **kwargs):
        return

    def appendChild(self, *args, **kwargs):
        return

    def setAttribute(self, *args, **kwargs):
        return
# __pragma__ ('noskip')


class OOMEntityState:
    """Enum for completeness of the OOM block"""
    unknown = 0
    empty = 1
    invalid = 2
    started = 3
    complete = 4


class OOMEntityType:
    """Enum for the type of the OOM"""
    unknown = 0
    automatic = 1
    manual = 2


def is_visible(element):
    return element.offsetWidth > 0 and element.offsetHeight > 0


def hide_element(element_id):
    """Hide the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.add('js-text--display-none')


def show_element(element_id):
    """Show the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.remove('js-text--display-none')


def hide_elements(selector):
    """Hide all matching elements by adding class js-text--display-none"""
    for element in document.querySelectorAll(selector):
        element.classList.add('js-text--display-none')


def show_elements(selector):
    """Show all matching elements by removing class js-text--display-none"""
    for element in document.querySelectorAll(selector):
        element.classList.remove('js-text--display-none')


def toggle(element_id):
    """Toggle the visibility of the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.toggle('js-text--display-none')


def escape_html(unsafe):
    """
    Escape unsafe HTML entities

    @type unsafe: str
    @rtype: str
    """
    return unsafe.replace('&', "&amp;")\
        .replace('<', "&lt;")\
        .replace('>', "&gt;")\
        .replace('"', "&quot;")\
        .replace("'", "&#039;")


def error(msg):
    """Show the error box and add the error message"""
    show_notifybox('ERROR', msg)


def internal_error(msg):
    """Show the error box and add the internal error message"""
    show_notifybox('INTERNAL ERROR', msg)


def warning(msg):
    """Show the error box and add the warning message"""
    show_notifybox('WARNING', msg)


def show_notifybox(prefix, msg):
    """Show escaped message in the notification box"""
    if prefix == 'WARNING':
        css_class = 'js-notify_box__msg--warning'
    else:
        css_class = 'js-notify_box__msg--error'
    show_element('notify_box')
    notify_box = document.getElementById('notify_box')
    notification = document.createElement('div')
    notification.classList.add(css_class)
    notification.innerHTML = '{}: {}<br>'.format(prefix, escape_html(msg))
    notify_box.appendChild(notification)


class BaseKernelConfig:
    """Base class for all kernel specific configuration"""

    name = 'Base configuration for all kernels'
    """Name/description of this kernel configuration"""

    EXTRACT_PATTERN = None
    """
    Instance specific dictionary of RE pattern to analyse a OOM block for a specific kernel version
    
    This dict will be filled from EXTRACT_PATTERN_BASE and EXTRACT_PATTERN_OVERLAY during class constructor is executed.
    
    :type: None|Dict
    :see: EXTRACT_PATTERN_BASE and EXTRACT_PATTERN_OVERLAY
    """

    EXTRACT_PATTERN_BASE = {
        'invoked oom-killer': (
            r'^(?P<trigger_proc_name>[\S ]+) invoked oom-killer: '
            r'gfp_mask=(?P<trigger_proc_gfp_mask>0x[a-z0-9]+)(\((?P<trigger_proc_gfp_flags>[A-Z_|]+)\))?, '
            r'(nodemask=(?P<trigger_proc_nodemask>([\d,-]+|\(null\))), )?'
            r'order=(?P<trigger_proc_order>-?\d+), '
            r'oom_score_adj=(?P<trigger_proc_oomscore>\d+)',
            True,
        ),
        'Trigger process and kernel version': (
            r'^CPU: \d+ PID: (?P<trigger_proc_pid>\d+) '
            r'Comm: .* (Not tainted|Tainted:.*) '
            r'(?P<kernel_version>\d[\w.-]+) #\d',
            True,
        ),

        # split caused by a limited number of iterations during converting PY regex into JS regex
        'Mem-Info (part 1)': (
            r'^Mem-Info:.*'
            r'(?:\n)'

            # first line (starting w/o a space)
            r'^active_anon:(?P<active_anon_pages>\d+) inactive_anon:(?P<inactive_anon_pages>\d+) '
            r'isolated_anon:(?P<isolated_anon_pages>\d+)'
            r'(?:\n)'

            # remaining lines (w/ leading space)
            r'^ active_file:(?P<active_file_pages>\d+) inactive_file:(?P<inactive_file_pages>\d+) '
            r'isolated_file:(?P<isolated_file_pages>\d+)'
            r'(?:\n)'

            r'^ unevictable:(?P<unevictable_pages>\d+) dirty:(?P<dirty_pages>\d+) writeback:(?P<writeback_pages>\d+) '
            r'unstable:(?P<unstable_pages>\d+)',
            True,
        ),
        'Mem-Info (part 2)': (
            r'^ slab_reclaimable:(?P<slab_reclaimable_pages>\d+) slab_unreclaimable:(?P<slab_unreclaimable_pages>\d+)'
            r'(?:\n)'
            r'^ mapped:(?P<mapped_pages>\d+) shmem:(?P<shmem_pages>\d+) pagetables:(?P<pagetables_pages>\d+) '
            r'bounce:(?P<bounce_pages>\d+)'
            r'(?:\n)'
            r'^ free:(?P<free_pages>\d+) free_pcp:(?P<free_pcp_pages>\d+) free_cma:(?P<free_cma_pages>\d+)',
            True,
        ),
        'Memory node information': (
            r'(^Node \d+ (DMA|Normal|hugepages).*(:?\n))+',
            False,
        ),
        'Page cache': (
            r'^(?P<pagecache_total_pages>\d+) total pagecache pages.*$',
            True,
        ),
        'Swap usage information': (
            r'^(?P<swap_cache_pages>\d+) pages in swap cache'
            r'(?:\n)'
            r'^Swap cache stats: add \d+, delete \d+, find \d+\/\d+'
            r'(?:\n)'
            r'^Free swap  = (?P<swap_free_kb>\d+)kB'
            r'(?:\n)'
            r'^Total swap = (?P<swap_total_kb>\d+)kB',
            False,
        ),
        'Page information': (
            r'^(?P<ram_pages>\d+) pages RAM'
            r'('
            r'(?:\n)'
            r'^(?P<highmem_pages>\d+) pages HighMem/MovableOnly'
            r')?'
            r'(?:\n)'
            r'^(?P<reserved_pages>\d+) pages reserved'
            r'('
            r'(?:\n)'
            r'^(?P<cma_pages>\d+) pages cma reserved'
            r')?'
            r'('
            r'(?:\n)'
            r'^(?P<pagetablecache_pages>\d+) pages in pagetable cache'
            r')?'
            r'('
            r'(?:\n)'
            r'^(?P<hwpoisoned_pages>\d+) pages hwpoisoned'
            r')?',
            True,
        ),
        'Process killed by OOM': (
            r'^Out of memory: Kill process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) '
            r'score (?P<killed_proc_score>\d+) or sacrifice child',
            True,
        ),
        'Details of process killed by OOM': (
            r'^Killed process \d+ \(.*\)'
            r'(, UID \d+,)?'
            r' total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, '
            r'file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB.*',
            True,
        ),
    }
    """
    RE pattern to extract information from OOM.
    
    The first item is the RE pattern and the second is whether it is mandatory to find this pattern.
    
    This dictionary will be copied to EXTRACT_PATTERN during class constructor is executed. 
    
    :type: dict(tuple(str, bool))
    :see: EXTRACT_PATTERN
    """

    EXTRACT_PATTERN_OVERLAY = {}
    """
    To extend / overwrite parts of EXTRACT_PATTERN in kernel configuration.
    
    :type: dict(tuple(str, bool))
    :see: EXTRACT_PATTERN
    """

    GFP_FLAGS = {
        'GFP_ATOMIC':           {'value': '__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM'},
        'GFP_KERNEL':           {'value': '__GFP_RECLAIM | __GFP_IO | __GFP_FS'},
        'GFP_KERNEL_ACCOUNT':   {'value': 'GFP_KERNEL | __GFP_ACCOUNT'},
        'GFP_NOWAIT':           {'value': '__GFP_KSWAPD_RECLAIM'},
        'GFP_NOIO':             {'value': '__GFP_RECLAIM'},
        'GFP_NOFS':             {'value': '__GFP_RECLAIM | __GFP_IO'},
        'GFP_USER':             {'value': '__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL'},
        'GFP_DMA':              {'value': '__GFP_DMA'},
        'GFP_DMA32':            {'value': '__GFP_DMA32'},
        'GFP_HIGHUSER':         {'value': 'GFP_USER | __GFP_HIGHMEM'},
        'GFP_HIGHUSER_MOVABLE': {'value': 'GFP_HIGHUSER | __GFP_MOVABLE'},
        'GFP_TRANSHUGE_LIGHT':  {'value': 'GFP_HIGHUSER_MOVABLE | __GFP_COMP |  __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM'},
        'GFP_TRANSHUGE':        {'value': 'GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM'},
        '__GFP_DMA':            {'value': 0x01},
        '__GFP_HIGHMEM':        {'value': 0x02},
        '__GFP_DMA32':          {'value': 0x04},
        '__GFP_MOVABLE':        {'value': 0x08},
        '__GFP_RECLAIMABLE':    {'value': 0x10},
        '__GFP_HIGH':           {'value': 0x20},
        '__GFP_IO':             {'value': 0x40},
        '__GFP_FS':             {'value': 0x80},
        '__GFP_COLD':           {'value': 0x100},
        '__GFP_NOWARN':         {'value': 0x200},
        '__GFP_RETRY_MAYFAIL':  {'value': 0x400},
        '__GFP_NOFAIL':         {'value': 0x800},
        '__GFP_NORETRY':        {'value': 0x1000},
        '__GFP_MEMALLOC':       {'value': 0x2000},
        '__GFP_COMP':           {'value': 0x4000},
        '__GFP_ZERO':           {'value': 0x8000},
        '__GFP_NOMEMALLOC':     {'value': 0x10000},
        '__GFP_HARDWALL':       {'value': 0x20000},
        '__GFP_THISNODE':       {'value': 0x40000},
        '__GFP_ATOMIC':         {'value': 0x80000},
        '__GFP_ACCOUNT':        {'value': 0x100000},
        '__GFP_DIRECT_RECLAIM': {'value': 0x400000},
        '__GFP_WRITE':          {'value': 0x800000},
        '__GFP_KSWAPD_RECLAIM': {'value': 0x1000000},
        '__GFP_NOLOCKDEP':      {'value': 0x2000000},
        '__GFP_RECLAIM':        {'value': '__GFP_DIRECT_RECLAIM|__GFP_KSWAPD_RECLAIM'},
    }
    """
    Definition of GFP flags

    The decimal value of a flag will be calculated by evaluating the entries from left to right. Grouping by
    parentheses is not supported.

    Source: include/linux/gpf.h

    @note : This list os probably a mixture of different kernel versions - be carefully

    @todo: Implement kernel specific versions because this flags are not constant
          (see https://github.com/torvalds/linux/commit/e67d4ca79aaf9d13a00d229b1b1c96b86828e8ba#diff-020720d0699e3ae1afb6fcd815ca8500)
    """

    pstable_items = ['pid', 'uid', 'tgid', 'total_vm_pages', 'rss_pages', 'nr_ptes_pages', 'swapents_pages',
                      'oom_score_adj', 'name', 'notes']
    """Elements of the process table"""

    pstable_html = ['PID', 'UID', 'TGID', 'Total VM', 'RSS', 'Page Table Entries', 'Swap Entries', 'OOM Adjustment',
                    'Name', 'Notes']
    """
    Headings of the process table columns
    """

    pstable_non_ints = ['pid', 'name', 'notes']
    """Columns that are not converted to an integer"""

    REC_PROCESS_LINE = re.compile(
        r'^\[(?P<pid>[ \d]+)\]\s+(?P<uid>\d+)\s+(?P<tgid>\d+)\s+(?P<total_vm_pages>\d+)\s+(?P<rss_pages>\d+)\s+'
        r'(?P<nr_ptes_pages>\d+)\s+(?P<swapents_pages>\d+)\s+(?P<oom_score_adj>-?\d+)\s+(?P<name>.+)\s*')
    """Match content of process table"""

    pstable_start = '[ pid ]'
    """
    Pattern to find the start of the process table
    
    :type: str
    """

    rec_version4kconfig = re.compile('.+')
    """RE to match kernel version to kernel configuration"""

    rec_oom_begin = re.compile(r'invoked oom-killer:', re.MULTILINE)
    """RE to match the first line of an OOM block"""

    rec_oom_end = re.compile(r'^Killed process \d+', re.MULTILINE)
    """RE to match the last line of an OOM block"""

    def __init__(self):
        super().__init__()

        if self.EXTRACT_PATTERN is None:
            # Create a copy to prevent modifications on the class dictionary
            # TODO replace with self.EXTRACT_PATTERN = self.EXTRACT_PATTERN.copy() after
            #      https://github.com/QQuick/Transcrypt/issues/716 "dict does not have a copy method" is fixed
            self.EXTRACT_PATTERN = {}
            self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_BASE)

        if self.EXTRACT_PATTERN_OVERLAY:
            self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY)


class KernelConfig_4_6(BaseKernelConfig):
    # Support changes:
    #  * "mm, oom_reaper: report success/failure" (bc448e897b6d24aae32701763b8a1fe15d29fa26)

    name = 'Configuration for Linux kernel 4.6 or later'
    rec_version4kconfig = re.compile(r'^4\.([6-9]\.|[12][0-9]\.).+')

    # The "oom_reaper" line is optionally
    rec_oom_end = re.compile(r'^((Out of memory.*|Memory cgroup out of memory): Killed process \d+|oom_reaper:)',
                             re.MULTILINE)

    def __init__(self):
        super().__init__()


class KernelConfig_4_9(KernelConfig_4_6):
    # Support changes:
    # * "mm: oom: deduplicate victim selection code for memcg and global oom" (7c5f64f84483bd13886348edda8b3e7b799a7fdb)

    name = 'Configuration for Linux kernel 4.9 or later'
    rec_version4kconfig = re.compile(r'^4\.([9]\.|[12][0-9]\.).+')

    EXTRACT_PATTERN_OVERLAY_49 = {
        'Details of process killed by OOM': (
            r'^(Out of memory.*|Memory cgroup out of memory): Killed process \d+ \(.*\)'
            r'(, UID \d+,)?'
            r' total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, '
            r'file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB.*',
            True,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_49)


class KernelConfig_4_15(KernelConfig_4_9):
    # Support changes:
    # * mm: consolidate page table accounting (af5b0f6a09e42c9f4fa87735f2a366748767b686)

    # nr_ptes -> pgtables_bytes
    # pr_info("[ pid ]   uid  tgid total_vm      rss nr_ptes nr_pmds nr_puds swapents oom_score_adj name\n");
    # pr_info("[ pid ]   uid  tgid total_vm      rss pgtables_bytes swapents oom_score_adj name\n");
    REC_PROCESS_LINE = re.compile(
        r'^\[(?P<pid>[ \d]+)\]\s+(?P<uid>\d+)\s+(?P<tgid>\d+)\s+(?P<total_vm_pages>\d+)\s+(?P<rss_pages>\d+)\s+'
        r'(?P<pgtables_bytes>\d+)\s+(?P<swapents_pages>\d+)\s+(?P<oom_score_adj>-?\d+)\s+(?P<name>.+)\s*')

    pstable_items = ['pid', 'uid', 'tgid', 'total_vm_pages', 'rss_pages', 'pgtables_bytes', 'swapents_pages',
                      'oom_score_adj', 'name', 'notes']

    pstable_html = ['PID', 'UID', 'TGID', 'Total VM', 'RSS', 'Page Table Bytes', 'Swap Entries Pages',
                    'OOM Adjustment', 'Name', 'Notes']


class KernelConfig_4_19(KernelConfig_4_15):
    # Support changes:
    # * mm, oom: describe task memory unit, larger PID pad (c3b78b11efbb2865433abf9d22c004ffe4a73f5c)

    pstable_start = '[  pid  ]'


class KernelConfig_5_0(KernelConfig_4_19):
    # Support changes:
    #  * "mm, oom: reorganize the oom report in dump_header" (ef8444ea01d7442652f8e1b8a8b94278cb57eafd)

    name = 'Configuration for Linux kernel 5.0 or later'
    rec_version4kconfig = re.compile(r'^[5-9]\..+')

    EXTRACT_PATTERN_OVERLAY_50 = {
        # third last line - not integrated yet
        # oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=/,mems_allowed=0,global_oom,task_memcg=/,task=sed,pid=29481,uid=12345

        'Process killed by OOM': (
            r'^Out of memory: Killed process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) '
            r'total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, '
            r'file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB, '
            r'UID:\d+ pgtables:(?P<killed_proc_pgtables>\d+)kB oom_score_adj:(?P<killed_proc_oom_score_adj>\d+)',
            True,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_50)


class KernelConfig_5_8(KernelConfig_5_0):
    # Support changes:
    #  * "mm/writeback: discard NR_UNSTABLE_NFS, use NR_WRITEBACK instead" (8d92890bd6b8502d6aee4b37430ae6444ade7a8c)

    name = 'Configuration for Linux kernel 5.8 or later'

    rec_version4kconfig = re.compile(r'^(5\.[8-9]\.|5\.[1-9][0-9]\.|[6-9]\.).+')

    EXTRACT_PATTERN_OVERLAY_58 = {
        'Mem-Info (part 1)': (
            r'^Mem-Info:.*'
            r'(?:\n)'

            # first line (starting w/o a space)
            r'^active_anon:(?P<active_anon_pages>\d+) inactive_anon:(?P<inactive_anon_pages>\d+) '
            r'isolated_anon:(?P<isolated_anon_pages>\d+)'
            r'(?:\n)'
        
            # remaining lines (w/ leading space)
            r'^ active_file:(?P<active_file_pages>\d+) inactive_file:(?P<inactive_file_pages>\d+) '
            r'isolated_file:(?P<isolated_file_pages>\d+)'
            r'(?:\n)'
        
            r'^ unevictable:(?P<unevictable_pages>\d+) dirty:(?P<dirty_pages>\d+) writeback:(?P<writeback_pages>\d+)',
            True,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_58)


class KernelConfigRhel7(BaseKernelConfig):
    """RHEL7 / CentOS7 specific configuration"""

    name = 'Configuration for RHEL7 / CentOS7 specific Linux kernel (3.10)'

    rec_version4kconfig = re.compile(r'^3\..+')

    def __init__(self):
        super().__init__()


AllKernelConfigs = [
    KernelConfig_5_8(),
    KernelConfig_5_0(),
    KernelConfig_4_15(),
    KernelConfig_4_19(),
    KernelConfig_4_9(),
    KernelConfig_4_6(),
    KernelConfigRhel7(),
    BaseKernelConfig(),
]
"""
Instances of all available kernel configurations.

The last entry in this list is the base configuration as a fallback.

@type: List(BaseKernelConfig)
"""


class OOMEntity:
    """Hold whole OOM message block and provide access"""

    current_line = 0
    """Zero based index of the current line in self.lines"""

    lines = []
    """OOM text as list of lines"""

    state = OOMEntityState.unknown
    """State of the OOM after initial parsing"""

    text = ""
    """OOM as text"""

    def __init__(self, text):
        # use Unix LF only
        text = text.replace('\r\n', '\n')
        text = text.strip()
        oom_lines = text.split('\n')

        self.current_line = 0
        self.lines = oom_lines
        self.text = text

        # don't do anything if the text is empty or does not contains the leading OOM message
        if not text:
            self.state = OOMEntityState.empty
            return
        elif 'invoked oom-killer:' not in text:
            self.state = OOMEntityState.invalid
            return

        oom_lines = self._remove_non_oom_lines(oom_lines)
        oom_lines = self._remove_kernel_colon(oom_lines)
        cols_to_strip = self._number_of_columns_to_strip(oom_lines[self._get_CPU_index(oom_lines)])
        oom_lines = self._journalctl_add_leading_columns_to_meminfo(oom_lines, cols_to_strip)
        oom_lines = self._strip_needless_columns(oom_lines, cols_to_strip)
        oom_lines = self._rsyslog_unescape_lf(oom_lines)

        self.lines = oom_lines
        self.text = '\n'.join(oom_lines)

        if 'Killed process' in text:
            self.state = OOMEntityState.complete
        else:
            self.state = OOMEntityState.started

    def _journalctl_add_leading_columns_to_meminfo(self, oom_lines, cols_to_add):
        """
        Add leading columns to handle line breaks in journalctl output correctly.

        The output of the "Mem-Info:" block contains line breaks. journalctl breaks these lines accordingly, but
        inserts at the beginning spaces instead of date and time. As a result, removing the needless columns no longer
        works correctly.

        This function adds columns back in the affected rows so that the removal works cleanly over all rows.

        @see: _rsyslog_unescape_lf()
        """
        pattern = r'^\s+ (active_file|unevictable|slab_reclaimable|mapped|free):.+$'
        rec = re.compile(pattern)

        add_cols = ""
        for i in range(cols_to_add):
            add_cols += "Col{} ".format(i)

        expanded_lines = []
        for line in oom_lines:
            match = rec.search(line)
            if match:
                line = "{} {}".format(add_cols, line.strip())
            expanded_lines.append(line)

        return expanded_lines

    def _get_CPU_index(self, lines):
        """
        Return the index of the first line with "CPU: "

        Depending on the OOM version the "CPU: " pattern is in second or third oom line.
        """
        for i in range(len(lines)):
            if 'CPU: ' in lines[i]:
                return i

        return 0

    def _number_of_columns_to_strip(self, line):
        """
        Determinate number of columns left to the OOM message to strip.

        Sometime timestamps, hostnames and or syslog tags are left to the OOM message. This columns will be count to
        strip later.
        """
        to_strip = 0
        columns = line.split(" ")

        # Examples:
        # [11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        # Apr 01 14:13:32 mysrv kernel: CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        # Apr 01 14:13:32 mysrv kernel: [11686.888109] CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
        try:
            # strip all excl. "CPU:"
            if 'CPU:' in line:
                to_strip = columns.index("CPU:")
        except ValueError:
            pass

        return to_strip

    def _remove_non_oom_lines(self, oom_lines):
        """Remove all lines before and after OOM message block"""
        cleaned_lines = []
        in_oom_lines = False
        killed_process = False

        for line in oom_lines:
            # first line of the oom message block
            if "invoked oom-killer:" in line:
                in_oom_lines = True

            if in_oom_lines:
                cleaned_lines.append(line)

            # OOM blocks ends with the second last only or both lines
            #   Out of memory: Killed process ...
            #   oom_reaper: reaped process ...
            if 'Killed process' in line:
                killed_process = True
                continue

            # next line after "Killed process \d+ ..."
            if killed_process:
                if 'oom_reaper' in line:
                    break
                else:
                    # remove this line
                    del cleaned_lines[-1]
                    break

        return cleaned_lines

    def _rsyslog_unescape_lf(self, oom_lines):
        """
        Split lines at '#012' (octal representation of LF).

        The output of the "Mem-Info:" block contains line breaks. Rsyslog replaces these line breaks with their octal
        representation #012. This breaks the removal of needless columns as well as the detection of the OOM values.

        Splitting the lines (again) solves this issue.

        This feature can be controlled inside the rsyslog configuration with the directives
        $EscapeControlCharactersOnReceive, $Escape8BitCharactersOnReceive and $ControlCharactersEscapePrefix.

        @see: _journalctl_add_leading_columns_to_meminfo()
        """
        lines = []

        for line in oom_lines:
            if '#012' in line:
                lines.extend(line.split('#012'))
            else:
                lines.append(line)

        return lines

    def _remove_kernel_colon(self, oom_lines):
        """
        Remove the "kernel:" pattern w/o leading and tailing spaces.

        Some OOM messages don't have a space between "kernel:" and the process name. _strip_needless_columns() will
        fail in such cases. Therefore the pattern is removed.
        """
        oom_lines = [i.replace('kernel:', '') for i in oom_lines]
        return oom_lines

    def _strip_needless_columns(self, oom_lines, cols_to_strip=0):
        """
        Remove needless columns at the start of every line.

        This function removes all leading items w/o any relation to the OOM message like, date and time, hostname,
        syslog priority/facility.
        """
        stripped_lines = []
        for line in oom_lines:
            # remove empty lines
            if not line.strip():
                continue

            if cols_to_strip:
                # [-1] slicing needs Transcrypt operator overloading
                line = line.split(" ", cols_to_strip)[-1]  # __:opov
            stripped_lines.append(line)

        return stripped_lines

    def back(self):
        """Return the previous line"""
        if self.current_line - 1 < 0:
            raise StopIteration()
        self.current_line -= 1
        return self.lines[self.current_line]

    def current(self):
        """Return the current line"""
        return self.lines[self.current_line]

    def next(self):
        """Return the next line"""
        if self.current_line + 1 < len(self.lines):
            self.current_line += 1
            return self.lines[self.current_line]
        raise StopIteration()

    def find_text(self, pattern):
        """
        Search the pattern and set the position to the first found line.
        Otherwise the position pointer won't be changed.

        :param pattern: Text to find
        :type pattern: str

        :return: True if the marker has found.
        """
        for line in self.lines:
            if pattern in line:
                self.current_line = self.lines.index(line)
                return True
        return False

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()


class OOMResult:
    """Results of an OOM analysis"""

    kconfig = BaseKernelConfig()
    """Kernel configuration"""

    details = {}
    """Extracted result"""

    oom_entity = None
    """
    State of this OOM (unknown, incomplete, ...)
    
    :type: OOMEntityState
    """

    oom_type = OOMEntityType.unknown
    """
    Type of this OOM (manually or automatically triggered)
    
    :type: OOMEntityType
    """

    error_msg = ""
    """
    Error message
    
    @type: str
    """

    kversion = None
    """
    Kernel version
    
    @type: str
    """

    oom_text = None
    """
    OOM text
    
    @type: str
    """

    swap_active = False
    """
    Swap space active or inactive
    
    @type: bool
    """


class OOMAnalyser:
    """Analyse an OOM object and calculate additional values"""

    oom_entity = None
    """
    State of this OOM (unknown, incomplete, ...)
    
    :type: OOMEntityState
    """

    oom_result = OOMResult()
    """
    Store details of OOM analysis
    
    :type: OOMResult
    """

    def __init__(self, oom):
        self.oom_entity = oom
        self.oom_result = OOMResult()

    def _identify_kernel_version(self):
        """
        Identify the used kernel version and

        @rtype: bool
        """
        pattern = r'CPU: \d+ PID: \d+ Comm: .* (Not tainted|Tainted: [A-Z ]+) (?P<kernel_version>\d[\w.-]+) #.+'
        rec = re.compile(pattern, re.MULTILINE)
        match = rec.search(self.oom_entity.text)
        if not match:
            self.oom_result.error_msg = 'Failed to extract kernel version from OOM text'
            return False
        self.oom_result.kversion = match.group('kernel_version')
        return True

    def _choose_kernel_config(self):
        """
        Select proper kernel configuration

        @rtype: bool
        """
        for kcfg in AllKernelConfigs:
            match = kcfg.rec_version4kconfig.match(self.oom_result.kversion)
            if match:
                self.oom_result.kconfig = kcfg
                break

        if not self.oom_result.kconfig:
            warning('Failed to find a proper configuration for kernel "{}"'.format(self.oom_result.kversion))
            self.oom_result.kconfig = BaseKernelConfig()
        return True

    def _check_for_empty_oom(self):
        """
        Check for an empty OOM text

        @rtype: bool
        """
        if not self.oom_entity.text:
            self.state = OOMEntityState.empty
            self.oom_result.error_msg = 'Empty OOM text. Please insert an OOM message block.'
            return False
        return True

    def _check_for_complete_oom(self):
        """
        Check if the OOM in self.oom_entity is complete and update self.oom_state accordingly

        @rtype: bool
        """
        self.oom_state = OOMEntityState.unknown
        self.oom_result.error_msg = 'Unknown OOM format'

        if not self.oom_result.kconfig.rec_oom_begin.search(self.oom_entity.text):
            self.state = OOMEntityState.invalid
            self.oom_result.error_msg = 'The inserted text is not a valid OOM block! The initial pattern was not found!'
            return False

        if not self.oom_result.kconfig.rec_oom_end.search(self.oom_entity.text):
            self.state = OOMEntityState.started
            self.oom_result.error_msg = 'The inserted OOM is incomplete! The initial pattern was found but not the '\
                                        'final.'
            return False

        self.state = OOMEntityState.complete
        self.oom_result.error_msg = None
        return True

    def _extract_block_from_next_pos(self, marker):
        """
        Extract a block that starts with the marker and contains all lines up to the next line with ":".
        :rtype: str
        """
        block = ''
        if not self.oom_entity.find_text(marker):
            return block

        line = self.oom_entity.current()
        block += "{}\n".format(line)
        for line in self.oom_entity:
            if ':' in line:
                self.oom_entity.back()
                break
            block += "{}\n".format(line)
        return block

    def _extract_from_oom_text(self):
        """Extract details from OOM message text"""

        self.oom_result.details = {}
        # __pragma__ ('jsiter')
        for k in self.oom_result.kconfig.EXTRACT_PATTERN:
            pattern, is_mandatory = self.oom_result.kconfig.EXTRACT_PATTERN[k]
            rec = re.compile(pattern, re.MULTILINE)
            match = rec.search(self.oom_entity.text)
            if match:
                self.oom_result.details.update(match.groupdict())
            elif is_mandatory:
                error('Failed to extract information from OOM text. The regular expression "{}" (pattern "{}") '
                      'does not find anything. This can lead to errors later on.'.format(k, pattern))
        # __pragma__ ('nojsiter')

        if self.oom_result.details['trigger_proc_order'] == "-1":
            self.oom_result.oom_type = OOMEntityType.manual
        else:
            self.oom_result.oom_type = OOMEntityType.automatic

        self.oom_result.details['hardware_info'] = self._extract_block_from_next_pos('Hardware name:')

        # strip "Call Trace" line at beginning and remove leading spaces
        call_trace = ''
        block = self._extract_block_from_next_pos('Call Trace:')
        for line in block.split('\n'):
            if line.startswith('Call Trace'):
                continue
            call_trace += "{}\n".format(line.strip())
        self.oom_result.details['call_trace'] = call_trace

        self._extract_pstable()

    def _extract_pstable(self):
        """Extract process table"""
        self.oom_result.details['_pstable'] = {}
        self.oom_entity.find_text(self.oom_result.kconfig.pstable_start)
        for line in self.oom_entity:
            if not line.startswith('['):
                break
            if line.startswith(self.oom_result.kconfig.pstable_start):
                continue
            match = self.oom_result.kconfig.REC_PROCESS_LINE.match(line)
            if match:
                details = match.groupdict()
                details['notes'] = ''
                pid = details.pop('pid')
                self.oom_result.details['_pstable'][pid] = {}
                self.oom_result.details['_pstable'][pid].update(details)

    def _hex2flags(self, hexvalue, flag_definition):
        """\
        Convert the hexadecimal value into flags specified by definition

        @return: list of flags and the decimal sum of all unknown flags
        """
        remaining = int(hexvalue, 16)
        converted_flags = []

        # __pragma__ ('jsiter')
        for flag in flag_definition:
            value = self._flag2decimal(flag, flag_definition)
            if remaining & value:
                # delete flag by "and" with a reverted mask
                remaining &= ~value
                converted_flags.append(flag)
        # __pragma__ ('nojsiter')

        return converted_flags, remaining

    def _flag2decimal(self, flag, flag_definition):
        """\
        Convert a single flag into a decimal value
        """
        if flag not in flag_definition:
            error('No definition for flag {} found'.format(flag))
            return 0

        value = flag_definition[flag]['value']
        if isinstance(value, int):
            return value

        tokenlist = iter(re.split('([|&])', value))
        operator = None
        negate_rvalue = False
        lvalue = 0
        while True:
            try:
                token = next(tokenlist)
            except StopIteration:
                break
            token = token.strip()
            if token in ['|', '&']:
                operator = token
                continue

            if token.startswith('~'):
                token = token[1:]
                negate_rvalue = True

            if token.isdigit():
                rvalue = int(token)
            elif token.startswith('0x') and token[2:].isdigit():
                rvalue = int(token, 16)
            else:
                # it's not a decimal nor a hexadecimal value - reiterate assuming it's a flag string
                rvalue = self._flag2decimal(token, flag_definition)

            if negate_rvalue:
                rvalue = ~rvalue

            if operator == '|':
                lvalue |= rvalue
            elif operator == '&':
                lvalue &= rvalue

            operator = None
            negate_rvalue = False

        return lvalue

    def _convert_numeric_results_to_integer(self):
        """Convert all *_pages and *_kb to integer"""
        # __pragma__ ('jsiter')
        for item in self.oom_result.details:
            if self.oom_result.details[item] is None:
                self.oom_result.details[item] = '<not found>'
                continue
            if item.endswith('_bytes') or item.endswith('_kb') or item.endswith('_pages') or item.endswith('_pid') or \
                    item in ['killed_proc_score', 'trigger_proc_order', 'trigger_proc_oomscore']:
                try:
                    self.oom_result.details[item] = int(self.oom_result.details[item])
                except:
                    error('Converting item "{}={}" to integer failed'.format(item, self.oom_result.details[item]))
        # __pragma__ ('nojsiter')

    def _convert_pstable_values_to_integer(self):
        """Convert numeric values in process table to integer values"""
        ps = self.oom_result.details['_pstable']
        ps_index = []
        # TODO Check if transcrypt issue: pragma jsiter for the whole block "for pid_str in ps: ..."
        #      sets item in "for item in ['uid',..." to 0 instead of 'uid'
        #      jsiter is necessary to iterate over ps
        for pid_str in ps.keys():
            converted = {}
            process = ps[pid_str]
            for item in self.oom_result.kconfig.pstable_items:
                if item in self.oom_result.kconfig.pstable_non_ints:
                    continue
                try:
                    converted[item] = int(process[item])
                except:
                    if item not in process:
                        pitem = '<not in process table>'
                    else:
                        pitem = process[item]
                    error('Converting process parameter "{}={}" to integer failed'.format(item, pitem))

            converted['name'] = process['name']
            converted['notes'] = process['notes']
            pid_int = int(pid_str)
            del ps[pid_str]
            ps[pid_int] = converted
            ps_index.append(pid_int)

        ps_index.sort(key=int)
        self.oom_result.details['_pstable_index'] = ps_index

    def _calc_pstable_values(self):
        """Set additional notes to processes listed in the process table"""
        tpid = self.oom_result.details['trigger_proc_pid']
        kpid = self.oom_result.details['killed_proc_pid']

        # sometimes the trigger process isn't part of the process table
        if tpid in self.oom_result.details['_pstable']:
            self.oom_result.details['_pstable'][tpid]['notes'] = 'trigger process'

        # assume the killed process may also not part of the process table
        if kpid in self.oom_result.details['_pstable']:
            self.oom_result.details['_pstable'][kpid]['notes'] = 'killed process'

    def _calc_trigger_process_values(self):
        """Calculate all values related with the trigger process"""
        self.oom_result.details['trigger_proc_requested_memory_pages'] = 2 ** self.oom_result.details['trigger_proc_order']
        self.oom_result.details['trigger_proc_requested_memory_pages_kb'] = self.oom_result.details['trigger_proc_requested_memory_pages'] * \
                                                                            self.oom_result.details['page_size_kb']
        # process gfp_mask
        if self.oom_result.details['trigger_proc_gfp_flags'] != '<not found>':     # None has been is converted to '<not found>'
            flags = self.oom_result.details['trigger_proc_gfp_flags']
            del self.oom_result.details['trigger_proc_gfp_flags']
        else:
            flags, unknown = self._hex2flags(self.oom_result.details['trigger_proc_gfp_mask'], self.oom_result.kconfig.GFP_FLAGS)
            if unknown:
                flags.append('0x{0:x}'.format(unknown))
            flags = ' | '.join(flags)

        self.oom_result.details['trigger_proc_gfp_mask'] = '{} ({})'.format(self.oom_result.details['trigger_proc_gfp_mask'], flags)
        # already fully processed and no own element to display -> delete otherwise an error msg will be shown
        del self.oom_result.details['trigger_proc_gfp_flags']

    def _calc_killed_process_values(self):
        """Calculate all values related with the killed process"""
        self.oom_result.details['killed_proc_total_rss_kb'] = self.oom_result.details['killed_proc_anon_rss_kb'] + \
                                                              self.oom_result.details['killed_proc_file_rss_kb'] + \
                                                              self.oom_result.details['killed_proc_shmem_rss_kb']

        self.oom_result.details['killed_proc_rss_percent'] = int(100 *
                                                                 self.oom_result.details['killed_proc_total_rss_kb'] /
                                                                 int(self.oom_result.details['system_total_ram_kb']))

    def _calc_swap_values(self):
        """Calculate all swap related values"""
        try:
            self.oom_result.swap_active = self.oom_result.details['swap_total_kb'] > 0
        except KeyError:
            self.oom_result.swap_active = False

        if not self.oom_result.swap_active:
            return

        self.oom_result.details['swap_cache_kb'] = self.oom_result.details['swap_cache_pages'] * self.oom_result.details['page_size_kb']
        del self.oom_result.details['swap_cache_pages']

        #  SwapUsed = SwapTotal - SwapFree - SwapCache
        self.oom_result.details['swap_used_kb'] = self.oom_result.details['swap_total_kb'] - self.oom_result.details['swap_free_kb'] - \
                                                  self.oom_result.details['swap_cache_kb']
        self.oom_result.details['system_swap_used_percent'] = int(100 *
                                                                  self.oom_result.details['swap_total_kb'] /
                                                                  self.oom_result.details['swap_used_kb'])

    def _calc_system_values(self):
        """Calculate system memory"""

        # educated guess
        self.oom_result.details['page_size_kb'] = 4

        # calculate remaining explanation values
        self.oom_result.details['system_total_ram_kb'] = self.oom_result.details['ram_pages'] * self.oom_result.details['page_size_kb']
        if self.oom_result.swap_active:
            self.oom_result.details['system_total_ramswap_kb'] = self.oom_result.details['system_total_ram_kb'] + \
                                                                 self.oom_result.details['swap_total_kb']
        else:
            self.oom_result.details['system_total_ramswap_kb'] = self.oom_result.details['system_total_ram_kb']
        total_rss_pages = 0
        for pid in self.oom_result.details['_pstable'].keys():
            total_rss_pages += self.oom_result.details['_pstable'][pid]['rss_pages']
        self.oom_result.details['system_total_ram_used_kb'] = total_rss_pages * self.oom_result.details['page_size_kb']

        self.oom_result.details['system_total_used_percent'] = int(100 *
                                                                   self.oom_result.details['system_total_ram_used_kb'] /
                                                                   self.oom_result.details['system_total_ram_kb'])

    def _determinate_platform_and_distribution(self):
        """Determinate platform and distribution"""
        kernel_version = self.oom_result.details.get('kernel_version', '')
        if 'x86_64' in kernel_version:
            self.oom_result.details['platform'] = 'x86 64bit'
        else:
            self.oom_result.details['platform'] = 'unknown'

        dist = 'unknown'
        if '.el7uek' in kernel_version:
            dist = 'Oracle Linux 7 (Unbreakable Enterprise Kernel)'
        elif '.el7' in kernel_version:
            dist = 'RHEL 7/CentOS 7'
        elif '.el6' in kernel_version:
            dist = 'RHEL 6/CentOS 6'
        elif '.el5' in kernel_version:
            dist = 'RHEL 5/CentOS 5'
        elif 'ARCH' in kernel_version:
            dist = 'Arch Linux'
        elif '-generic' in kernel_version:
            dist = 'Ubuntu'
        self.oom_result.details['dist'] = dist

    def _calc_from_oom_details(self):
        """
        Calculate values from already extracted details

        @see: self.details
        """
        self._convert_numeric_results_to_integer()
        self._convert_pstable_values_to_integer()
        self._calc_pstable_values()

        self._determinate_platform_and_distribution()
        self._calc_system_values()
        self._calc_trigger_process_values()
        self._calc_killed_process_values()
        self._calc_swap_values()

    def analyse(self):
        """
        Extract and calculate values from the given OOM object

        If the return value is False, the OOM is too incomplete to perform an analysis.

        @rtype: bool
        """
        if not self._check_for_empty_oom():
            error(self.oom_result.error_msg)
            return False

        if not self._identify_kernel_version():
            error(self.oom_result.error_msg)
            return False

        if not self._choose_kernel_config():
            error(self.oom_result.error_msg)
            return False

        if not self._check_for_complete_oom():
            error(self.oom_result.error_msg)
            return False

        self._extract_from_oom_text()
        self._calc_from_oom_details()
        self.oom_result.oom_text = self.oom_entity.text

        return True


class SVGChart:
    """
    Creates a horizontal stacked bar chart with a legend underneath.
    
    The entries of the legend are arranged from left to right and from top to bottom.  
    """

    cfg = dict(
        chart_height=150,
        chart_width=600,
        label_height=80,
        legend_entry_width=160,
        legend_margin=7,
        title_height=20,
        title_margin=10,
        css_class='js-mem-usage__svg',     # CSS class for SVG diagram
    )
    """Basic chart configuration"""

    # generated with Colorgorical http://vrl.cs.brown.edu/color
    colors = [
        '#aee39a',
        '#344b46',
        '#1ceaf9',
        '#5d99aa',
        '#32e195',
        '#b02949',
        '#deae9e',
        '#805257',
        '#add51f',
        '#544793',
        '#a794d3',
        '#e057e1',
        '#769b5a',
        '#76f014',
        '#621da6',
        '#ffce54',
        '#d64405',
        '#bb8801',
        '#096013',
        '#ff0087'
    ]
    """20 different colors for memory usage diagrams"""

    max_entries_per_row = 3
    """Maximum chart legend entries per row"""

    namespace = 'http://www.w3.org/2000/svg'

    def __init__(self):
        super().__init__()
        self.cfg['bar_topleft_x'] = 0
        self.cfg['bar_topleft_y'] = self.cfg['title_height'] + self.cfg['title_margin']
        self.cfg['bar_bottomleft_x'] = self.cfg['bar_topleft_x']
        self.cfg['bar_bottomleft_y'] = self.cfg['bar_topleft_y'] + self.cfg['chart_height']

        self.cfg['bar_bottomright_x'] = self.cfg['bar_topleft_x'] + self.cfg['chart_width']
        self.cfg['bar_bottomright_y'] = self.cfg['bar_topleft_y'] + self.cfg['chart_height']

        self.cfg['legend_topleft_x'] = self.cfg['bar_topleft_x']
        self.cfg['legend_topleft_y'] = self.cfg['bar_topleft_y'] + self.cfg['legend_margin']
        self.cfg['legend_width'] = self.cfg['legend_entry_width'] + self.cfg['legend_margin'] + \
                                   self.cfg['legend_entry_width']

        self.cfg['diagram_height'] = self.cfg['chart_height'] + self.cfg['title_margin'] + self.cfg['title_height']
        self.cfg['diagram_width'] = self.cfg['chart_width']

        self.cfg['title_bottommiddle_y'] = self.cfg['title_height']
        self.cfg['title_bottommiddle_x'] = self.cfg['diagram_width'] // 2

    # __pragma__ ('kwargs')
    def create_element(self, tag, **kwargs):
        """
        Create an SVG element of the given tag.

        @note: Underscores in the argument names will be replaced by minus
        @param str tag: Type of element to be created
        @rtype: Node
        """
        element = document.createElementNS(self.namespace, tag)
        # __pragma__ ('jsiter')
        for k in kwargs:
            k2 = k.replace('_', '-')
            element.setAttribute(k2, kwargs[k])
        # __pragma__ ('nojsiter')
        return element
    # __pragma__ ('nokwargs')

    # __pragma__ ('kwargs')
    def create_element_text(self, text, **kwargs):
        """
        Create an SVG text element

        @note: Underscores in the argument names will be replaced by minus
        @param str text: Text
        @rtype: Node
        """
        element = self.create_element('text', **kwargs)
        element.textContent = text
        return element
    # __pragma__ ('nokwargs')

    def create_element_svg(self, height, width, css_class=None):
        """Return a SVG element"""
        svg = self.create_element('svg', version='1.1', height=height, width=width,
                                  viewBox='0 0 {} {}'.format(width, height))
        if css_class:
            svg.setAttribute('class', css_class)
        return svg

    def create_rectangle(self, x, y, width, height, color=None, title=None):
        """
        Return a rect-element in a group container

        If a title is given, the container also contains a <title> element.
        """
        g = self.create_element('g')
        rect = self.create_element('rect', x=x, y=y, width=width, height=height)
        if color:
            rect.setAttribute('fill', color)
        if title:
            t = self.create_element('title')
            t.textContent = title
            g.appendChild(t)
        g.appendChild(rect)
        return g

    def create_legend_entry(self, color, desc, pos):
        """
        Create a legend entry for the given position. Both elements of the entry are grouped within a g-element.

        @param str color: Colour of the entry
        @param str desc: Description
        @param int pos: Continuous position
        @rtype: Node
        """
        label_group = self.create_element('g', id=desc)
        color_rect = self.create_rectangle(0, 0, 20, 20, color)
        label_group.appendChild(color_rect)

        desc_element = self.create_element_text(desc, x='30', y='18')
        desc_element.textContent = desc
        label_group.appendChild(desc_element)

        # move group to right position
        x, y = self.legend_calc_xy(pos)
        label_group.setAttribute('transform', 'translate({}, {})'.format(x, y))

        return label_group

    def legend_max_row(self, pos):
        """
        Returns the maximum number of rows in the legend

        @param int pos: Continuous position
        """
        max_row = math.ceil(pos / self.max_entries_per_row)
        return max_row

    def legend_max_col(self, pos):
        """
        Returns the maximum number of columns in the legend

        @param int pos: Continuous position
        @rtype: int
        """
        if pos < self.max_entries_per_row:
            return pos
        return self.max_entries_per_row

    def legend_calc_x(self, column):
        """
        Calculate the X-axis using the given column

        @type column: int
        @rtype: int
        """
        x = self.cfg['bar_bottomleft_x'] + self.cfg['legend_margin']
        x += column * (self.cfg['legend_margin'] + self.cfg['legend_entry_width'])
        return x

    def legend_calc_y(self, row):
        """
        Calculate the Y-axis using the given row

        @type row: int
        @rtype: int
        """
        y = self.cfg['bar_bottomleft_y'] + self.cfg['legend_margin']
        y += row * 40
        return y

    def legend_calc_xy(self, pos):
        """
        Calculate the X-axis and Y-axis

        @param int pos: Continuous position
        @rtype: int, int
        """
        if not pos:
            col = 0
            row = 0
        else:
            col = pos % self.max_entries_per_row
            row = math.floor(pos / self.max_entries_per_row)

        x = self.cfg['bar_bottomleft_x'] + self.cfg['legend_margin']
        y = self.cfg['bar_bottomleft_y'] + self.cfg['legend_margin']
        x += col * (self.cfg['legend_margin'] + self.cfg['legend_entry_width'])
        y += row * 40

        return x, y

    def generate_bar_area(self, elements):
        """
        Generate colord stacked bars. All entries are group within a g-element.

        @rtype: Node
        """
        bar_group = self.create_element('g', id='bar_group', stroke='black', stroke_width=2)
        current_x = 0
        total_length = sum([length for unused, length in elements])

        for i, two in enumerate(elements):
            name, length = two
            color = self.colors[i % len(self.colors)]
            rect_len = int(length / total_length * self.cfg['chart_width'])
            if rect_len == 0:
                rect_len = 1
            rect = self.create_rectangle(current_x, self.cfg['bar_topleft_y'], rect_len, self.cfg['chart_height'],
                                         color, name)
            current_x += rect_len
            bar_group.appendChild(rect)

        return bar_group

    def generate_legend(self, elements):
        """
        Generate a legend for all elements. All entries are group within a g-element.

        @rtype: Node
        """
        legend_group = self.create_element('g', id='legend_group')
        for i, two in enumerate(elements):
            element_name = two[0]
            color = self.colors[i % len(self.colors)]
            label_group = self.create_legend_entry(color, element_name, i)
            legend_group.appendChild(label_group)

        # re-calculate chart height after all legend entries added
        self.cfg['diagram_height'] = self.legend_calc_y(self.legend_max_row(len(elements)))

        return legend_group

    def generate_chart(self, title, *elements):
        """
        Return a SVG bar chart for all elements

        @param str title: Chart title
        @param elements: List of tuple with name and length of the entry (not normalized)
        @rtype: Node
        """
        filtered_elements = [(name, length) for name, length in elements if length > 0]
        bar_group = self.generate_bar_area(filtered_elements)
        legend_group = self.generate_legend(filtered_elements)
        svg = self.create_element_svg(self.cfg['diagram_height'], self.cfg['diagram_width'], self.cfg['css_class'])
        chart_title = self.create_element_text(title, font_size=self.cfg['title_height'], font_weight="bold",
                                               stroke_width='0', text_anchor='middle',
                                               x=self.cfg['title_bottommiddle_x'], y=self.cfg['title_bottommiddle_y'])
        svg.appendChild(chart_title)
        svg.appendChild(bar_group)
        svg.appendChild(legend_group)
        return svg


class OOMDisplay:
    """Display the OOM analysis"""

    # result ergibt an manchen stellen self.result.result :-/
    oom_result = OOMResult()
    """
    OOM analysis details
    
    @rtype: OOMResult
    """

    example_rhel7 = u'''\
sed invoked oom-killer: gfp_mask=0x201da, order=0, oom_score_adj=0
sed cpuset=/ mems_allowed=0-1
CPU: 4 PID: 29481 Comm: sed Not tainted 3.10.0-514.6.1.el7.x86_64 #1
Hardware name: HP ProLiant DL385 G7, BIOS A18 12/08/2012
 ffff880182272f10 00000000021dcb0a ffff880418207938 ffffffff816861ac
 ffff8804182079c8 ffffffff81681157 ffffffff810eab9c ffff8804182fe910
 ffff8804182fe928 0000000000000202 ffff880182272f10 ffff8804182079b8
Call Trace:
 [<ffffffff816861ac>] dump_stack+0x19/0x1b
 [<ffffffff81681157>] dump_header+0x8e/0x225
 [<ffffffff810eab9c>] ? ktime_get_ts64+0x4c/0xf0
 [<ffffffff8113ccaf>] ? delayacct_end+0x8f/0xb0
 [<ffffffff8118475e>] oom_kill_process+0x24e/0x3c0
 [<ffffffff811841fd>] ? oom_unkillable_task+0xcd/0x120
 [<ffffffff811842a6>] ? find_lock_task_mm+0x56/0xc0
 [<ffffffff810937ee>] ? has_capability_noaudit+0x1e/0x30
 [<ffffffff81184f96>] out_of_memory+0x4b6/0x4f0
 [<ffffffff81681c60>] __alloc_pages_slowpath+0x5d7/0x725
 [<ffffffff8118b0a5>] __alloc_pages_nodemask+0x405/0x420
 [<ffffffff811cf25a>] alloc_pages_current+0xaa/0x170
 [<ffffffff81180667>] __page_cache_alloc+0x97/0xb0
 [<ffffffff811831b0>] filemap_fault+0x170/0x410
 [<ffffffffa018f016>] ext4_filemap_fault+0x36/0x50 [ext4]
 [<ffffffff811ac2ec>] __do_fault+0x4c/0xc0
 [<ffffffff811ac783>] do_read_fault.isra.42+0x43/0x130
 [<ffffffff811b0f11>] handle_mm_fault+0x6b1/0xfe0
 [<ffffffff811b7825>] ? do_mmap_pgoff+0x305/0x3c0
 [<ffffffff81691c94>] __do_page_fault+0x154/0x450
 [<ffffffff81691fc5>] do_page_fault+0x35/0x90
 [<ffffffff8168e288>] page_fault+0x28/0x30
Mem-Info:
active_anon:7355653 inactive_anon:660960 isolated_anon:0#012 active_file:1263 inactive_file:1167 isolated_file:32#012 unevictable:0 dirty:4 writeback:0 unstable:0#012 slab_reclaimable:27412 slab_unreclaimable:13708#012 mapped:4818 shmem:87896 pagetables:25222 bounce:0#012 free:39513 free_pcp:2958 free_cma:0
Node 0 DMA free:15872kB min:40kB low:48kB high:60kB active_anon:0kB inactive_anon:0kB active_file:0kB inactive_file:0kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:15992kB managed:15908kB mlocked:0kB dirty:0kB writeback:0kB mapped:0kB shmem:0kB slab_reclaimable:0kB slab_unreclaimable:0kB kernel_stack:0kB pagetables:0kB unstable:0kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB writeback_tmp:0kB pages_scanned:0 all_unreclaimable? yes lowmem_reserve[]: 0 2780 15835 15835
Node 0 DMA32 free:59728kB min:7832kB low:9788kB high:11748kB active_anon:2154380kB inactive_anon:604748kB active_file:500kB inactive_file:112kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:3094644kB managed:2848912kB mlocked:0kB dirty:0kB writeback:0kB mapped:4016kB shmem:5140kB slab_reclaimable:6448kB slab_unreclaimable:2796kB kernel_stack:1040kB pagetables:6876kB unstable:0kB bounce:0kB free_pcp:3788kB local_pcp:228kB free_cma:0kB writeback_tmp:0kB pages_scanned:28 all_unreclaimable? no lowmem_reserve[]: 0 0 13055 13055
Node 0 Normal free:36692kB min:36784kB low:45980kB high:55176kB active_anon:12301636kB inactive_anon:793132kB active_file:604kB inactive_file:176kB unevictable:0kB isolated(anon):0kB isolated(file):128kB present:13631488kB managed:13368348kB mlocked:0kB dirty:0kB writeback:0kB mapped:4108kB shmem:207940kB slab_reclaimable:47900kB slab_unreclaimable:28884kB kernel_stack:6624kB pagetables:43340kB unstable:0kB bounce:0kB free_pcp:4204kB local_pcp:640kB free_cma:0kB writeback_tmp:0kB pages_scanned:128 all_unreclaimable? no lowmem_reserve[]: 0 0 0 0
Node 1 Normal free:49436kB min:45444kB low:56804kB high:68164kB active_anon:14967844kB inactive_anon:1244560kB active_file:1552kB inactive_file:1992kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:16777212kB managed:16514220kB mlocked:0kB dirty:16kB writeback:0kB mapped:10760kB shmem:138504kB slab_reclaimable:55300kB slab_unreclaimable:23152kB kernel_stack:6176kB pagetables:50672kB unstable:0kB bounce:0kB free_pcp:3360kB local_pcp:248kB free_cma:0kB writeback_tmp:0kB pages_scanned:125777 all_unreclaimable? yes lowmem_reserve[]: 0 0 0 0
Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 2*64kB (U) 1*128kB (U) 1*256kB (U) 0*512kB 1*1024kB (U) 1*2048kB (M) 3*4096kB (M) = 15872kB
Node 0 DMA32: 203*4kB (UEM) 231*8kB (UEM) 259*16kB (UEM) 231*32kB (UEM) 157*64kB (UEM) 90*128kB (UEM) 49*256kB (UEM) 20*512kB (UE) 3*1024kB (UEM) 1*2048kB (M) 0*4096kB = 63668kB
Node 0 Normal: 1231*4kB (UEM) 391*8kB (UEM) 456*16kB (UEM) 342*32kB (UEM) 141*64kB (UEM) 23*128kB (UEM) 0*256kB 0*512kB 0*1024kB 0*2048kB 0*4096kB = 38260kB
Node 1 Normal: 2245*4kB (UEM) 732*8kB (UEM) 594*16kB (UEM) 396*32kB (UEM) 160*64kB (UEM) 16*128kB (UEM) 2*256kB (UM) 0*512kB 1*1024kB (M) 0*2048kB 0*4096kB = 50836kB
Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=1048576kB
Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB
Node 1 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=1048576kB
Node 1 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB
100155 total pagecache pages
11342 pages in swap cache
Swap cache stats: add 31260615, delete 31249273, find 295999950/297583545
Free swap  = 0kB
Total swap = 8388604kB
8379834 pages RAM
0 pages HighMem/MovableOnly
192987 pages reserved
[ pid ]   uid  tgid total_vm      rss nr_ptes swapents oom_score_adj name
[  390]     0   390    39012     6739      78       51             0 systemd-journal
[  433]     0   433    11104        2      22      360         -1000 systemd-udevd
[  530]     0   530    13854       28      27       83         -1000 auditd
[  559]     0   559     7692       65      19       87             0 systemd-logind
[  563]     0   563     4817       41      14       36             0 irqbalance
[  569]    87   569     7684       52      20       48          -900 dbus-daemon
[  587]    32   587    16240       17      34      116             0 rpcbind
[  647]     0   647    50303       11      36      113             0 gssproxy
[  796]     0   796   193856     2897     207      112             0 rsyslogd
[  818]     0   818    13177        0      27      146             0 vsftpd
[  840]     0   840    62892        9      36      103             0 ypbind
[  868]     0   868    21663       28      43      191         -1000 sshd
[  871]    29   871    11126        2      25      222             0 rpc.statd
[  907]     0   907     8044        4      21       53             0 atd
[  916]     0   916    27509        2      10       30             0 agetty
[  934]     0   934    27509        2      10       31             0 agetty
[ 1255]     0  1255    45716        1      39      337             0 rscd
[ 1268]     0  1268    45746       28      38      353             0 rscd
[ 1269]     0  1269    45716       29      38      311             0 rscd
[ 1285]     0  1285    23290       25      45      235             0 master
[ 1287]    89  1287    23379       52      47      242             0 qmgr
[ 1830]     0  1830   446643      959      68     1234             0 ovcd
[ 2062]     0  2062   144894      511      37      309             0 ovbbccb
[ 2121]     0  2121    33138       26      19      138             0 crond
[ 2136]    38  2136     7846       40      19       88             0 ntpd
[ 2451]     0  2451   177827        0      36      816             0 ovconfd
[ 8145]     0  8145   300303     1616      58      692             0 hpsensor
[ 8204]     0  8204    31508      119      31      328             0 opcmsgi
[ 8405]     0  8405   201479     1289      49      244             0 opcmsga
[ 8472]     0  8472   134080      236      46      514             0 opcmona
[ 8596]     0  8596    31377      172      29      301             0 opcle
[ 8658]     0  8658    81199      124      34      336             0 opcacta
[ 8685]     0  8685   137169    23313      97     3256             0 oacore
[ 6330] 12345  6330     7520       15      18       61             0 rotatelogs
[ 6331] 12345  6331    28318        0      12       83             0 run.sh
[ 6576] 12345  6576  8478546  5157063   15483  1527848             0 mysqld
[27171] 12345 27171     7522       10      18       58             0 rotatelogs
[27172] 12345 27172    28320        3      11       94             0 run.sh
[27502] 12345 27502  4029300  2716569    6505   226225             0 java
[11729]     0 11729    64122     5003      79     2465             0 snmpd
[12130]     0 12130   122202      565      29      175             0 hpasmlited
[12166]     0 12166    11905       89      24      121             0 cmahealthd
[12190]     0 12190    11871       89      24      119             0 cmastdeqd
[12214]     0 12214    13707       84      31      211             0 cmahostd
[12237]     0 12237    12493       38      28      352             0 cmathreshd
[12276]     0 12276    12368       45      30      210             0 cmasm2d
[12299]     0 12299    12485       43      26      282             0 cmaperfd
[12324]     0 12324    31932      184      31      143             0 cmapeerd
[12352]     0 12352    14280       48      32      169             0 cmaeventd
[12379]     0 12379    14831       26      30      198             0 cmafcad
[12407]     0 12407    11806       12      25      128             0 cmasasd
[12436]     0 12436    14364       86      31      181             0 cmaidad
[12463]     0 12463    11288       15      25      125             0 cmaided
[12492]     0 12492    11805       14      26      127             0 cmascsid
[12523]     0 12523    92228      129      63      433             0 cmanicd
[14002]     0 14002    11803       12      25      128             0 cmasm2d
[32615]     0 32615    36254      323      73        7             0 sshd
[  894] 12345   894    36254      328      70        5             0 sshd
[  895] 12345   895     3389      123      11        0             0 ksh
[10620]     0 10620    36254      328      72        0             0 sshd
[10634] 38714 10634    36290      329      70        8             0 sshd
[10635] 38714 10635    14221       25      31      124             0 sftp-server
[29021]     0 29021    36254      314      69        0             0 sshd
[29025] 12345 29025    36254      316      67        0             0 sshd
[29026] 12345 29026    29286       96      12        1             0 ksh
[29051] 12345 29051    29494      330      12       74             0 svr05
[29979] 12345 29979     1666       42       9        0             0 less
[29662]    89 29662    23316      258      43        0             0 pickup
[26065]    89 26065    23317      256      45        0             0 trivial-rewrite
[26066]    89 26066    23353      265      45        0             0 cleanup
[26067]    89 26067    23368      271      45        0             0 smtp
[26743]     0 26743    36254      314      68        0             0 sshd
[26937] 12345 26937    36254      314      67        0             0 sshd
[26938] 12345 26938    29286       96      11        0             0 ksh
[27122] 12345 27122    29494      459      12        0             0 svr05
[28657]     0 28657    36254      314      74        0             0 sshd
[28702] 12345 28702    36254      314      72        0             0 sshd
[28703] 12345 28703    29286       97      11        0             0 ksh
[28993]     0 28993    36254      314      72        0             0 sshd
[28996] 12345 28996    29526      531      12        0             0 svr05
[29006] 12345 29006    36254      314      69        0             0 sshd
[29007] 12345 29007    29286       96      11        0             0 ksh
[29110] 12345 29110    29558      745      12        0             0 svr05
[29481] 12345 29481    29214       58      14        0             0 sed
[29752] 12345 29752     7522      296      19        0             0 rotatelogs
Out of memory: Kill process 6576 (mysqld) score 651 or sacrifice child
Killed process 6576 (mysqld) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
'''

    example_ubuntu2110 = u'''\
kworker/0:2 invoked oom-killer: gfp_mask=0xcc0(GFP_KERNEL), order=-1, oom_score_adj=0
CPU: 0 PID: 735 Comm: kworker/0:2 Not tainted 5.13.0-19-generic #19-Ubuntu
Hardware name: QEMU Standard PC (i440FX + PIIX, 1996), BIOS ArchLinux 1.14.0-1 04/01/2014
Workqueue: events moom_callback
Call Trace:
 show_stack+0x52/0x58
 dump_stack+0x7d/0x9c
 dump_header+0x4f/0x1f9
 oom_kill_process.cold+0xb/0x10
 out_of_memory.part.0+0xce/0x270
 out_of_memory+0x41/0x80
 moom_callback+0x7a/0xb0
 process_one_work+0x220/0x3c0
 worker_thread+0x53/0x420
 kthread+0x11f/0x140
 ? process_one_work+0x3c0/0x3c0
 ? set_kthread_struct+0x50/0x50
 ret_from_fork+0x22/0x30
Mem-Info:
active_anon:221 inactive_anon:14331 isolated_anon:0
 active_file:18099 inactive_file:22324 isolated_file:0
 unevictable:4785 dirty:633 writeback:0
 slab_reclaimable:6027 slab_unreclaimable:6546
 mapped:15338 shmem:231 pagetables:412 bounce:0
 free:427891 free_pcp:153 free_cma:0
Node 0 active_anon:884kB inactive_anon:57324kB active_file:72396kB inactive_file:89296kB unevictable:19140kB isolated(anon):0kB isolated(file):0kB mapped:61352kB dirty:2532kB writeback:0kB shmem:924kB shmem_thp: 0kB shmem_pmdmapped: 0kB anon_thp: 0kB writeback_tmp:0kB kernel_stack:1856kB pagetables:1648kB all_unreclaimable? no
Node 0 DMA free:15036kB min:352kB low:440kB high:528kB reserved_highatomic:0KB active_anon:0kB inactive_anon:0kB active_file:0kB inactive_file:0kB unevictable:0kB writepending:0kB present:15992kB managed:15360kB mlocked:0kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB
lowmem_reserve[]: 0 1893 1893 1893 1893
Node 0 DMA32 free:1696528kB min:44700kB low:55872kB high:67044kB reserved_highatomic:0KB active_anon:884kB inactive_anon:57324kB active_file:72396kB inactive_file:89296kB unevictable:19140kB writepending:2532kB present:2080640kB managed:2010036kB mlocked:19140kB bounce:0kB free_pcp:612kB local_pcp:612kB free_cma:0kB
lowmem_reserve[]: 0 0 0 0 0
Node 0 DMA: 1*4kB (U) 1*8kB (U) 1*16kB (U) 1*32kB (U) 0*64kB 1*128kB (U) 0*256kB 1*512kB (U) 0*1024kB 1*2048kB (M) 3*4096kB (M) = 15036kB
Node 0 DMA32: 0*4kB 4*8kB (UM) 25*16kB (UME) 151*32kB (UM) 56*64kB (UM) 21*128kB (ME) 36*256kB (UME) 47*512kB (UM) 41*1024kB (UM) 32*2048kB (UM) 377*4096kB (UM) = 1696528kB
Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB
42845 total pagecache pages
0 pages in swap cache
Swap cache stats: add 0, delete 0, find 0/0
Free swap  = 0kB
Total swap = 0kB
524158 pages RAM
0 pages HighMem/MovableOnly
17809 pages reserved
0 pages hwpoisoned
Tasks state (memory values in pages):
[  pid  ]   uid  tgid total_vm      rss pgtables_bytes swapents oom_score_adj name
[    323]     0   323     9458     2766    77824        0          -250 systemd-journal
[    356]     0   356     5886     1346    69632        0         -1000 systemd-udevd
[    507]     0   507    70208     4646    98304        0         -1000 multipathd
[    542]   101   542    21915     1391    69632        0             0 systemd-timesyn
[    587]   102   587     4635     1882    73728        0             0 systemd-network
[    589]   103   589     5875     2951    86016        0             0 systemd-resolve
[    602]     0   602     1720      322    53248        0             0 cron
[    603]   104   603     2159     1168    53248        0          -900 dbus-daemon
[    608]     0   608     7543     4677    94208        0             0 networkd-dispat
[    609]   107   609    55313     1248    73728        0             0 rsyslogd
[    611]     0   611   311571     8248   221184        0          -900 snapd
[    613]     0   613     3404     1668    65536        0             0 systemd-logind
[    615]     0   615    98223     3142   126976        0             0 udisksd
[    620]     0   620     1443      278    45056        0             0 agetty
[    623]     0   623     1947     1147    57344        0             0 login
[    650]     0   650     3283     1683    65536        0         -1000 sshd
[    651]     0   651    27005     5232   106496        0             0 unattended-upgr
[    661]     0   661    58546     1812    90112        0             0 polkitd
[    856]  1000   856     3789     2157    73728        0             0 systemd
[    857]  1000   857    25433      835    86016        0             0 (sd-pam)
[    862]  1000   862     2208     1373    53248        0             0 bash
[    876]  1000   876     2870     1356    57344        0             0 sudo
[    877]     0   877     1899     1052    53248        0             0 bash
oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=/,mems_allowed=0,global_oom,task_memcg=/system.slice/unattended-upgrades.service,task=unattended-upgr,pid=651,uid=0
Out of memory: Killed process 651 (unattended-upgr) total-vm:108020kB, anon-rss:8380kB, file-rss:12548kB, shmem-rss:0kB, UID:0 pgtables:104kB oom_score_adj:0
'''

    sorted_column_number = None
    """
    Processes will sort by values in this column
    
    @type: int 
    """

    sort_order = None
    """Sort order for process values"""

    svg_array_updown = """
<svg width="8" height="11">
  <use xlink:href="#svg_array_updown" />
</svg>
    """
    """SVG graphics with two black triangles UP and DOWN for sorting"""

    svg_array_up = """
<svg width="8" height="11">
    <use xlink:href="#svg_array_up" />
</svg>
    """
    """SVG graphics with one black triangle UP for sorting"""

    svg_array_down = """
<svg width="8" height="11">
    <use xlink:href="#svg_array_down" />
</svg>
    """
    """SVG graphics with one black triangle DOWN for sorting"""

    def __init__(self):
        self.oom = None
        self.set_HTML_defaults()
        self.update_toc()

        element = document.getElementById('version')
        element.textContent = "v{}".format(VERSION)

    def _set_item(self, item):
        """
        Paste the content into HTML elements with the ID / Class that matches the item name.

        The content won't be formatted. Only suffixes for pages and kbytes are added in the singular or plural.
        """
        elements = document.getElementsByClassName(item)
        for element in elements:
            content = self.oom_result.details.get(item, '')
            if isinstance(content, str):
                content = content.strip()

            if content == '<not found>':
                row = element.parentNode
                row.classList.add('js-text--display-none')

            if item.endswith('_pages') and isinstance(content, int):
                if content == 1:
                    content = "{} page".format(content)
                else:
                    content = "{} pages".format(content)

            if item.endswith('_bytes') and isinstance(content, int):
                if content == 1:
                    content = "{} Byte".format(content)
                else:
                    content = "{} Bytes".format(content)

            if item.endswith('_kb') and isinstance(content, int):
                if content == 1:
                    content = "{} kByte".format(content)
                else:
                    content = "{} kBytes".format(content)

            if item.endswith('_percent') and isinstance(content, int):
                content = "{}%".format(content)

            element.textContent = content

        if DEBUG:
            show_element('notify_box')

    def update_toc(self):
        """
        Update the TOC to show current headlines only

        There are two conditions to show a h2 headline in TOC:
         * the headline is visible
         * the id attribute is set
        """
        new_toc = ''

        toc_content = document.querySelectorAll('nav > ul')[0]

        for element in document.querySelectorAll('h2'):
            if not (is_visible(element) and element.id):
                continue

            new_toc += '<li><a href="#{}">{}</a></li>'.format(element.id, element.textContent)

        toc_content.innerHTML = new_toc

    def pstable_fill_HTML(self):
        """
        Create the process table with additional information
        """
        # update table heading
        for i, element in enumerate(document.querySelectorAll('#pstable_header > tr > td')):
            element.classList.remove('pstable__row-pages--width', 'pstable__row-numeric--width',
                                     'pstable__row-oom-score-adj--width')

            key = self.oom_result.kconfig.pstable_items[i]
            if key in ['notes', 'names']:
                klass = 'pstable__row-notes--width'
            elif key == 'oom_score_adj':
                klass = 'pstable__row-oom-score-adj--width'
            elif key.endswith('_bytes') or key.endswith('_kb') or key.endswith('_pages'):
                klass = 'pstable__row-pages--width'
            else:
                klass = "pstable__row-numeric--width"
            element.firstChild.textContent = self.oom_result.kconfig.pstable_html[i]
            element.classList.add(klass)

        # create new table
        new_table = ''
        table_content = document.getElementById('pstable_content')
        for pid in self.oom_result.details['_pstable_index']:
            if pid == self.oom_result.details['trigger_proc_pid']:
                css_class = 'class="js-pstable__triggerproc--bgcolor"'
            elif pid == self.oom_result.details['killed_proc_pid']:
                css_class = 'class="js-pstable__killedproc--bgcolor"'
            else:
                css_class = ''
            process = self.oom_result.details['_pstable'][pid]
            fmt_list = [process[i] for i in self.oom_result.kconfig.pstable_items if not i == 'pid']
            fmt_list.insert(0, css_class)
            fmt_list.insert(1, pid)
            line = """
            <tr {}>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
            </tr>
            """.format(*fmt_list)
            new_table += line

        table_content.innerHTML = new_table

    def pstable_set_sort_triangle(self):
        """Set the sorting symbols for all columns in the process table"""
        for column_name in self.oom_result.kconfig.pstable_items:
            column_number = self.oom_result.kconfig.pstable_items.index(column_name)
            element_id = "js-pstable_sort_col{}".format(column_number)
            element = document.getElementById(element_id)
            if not element:
                internal_error('Missing id "{}" in process table.'.format(element_id))
                continue

            if column_number == self.sorted_column_number:
                if self.sort_order == 'descending':
                    element.innerHTML = self.svg_array_down
                else:
                    element.innerHTML = self.svg_array_up
            else:
                element.innerHTML = self.svg_array_updown

    def set_HTML_defaults(self):
        """Reset the HTML document but don't clean elements"""
        # hide all elements marked to be hidden by default
        hide_elements('.js-text--default-hide')

        # show all elements marked to be shown by default
        show_elements('.js-text--default-show')

        # show hidden rows
        show_elements('table .js-text--display-none')

        # clear notification box
        element = document.getElementById('notify_box')
        while element.firstChild:
            element.removeChild(element.firstChild)

        # remove svg charts
        for element_id in ('svg_swap', 'svg_ram'):
            element = document.getElementById(element_id)
            while element.firstChild:
                element.removeChild(element.firstChild)

        self._clear_pstable()

    def _clear_pstable(self):
        """Clear process table"""
        element = document.getElementById('pstable_content')
        while element.firstChild:
            element.removeChild(element.firstChild)

        # reset sort triangles
        self.sorted_column_number = None
        self.sort_order = None
        self.pstable_set_sort_triangle()

        # reset table heading
        for i, element in enumerate(document.querySelectorAll('#pstable_header > tr > td')):
            element.classList.remove('pstable__row-pages--width', 'pstable__row-numeric--width',
                                     'pstable__row-oom-score-adj--width')
            element.firstChild.textContent = "col {}".format(i + 1)

    def copy_example_rhel7_to_form(self):
        document.getElementById('textarea_oom').value = self.example_rhel7

    def copy_example_ubuntu_to_form(self):
        document.getElementById('textarea_oom').value = self.example_ubuntu2110

    def reset_form(self):
        document.getElementById('textarea_oom').value = ""
        self.set_HTML_defaults()
        self.update_toc()

    def toggle_oom(self, show=False):
        """Toggle the visibility of the full OOM message"""
        oom_element = document.getElementById('oom')
        row_with_oom = oom_element.parentNode.parentNode
        toggle_msg = document.getElementById('oom_toogle_msg')

        if show or row_with_oom.classList.contains('js-text--display-none'):
            row_with_oom.classList.remove('js-text--display-none')
            toggle_msg.text = "(click to hide)"
        else:
            row_with_oom.classList.add('js-text--display-none')
            toggle_msg.text = "(click to show)"

    def analyse_and_show(self):
        """Analyse the OOM text inserted into the form and show the results"""
        self.oom = OOMEntity(self.load_from_form())

        # set defaults and clear notifications
        self.set_HTML_defaults()

        analyser = OOMAnalyser(self.oom)
        success = analyser.analyse()
        if success:
            self.oom_result = analyser.oom_result
            self.show_oom_details()
            self.update_toc()
        else:
            # don't show results - just return
            return

    def load_from_form(self):
        """
        Return the OOM text from textarea element
        
        @rtype: str 
        """
        element = document.getElementById('textarea_oom')
        oom_text = element.value
        return oom_text

    def show_oom_details(self):
        """
        Show all extracted details as well as additionally generated information
        """
        hide_element('input')
        show_element('analysis')
        if self.oom_result.oom_type == OOMEntityType.manual:
            hide_elements('.js-oom-automatic--show')
            show_elements('.js-oom-manual--show')
        else:
            show_elements('.js-oom-automatic--show')
            hide_elements('.js-oom-manual--show')

        for item in self.oom_result.details.keys():
            # ignore internal items
            if item.startswith('_'):
                continue
            self._set_item(item)

        # Hide "OOM Score" if not available
        # since KernelConfig_5_0.EXTRACT_PATTERN_OVERLAY_50['Process killed by OOM']
        if 'killed_proc_score' in self.oom_result.details:
            show_elements('.js-killed-proc-score--show')
        else:
            hide_elements('.js-killed-proc-score--show')

        # generate process table
        self.pstable_fill_HTML()
        self.pstable_set_sort_triangle()

        # show/hide swap space
        if self.oom_result.swap_active:
            # generate swap usage diagram
            svg = SVGChart()
            svg_swap = svg.generate_chart('Swap Summary',
                                          ('Swap Used', self.oom_result.details['swap_used_kb']),
                                          ('Swap Free', self.oom_result.details['swap_free_kb']),
                                          ('Swap Cached', self.oom_result.details['swap_cache_kb']))
            elem_svg_swap = document.getElementById('svg_swap')
            elem_svg_swap.appendChild(svg_swap)
            show_elements('.js-swap-active--show')
            hide_elements('.js-swap-inactive--show')
        else:
            hide_elements('.js-swap-active--show')
            show_elements('.js-swap-inactive--show')

        # generate RAM usage diagram
        ram_title_attr = (
            ('Active mem',         'active_anon_pages'),
            ('Inactive mem',       'inactive_anon_pages'),
            ('Isolated mem',       'isolated_anon_pages'),
            ('Active PC',          'active_file_pages'),
            ('Inactive PC',        'inactive_file_pages'),
            ('Isolated PC',        'isolated_file_pages'),
            ('Unevictable',        'unevictable_pages'),
            ('Dirty',              'dirty_pages'),
            ('Writeback',          'writeback_pages'),
            ('Unstable',           'unstable_pages'),
            ('Slab reclaimable',   'slab_reclaimable_pages'),
            ('Slab unreclaimable', 'slab_unreclaimable_pages'),
            ('Mapped',             'mapped_pages'),
            ('Shared',             'shmem_pages'),
            ('Pagetable',          'pagetables_pages'),
            ('Bounce',             'bounce_pages'),
            ('Free',               'free_pages'),
            ('Free PCP',           'free_pcp_pages'),
            ('Free CMA',           'free_cma_pages'),
        )
        chart_elements = [(title, self.oom_result.details[value]) for title, value in ram_title_attr
                          if value in self.oom_result.details]
        svg = SVGChart()
        svg_ram = svg.generate_chart('RAM Summary', *chart_elements)
        elem_svg_ram = document.getElementById('svg_ram')
        elem_svg_ram.appendChild(svg_ram)

        element = document.getElementById('oom')
        element.textContent = self.oom_result.oom_text
        self.toggle_oom(show=False)

    def sort_pstable(self, column_number):
        """
        Sort process table by values

        :param int column_number: Number of column to sort
        """
        # TODO Check operator overloading
        #      Operator overloading (Pragma opov) does not work in this context.
        #      self.oom_result.kconfig.pstable_items + ['notes'] will compile to a string
        #      "pid,uid,tgid,total_vm_pages,rss_pages,nr_ptes_pages,swapents_pages,oom_score_adjNotes" and not to an
        #      array
        ps_table_and_notes = self.oom_result.kconfig.pstable_items[:]
        ps_table_and_notes.append('notes')
        column_name = ps_table_and_notes[column_number]
        if column_name not in ps_table_and_notes:
            internal_error('Can not sort process table with an unknown column name "{}"'.format(column_name))
            return

        # reset sort order if the column has changes
        if column_number != self.sorted_column_number:
            self.sort_order = None
        self.sorted_column_number = column_number

        if not self.sort_order or self.sort_order == 'descending':
            self.sort_order = 'ascending'
            self.sort_psindex_by_column(column_name)
        else:
            self.sort_order = 'descending'
            self.sort_psindex_by_column(column_name, True)

        self.pstable_fill_HTML()
        self.pstable_set_sort_triangle()

    def sort_psindex_by_column(self, column_name, reverse=False):
        """
        Sort the pid list '_pstable_index' based on the values in the process dict '_pstable'.

        Is uses bubble sort with all disadvantages but just a few lines of code
        """
        ps = self.oom_result.details['_pstable']
        ps_index = self.oom_result.details['_pstable_index']

        def getvalue(column, pos):
            if column == 'pid':
                value = ps_index[pos]
            else:
                value = ps[ps_index[pos]][column]
            # JS sorts alphanumeric by default, convert values explicit to integers to sort numerically
            if column not in self.oom_result.kconfig.pstable_non_ints and value is not js_undefined:
                value = int(value)
            return value

        # We set swapped to True so the loop looks runs at least once
        swapped = True
        while swapped:
            swapped = False
            for i in range(len(ps_index) - 1):

                v1 = getvalue(column_name, i)
                v2 = getvalue(column_name, i+1)

                if (not reverse and v1 > v2) or (reverse and v1 < v2):
                    # Swap the elements
                    ps_index[i], ps_index[i+1] = ps_index[i+1], ps_index[i]

                    # Set the flag to True so we'll loop again
                    swapped = True


OOMDisplayInstance = OOMDisplay()
