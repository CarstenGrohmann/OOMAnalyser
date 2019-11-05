# -*- coding: Latin-1 -*-
#
# Linux OOM Analyser
#
# Copyright (c) 2017-2019 Carsten Grohmann
# License: MIT - THIS PROGRAM COMES WITH NO WARRANTY

import re

DEBUG = False
"""Show additional information during the development cycle"""

VERSION = "0.2.0"
"""Version number"""


def hide_element(element_id):
    """Hide the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.add('js-text--display-none')


def show_element(element_id):
    """Show the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.remove('js-text--display-none')


def toggle(element_id):
    """Toggle the visibility of the given HTML element"""
    element = document.getElementById(element_id)
    element.classList.toggle('js-text--display-none')


def error(msg):
    """Show the error box and add the error message"""
    show_notifybox('ERROR', msg)


def warning(msg):
    """Show the error box and add the warning message"""
    show_notifybox('WARNING', msg)


def show_notifybox(prefix, msg):
    """Show the error box and the message"""
    if prefix == 'WARNING':
        css_class = 'js-notify_box__msg--warning'
    else:
        css_class = 'js-notify_box__msg--error'
    show_element('notify_box')
    notify_box = document.getElementById('notify_box')
    notification = document.createElement('div')
    notification.classList.add(css_class)
    notification.innerHTML = '{}: {}<br>'.format(prefix, msg)
    notify_box.appendChild(notification)


class OOM(object):
    """Hold OOM object and provide access"""

    current_line = 0
    """Zero based index of the current line in self.lines"""

    lines = []
    """OOM text as list of lines"""

    state = "unknown"
    """State of the OOM after initial parsing"""

    text = ""
    """OOM as text"""

    def __init__(self, text):
        # use Unix LF only
        text = text.replace('\r\n', '\r')
        oom_lines = text.split('\n')

        self.current_line = 0
        self.lines = oom_lines
        self.text = text

        # don't do  anything if the text does not contains the leading OOM message
        if 'invoked oom-killer:' not in text:
            self.state = "oom_invalid"
            return

        oom_lines = self._remove_non_oom_lines(oom_lines)
        oom_lines = self._strip_needless_columns(oom_lines)
        oom_lines = self._rsyslog_unescape_lf(oom_lines)

        self.lines = oom_lines
        self.text = '\n'.join(oom_lines)

        if 'Killed process' in text:
            self.state = "oom_complete"
        else:
            self.state = "oom_started"

    def _number_of_columns_to_strip(self, first_line):
        """
        Determinate number of columns left to the OOM message to strip.

        Sometime timestamps, hostnames and or syslog tags are left to the OOM message. This columns will be count to
        strip later.
        """
        to_strip = 0

        columns = first_line.split(" ")
        try:
            # strip all before "<program name> invoked oom-killer: gfp_mask=0x280da, order=0, oom_score_adj=0
            to_strip = columns.index("invoked")
            # decrease to include <program name>
            to_strip -= 1
        except ValueError:
            pass

        return to_strip
        
    def _remove_non_oom_lines(self, oom_lines):
        """Remove all lines before and after OOM message block"""
        cleaned_lines = []
        in_oom_lines = False
        
        for line in oom_lines:
            # first line of the oom message block
            if "invoked oom-killer:" in line:
                in_oom_lines = True
                
            if in_oom_lines:
                cleaned_lines.append(line)

            # next line will not be part of the oom anymore
            if 'Killed process' in line:
                break
        
        return cleaned_lines

    def _rsyslog_unescape_lf(self, oom_lines):
        """
        Rsyslog replaces line breaks with their ocal representation #012.

        This feature can be controlled inside the rsyslog configuration with the directives
        $EscapeControlCharactersOnReceive, $Escape8BitCharactersOnReceive and $ControlCharactersEscapePrefix.

        The replacement is only in second line (active_anon:....) of the Mem-Info block.
        """
        lines = []

        for line in oom_lines:
            if '#012' in line:
                line = line.replace('#012', '\r')
                expanded = line.split('\r')
                lines.extend(expanded)
            else:
                lines.append(line)

        return lines

    def _strip_needless_columns(self, oom_lines):
        """
        Remove needless columns at the start of every line.

        This function removes all leading items w/o any relation to the OOM message like, date and time, hostname,
        syslog priority/facility.
        """
        stripped_lines = []
        cols_to_strip = self._number_of_columns_to_strip(oom_lines[0])

        for line in oom_lines:
            # remove empty lines
            if not line.strip():
                continue

            if cols_to_strip:
                elements = line.split(" ", cols_to_strip)
                line = elements.pop(-1)

            # OOMs logged to /var/log/messages / journalctl may contain
            # "kernel:" at the begin of the content
            if line.startswith('kernel:'):
                line = line[7:]

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

        :param pattern: Text to fine
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


class OOMAnalyser(object):
    """Analyse an OOM object and calculate additional values"""

    REC_INVOKED_OOMKILLER = re.compile(
        r'^(?P<trigger_proc_name>[\w ]+) invoked oom-killer: '
        r'gfp_mask=(?P<trigger_proc_gfp_mask>0x[a-z0-9]+)(\((?P<trigger_proc_gfp_flags>[A-Z_|]+)\))?, '
        r'(nodemask=(?P<trigger_proc_nodemask>([\d,-]+|\(null\))), )?'
        r'order=(?P<trigger_proc_order>\d+), '
        r'oom_score_adj=(?P<trigger_proc_oomscore>\d+)',
        re.MULTILINE)

    REC_PID_KERNELVERSION = re.compile(
        r'^CPU: \d+ PID: (?P<trigger_proc_pid>\d+) '
        r'Comm: .* (Not tainted|Tainted:.*) '
        r'(?P<kernel_version>\d[\w.-]+) #\d',
        re.MULTILINE
    )

    # split caused by a limited number of iterations during converting PY regex into JS regex
    REC_MEMINFO_1 = re.compile(
        # head line
        r'^Mem-Info:.*'

        # first line break
        r'(?:\n)'

        # first line (starting with a space)
        r'^active_anon:(?P<active_anon_pages>\d+) inactive_anon:(?P<inactive_anon_pages>\d+) '
        r'isolated_anon:(?P<isolated_anon_pages>\d+)'

        # next line break
        r'(?:\n)'

        # remaining lines (with leading space)
        r'^ active_file:(?P<active_file_pages>\d+) inactive_file:(?P<inactive_file_pages>\d+) '
        r'isolated_file:(?P<isolated_file_pages>\d+)'

        # next line break
        r'(?:\n)'

        r'^ unevictable:(?P<unevictable_pages>\d+) dirty:(?P<dirty_pages>\d+) writeback:(?P<writeback_pages>\d+) '
        r'unstable:(?P<unstable_pages>\d+)'

        # # next line break
        # r'(?:\n)'
        #
        , re.MULTILINE
    )

    REC_MEMINFO_2 = re.compile(
        r'^ slab_reclaimable:(?P<slab_reclaimable_pages>\d+) slab_unreclaimable:(?P<slab_unreclaimable_pages>\d+)'
        r'(?:\n)'
        r'^ mapped:(?P<mapped_pages>\d+) shmem:(?P<shmem_pages>\d+) pagetables:(?P<pagetables_pages>\d+) '
        r'bounce:(?P<bounce_pages>\d+)'
        r'(?:\n)'
        r'^ free:(?P<free_pages>\d+) free_pcp:(?P<free_pcp_pages>\d+) free_cma:(?P<free_cma_pages>\d+)',
        re.MULTILINE
    )

    REC_MEM_NODEINFO = re.compile(r'(^Node \d+ (DMA|Normal|hugepages).*(:?\n))+', re.MULTILINE)

    REC_PAGECACHE = re.compile(r'^(?P<pagecache_total_pages>\d+) total pagecache pages.*$', re.MULTILINE)

    REC_SWAP = re.compile(
        r'^(?P<swap_cache_pages>\d+) pages in swap cache'
        r'(?:\n)'
        r'^Swap cache stats: add \d+, delete \d+, find \d+/\d+'
        r'(?:\n)'
        r'^Free swap  = (?P<swap_free_kb>\d+)kB'
        r'(?:\n)'
        r'^Total swap = (?P<swap_total_kb>\d+)kB',
        re.MULTILINE)

    REC_PAGEINFO = re.compile(
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
        re.MULTILINE)

    REC_PROCESSES = re.compile(
        r'^\[ pid \].*(?:\n)'
        r'(^(\[[ \d]+.+)(?:\n))+',
        re.MULTILINE)

    REC_KILLED = re.compile(
        r'^Out of memory: Kill process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\w ]+)\) '
        r'score (?P<killed_proc_score>\d+) or sacrifice child'
        r'(?:\n)'
        r'Killed process \d+ \(.*\) total-vm:(?P<killed_proc_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, '
        r'file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB',
        re.MULTILINE)

    lines = []
    """All lines of an OOM without leading timestamps"""

    results = {}
    """Extracted result"""

    # Reference to the OOM object
    oom = None

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

    def __init__(self, oom):
        self.results = {}
        self.oom = oom

    def _extract_block_from_next_pos(self, marker):
        """
        Extract a block starting with the marker and add all lines with a leading space character

        :rtype: str
        """
        block = ''
        if not self.oom.find_text(marker):
            return block

        line = self.oom.current()
        block += "{}\n".format(line)
        for line in self.oom:
            if not line.startswith(' '):
                self.oom.back()
                break
            block += "{}\n".format(line)
        return block

    def _extract_from_oom_text(self):
        """Extract details from OOM message text"""

        for rec in [self.REC_INVOKED_OOMKILLER,
                    self.REC_KILLED,
                    self.REC_MEMINFO_1,
                    self.REC_MEMINFO_2,
                    self.REC_PAGECACHE,
                    self.REC_PAGEINFO,
                    self.REC_PID_KERNELVERSION,
                    self.REC_SWAP,
                    ]:
            match = rec.search(self.oom.text)
            if match:
                self.results.update(match.groupdict())

        for groupname, rec in [('mem_node_info', self.REC_MEM_NODEINFO),
                               ('process_table', self.REC_PROCESSES),
                               ]:
            match = rec.search(self.oom.text)
            if match:
                self.results[groupname] = match.group()

        self.results['hardware_info'] = self._extract_block_from_next_pos('Hardware name:')

        # strip "Call Trace" line at beginning and remove leading spaces
        call_trace = ''
        block = self._extract_block_from_next_pos('Call Trace:')
        for line in block.split('\n'):
            if line.startswith('Call Trace'):
                continue
            call_trace += "{}\n".format(line.strip())
        self.results['call_trace'] = call_trace

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

    def _calc_from_oom_details(self):
        """
        Calculate values from already extracted details

        @see: self.results
        """
        # convert all *_pages and *_kb to integer
        # __pragma__ ('jsiter')
        for item in self.results:
            if self.results[item] is None:
                self.results[item] = '<not found>'
                continue
            if item.endswith('_kb') or item.endswith('_pages'):
                try:
                    self.results[item] = int(self.results[item])
                except:
                    error('Converting item {}: {} to integer failed'.format(item, self.results[item]))

        # __pragma__ ('nojsiter')

        kernel_version = self.results.get('kernel_version', '')
        if 'x86_64' in kernel_version:
            self.results['platform'] = 'x86 64bit'
        else:
            self.results['platform'] = 'unknown'

        self.results['dist'] = self.guess_distribution(kernel_version)

        # educated guess
        self.results['page_size'] = 4

        self.results['swap_cache_kb'] = self.results['swap_cache_pages'] * self.results['page_size']
        del self.results['swap_cache_pages']

        #  SwapUsed = SwapTotal - SwapFree - SwapCache
        self.results['swap_used_kb'] = self.results['swap_total_kb'] - self.results['swap_free_kb'] - \
                                       self.results['swap_cache_kb']

        self.results['trigger_proc_requested_memory'] = 2 ** self.results['trigger_proc_order']
        self.results['trigger_proc_requested_memory_kbytes'] = self.results['page_size']

        # process gfp_mask
        if self.results['trigger_proc_gfp_flags'] != '<not found>':     # None has been is converted to '<not found>'
            flags = self.results['trigger_proc_gfp_flags']
            del self.results['trigger_proc_gfp_flags']
        else:
            flags, unknown = self._hex2flags(self.results['trigger_proc_gfp_mask'], self.GFP_FLAGS)
            if unknown:
                # TODO Missing format specifier {0:x} in Transcrypt?
                flags.append('0x{}'.format(unknown.toString(16)))
            flags = ' | '.join(flags)

        self.results['trigger_proc_gfp_mask'] = '{} ({})'.format(self.results['trigger_proc_gfp_mask'], flags)
        # already fully processed and no own element to display -> delete otherwise an error msg will be shown
        del self.results['trigger_proc_gfp_flags']

    def guess_distribution(self, kernel_version):
        """Guess distribution from kernel version"""
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
        elif '_generic' in kernel_version:
            dist = 'Ubuntu'
        return dist

    def analyse(self):
        """Return the analysis of the given OOM object"""
        self._extract_from_oom_text()
        self._calc_from_oom_details()
        return self.results


class OOMDisplay(object):
    """Display the OOM analysis"""

    oom_details = {}
    """Extracted result"""

    example = u'''\
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
active_anon:7355653 inactive_anon:660960 isolated_anon:0
 active_file:1263 inactive_file:1167 isolated_file:32
 unevictable:0 dirty:4 writeback:0 unstable:0
 slab_reclaimable:27412 slab_unreclaimable:13708
 mapped:4818 shmem:87896 pagetables:25222 bounce:0
 free:39513 free_pcp:2958 free_cma:0
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
[ 6576] 12345  6576  8478546  5157063   15483  1527848             0 java
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
Out of memory: Kill process 6576 (java) score 651 or sacrifice child
Killed process 6576 (java) total-vm:33914892kB, anon-rss:20629004kB, file-rss:0kB, shmem-rss:0kB
'''

    mem_modinfo_entries = ("active_anon_pages", "inactive_anon_pages", "isolated_anon_pages",
                           "active_file_pages", "inactive_file_pages", "isolated_file_pages",
                           "unevictable_pages", "dirty_pages", "writeback_pages", "unstable_pages",
                           "slab_reclaimable_pages", "slab_unreclaimable_pages",
                           "mapped_pages", "shmem_pages", "pagetables_pages", "bounce_pages",
                           "free_pages", "free_pcp_pages", "free_cma_pages",
                           )

    svg_namespace = 'http://www.w3.org/2000/svg'

    # from Sasha Trubetskoy - https://sashat.me/2017/01/11/list-of-20-simple-distinct-colors/
    svg_colours = [
        '#e6194b',  # Red
        '#3cb44b',  # Green
        '#ffe119',  # Yellow
        '#0082c8',  # Blue
        '#f58231',  # Orange
        '#911eb4',  # Purple
        '#46f0f0',  # Cyan
        '#f032e6',  # Magenta
        '#d2f53c',  # Lime
        '#fabebe',  # Pink
        '#008080',  # Teal
        '#e6beff',  # Lavender
        '#aa6e28',  # Brown
        '#fffac8',  # Beige
        '#800000',  # Maroon
        '#aaffc3',  # Mint
        '#808000',  # Olive
        '#ffd8b1',  # Coral
        '#000080',  # Navy
        '#808080',  # Grey
    ]

    def __init__(self):
        self.set_HTML_defaults()

        element = document.getElementById('version')
        element.textContent = "v{}".format(VERSION)

    def _set_single_item(self, item):
        """
        Set content of a single item to the HTML element with the same name.

        The content won't be formatted.
        """
        element = document.getElementById(item)
        if not element:
            print("ERROR: HTML element not found: ", item)
            return

        content = self.oom_details.get(item, '')
        if isinstance(content, str):
            content = content.strip()
        element.textContent = content

        if content == '<not found>':
            row = element.parentNode
            row.classList.add('js-text--display-none')

        if DEBUG:
            show_element('notify_box')

    def set_HTML_defaults(self, clean_oom=True):
        """Reset the whole HTML document"""
        if clean_oom:
            document.getElementById('textarea_oom').value = "<paste your OOM here>"

        hide_element('analysis')
        hide_element('notify_box')
        show_element('input')

        # show hidden rows
        for element in document.querySelectorAll('table .js-text--display-none'):
            element.classList.remove('js-text--display-none')

        for item in self.mem_modinfo_entries:
            element = document.getElementById(item)
            element.textContent = ""

        # clear notification box
        element = document.getElementById('notify_box')
        while element.firstChild:
            element.removeChild(element.firstChild)
        hide_element('notify_box')

        # remove svg charts
        for element_id in ('svg_swap', 'svg_ram'):
            element = document.getElementById(element_id)
            while element.firstChild:
                element.removeChild(element.firstChild)

    def svg_create_element(self, height, width):
        """Return an empty SVG element"""
        svg = document.createElementNS(self.svg_namespace, 'svg')
        svg.setAttribute('version', '1.1')
        svg.setAttribute('height', height)
        svg.setAttribute('width', width)
        svg.setAttribute('viewBox', '0 0 {} {}'.format(width, height))
        return svg

    def svg_create_rect(self, x=0, y=0, width=0, height=0, colour=None):
        rect = document.createElementNS(self.svg_namespace, 'rect')
        if x:
            rect.setAttribute('x', x)
        if y:
            rect.setAttribute('y', y)
        if width:
            rect.setAttribute('width', width)
        if height:
            rect.setAttribute('height', height)
        if colour:
            rect.setAttribute('fill', colour)
        return rect

    def svg_generate_bar_chart(self, *elements):
        """Generate a SVG bar chart"""
        bar_height = 100
        label_height = 80
        length_factor = 4
        overall_height = bar_height + label_height
        overall_width = 100 * length_factor

        svg = self.svg_create_element(overall_height, overall_width)

        sum_all_elements = sum([length for unused, length in elements])

        current_pos = 0
        bar_group = document.createElementNS(self.svg_namespace, 'g')
        bar_group.setAttribute('id', 'bar_group')
        bar_group.setAttribute('stroke', 'black')
        bar_group.setAttribute('stroke-width', 2)

        nr_processed_elements = 0
        for title, length in elements:
            # length is None/undefined is the regular expression doesn't find any values
            if not length:
                continue

            rect_len = int(100 * length / sum_all_elements) * length_factor

            if not rect_len:
                continue

            colour = self.svg_colours[nr_processed_elements % len(self.svg_colours)]

            rect = self.svg_create_rect(current_pos, 0, rect_len, bar_height, colour)
            bar_group.appendChild(rect)

            label_group = document.createElementNS(self.svg_namespace, 'g')
            label_group.setAttribute('id', title)
            colour_rect = self.svg_create_rect(0, 0, 20, 20, colour)
            colour_rect.setAttribute('stroke', 'black')
            colour_rect.setAttribute('stroke-width', 2)

            text = document.createElementNS(self.svg_namespace, 'text')
            text.setAttribute('x', '30')
            text.setAttribute('y', '18')
            text.textContent = title

            label_group.appendChild(colour_rect)
            label_group.appendChild(text)

            # TODO replace hardcoded values
            x = 5 + 125 * (nr_processed_elements // 2)
            y = bar_height + 10 + (nr_processed_elements % 2) * 40
            label_group.setAttribute('transform', 'translate({}, {})'.format(x, y))

            bar_group.appendChild(label_group)

            current_pos += rect_len
            nr_processed_elements += 1

        svg.appendChild(bar_group)

        return svg

    def copy_example_to_form(self):
        document.getElementById('textarea_oom').value = self.example

    def reset_form(self):
        self.set_HTML_defaults()

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
        self.oom = OOM(self.load_from_form())
        if not self.is_valid(self.oom):
            self.oom = None
            return

        # set defaults
        self.oom_details.clear()
        self.set_HTML_defaults(False)

        # analyse
        analyser = OOMAnalyser(self.oom)
        analyser.analyse()
        self.oom_details = analyser.results

        # display results
        self.show()

    def load_from_form(self):
        element = document.getElementById('textarea_oom')
        oom_text = element.value
        return oom_text

    def is_valid(self, oom):
        """
        Return True for a complete OOM otherwise False and a warning msg for a incomplete or an error msg
        if the start sequence was not found.
        """
        if oom.state == "oom_complete":
            return True
        elif oom.state == "oom_started":
            warning('The inserted OOM is incomplete - only the beginning has found.')
            warning('The result may be incomplete!')
        elif oom.state == "oom_invalid":
            error('The inserted text is not a valid OOM!')
        else:
            error('Invalid state "{}" after the OOM has formally checked!'.format(self.oom.state))
        return False

    def show(self):
        """
        Show all extracted details as well as additionally generated information
        """
        if DEBUG:
            print(self.oom_details)

        hide_element('input')
        show_element('analysis')

        for item in self.oom_details.keys():
            self._set_single_item(item)

        svg_swap = self.svg_generate_bar_chart(
            ('Swap Used', self.oom_details['swap_used_kb']),
            ('Swap Free', self.oom_details['swap_free_kb']),
            ('Swap Cached', self.oom_details['swap_cache_kb']),
        )
        elem_svg_swap = document.getElementById('svg_swap')
        elem_svg_swap.appendChild(svg_swap)

        svg_ram = self.svg_generate_bar_chart(
            ('Active mem', self.oom_details['active_anon_pages']),
            ('Inactive mem', self.oom_details['inactive_anon_pages']),
            ('Isolated mem', self.oom_details['isolated_anon_pages']),
            ('Active PC', self.oom_details['active_file_pages']),
            ('Inactive PC', self.oom_details['inactive_file_pages']),
            ('Isolated PC', self.oom_details['isolated_file_pages']),
            ('Unevictable', self.oom_details['unevictable_pages']),
            ('Dirty', self.oom_details['dirty_pages']),
            ('Writeback', self.oom_details['writeback_pages']),
            ('Unstable', self.oom_details['unstable_pages']),
            ('Slab reclaimable', self.oom_details['slab_reclaimable_pages']),
            ('Slab unreclaimable', self.oom_details['slab_unreclaimable_pages']),
            ('Mapped', self.oom_details['mapped_pages']),
            ('Shared', self.oom_details['shmem_pages']),
            ('Pagetable', self.oom_details['pagetables_pages']),
            ('Bounce', self.oom_details['bounce_pages']),
            ('Free', self.oom_details['free_pages']),
            ('Free PCP', self.oom_details['free_pcp_pages']),
            ('Free CMA', self.oom_details['free_cma_pages']),
        )
        elem_svg_ram = document.getElementById('svg_ram')
        elem_svg_ram.appendChild(svg_ram)

        element = document.getElementById('oom')
        element.textContent = self.oom.text
        self.toggle_oom(show=False)


OOMDisplayInstance = OOMDisplay()
