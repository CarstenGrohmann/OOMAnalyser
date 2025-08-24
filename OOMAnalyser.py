# -*- coding: Latin-1 -*-
#
# Linux OOMAnalyser
#
# Copyright (c) 2017-2025 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY
import math
import re

DEBUG = False
"""Show additional information during the development cycle"""

VERSION = "0.8.0_devel"
"""Version number e.g. "0.6.0" or "0.6.0 (devel)" """

# __pragma__ ('skip')
from typing import List, Optional, Tuple, Any

# MOC objects to satisfy statical checkers and imports in unit tests
js_undefined = 0


class DOMTokenList:
    def add(self, *tokens: str) -> None:
        pass

    def contains(self, token: str) -> bool:
        return False

    def remove(self, *tokens: str) -> None:
        pass

    def toggle(self, token: str, force: Optional[bool] = None) -> bool:
        return False


class Console:
    @staticmethod
    def log(*messages: Any) -> None:
        pass

    @staticmethod
    def clear() -> None:
        pass

    @staticmethod
    def js_clear() -> None:
        pass


class EventTarget:
    def addEventListener(
        self, type: str, listener: callable, options: Optional[dict] = None
    ) -> None:
        pass

    def removeEventListener(
        self, type: str, listener: callable, options: Optional[dict] = None
    ) -> None:
        pass


class Node(EventTarget):
    classList: DOMTokenList = DOMTokenList()
    id: Optional[str] = None
    offsetHeight: int = 0
    offsetWidth: int = 0
    textContent: Optional[str] = ""
    innerHTML: str = ""

    def __init__(self, nr_children=1, *args: Any, **kwargs: Any) -> None:
        self.nr_children = nr_children

    def closest(self, selector: str) -> Optional["Node"]:
        return None

    @property
    def firstChild(self) -> Optional["Node"]:
        if self.nr_children:  # prevent infinite recursion in while loops
            self.nr_children -= 1
            return Node(self.nr_children)
        return None

    @property
    def parentNode(self) -> Optional["Node"]:
        return Node()

    def querySelector(self, selector: str) -> Optional["Element"]:
        return Element()

    def remove(self) -> None:
        pass

    def removeChild(self, child: "Node") -> Optional["Node"]:
        return

    def appendChild(self, child: "Node") -> "Node":
        return child

    def removeAttribute(self, name: str) -> None:
        pass

    def setAttribute(self, name: str, value: str) -> None:
        pass

    @property
    def tagName(self) -> str:
        return ""


class Element(Node):
    value: Optional[str] = None


class Document(Node):
    def querySelectorAll(self, selector: str) -> List[Element]:
        return [Element()]

    @staticmethod
    def getElementsByClassName(names: str) -> List[Element]:
        return [Element()]

    @staticmethod
    def getElementsByTagName(tagName: str) -> List[Element]:
        return [Element()]

    @staticmethod
    def getElementById(element_id: str) -> Optional[Element]:
        return Element()

    @staticmethod
    def createElementNS(namespaceURI: str, qualifiedName: str, *args: Any) -> Element:
        return Element()

    @staticmethod
    def createElement(tagName: str, *args: Any) -> Element:
        return Element()


class Window(EventTarget):
    def scrollTo(self, *args, **kwargs) -> None:
        pass


document = Document()
console = Console()
window = Window()


# __pragma__ ('noskip')


class OOMEntityState:
    """Enum for completeness of the OOM block"""

    unknown = 0
    empty = 1
    invalid = 2
    started = 3
    complete = 4


class OOMType:
    """Enum for the type of the OOM"""

    UNKNOWN = "UNKNOWN"
    KERNEL_AUTOMATIC_OR_MANUAL = "KERNEL_AUTOMATIC_OR_MANUAL"
    KERNEL_AUTOMATIC = "KERNEL_AUTOMATIC"
    KERNEL_MANUAL = "KERNEL_MANUAL"
    CGROUP_AUTOMATIC = "CGROUP_AUTOMATIC"


class OOMPatternType:
    """Enum for the type of the RE pattern to extract information from an OOM block"""

    ALL_OPTIONAL = "ALL_OPTIONAL"
    ALL_MANDATORY = "ALL_MANDATORY"
    KERNEL_MANDATORY = "KERNEL_MANDATORY"
    KERNEL_OPTIONAL = "KERNEL_OPTIONAL"
    CGROUP_MANDATORY = "CGROUP_MANDATORY"
    CGROUP_OPTIONAL = "CGROUP_OPTIONAL"


class OOMMemoryAllocFailureType:
    """Enum to store the results why the memory allocation could have failed"""

    not_started = 0
    """Analysis not started"""

    missing_data = 1
    """Missing data to start analysis"""

    failed_below_low_watermark = 2
    """Failed, because after satisfying this request, the free memory will be below the low memory watermark"""

    failed_no_free_chunks = 3
    """Failed, because no suitable chunk is free in the current or any higher order."""

    failed_unknown_reason = 4
    """Failed, but the reason is unknown"""

    skipped_high_order_dont_trigger_oom = 5
    """"high order" requests don't trigger OOM"""


def is_visible(element):
    return element.offsetWidth > 0 and element.offsetHeight > 0


def hide_element_by_id(element_id):
    """Hide the specified HTML element"""
    element = document.getElementById(element_id)
    if element:
        element.classList.add("js-text--display-none")
    else:
        internal_error("Element with id '{}' not found".format(element_id))


def show_element_by_id(element_id):
    """Show the specified HTML element"""
    element = document.getElementById(element_id)
    if element:
        element.classList.remove("js-text--display-none")
    else:
        internal_error("Element with id '{}' not found".format(element_id))


def hide_elements_by_selector(selector):
    """Hide all matching elements by adding class js-text--display-none"""
    for element in document.querySelectorAll(selector):
        element.classList.add("js-text--display-none")


def show_elements_by_selector(selector):
    """Show all matching elements by removing class js-text--display-none"""
    for element in document.querySelectorAll(selector):
        element.classList.remove("js-text--display-none")


def toggle_visibility_by_id(element_id):
    """Toggle the visibility of the specified HTML element"""
    element = document.getElementById(element_id)
    element.classList.toggle("js-text--display-none")


def escape_html(unsafe):
    """
    Escape unsafe HTML entities

    @type unsafe: str
    @rtype: str
    """
    return (
        unsafe.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def debug(msg):
    """Add a debug message to the notification box"""
    add_to_notifybox("DEBUG", msg)


def error(msg):
    """Show the notification box and add the error message"""
    add_to_notifybox("ERROR", msg)


def internal_error(msg):
    """Show the notification box and add the internal error message"""
    add_to_notifybox("INTERNAL ERROR", msg)


def warning(msg):
    """Show the notification box and add the warning message"""
    add_to_notifybox("WARNING", msg)


def add_to_notifybox(prefix, msg):
    """
    Escaped and add a message to the notification box

    If the message has a prefix "ERROR" or "WARNING" the notification box will be shown.
    """
    if prefix == "DEBUG":
        css_class = "js-notify_box__msg--debug"
    elif prefix == "WARNING":
        css_class = "js-notify_box__msg--warning"
    else:
        css_class = "js-notify_box__msg--error"
    if prefix != "DEBUG":
        show_element_by_id("notify_box")
    notify_box = document.getElementById("notify_box")
    notification = document.createElement("div")
    notification.classList.add(css_class)
    notification.innerHTML = "{}: {}<br>".format(prefix, escape_html(msg))
    notify_box.appendChild(notification)

    # Also show all messages on the JS console
    console.log("{}: {}".format(prefix, msg))


class BaseKernelConfig:
    """Base class for all kernel-specific configuration"""

    name = "Base configuration for all kernels based on vanilla kernel 3.10"
    """Name/description of this kernel configuration"""

    EXTRACT_PATTERN = None
    """
    Instance specific dictionary of RE pattern to analyse a OOM block for a specific kernel version

    This dict will be filled from EXTRACT_PATTERN_BASE and EXTRACT_PATTERN_OVERLAY during class constructor is executed.

    @type: None|Dict
    @see: EXTRACT_PATTERN_BASE and EXTRACT_PATTERN_OVERLAY
    """

    EXTRACT_PATTERN_BASE = {
        "invoked oom-killer": (
            r"^(?P<trigger_proc_name>[\S ]+) invoked oom-killer: "
            r"gfp_mask=(?P<trigger_proc_gfp_mask>0x[a-z0-9]+)(\((?P<trigger_proc_gfp_flags>[A-Z_|]+)\))?, "
            r"(nodemask=(?P<trigger_proc_nodemask>([\d,-]+|\(null\))), )?"
            r"order=(?P<trigger_proc_order>-?\d+), "
            r"oom_score_adj=(?P<trigger_proc_oomscore>-?\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        # Source: lib/dump_stack:dump_stack_print_info()
        "Trigger process and kernel version": (
            r"^CPU: \d+ PID: (?P<trigger_proc_pid>\d+) "
            r"Comm: .* (Not tainted|Tainted:.*) "
            r"(?P<kernel_version>\d[\w.+-]+) #\d",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        # split caused by a limited number of iterations during converting PY regex into JS regex
        # Source: mm/page_alloc.c:__show_free_areas()
        "Overall Mem-Info (part 1)": (
            r"^Mem-Info:.*"
            #
            r"(?:\n)"
            # first line (starting w/o a space)
            r"^active_anon:(?P<active_anon_pages>\d+) inactive_anon:(?P<inactive_anon_pages>\d+) "
            r"isolated_anon:(?P<isolated_anon_pages>\d+)"
            r"(?:\n)"
            # remaining lines (w/ leading space)
            r"^ active_file:(?P<active_file_pages>\d+) inactive_file:(?P<inactive_file_pages>\d+) "
            r"isolated_file:(?P<isolated_file_pages>\d+)"
            r"(?:\n)"
            r"^ unevictable:(?P<unevictable_pages>\d+) dirty:(?P<dirty_pages>\d+) writeback:(?P<writeback_pages>\d+) "
            r"unstable:(?P<unstable_pages>\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        "Overall Mem-Info (part 2)": (
            r"^ slab_reclaimable:(?P<slab_reclaimable_pages>\d+) slab_unreclaimable:(?P<slab_unreclaimable_pages>\d+)"
            r"(?:\n)"
            r"^ mapped:(?P<mapped_pages>\d+) shmem:(?P<shmem_pages>\d+) pagetables:(?P<pagetables_pages>\d+) "
            r"bounce:(?P<bounce_pages>\d+)"
            r"(?:\n)"
            r"^ free:(?P<free_pages>\d+) free_pcp:(?P<free_pcp_pages>\d+) free_cma:(?P<free_cma_pages>\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        "Available memory chunks": (
            r"(?P<mem_node_info>(^Node \d+ ((DMA|DMA32|Normal):|(hugepages)).+(\n|$))+)",
            OOMPatternType.ALL_OPTIONAL,
        ),
        "Memory watermarks": (
            r"(?P<mem_watermarks>(^(Node \d+ (DMA|DMA32|Normal) free:|lowmem_reserve\[\]:).+(\n|$))+)",
            OOMPatternType.ALL_OPTIONAL,
        ),
        "Page cache": (
            r"^(?P<pagecache_total_pages>\d+) total pagecache pages.*$",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        # Source:mm/swap_state.c:show_swap_cache_info()
        "Swap usage information": (
            r"^(?P<swap_cache_pages>\d+) pages in swap cache"
            r"(?:\n)"
            r"^Swap cache stats: add \d+, delete \d+, find \d+\/\d+"
            r"(?:\n)"
            r"^Free swap  = (?P<swap_free_kb>\d+)kB"
            r"(?:\n)"
            r"^Total swap = (?P<swap_total_kb>\d+)kB",
            OOMPatternType.ALL_OPTIONAL,
        ),
        "Page information": (
            r"^(?P<ram_pages>\d+) pages RAM"
            r"("
            r"(?:\n)"
            r"^(?P<highmem_pages>\d+) pages HighMem/MovableOnly"
            r")?"
            r"(?:\n)"
            r"^(?P<reserved_pages>\d+) pages reserved"
            r"("
            r"(?:\n)"
            r"^(?P<cma_pages>\d+) pages cma reserved"
            r")?"
            r"("
            r"(?:\n)"
            r"^(?P<pagetablecache_pages>\d+) pages in pagetable cache"
            r")?"
            r"("
            r"(?:\n)"
            r"^(?P<hwpoisoned_pages>\d+) pages hwpoisoned"
            r")?",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        "Process killed by OOM": (
            r"^Out of memory: Kill process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) "
            r"score (?P<killed_proc_score>\d+) or sacrifice child",
            OOMPatternType.KERNEL_MANDATORY,
        ),
        "Details of process killed by OOM": (
            r"^Killed process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) "
            r"total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, "
            r"file-rss:(?P<killed_proc_file_rss_kb>\d+)kB",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }
    """
    RE pattern to extract information from OOM.

    The first item is the RE pattern and the second is whether it is mandatory to find this pattern.

    This dictionary will be copied to EXTRACT_PATTERN during class constructor is executed.

    @type: dict(tuple(str, bool))
    @see: EXTRACT_PATTERN
    """

    EXTRACT_PATTERN_OVERLAY = {}
    """
    To extend / overwrite parts of EXTRACT_PATTERN in kernel configuration.

    @type: dict(tuple(str, bool))
    @see: EXTRACT_PATTERN
    """

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM"
        },
        "GFP_HIGHUSER_MOVABLE": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM | __GFP_MOVABLE"
        },
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KMEMCG": {"value": "___GFP_KMEMCG"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_KMEMCG": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }
    """
    Definition of GFP flags

    The decimal value of a flag will be calculated by evaluating the entries from left to right. Grouping by
    parentheses is not supported.

    Source: include/linux/gpf.h

    @note: This list os probably a mixture of different kernel versions - be carefully
    """

    gfp_reverse_lookup = []
    """
    Sorted list of flags used to do a reverse lookup.

    This list doesn't contain all flags. It contains the "useful flags" (GFP_*) as
    well as "modifier flags" (__GFP_*). "Plain flags" (___GFP_*) are not part of
    this list.

    @type: List(str)
    @see: _gfp_create_reverse_lookup()
    """

    MAX_ORDER = -1
    """
    The kernel memory allocator divides physically contiguous memory
    blocks into "zones", where each zone is a power of two number of
    pages.  This option selects the largest power of two that the kernel
    keeps in the memory allocator.

    This config option is actually maximum order plus one. For example,
    a value of 11 means that the largest free memory block is 2^10 pages.

    The value will be calculated dynamically based on the numbers of
    orders in OOMAnalyser._extract_buddyinfo().

    @see: OOMAnalyser._extract_buddyinfo().
    """

    pstable_items = [
        "pid",
        "uid",
        "tgid",
        "total_vm_pages",
        "rss_pages",
        "nr_ptes_pages",
        "swapents_pages",
        "oom_score_adj",
        "name",
        "notes",
    ]
    """Elements of the process table"""

    PAGE_ALLOC_COSTLY_ORDER = 3
    """
    Requests with order > PAGE_ALLOC_COSTLY_ORDER will never trigger the OOM-killer to satisfy the request.
    """

    PLATFORM_DESCRIPTION = (
        ("aarch64", "ARM 64-bit"),
        ("amd64", "x86 64-bit"),
        ("arm64", "ARM 64-bit"),
        ("armv8", "ARM 64-bit"),
        ("i386", "x86 32-bit"),
        ("i686", "x86 32-bit (6th generation)"),
        ("x86_64", "x86 64-bit"),
    )
    """
    Brief description of some platforms based on an identifier
    """

    pstable_html = [
        "PID",
        "UID",
        "TGID",
        "Total VM",
        "RSS",
        "Page Table Entries",
        "Swap Entries",
        "OOM Adjustment",
        "Name",
        "Notes",
    ]
    """
    Headings of the process table columns
    """

    pstable_non_ints = ["pid", "name", "notes"]
    """Columns that are not converted to an integer"""

    pstable_start = "[ pid ]"
    """
    Pattern to find the start of the process table

    @type: str
    """

    release = (3, 10, "")
    """
    Kernel release with this configuration

    The tuple contains major and minor version as well as a suffix like "-aws" or ".el7."

    The patch level isn't part of this version tuple, because I don't assume any changes in GFP flags within a patch
    release.

    @see: OOMAnalyser._choose_kernel_config()
    @type: (int, int, str)
    """

    REC_FREE_MEMORY_CHUNKS = re.compile(
        r"Node (?P<node>\d+) (?P<zone>DMA|DMA32|Normal): (?P<zone_usage>.*) = (?P<total_free_kb_per_node>\d+)kB"
    )
    """RE to extract free memory chunks of a memory zone"""

    REC_OOM_BEGIN = re.compile(r"invoked oom-killer:", re.MULTILINE)
    """RE to match the first line of an OOM block"""

    REC_OOM_END = re.compile(r"^Killed process \d+", re.MULTILINE)
    """RE to match the last line of an OOM block"""

    REC_OOM_CGROUP = re.compile(
        r"^memory: usage \d+kB, limit \d+kB, failcnt \d+", re.MULTILINE
    )
    """RE to match if the OOM is a cgroup OOM"""

    REC_PAGE_SIZE = re.compile(r"Node 0 DMA: \d+\*(?P<page_size>\d+)kB")
    """RE to extract the page size from buddyinfo DMA zone"""

    REC_PROCESS_LINE = re.compile(
        r"^\[(?P<pid>[ \d]+)\]\s+(?P<uid>\d+)\s+(?P<tgid>\d+)\s+(?P<total_vm_pages>\d+)\s+(?P<rss_pages>\d+)\s+"
        r"(?P<nr_ptes_pages>\d+)\s+(?P<swapents_pages>\d+)\s+(?P<oom_score_adj>-?\d+)\s+(?P<name>.+)\s*"
    )
    """Match content of process table"""

    REC_WATERMARK = re.compile(
        r"Node (?P<node>\d+) (?P<zone>DMA|DMA32|Normal) "
        r"free:(?P<free>\d+)kB "
        r"min:(?P<min>\d+)kB "
        r"low:(?P<low>\d+)kB "
        r"high:(?P<high>\d+)kB "
        r".*"
    )
    """
    RE to extract watermark information in a memory zone

    Source: mm/page_alloc.c:__show_free_areas()
    """

    watermark_start = "Node 0 DMA free:"
    """
    Pattern to find the start of the memory watermark information

    @type: str
     """

    zoneinfo_start = "Node 0 DMA: "
    """
    Pattern to find the start of the memory chunk information (buddyinfo)

    @type: str
    """

    ZONE_TYPES = ["DMA", "DMA32", "Normal", "HighMem", "Movable"]
    """
    List of memory zones

    @type: List(str)
    """

    def __init__(self):
        super().__init__()

        # Initialise pattern only once in the base class constructor and
        # not in every derived class constructor
        if self.EXTRACT_PATTERN is None:
            # Create a copy to prevent modifications on the class dictionary
            # TODO replace with self.EXTRACT_PATTERN = self.EXTRACT_PATTERN.copy() after
            #      https://github.com/QQuick/Transcrypt/issues/716 "dict does not have a copy method" is fixed
            self.EXTRACT_PATTERN = {}
            self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_BASE)

        if self.EXTRACT_PATTERN_OVERLAY:
            self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY)

        self._gfp_calc_all_values()
        self.gfp_reverse_lookup = self._gfp_create_reverse_lookup()

        self._check_mandatory_gfp_flags()

    def _gfp_calc_all_values(self):
        """
        Calculate decimal values for all GFP flags and store in in GFP_FLAGS[<flag>]["_value"]
        """
        # __pragma__ ('jsiter')
        for flag in self.GFP_FLAGS:
            value = self._gfp_flag2decimal(flag)
            self.GFP_FLAGS[flag]["_value"] = value
        # __pragma__ ('nojsiter')

    def _gfp_flag2decimal(self, flag):
        """\
        Convert a single flag into a decimal value.

        The flags can be concatenated with "|" or "~" and negated with "~". The
        flags will be processed from left to right. Parentheses are not supported.
        """
        if flag not in self.GFP_FLAGS:
            error("Missing definition for flag {}".format(flag))
            return 0

        value = self.GFP_FLAGS[flag]["value"]
        if isinstance(value, int):
            return value

        tokenlist = iter(re.split("([|&])", value))
        operator = "|"  # set to process the first flag
        negate_rvalue = False
        lvalue = 0
        while True:
            try:
                token = next(tokenlist)
            except StopIteration:
                break
            token = token.strip()
            if token in ["|", "&"]:
                operator = token
                continue

            if token.startswith("~"):
                token = token[1:]
                negate_rvalue = True

            if token.isdigit():
                rvalue = int(token)
            elif token.startswith("0x") and token[2:].isdigit():
                rvalue = int(token, 16)
            else:
                # it's not a decimal nor a hexadecimal value - reiterate assuming it's a flag string
                rvalue = self._gfp_flag2decimal(token)

            if negate_rvalue:
                rvalue = ~rvalue

            if operator == "|":
                lvalue |= rvalue
            elif operator == "&":
                lvalue &= rvalue

            operator = None
            negate_rvalue = False

        return lvalue

    def _gfp_create_reverse_lookup(self):
        """
        Create a sorted list of flags used to do a reverse lookup from value to the flag.

        @rtype: List(str)
        """
        # __pragma__ ('jsiter')
        useful = [
            key
            for key in self.GFP_FLAGS
            if key.startswith("GFP") and self.GFP_FLAGS[key]["_value"] != 0
        ]
        useful = sorted(
            useful, key=lambda key: self.GFP_FLAGS[key]["_value"], reverse=True
        )
        modifier = [
            key
            for key in self.GFP_FLAGS
            if key.startswith("__GFP") and self.GFP_FLAGS[key]["_value"] != 0
        ]
        modifier = sorted(
            modifier, key=lambda key: self.GFP_FLAGS[key]["_value"], reverse=True
        )
        # __pragma__ ('nojsiter')

        # useful + modifier produces a string with all values concatenated
        res = useful
        res.extend(modifier)
        return res

    def _check_mandatory_gfp_flags(self):
        """
        Check the existence of mandatory flags used in
        OOMAnalyser._calc_trigger_process_values() to calculate the memory zone
        """
        if "__GFP_DMA" not in self.GFP_FLAGS:
            error(
                "Missing definition of GFP flag __GFP_DMA for kernel {}.{}.{}".format(
                    *self.release
                )
            )
        if "__GFP_DMA32" not in self.GFP_FLAGS:
            error(
                "Missing definition of GFP flag __GFP_DMA for kernel {}.{}.{}".format(
                    *self.release
                )
            )


class KernelConfig_3_10(BaseKernelConfig):
    name = "Configuration for Linux kernel 3.10 or later"
    release = (3, 10, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM"
        },
        "GFP_HIGHUSER_MOVABLE": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM | __GFP_MOVABLE"
        },
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KMEMCG": {"value": "___GFP_KMEMCG"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_KMEMCG": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }


class KernelConfig_3_10_EL7(KernelConfig_3_10):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for RHEL 7 / CentOS 7 specific Linux kernel (3.10)"
    release = (3, 10, ".el7.")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM"
        },
        "GFP_HIGHUSER_MOVABLE": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM | __GFP_MOVABLE"
        },
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }


class KernelConfig_3_16(KernelConfig_3_10):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 3.16 or later"
    release = (3, 16, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM"
        },
        "GFP_HIGHUSER_MOVABLE": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL | __GFP_HIGHMEM | __GFP_MOVABLE"
        },
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }


class KernelConfig_3_19(KernelConfig_3_16):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 3.19 or later"
    release = (3, 19, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }


class KernelConfig_4_1(KernelConfig_3_19):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.1 or later"
    release = (4, 1, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_IOFS": {"value": "__GFP_IO | __GFP_FS"},
        "GFP_KERNEL": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_WAIT | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_WAIT"},
        "GFP_NOWAIT": {"value": "GFP_ATOMIC & ~__GFP_HIGH"},
        "GFP_TEMPORARY": {
            "value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN | __GFP_NO_KSWAPD"
        },
        "GFP_USER": {"value": "__GFP_WAIT | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOACCOUNT": {"value": "___GFP_NOACCOUNT"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_KSWAPD": {"value": "___GFP_NO_KSWAPD"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WAIT": {"value": "___GFP_WAIT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_WAIT": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_RECLAIMABLE": {"value": 0x80000},
        "___GFP_NOACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_NO_KSWAPD": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
    }


class KernelConfig_4_4(KernelConfig_4_1):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.4 or later"
    release = (4, 4, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN & ~__GFP_KSWAPD_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOACCOUNT": {"value": "___GFP_NOACCOUNT"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_NOACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x2000000},
    }


class KernelConfig_4_5(KernelConfig_4_4):
    # Supported changes:
    #  * update GFP flags
    #  * "mm, shmem: add internal shmem resident memory accounting" (eca56ff)

    name = "Configuration for Linux kernel 4.5 or later"
    release = (4, 5, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN & ~__GFP_KSWAPD_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x2000000},
    }

    EXTRACT_PATTERN_OVERLAY_45 = {
        "Details of process killed by OOM": (
            r"^Killed process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) "
            r"total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, "
            r"file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_45)


class KernelConfig_4_6(KernelConfig_4_5):
    # Supported changes:
    #  * "mm, oom_reaper: report success/failure" (bc448e8)
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.6 or later"
    release = (4, 6, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NORETRY | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x2000000},
    }

    # The "oom_reaper" line is optionally
    REC_OOM_END = re.compile(
        r"^((Out of memory.*|Memory cgroup out of memory): Killed process \d+|oom_reaper:)",
        re.MULTILINE,
    )


class KernelConfig_4_8(KernelConfig_4_6):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.8 or later"
    release = (4, 8, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_OTHER_NODE": {"value": "___GFP_OTHER_NODE"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_OTHER_NODE": {"value": 0x800000},
        "___GFP_WRITE": {"value": 0x1000000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x2000000},
    }


class KernelConfig_4_9(KernelConfig_4_8):
    # Supported changes:
    #  * "mm: oom: deduplicate victim selection code for memcg and global oom" (7c5f64f)

    name = "Configuration for Linux kernel 4.9 or later"
    release = (4, 9, "")

    EXTRACT_PATTERN_OVERLAY_49 = {
        "Details of process killed by OOM": (
            r"^Killed process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) "
            r"total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, "
            r"file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_49)


class KernelConfig_4_10(KernelConfig_4_9):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.10 or later"
    release = (4, 10, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_WRITE": {"value": 0x800000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x1000000},
    }


class KernelConfig_4_12(KernelConfig_4_10):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.12 or later"
    release = (4, 12, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_REPEAT": {"value": "___GFP_REPEAT"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_REPEAT": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_WRITE": {"value": 0x800000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }


class KernelConfig_4_13(KernelConfig_4_12):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.13 or later"
    release = (4, 13, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TEMPORARY": {
            "value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_RECLAIMABLE"
        },
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_RETRY_MAYFAIL": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_WRITE": {"value": 0x800000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }


class KernelConfig_4_14(KernelConfig_4_13):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.14 or later"
    release = (4, 14, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COLD": {"value": "___GFP_COLD"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOTRACK": {"value": "___GFP_NOTRACK"},
        "__GFP_NOTRACK_FALSE_POSITIVE": {"value": "__GFP_NOTRACK"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_COLD": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_RETRY_MAYFAIL": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_NOTRACK": {"value": 0x200000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_WRITE": {"value": 0x800000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }


class KernelConfig_4_15(KernelConfig_4_14):
    # Supported changes:
    #  * mm: consolidate page table accounting (af5b0f6)
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.15 or later"
    release = (4, 15, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_RETRY_MAYFAIL": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400000},
        "___GFP_WRITE": {"value": 0x800000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }

    # nr_ptes -> pgtables_bytes
    # pr_info("[ pid ]   uid  tgid total_vm      rss nr_ptes nr_pmds nr_puds swapents oom_score_adj name\n");
    # pr_info("[ pid ]   uid  tgid total_vm      rss pgtables_bytes swapents oom_score_adj name\n");
    REC_PROCESS_LINE = re.compile(
        r"^\[(?P<pid>[ \d]+)\]\s+(?P<uid>\d+)\s+(?P<tgid>\d+)\s+(?P<total_vm_pages>\d+)\s+(?P<rss_pages>\d+)\s+"
        r"(?P<pgtables_bytes>\d+)\s+(?P<swapents_pages>\d+)\s+(?P<oom_score_adj>-?\d+)\s+(?P<name>.+)\s*"
    )

    pstable_items = [
        "pid",
        "uid",
        "tgid",
        "total_vm_pages",
        "rss_pages",
        "pgtables_bytes",
        "swapents_pages",
        "oom_score_adj",
        "name",
        "notes",
    ]

    pstable_html = [
        "PID",
        "UID",
        "TGID",
        "Total VM",
        "RSS",
        "Page Table Bytes",
        "Swap Entries Pages",
        "OOM Adjustment",
        "Name",
        "Notes",
    ]


class KernelConfig_4_18(KernelConfig_4_15):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 4.18 or later"
    release = (4, 18, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_WRITE": {"value": 0x100},
        "___GFP_NOWARN": {"value": 0x200},
        "___GFP_RETRY_MAYFAIL": {"value": 0x400},
        "___GFP_NOFAIL": {"value": 0x800},
        "___GFP_NORETRY": {"value": 0x1000},
        "___GFP_MEMALLOC": {"value": 0x2000},
        "___GFP_COMP": {"value": 0x4000},
        "___GFP_ZERO": {"value": 0x8000},
        "___GFP_NOMEMALLOC": {"value": 0x10000},
        "___GFP_HARDWALL": {"value": 0x20000},
        "___GFP_ATOMIC": {"value": 0x80000},
        "___GFP_ACCOUNT": {"value": 0x100000},
        "___GFP_DIRECT_RECLAIM": {"value": 0x200000},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x400000},
        "___GFP_NOLOCKDEP": {"value": 0x800000},
    }


class KernelConfig_4_19(KernelConfig_4_18):
    # Supported changes:
    #  * mm, oom: describe task memory unit, larger PID pad (c3b78b1)

    name = "Configuration for Linux kernel 4.19 or later"
    release = (4, 19, "")

    pstable_start = "[  pid  ]"


class KernelConfig_5_1(KernelConfig_4_19):
    # Supported changes:
    #  * update GFP flags
    #  * "mm, oom: remove 'prefer children over parent' heuristic" (bbbe480)

    name = "Configuration for Linux kernel 5.1 or later"
    release = (5, 1, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {"value": "GFP_HIGHUSER | __GFP_MOVABLE"},
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_ATOMIC": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_NOLOCKDEP": {"value": 0x800000},
    }

    def __init__(self):
        super().__init__()
        # Removed with kernel 5.1 "mm, oom: remove 'prefer children over parent' heuristic" (bbbe480)
        del self.EXTRACT_PATTERN["Process killed by OOM"]


class KernelConfig_5_4(KernelConfig_5_1):
    # Supported changes:
    #  * "mm/oom: add oom_score_adj and pgtables to Killed process message" (70cb6d2)
    #  * "mm/oom_kill.c: add task UID to info message on an oom kill" (8ac3f8f)

    name = "Configuration for Linux kernel 5.4 or later"
    release = (5, 4, "")

    EXTRACT_PATTERN_OVERLAY_54 = {
        "Details of process killed by OOM": (
            # message pattern:
            #  * "Out of memory (oom_kill_allocating_task)"
            #  * "Out of memory"
            #  * "Memory cgroup out of memory"
            r"^([\S ]+): "
            r"Killed process (?P<killed_proc_pid>\d+) \((?P<killed_proc_name>[\S ]+)\) "
            r"total-vm:(?P<killed_proc_total_vm_kb>\d+)kB, anon-rss:(?P<killed_proc_anon_rss_kb>\d+)kB, "
            r"file-rss:(?P<killed_proc_file_rss_kb>\d+)kB, shmem-rss:(?P<killed_proc_shmem_rss_kb>\d+)kB, "
            r"UID:\d+ pgtables:(?P<killed_proc_pgtables>\d+)kB oom_score_adj:(?P<killed_proc_oom_score_adj>-?\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_54)


class KernelConfig_5_8(KernelConfig_5_4):
    # Supported changes:
    #  * "mm/writeback: discard NR_UNSTABLE_NFS, use NR_WRITEBACK instead" (8d92890)

    name = "Configuration for Linux kernel 5.8 or later"
    release = (5, 8, "")

    EXTRACT_PATTERN_OVERLAY_58 = {
        "Overall Mem-Info (part 1)": (
            r"^Mem-Info:.*" r"(?:\n)"
            # first line (starting w/o a space)
            r"^active_anon:(?P<active_anon_pages>\d+) inactive_anon:(?P<inactive_anon_pages>\d+) "
            r"isolated_anon:(?P<isolated_anon_pages>\d+)"
            r"(?:\n)"
            # remaining lines (w/ leading space)
            r"^ active_file:(?P<active_file_pages>\d+) inactive_file:(?P<inactive_file_pages>\d+) "
            r"isolated_file:(?P<isolated_file_pages>\d+)"
            r"(?:\n)"
            r"^ unevictable:(?P<unevictable_pages>\d+) dirty:(?P<dirty_pages>\d+) writeback:(?P<writeback_pages>\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_58)


class KernelConfig_5_14(KernelConfig_5_8):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 5.14 or later"
    release = (5, 14, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN_POISON"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN_POISON": {"value": "___GFP_SKIP_KASAN_POISON"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_ATOMIC": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_KASAN_POISON": {"value": 0x0},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }


class KernelConfig_5_16(KernelConfig_5_14):
    # Supported changes:
    #  * mm/page_alloc.c: show watermark_boost of zone in zoneinfo (a6ea8b5)

    name = "Configuration for Linux kernel 5.16 or later"
    release = (5, 16, "")

    REC_WATERMARK = re.compile(
        r"Node (?P<node>\d+) (?P<zone>DMA|DMA32|Normal) "
        r"free:(?P<free>\d+)kB "
        r"boost:(?P<boost>\d+)kB "
        r"min:(?P<min>\d+)kB "
        r"low:(?P<low>\d+)kB "
        r"high:(?P<high>\d+)kB "
        r".*"
    )


class KernelConfig_5_18(KernelConfig_5_16):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 5.18 or later"
    release = (5, 18, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN_POISON"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN_POISON": {"value": "___GFP_SKIP_KASAN_POISON"},
        "__GFP_SKIP_KASAN_UNPOISON": {"value": "___GFP_SKIP_KASAN_UNPOISON"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_ATOMIC": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_ZERO": {"value": 0x0},
        "___GFP_SKIP_KASAN_UNPOISON": {"value": 0x0},
        "___GFP_SKIP_KASAN_POISON": {"value": 0x0},
        "___GFP_NOLOCKDEP": {"value": 0x8000000},
    }


class KernelConfig_6_0(KernelConfig_5_18):
    # Supported changes:
    #  * update GFP flags
    #  * "mm/swap: remove swap_cache_info statistics" (442701e)

    name = "Configuration for Linux kernel 6.0 or later"
    release = (6, 0, "")

    # NOTE: These flags are automatically extracted from the gfp_types.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_ATOMIC | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN_POISON | __GFP_SKIP_KASAN_UNPOISON"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_ATOMIC": {"value": "___GFP_ATOMIC"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN_POISON": {"value": "___GFP_SKIP_KASAN_POISON"},
        "__GFP_SKIP_KASAN_UNPOISON": {"value": "___GFP_SKIP_KASAN_UNPOISON"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_ATOMIC": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_ZERO": {"value": 0x0},
        "___GFP_SKIP_KASAN_UNPOISON": {"value": 0x0},
        "___GFP_SKIP_KASAN_POISON": {"value": 0x0},
        "___GFP_NOLOCKDEP": {"value": 0x8000000},
    }

    EXTRACT_PATTERN_OVERLAY_60 = {
        "Swap usage information": (
            r"^(?P<swap_cache_pages>\d+) pages in swap cache"
            r"(?:\n)"
            r"^Free swap  = (?P<swap_free_kb>\d+)kB"
            r"(?:\n)"
            r"^Total swap = (?P<swap_total_kb>\d+)kB",
            OOMPatternType.ALL_OPTIONAL,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_60)


class KernelConfig_6_1(KernelConfig_6_0):
    # Supported changes:
    #  * "mm: add NR_SECONDARY_PAGETABLE to count secondary page table uses." (ebc97a5)

    name = "Configuration for Linux kernel 6.1 or later"
    release = (6, 1, "")

    EXTRACT_PATTERN_OVERLAY_61 = {
        "Overall Mem-Info (part 2)": (
            r"^ slab_reclaimable:(?P<slab_reclaimable_pages>\d+) slab_unreclaimable:(?P<slab_unreclaimable_pages>\d+)"
            r"(?:\n)"
            r"^ mapped:(?P<mapped_pages>\d+) shmem:(?P<shmem_pages>\d+) pagetables:(?P<pagetables_pages>\d+)"
            r"(?:\n)"
            r"^ sec_pagetables:(?P<sec_pagetables>\d+) bounce:(?P<bounce_pages>\d+)"
            r"(?:\n)"
            r"^ kernel_misc_reclaimable:(?P<kernel_misc_reclaimable>\d+)"
            r"(?:\n)"
            r"^ free:(?P<free_pages>\d+) free_pcp:(?P<free_pcp_pages>\d+) free_cma:(?P<free_cma_pages>\d+)",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }

    def __init__(self):
        super().__init__()
        self.EXTRACT_PATTERN.update(self.EXTRACT_PATTERN_OVERLAY_61)


class KernelConfig_6_3(KernelConfig_6_1):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 6.3 or later"
    release = (6, 3, "")

    # NOTE: These flags are automatically extracted from the gfp.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN_POISON | __GFP_SKIP_KASAN_UNPOISON"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN_POISON": {"value": "___GFP_SKIP_KASAN_POISON"},
        "__GFP_SKIP_KASAN_UNPOISON": {"value": "___GFP_SKIP_KASAN_UNPOISON"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_ZERO": {"value": 0x1000000},
        "___GFP_SKIP_KASAN_UNPOISON": {"value": 0x2000000},
        "___GFP_SKIP_KASAN_POISON": {"value": 0x4000000},
        "___GFP_NOLOCKDEP": {"value": 0x8000000},
    }


class KernelConfig_6_4(KernelConfig_6_3):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 6.4 or later"
    release = (6, 4, "")

    # NOTE: These flags are automatically extracted from the gfp_types.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Useful GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN": {"value": "___GFP_SKIP_KASAN"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_ZERO": {"value": 0x1000000},
        "___GFP_SKIP_KASAN": {"value": 0x2000000},
        "___GFP_NOLOCKDEP": {"value": 0x4000000},
    }


class KernelConfig_6_8(KernelConfig_6_4):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 6.8 or later"
    release = (6, 8, "")

    # NOTE: These flags are automatically extracted from the gfp_types.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Top-level GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM | __GFP_NOWARN"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN": {"value": "___GFP_SKIP_KASAN"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x400000},
        "___GFP_ZEROTAGS": {"value": 0x800000},
        "___GFP_SKIP_ZERO": {"value": 0x1000000},
        "___GFP_SKIP_KASAN": {"value": 0x2000000},
        "___GFP_NOLOCKDEP": {"value": 0x4000000},
    }


class KernelConfig_6_9(KernelConfig_6_8):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 6.9 or later"
    release = (6, 9, "")

    # NOTE: These flags are automatically extracted from the gfp_types.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Top-level GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM | __GFP_NOWARN"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN": {"value": "___GFP_SKIP_KASAN"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_UNUSED_BIT": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x200000},
        "___GFP_ZEROTAGS": {"value": 0x400000},
        "___GFP_SKIP_ZERO": {"value": 0x800000},
        "___GFP_SKIP_KASAN": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
    }


class KernelConfig_6_10(KernelConfig_6_9):
    # Supported changes:
    #  * update GFP flags

    name = "Configuration for Linux kernel 6.10 or later"
    release = (6, 10, "")

    # NOTE: These flags are automatically extracted from the gfp_types.h file.
    #       Please do not change them manually!
    GFP_FLAGS = {
        #
        #
        # Top-level GFP flag combinations:
        "GFP_ATOMIC": {"value": "__GFP_HIGH | __GFP_KSWAPD_RECLAIM"},
        "GFP_HIGHUSER": {"value": "GFP_USER | __GFP_HIGHMEM"},
        "GFP_HIGHUSER_MOVABLE": {
            "value": "GFP_HIGHUSER | __GFP_MOVABLE | __GFP_SKIP_KASAN"
        },
        "GFP_KERNEL": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS"},
        "GFP_KERNEL_ACCOUNT": {"value": "GFP_KERNEL | __GFP_ACCOUNT"},
        "GFP_NOFS": {"value": "__GFP_RECLAIM | __GFP_IO"},
        "GFP_NOIO": {"value": "__GFP_RECLAIM"},
        "GFP_NOWAIT": {"value": "__GFP_KSWAPD_RECLAIM | __GFP_NOWARN"},
        "GFP_TRANSHUGE": {"value": "GFP_TRANSHUGE_LIGHT | __GFP_DIRECT_RECLAIM"},
        "GFP_TRANSHUGE_LIGHT": {
            "value": "GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN & ~__GFP_RECLAIM"
        },
        "GFP_USER": {"value": "__GFP_RECLAIM | __GFP_IO | __GFP_FS | __GFP_HARDWALL"},
        #
        #
        # Modifier, mobility and placement hints:
        "__GFP_ACCOUNT": {"value": "___GFP_ACCOUNT"},
        "__GFP_COMP": {"value": "___GFP_COMP"},
        "__GFP_DIRECT_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM"},
        "__GFP_DMA": {"value": "___GFP_DMA"},
        "__GFP_DMA32": {"value": "___GFP_DMA32"},
        "__GFP_FS": {"value": "___GFP_FS"},
        "__GFP_HARDWALL": {"value": "___GFP_HARDWALL"},
        "__GFP_HIGH": {"value": "___GFP_HIGH"},
        "__GFP_HIGHMEM": {"value": "___GFP_HIGHMEM"},
        "__GFP_IO": {"value": "___GFP_IO"},
        "__GFP_KSWAPD_RECLAIM": {"value": "___GFP_KSWAPD_RECLAIM"},
        "__GFP_MEMALLOC": {"value": "___GFP_MEMALLOC"},
        "__GFP_MOVABLE": {"value": "___GFP_MOVABLE"},
        "__GFP_NOFAIL": {"value": "___GFP_NOFAIL"},
        "__GFP_NOLOCKDEP": {"value": "___GFP_NOLOCKDEP"},
        "__GFP_NOMEMALLOC": {"value": "___GFP_NOMEMALLOC"},
        "__GFP_NORETRY": {"value": "___GFP_NORETRY"},
        "__GFP_NOWARN": {"value": "___GFP_NOWARN"},
        "__GFP_NO_OBJ_EXT": {"value": "___GFP_NO_OBJ_EXT"},
        "__GFP_RECLAIM": {"value": "___GFP_DIRECT_RECLAIM | ___GFP_KSWAPD_RECLAIM"},
        "__GFP_RECLAIMABLE": {"value": "___GFP_RECLAIMABLE"},
        "__GFP_RETRY_MAYFAIL": {"value": "___GFP_RETRY_MAYFAIL"},
        "__GFP_SKIP_KASAN": {"value": "___GFP_SKIP_KASAN"},
        "__GFP_SKIP_ZERO": {"value": "___GFP_SKIP_ZERO"},
        "__GFP_WRITE": {"value": "___GFP_WRITE"},
        "__GFP_ZERO": {"value": "___GFP_ZERO"},
        "__GFP_ZEROTAGS": {"value": "___GFP_ZEROTAGS"},
        #
        #
        # Plain integer GFP bitmasks (for internal use only):
        "___GFP_DMA": {"value": 0x01},
        "___GFP_HIGHMEM": {"value": 0x02},
        "___GFP_DMA32": {"value": 0x04},
        "___GFP_MOVABLE": {"value": 0x08},
        "___GFP_RECLAIMABLE": {"value": 0x10},
        "___GFP_HIGH": {"value": 0x20},
        "___GFP_IO": {"value": 0x40},
        "___GFP_FS": {"value": 0x80},
        "___GFP_ZERO": {"value": 0x100},
        "___GFP_UNUSED_BIT": {"value": 0x200},
        "___GFP_DIRECT_RECLAIM": {"value": 0x400},
        "___GFP_KSWAPD_RECLAIM": {"value": 0x800},
        "___GFP_WRITE": {"value": 0x1000},
        "___GFP_NOWARN": {"value": 0x2000},
        "___GFP_RETRY_MAYFAIL": {"value": 0x4000},
        "___GFP_NOFAIL": {"value": 0x8000},
        "___GFP_NORETRY": {"value": 0x10000},
        "___GFP_MEMALLOC": {"value": 0x20000},
        "___GFP_COMP": {"value": 0x40000},
        "___GFP_NOMEMALLOC": {"value": 0x80000},
        "___GFP_HARDWALL": {"value": 0x100000},
        "___GFP_ACCOUNT": {"value": 0x200000},
        "___GFP_ZEROTAGS": {"value": 0x400000},
        "___GFP_SKIP_ZERO": {"value": 0x800000},
        "___GFP_SKIP_KASAN": {"value": 0x1000000},
        "___GFP_NOLOCKDEP": {"value": 0x2000000},
        "___GFP_NO_OBJ_EXT": {"value": 0x4000000},
    }


class KernelConfig_6_11(KernelConfig_6_10):
    # Supported changes:
    #  * "lib/dump_stack: report process UID in dump_stack_print_info()" (d2917ff)

    name = "Configuration for Linux kernel 6.11 or later"
    release = (6, 11, "")

    EXTRACT_PATTERN_OVERLAY = {
        # Source: lib/dump_stack:dump_stack_print_info()
        "Trigger process and kernel version": (
            r"^CPU: \d+ UID: (?P<trigger_proc_uid>\d+) PID: (?P<trigger_proc_pid>\d+) "
            r"Comm: .* (Not tainted|Tainted:.*) "
            r"(?P<kernel_version>\d[\w.+-]+) #\d",
            OOMPatternType.KERNEL_MANDATORY,
        ),
    }


AllKernelConfigs = [
    KernelConfig_6_11(),
    KernelConfig_6_10(),
    KernelConfig_6_9(),
    KernelConfig_6_8(),
    KernelConfig_6_4(),
    KernelConfig_6_3(),
    KernelConfig_6_1(),
    KernelConfig_6_0(),
    KernelConfig_5_18(),
    KernelConfig_5_16(),
    KernelConfig_5_14(),
    KernelConfig_5_8(),
    KernelConfig_5_4(),
    KernelConfig_5_1(),
    KernelConfig_4_19(),
    KernelConfig_4_18(),
    KernelConfig_4_15(),
    KernelConfig_4_14(),
    KernelConfig_4_13(),
    KernelConfig_4_12(),
    KernelConfig_4_10(),
    KernelConfig_4_9(),
    KernelConfig_4_8(),
    KernelConfig_4_6(),
    KernelConfig_4_5(),
    KernelConfig_4_4(),
    KernelConfig_4_1(),
    KernelConfig_3_19(),
    KernelConfig_3_16(),
    KernelConfig_3_10_EL7(),
    KernelConfig_3_10(),
    BaseKernelConfig(),
]
"""
Instances of all available kernel configurations.

Manually sorted from newest to oldest and from specific to general.

The last entry in this list is the base configuration as a fallback.
"""


class OOMEntity:
    """Hold the whole OOM message block and provide access"""

    current_line = 0
    """Zero based index of the current line in self.lines"""

    lines = []
    """OOM text as list of lines"""

    REC_MEMINFO_BLOCK_SECOND_PART = re.compile(
        r"^\s*( (active_file|unevictable|slab_reclaimable|mapped|sec_pagetables|kernel_misc_reclaimable|free):.+)$"
    )
    """RE to match the second part of the "Mem-Info:" block

    The second part of the "Mem-Info:" block as starting with the third line
    has not a prefix like the lines before and after it. It is indented only
    by a single space.

    This RE is designed to match these lines and to extract the line with a
    single leading space.
    """

    state = OOMEntityState.unknown
    """State of the OOM after initial parsing"""

    text = ""
    """OOM as text"""

    def __init__(self, text):
        # use Unix LF only
        text = text.replace("\r\n", "\n")
        text = text.strip()
        oom_lines = text.split("\n")

        self.current_line = 0
        self.lines = oom_lines
        self.text = text

        # don't do anything if the text is empty or does not contain the leading OOM message
        if not text:
            self.state = OOMEntityState.empty
            return
        if "invoked oom-killer:" not in text:
            self.state = OOMEntityState.invalid
            return

        oom_lines = self._remove_non_oom_lines(oom_lines)
        oom_lines = self._remove_kernel_colon(oom_lines)
        cols_to_strip = self._number_of_columns_to_strip(
            oom_lines[self._get_CPU_index(oom_lines)]
        )
        oom_lines = self._strip_needless_columns(oom_lines, cols_to_strip)
        oom_lines = self._rsyslog_unescape_lf(oom_lines)

        self.lines = oom_lines
        self.text = "\n".join(oom_lines)

        if "Killed process" in text:
            self.state = OOMEntityState.complete
        else:
            self.state = OOMEntityState.started

    def _get_CPU_index(self, lines):
        """
        Return the index of the first line with "CPU: "

        Depending on the OOM version, the "CPU: " pattern is in second or third oom line.
        """
        for i in range(len(lines)):
            if "CPU: " in lines[i]:
                return i

        return 0

    def _number_of_columns_to_strip(self, line):
        """
        Determinate the number of columns left to the OOM message to strip.

        Sometime timestamps, hostnames and or syslog tags are left to the OOM message. These columns will be count to
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
            if "CPU:" in line:
                to_strip = columns.index("CPU:")
        except ValueError:
            pass

        return to_strip

    def _remove_non_oom_lines(self, oom_lines):
        """Remove all lines before and after the OOM message block"""
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
            if "Killed process" in line:
                killed_process = True
                continue

            # the next line after "Killed process \d+ ..."
            if killed_process:
                if "oom_reaper" in line:
                    break
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
            if "#012" in line:
                lines.extend(line.split("#012"))
            else:
                lines.append(line)

        return lines

    def _remove_kernel_colon(self, oom_lines):
        """
        Remove the "kernel:" pattern w/o leading and tailing spaces.

        Some OOM messages don't have a space between "kernel:" and the
        process name. _strip_needless_columns() will fail in such cases.
        Therefore, the pattern is removed.
        """
        oom_lines = [i.replace("kernel:", "") for i in oom_lines]
        return oom_lines

    def _strip_needless_columns(self, oom_lines, cols_to_strip=0):
        """
        Remove needless columns at the start of every line.

        This function removes all leading items w/o any relation to the OOM message like, date and time, hostname,
        syslog priority/facility.
        """
        stripped_lines = []
        for line in oom_lines:
            if not line.strip():  # remove empty lines
                continue

            # The output of the "Mem-Info:" block contains line breaks. journalctl breaks these lines but doesn't
            # insert a prefix e.g. with date and time. As a result, removing the needless columns does not work
            # correctly.
            # see: self._rsyslog_unescape_lf()

            # remove all leading whitespaces from "Mem-Info:" lines but keep the exact 1 space
            match = self.REC_MEMINFO_BLOCK_SECOND_PART.search(line)
            if match:
                line = match.group(1)

            elif cols_to_strip:  # remove needless columns
                # [-1] slicing needs Transcrypt operator overloading
                line = line.split(" ", cols_to_strip)[-1]  # __:opov

            stripped_lines.append(line)

        return stripped_lines

    def goto_previous_line(self):
        """Set line pointer to previous line

        If using in front of an iterator:
        The line pointer in self.current_line points to the first line of a block.
        An iterator-based loop starts with a next() call (as defined by the iterator
        protocol). This causes the current line to be skipped. Therefore, the line
        pointer is set to the previous line.
        """
        if self.current_line > 0:
            self.current_line -= 1

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
        Otherwise, the position pointer won't be changed.

        @param pattern: Text to find
        @type pattern: str

        @return: True if the marker has found.
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

    buddyinfo = {}
    """Information about free areas in all zones"""

    details = {}
    """Extracted result"""

    default_values = {
        "killed_proc_shmem_rss_kb": 0,  # set to 0 to show all values to calculate TotalRSS
    }
    """Predefined values used to populate details dictionary"""

    error_msg = ""
    """
    Error message

    @type: str
    """

    kconfig = BaseKernelConfig()
    """Kernel configuration"""

    kversion = None
    """
    Kernel version

    @type: str
    """

    mem_alloc_failure = OOMMemoryAllocFailureType.not_started
    """State/result of the memory allocation failure analysis

    @see: OOMAnalyser._analyse_alloc_failure()
    """

    mem_fragmented = None
    """True if the memory is heavily fragmented. This means that the higher order has no free chunks.

    @see: BaseKernelConfig.PAGE_ALLOC_COSTLY_ORDER, OOMAnalyser._check_for_memory_fragmentation()
    @type: None | bool
    """

    oom_entity = None
    """
    State of this OOM (unknown, incomplete, ...)

    @type: OOMEntityState
    """

    oom_text = None
    """
    OOM text

    @type: str
    """

    oom_type = OOMType.UNKNOWN
    """
    Type of this OOM (manually or automatically triggered)

    @type: OOMEntityType
    """

    swap_active = False
    """
    Swap space active or inactive

    @type: bool
    """

    watermarks = {}
    """Memory watermark information"""


class OOMAnalyser:
    """Analyze an OOM object and calculate additional values"""

    oom_entity = None
    """
    State of this OOM (unknown, incomplete, ...)

    @type: OOMEntityState
    """

    oom_result = OOMResult()
    """
    Store details of OOM analysis

    @type: OOMResult
    """

    # Optional UID field added for "lib/dump_stack: report process UID in dump_stack_print_info()" (d2917ff)
    REC_KERNEL_VERSION = re.compile(
        r"CPU: \d+ (UID: \d+ )?PID: \d+ Comm: .* (Not tainted|Tainted: [A-Z- ]+) (?P<kernel_version>\d[\w.+-]+) #.+"
    )
    """RE to match the OOM line with kernel version"""

    REC_SPLIT_KVERSION = re.compile(
        r"(?P<kernel_version>"
        r"(?P<major>\d+)\.(?P<minor>\d+)"  # major.minor
        r"(\.\d+)?"  # optional: patch level
        r"(-[\w.+-]+)?"  # optional: -rc6, -arch-1, -19-generic
        r")"
    )
    """
    RE for splitting the kernel version into parts

    Examples:
     - 5.19-rc6
     - 4.14.288
     - 5.18.6-arch1-1
     - 5.13.0-19-generic #19-Ubuntu
     - 5.13.0-1028-aws #31~20.04.1-Ubuntu
     - 3.10.0-514.6.1.el7.x86_64 #1
    """

    oom_block_complete = OOMEntityState.unknown
    """Completeness of the OOM block"""

    def __init__(self, oom):
        self.oom_entity = oom
        self.oom_result = OOMResult()
        self._set_oom_result_default_details()
        self.oom_block_complete = OOMEntityState.unknown

    def _identify_kernel_version(self):
        """
        Identify the used kernel version

        @rtype: bool
        """
        match = self.REC_KERNEL_VERSION.search(self.oom_entity.text)
        if not match:
            self.oom_result.error_msg = "Failed to extract kernel version from OOM text"
            return False
        self.oom_result.kversion = match.group("kernel_version")
        debug("Found kernel version: {}".format(self.oom_result.kversion))
        return True

    def _check_kversion_greater_equal(
        self, kversion: str, min_version: Tuple[int, int, str]
    ) -> bool:
        """
        Returns True if the kernel version is greater or equal to the minimum version
        """
        match = self.REC_SPLIT_KVERSION.match(kversion)

        if not match:
            self.oom_result.error_msg = (
                'Failed to extract version details from version string "{}"'.format(
                    kversion
                )
            )
            return False

        required_major = min_version[0]
        required_minor = min_version[1]
        suffix = min_version[2]
        current_major = int(match.group("major"))
        current_minor = int(match.group("minor"))

        if (required_major > current_major) or (
            required_major == current_major and required_minor > current_minor
        ):
            return False

        if bool(suffix) and (suffix not in kversion):
            return False

        return True

    def _choose_kernel_config(self):
        """
        Choose the first matching kernel configuration from AllKernelConfigs

        @see: _check_kversion_greater_equal(), AllKernelConfigs
        """
        for kcfg in AllKernelConfigs:
            if self._check_kversion_greater_equal(
                self.oom_result.kversion, kcfg.release
            ):
                self.oom_result.kconfig = kcfg
                break

        if not self.oom_result.kconfig:
            warning(
                'Failed to find a proper configuration for kernel "{}"'.format(
                    self.oom_result.kversion
                )
            )
            self.oom_result.kconfig = BaseKernelConfig()
        debug(
            "Choose kernel config {}.{}{}".format(
                self.oom_result.kconfig.release[0],
                self.oom_result.kconfig.release[1],
                self.oom_result.kconfig.release[2],
            )
        )

    def _check_for_empty_oom(self):
        """
        Check for an empty OOM text

        @rtype: bool
        """
        if not self.oom_entity.text:
            self.oom_block_complete = OOMEntityState.empty
            self.oom_result.error_msg = (
                "Empty OOM text. Please insert an OOM message block."
            )
            return False
        return True

    def _distinguish_between_cgroup_and_kernel_oom_type(self):
        """Set OOM type depending on CGROUP and KERNEL OOM"""
        if self.oom_result.kconfig.REC_OOM_CGROUP.search(self.oom_entity.text):
            debug("OOM triggered by cgroup memory limit")
            self.oom_result.oom_type = OOMType.CGROUP_AUTOMATIC
        else:
            debug("OOM triggered by kernel memory allocation failure")
            self.oom_result.oom_type = OOMType.KERNEL_AUTOMATIC_OR_MANUAL

    def _distinguish_between_automatic_and_manual_kernel_oom(self):
        """Set OOM type depending on automatic or manual kernel OOM"""
        if self.oom_result.oom_type == OOMType.KERNEL_AUTOMATIC_OR_MANUAL:
            if self.oom_result.details["trigger_proc_order"] == "-1":
                debug("OOM triggered by manual user action - order = -1")
                self.oom_result.oom_type = OOMType.KERNEL_MANUAL
            else:
                debug("OOM triggered automatically")
                self.oom_result.oom_type = OOMType.KERNEL_AUTOMATIC

    def _check_for_complete_oom(self):
        """
        Check if the OOM in self.oom_entity is complete and update self.oom_block_complete accordingly

        @rtype: bool
        """
        self.oom_block_complete = OOMEntityState.unknown
        self.oom_result.error_msg = "Unknown OOM format"

        if not self.oom_result.kconfig.REC_OOM_BEGIN.search(self.oom_entity.text):
            self.oom_block_complete = OOMEntityState.invalid
            self.oom_result.error_msg = "The inserted text is not a valid OOM block! The initial pattern was not found!"
            return False

        if not self.oom_result.kconfig.REC_OOM_END.search(self.oom_entity.text):
            self.oom_block_complete = OOMEntityState.started
            self.oom_result.error_msg = "The inserted OOM is incomplete! The initial pattern was found but not the final."
            return False

        self.oom_block_complete = OOMEntityState.complete
        self.oom_result.error_msg = None
        return True

    def _extract_block_from_next_pos(self, marker):
        """
        Extract a block that starts with the marker and contains all lines up to the next line with ":".
        @rtype: str
        """
        block = ""
        if not self.oom_entity.find_text(marker):
            return block

        line = self.oom_entity.current()
        block += "{}\n".format(line)
        for line in self.oom_entity:
            if ":" in line:
                self.oom_entity.goto_previous_line()
                break
            block += "{}\n".format(line)
        return block

    def _extract_details_with_re_pattern(self):
        """Extract details from the OOM text using regular expressions in kconfig.EXTRACT_PATTERN"""
        # __pragma__ ('jsiter')
        for k in self.oom_result.kconfig.EXTRACT_PATTERN:
            pattern, pattern_type = self.oom_result.kconfig.EXTRACT_PATTERN[k]
            if (
                self.oom_result.oom_type == OOMType.CGROUP_AUTOMATIC
                and pattern_type
                in [OOMPatternType.KERNEL_MANDATORY, OOMPatternType.KERNEL_OPTIONAL]
            ) or (
                self.oom_result.oom_type == OOMType.KERNEL_AUTOMATIC_OR_MANUAL
                and pattern_type
                in [OOMPatternType.CGROUP_MANDATORY, OOMPatternType.CGROUP_OPTIONAL]
            ):
                debug(
                    "Ignore pattern {} for OOM type {} as pattern type is different {}".format(
                        k,
                        self.oom_result.oom_type,
                        pattern_type,
                    )
                )
                continue

            rec = re.compile(pattern, re.MULTILINE)
            match = rec.search(self.oom_entity.text)
            if match and (
                (
                    (
                        pattern_type
                        in [OOMPatternType.ALL_MANDATORY, OOMPatternType.ALL_OPTIONAL]
                    )
                    or (
                        self.oom_result.oom_type == OOMType.CGROUP_AUTOMATIC
                        and pattern_type
                        in [
                            OOMPatternType.CGROUP_MANDATORY,
                            OOMPatternType.CGROUP_OPTIONAL,
                        ]
                    )
                    or (
                        self.oom_result.oom_type == OOMType.KERNEL_AUTOMATIC_OR_MANUAL
                        and pattern_type
                        in [
                            OOMPatternType.KERNEL_MANDATORY,
                            OOMPatternType.KERNEL_OPTIONAL,
                        ]
                    )
                )
            ):
                self.oom_result.details.update(match.groupdict())
                debug('Matched pattern "{}" for OOM type {}'.format(k, pattern_type))
            elif pattern_type in [
                OOMPatternType.ALL_MANDATORY,
                OOMPatternType.KERNEL_MANDATORY,
                OOMPatternType.CGROUP_MANDATORY,
            ]:
                error(
                    "Failed to extract information from OOM text. The regular "
                    'expression "{}" for kernel {} and OOM type "{}" with kernel '
                    "configuration {}.{}{} does not find anything. This can "
                    "lead to errors later on.".format(
                        k,
                        self.oom_result.kversion,
                        pattern_type,
                        self.oom_result.kconfig.release[0],
                        self.oom_result.kconfig.release[1],
                        self.oom_result.kconfig.release[2],
                    )
                )
            else:
                debug(
                    'Regular expression "{}" for OOM type {} does not match with current OOM text.'.format(
                        k, self.oom_result.oom_type
                    )
                )
        # __pragma__ ('nojsiter')

    def _extract_gpf_mask(self):
        """Extract the GFP (Get Free Pages) mask"""
        if self.oom_result.details["trigger_proc_gfp_flags"] is not None:
            flags = self.oom_result.details["trigger_proc_gfp_flags"]
        else:
            flags, unknown = self._gfp_hex2flags(
                self.oom_result.details["trigger_proc_gfp_mask"],
            )
            if unknown:
                flags.append("0x{0:x}".format(unknown))
            flags = " | ".join(flags)

        self.oom_result.details["_trigger_proc_gfp_mask_decimal"] = int(
            self.oom_result.details["trigger_proc_gfp_mask"], 16
        )
        self.oom_result.details["trigger_proc_gfp_mask"] = "{} ({})".format(
            self.oom_result.details["trigger_proc_gfp_mask"], flags
        )
        # already fully processed and no own element to display -> delete it,
        # otherwise an error msg will be shown
        del self.oom_result.details["trigger_proc_gfp_flags"]

        # TODO: Add check if given trigger_proc_gfp_flags is equal with calculated flags

    def _extract_from_oom_text(self):
        """Extract details from the OOM message text"""
        self._set_oom_result_default_details()

        self._distinguish_between_cgroup_and_kernel_oom_type()
        self._extract_details_with_re_pattern()
        self._distinguish_between_automatic_and_manual_kernel_oom()

        self.oom_result.details["hardware_info"] = self._extract_block_from_next_pos(
            "Hardware name:"
        )

        # strip "Call Trace" line at the beginning and remove leading spaces
        call_trace = ""
        block = self._extract_block_from_next_pos("Call Trace:")
        for line in block.split("\n"):
            if line.startswith("Call Trace"):
                continue
            call_trace += "{}\n".format(line.strip())
        self.oom_result.details["call_trace"] = call_trace

        self._extract_page_size()
        self._extract_pstable()
        self._extract_gpf_mask()
        self._extract_buddyinfo()
        self._extract_watermarks()

    def _extract_page_size(self):
        """Extract page size from buddyinfo DMZ zone"""
        match = self.oom_result.kconfig.REC_PAGE_SIZE.search(self.oom_entity.text)
        if match:
            self.oom_result.details["page_size_kb"] = int(match.group("page_size"))
            self.oom_result.details["_page_size_guessed"] = False
        else:
            # educated guess
            self.oom_result.details["page_size_kb"] = 4
            self.oom_result.details["_page_size_guessed"] = True

    def _extract_pstable(self):
        """Extract process table"""
        self.oom_result.details["_pstable"] = {}
        self.oom_entity.find_text(self.oom_result.kconfig.pstable_start)
        for line in self.oom_entity:
            if not line.startswith("["):
                break
            if line.startswith(self.oom_result.kconfig.pstable_start):
                continue
            match = self.oom_result.kconfig.REC_PROCESS_LINE.match(line)
            if match:
                details = match.groupdict()
                details["notes"] = ""
                pid = details.pop("pid")
                self.oom_result.details["_pstable"][pid] = {}
                self.oom_result.details["_pstable"][pid].update(details)

    def _extract_buddyinfo(self):
        """Extract information about free areas in all zones

        The migration types "(UEM)" or similar are not evaluated. They are documented in
        mm/page_alloc.c:show_migration_types().

        This function fills:
        * OOMResult.buddyinfo with [<zone>][<order>][<node>] = <number of free chunks>
        * OOMResult.buddyinfo with [zone]["total_free_kb_per_node"][node] = int(total_free_kb_per_node)
        """
        self.oom_result.buddyinfo = {}
        buddy_info = self.oom_result.buddyinfo
        self.oom_entity.find_text(self.oom_result.kconfig.zoneinfo_start)

        self.oom_entity.goto_previous_line()
        for line in self.oom_entity:
            match = self.oom_result.kconfig.REC_FREE_MEMORY_CHUNKS.match(line)
            if not match:
                continue
            node = int(match.group("node"))
            zone = match.group("zone")

            if zone not in buddy_info:
                buddy_info[zone] = {}

            if "total_free_kb_per_node" not in buddy_info[zone]:
                buddy_info[zone]["total_free_kb_per_node"] = {}
            buddy_info[zone]["total_free_kb_per_node"][node] = int(
                int(match.group("total_free_kb_per_node"))
            )

            order = -1  # to start with 0 after the first increment in for loop
            for element in match.group("zone_usage").split(" "):
                if element.startswith("("):  # skip migration types
                    continue
                order += 1
                if order not in buddy_info[zone]:
                    buddy_info[zone][order] = {}
                count = element.split("*")[0]
                count.strip()

                buddy_info[zone][order][node] = int(count)
                if "free_chunks_total" not in buddy_info[zone][order]:
                    buddy_info[zone][order]["free_chunks_total"] = 0
                buddy_info[zone][order]["free_chunks_total"] += buddy_info[zone][order][
                    node
                ]

        # MAX_ORDER is actually the maximum order plus one. For example,
        # a value of 11 means that the largest free memory block is 2^10 pages.
        # __pragma__ ('jsiter')
        max_order = 0
        for o in self.oom_result.buddyinfo["DMA"]:
            # JS: integer is sometimes a string :-/
            if (isinstance(o, str) and o.isdigit()) or isinstance(o, int):
                max_order += 1
        # __pragma__ ('nojsiter')
        self.oom_result.kconfig.MAX_ORDER = max_order

    def _extract_watermarks(self):
        """
        Extract memory watermark information from all zones

        This function fills:
        * OOMResult.watermarks with [<zone>][<node>][(free|min|low|high)] = int
        * OOMResult.watermarks with [<zone>][<node>][(lowmem_reserve)] = List(int)
        """
        self.oom_result.watermarks = {}
        watermark_info = self.oom_result.watermarks
        self.oom_entity.find_text(self.oom_result.kconfig.watermark_start)

        node = None
        zone = None
        self.oom_entity.goto_previous_line()
        for line in self.oom_entity:
            match = self.oom_result.kconfig.REC_WATERMARK.match(line)
            if match:
                node = int(match.group("node"))
                zone = match.group("zone")
                if zone not in watermark_info:
                    watermark_info[zone] = {}
                if node not in watermark_info[zone]:
                    watermark_info[zone][node] = {}
                for i in ["free", "min", "low", "high"]:
                    watermark_info[zone][node][i] = int(match.group(i))
            elif (
                line.startswith("lowmem_reserve[]:")
                and zone is not None
                and node is not None
            ):
                # REC_WATERMARK may not match for newer/unknown kernels,
                # "lowmem_reserve[]:" would match first in such cases, but zone and
                # node are not set, because both are set with the information from
                # REC_WATERMARK.
                watermark_info[zone][node]["lowmem_reserve"] = [
                    int(v) for v in line.split()[1:]
                ]

    def _search_node_with_memory_shortage(self):
        """
        Search NUMA node with memory shortage: watermark "free" < "min".

        This function fills:
        * OOMResult.details["trigger_proc_numa_node"] = <int(first node with memory shortage) | None>
        """
        self.oom_result.details["trigger_proc_numa_node"] = None
        zone = self.oom_result.details["trigger_proc_mem_zone"]
        watermark_info = self.oom_result.watermarks
        if zone not in watermark_info:
            debug(
                "Missing watermark info for zone {} - skip memory analysis".format(zone)
            )
            return
        # __pragma__ ('jsiter')
        for node in watermark_info[zone]:
            if watermark_info[zone][node]["free"] < watermark_info[zone][node]["min"]:
                self.oom_result.details["trigger_proc_numa_node"] = int(node)
                return
        # __pragma__ ('nojsiter')
        debug("No NUMA node has a memory shortage: watermark free < min")
        return

    def _gfp_hex2flags(self, hexvalue):
        """\
        Convert the hexadecimal value into flags specified by definition

        @return: Unsorted list of flags and the sum of all unknown flags as integer
        @rtype: List(str), int
        """
        remaining = int(hexvalue, 16)
        converted_flags = []

        for flag in self.oom_result.kconfig.gfp_reverse_lookup:
            value = self.oom_result.kconfig.GFP_FLAGS[flag]["_value"]
            if (remaining & value) == value:
                # delete the flag by "and" with a reverted mask
                remaining &= ~value
                converted_flags.append(flag)

        converted_flags.sort()
        return converted_flags, remaining

    def _convert_numeric_results_to_integer(self):
        """Convert all *_pages and *_kb to integer"""
        # __pragma__ ('jsiter')
        for item in self.oom_result.details:
            if self.oom_result.details[item] is None:
                self.oom_result.details[item] = "<not found>"
                continue
            if (
                item.endswith("_bytes")
                or item.endswith("_kb")
                or item.endswith("_pages")
                or item.endswith("_pid")
                or item
                in ["killed_proc_score", "trigger_proc_order", "trigger_proc_oomscore"]
            ):
                try:
                    self.oom_result.details[item] = int(self.oom_result.details[item])
                except:
                    error(
                        'Converting item "{}={}" to integer failed'.format(
                            item, self.oom_result.details[item]
                        )
                    )
        # __pragma__ ('nojsiter')

    def _convert_pstable_values_to_integer(self):
        """Convert numeric values in the process table to integer values"""
        ps = self.oom_result.details["_pstable"]
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
                        pitem = "<not in process table>"
                    else:
                        pitem = process[item]
                    error(
                        'Converting process parameter "{}={}" to integer failed'.format(
                            item, pitem
                        )
                    )

            converted["name"] = process["name"]
            converted["notes"] = process["notes"]
            pid_int = int(pid_str)
            del ps[pid_str]
            ps[pid_int] = converted
            ps_index.append(pid_int)

        ps_index.sort(key=int)
        self.oom_result.details["_pstable_index"] = ps_index

    def _check_free_chunks(self, start_with_order, zone, node):
        """Check for at least one free chunk in the current or any higher order.

        Returns True, if at least one suitable chunk is free.
        Returns None, if buddyinfo doesn't contain information for the requested node, order or zone

        @param int start_with_order: Start checking with this order
        @param str zone: Memory zone
        @param int node: Node number
        @rtype: None|bool
        """
        if not self.oom_result.buddyinfo:
            return None
        buddyinfo = self.oom_result.buddyinfo
        if zone not in buddyinfo:
            return None

        for order in range(start_with_order, self.oom_result.kconfig.MAX_ORDER):
            if order not in buddyinfo[zone]:
                break
            if node not in buddyinfo[zone][order]:
                return None
            free_chunks = buddyinfo[zone][order][node]
            if free_chunks:
                return True
        return False

    def _check_for_memory_fragmentation(self):
        """Check for heavy memory fragmentation. This means that the higher order has no free chunks.

        Returns True, all high-order chunks are in use.
        Returns False, if high-order chunks are available.
        Returns None, if buddyinfo doesn't contain information for the requested node, order or zone

        @see: BaseKernelConfig.PAGE_ALLOC_COSTLY_ORDER, OOMResult.mem_fragmented
        """
        zone = self.oom_result.details["trigger_proc_mem_zone"]
        node = self.oom_result.details["trigger_proc_numa_node"]
        if zone not in self.oom_result.buddyinfo:
            return
        self.oom_result.mem_fragmented = not self._check_free_chunks(
            self.oom_result.kconfig.PAGE_ALLOC_COSTLY_ORDER, zone, node
        )
        self.oom_result.details[
            "kconfig.PAGE_ALLOC_COSTLY_ORDER"
        ] = self.oom_result.kconfig.PAGE_ALLOC_COSTLY_ORDER

    def _analyse_alloc_failure(self):
        """
        Analyze why the memory allocation could be failed.

        The code in this function is inspired by mm/page_alloc.c:__zone_watermark_ok()
        """
        self.oom_result.mem_alloc_failure = OOMMemoryAllocFailureType.not_started

        if self.oom_result.oom_type == OOMType.KERNEL_MANUAL:
            debug("OOM triggered manually - skip memory analysis")
            return
        if not self.oom_result.buddyinfo:
            debug("Missing buddyinfo - skip memory analysis")
            return
        if ("trigger_proc_order" not in self.oom_result.details) or (
            "trigger_proc_mem_zone" not in self.oom_result.details
        ):
            debug(
                "Missing trigger_proc_order and/or trigger_proc_mem_zone - skip memory analysis"
            )
            return
        if not self.oom_result.watermarks:
            debug("Missing watermark information - skip memory analysis")
            return

        order = self.oom_result.details["trigger_proc_order"]
        zone = self.oom_result.details["trigger_proc_mem_zone"]
        watermark_info = self.oom_result.watermarks

        # "high order" requests don't trigger OOM
        if int(order) > self.oom_result.kconfig.PAGE_ALLOC_COSTLY_ORDER:
            debug("high order requests should not trigger OOM - skip memory analysis")
            self.oom_result.mem_alloc_failure = (
                OOMMemoryAllocFailureType.skipped_high_order_dont_trigger_oom
            )
            return

        # Node with memory shortage: watermark "free" < "min"
        node = self.oom_result.details["trigger_proc_numa_node"]
        if node is None:
            debug("No NUMA node found - skip analysis of memory allocation failure")
            return

        # the remaining code is similar to mm/page_alloc.c:__zone_watermark_ok()
        # =======================================================================

        # calculation in kB and not in pages
        free_kb = watermark_info[zone][node]["free"]
        highest_zoneidx = self.oom_result.kconfig.ZONE_TYPES.index(zone)
        lowmem_reserve = watermark_info[zone][node]["lowmem_reserve"]
        min_kb = watermark_info[zone][node]["low"]

        # reduce the minimum watermark for high-priority calls
        # ALLOC_HIGH == __GFP_HIGH
        gfp_mask_decimal = self.oom_result.details["_trigger_proc_gfp_mask_decimal"]
        gfp_flag_high = self.oom_result.kconfig.GFP_FLAGS["__GFP_DMA"]["_value"]
        if (gfp_mask_decimal & gfp_flag_high) == gfp_flag_high:
            min_kb -= int(min_kb / 2)

        # check watermarks, if these are not met, then a high-order request also
        # cannot go ahead even if a suitable page happened to be free.
        if free_kb <= (
            min_kb
            + (
                lowmem_reserve[highest_zoneidx]
                * self.oom_result.details["page_size_kb"]
            )
        ):
            self.oom_result.mem_alloc_failure = (
                OOMMemoryAllocFailureType.failed_below_low_watermark
            )
            return

        # For a high-order request, check at least one suitable page is free
        if not self._check_free_chunks(order, zone, node):
            self.oom_result.mem_alloc_failure = (
                OOMMemoryAllocFailureType.failed_no_free_chunks
            )
            return

        self.oom_result.mem_alloc_failure = (
            OOMMemoryAllocFailureType.failed_unknown_reason
        )

    def _calc_pstable_values(self):
        """Set additional notes to processes listed in the process table"""
        tpid = self.oom_result.details["trigger_proc_pid"]
        kpid = self.oom_result.details["killed_proc_pid"]

        # sometimes the trigger process isn't part of the process table
        if tpid in self.oom_result.details["_pstable"]:
            self.oom_result.details["_pstable"][tpid]["notes"] = "trigger process"

        # assume the killed process may also not part of the process table
        if kpid in self.oom_result.details["_pstable"]:
            self.oom_result.details["_pstable"][kpid]["notes"] = "killed process"

    def _calc_trigger_process_values(self):
        """Calculate all values related to the trigger process"""
        self.oom_result.details["trigger_proc_requested_memory_pages"] = (
            2 ** self.oom_result.details["trigger_proc_order"]
        )
        self.oom_result.details["trigger_proc_requested_memory_pages_kb"] = (
            self.oom_result.details["trigger_proc_requested_memory_pages"]
            * self.oom_result.details["page_size_kb"]
        )

        gfp_mask_decimal = self.oom_result.details["_trigger_proc_gfp_mask_decimal"]
        gfp_flag_dma = self.oom_result.kconfig.GFP_FLAGS["__GFP_DMA"]["_value"]
        gfp_flag_dma32 = self.oom_result.kconfig.GFP_FLAGS["__GFP_DMA32"]["_value"]
        if (gfp_mask_decimal & gfp_flag_dma) == gfp_flag_dma:
            zone = "DMA"
        elif (gfp_mask_decimal & gfp_flag_dma32) == gfp_flag_dma32:
            zone = "DMA32"
        else:
            zone = "Normal"
        self.oom_result.details["trigger_proc_mem_zone"] = zone

    def _calc_killed_process_values(self):
        """Calculate all values related to the killed process"""
        self.oom_result.details["killed_proc_total_rss_kb"] = (
            self.oom_result.details["killed_proc_anon_rss_kb"]
            + self.oom_result.details["killed_proc_file_rss_kb"]
            + self.oom_result.details.get("killed_proc_shmem_rss_kb", 0)
        )

        self.oom_result.details["killed_proc_rss_percent"] = int(
            100
            * self.oom_result.details["killed_proc_total_rss_kb"]
            / int(self.oom_result.details["system_total_ram_kb"])
        )

    def _calc_swap_values(self):
        """Calculate all swap related values"""
        if "swap_total_kb" in self.oom_result.details:
            self.oom_result.swap_active = self.oom_result.details["swap_total_kb"] > 0
        if not self.oom_result.swap_active:
            return

        self.oom_result.details["swap_cache_kb"] = (
            self.oom_result.details["swap_cache_pages"]
            * self.oom_result.details["page_size_kb"]
        )
        del self.oom_result.details["swap_cache_pages"]

        #  SwapUsed = SwapTotal - SwapFree - SwapCache
        self.oom_result.details["swap_used_kb"] = (
            self.oom_result.details["swap_total_kb"]
            - self.oom_result.details["swap_free_kb"]
            - self.oom_result.details["swap_cache_kb"]
        )
        self.oom_result.details["system_swap_used_percent"] = int(
            100
            * self.oom_result.details["swap_used_kb"]
            / self.oom_result.details["swap_total_kb"]
        )

    def _calc_system_values(self):
        """Calculate system memory"""

        # calculate remaining explanation values
        self.oom_result.details["system_total_ram_kb"] = (
            self.oom_result.details["ram_pages"]
            * self.oom_result.details["page_size_kb"]
        )
        if self.oom_result.swap_active:
            self.oom_result.details["system_total_ramswap_kb"] = (
                self.oom_result.details["system_total_ram_kb"]
                + self.oom_result.details["swap_total_kb"]
            )
        else:
            self.oom_result.details[
                "system_total_ramswap_kb"
            ] = self.oom_result.details["system_total_ram_kb"]

        # TODO: Current RSS calculation based on process table is probably incorrect,
        #       because it don't differentiates between processes and threads
        total_rss_pages = 0
        for pid in self.oom_result.details["_pstable"].keys():
            # convert to int to satisfy Python for unit tests
            total_rss_pages += int(
                self.oom_result.details["_pstable"][pid]["rss_pages"]
            )
        self.oom_result.details["system_total_ram_used_kb"] = (
            total_rss_pages * self.oom_result.details["page_size_kb"]
        )

        self.oom_result.details["system_total_used_percent"] = int(
            100
            * self.oom_result.details["system_total_ram_used_kb"]
            / self.oom_result.details["system_total_ram_kb"]
        )

    def _determinate_platform_and_distribution(self):
        """Determinate platform and distribution"""
        kernel_version = self.oom_result.details.get("kernel_version", "")
        dist = "unknown"
        platform = "unknown"

        for identifier, desc in self.oom_result.kconfig.PLATFORM_DESCRIPTION:
            if identifier in kernel_version:
                platform = desc
                break

        if ".el7uek" in kernel_version:
            dist = "Oracle Linux 7 (Unbreakable Enterprise Kernel)"
        elif ".el7" in kernel_version:
            dist = "RHEL 7/CentOS 7"
        elif ".el6" in kernel_version:
            dist = "RHEL 6/CentOS 6"
        elif ".el5" in kernel_version:
            dist = "RHEL 5/CentOS 5"
        elif "ARCH" in kernel_version or "-arch" in kernel_version:
            # ArchLinux has not platform identifier in the kernel version
            dist = "Arch Linux"
            platform = "x86 64-bit"
        elif "-generic" in kernel_version:
            dist = "Ubuntu"
            platform = "x86 64-bit"
        elif "-amd64" in kernel_version:
            dist = "Debian"
            platform = "x86 64-bit"
        self.oom_result.details["dist"] = dist
        self.oom_result.details["platform"] = platform

    def _calc_from_oom_details(self):
        """
        Calculate values from already extracted details

        @see: self.oom_result.details
        """
        self._convert_numeric_results_to_integer()
        self._convert_pstable_values_to_integer()
        self._calc_pstable_values()

        self._determinate_platform_and_distribution()
        self._calc_swap_values()
        self._calc_system_values()
        self._calc_trigger_process_values()
        self._calc_killed_process_values()
        self._search_node_with_memory_shortage()
        self._analyse_alloc_failure()
        self._check_for_memory_fragmentation()

    def _set_oom_result_default_details(self):
        """Set default values for OOM results"""
        # TODO replace with self.EXTRACT_PATTERN = self.EXTRACT_PATTERN.copy() after
        #      https://github.com/QQuick/Transcrypt/issues/716 "dict does not have a copy method" is fixed
        self.oom_result.details = {}
        self.oom_result.details.update(self.oom_result.default_values)

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

        self._choose_kernel_config()

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

    cfg = {
        "chart_height": 150,
        "chart_width": 600,
        "label_height": 80,
        "legend_entry_width": 160,
        "legend_margin": 7,
        "title_height": 20,
        "title_margin": 10,
        "css_class": "js-mem-usage__svg",  # CSS class for SVG diagram
    }
    """Basic chart configuration"""

    # generated with Colorgorical http://vrl.cs.brown.edu/color
    colors = [
        "#aee39a",
        "#344b46",
        "#1ceaf9",
        "#5d99aa",
        "#32e195",
        "#b02949",
        "#deae9e",
        "#805257",
        "#add51f",
        "#544793",
        "#a794d3",
        "#e057e1",
        "#769b5a",
        "#76f014",
        "#621da6",
        "#ffce54",
        "#d64405",
        "#bb8801",
        "#096013",
        "#ff0087",
    ]
    """20 different colors for memory usage diagrams"""

    max_entries_per_row = 3
    """Maximum chart legend entries per row"""

    namespace = "http://www.w3.org/2000/svg"

    def __init__(self):
        super().__init__()
        self.cfg["bar_topleft_x"] = 0
        self.cfg["bar_topleft_y"] = self.cfg["title_height"] + self.cfg["title_margin"]
        self.cfg["bar_bottomleft_x"] = self.cfg["bar_topleft_x"]
        self.cfg["bar_bottomleft_y"] = (
            self.cfg["bar_topleft_y"] + self.cfg["chart_height"]
        )

        self.cfg["bar_bottomright_x"] = (
            self.cfg["bar_topleft_x"] + self.cfg["chart_width"]
        )
        self.cfg["bar_bottomright_y"] = (
            self.cfg["bar_topleft_y"] + self.cfg["chart_height"]
        )

        self.cfg["legend_topleft_x"] = self.cfg["bar_topleft_x"]
        self.cfg["legend_topleft_y"] = (
            self.cfg["bar_topleft_y"] + self.cfg["legend_margin"]
        )
        self.cfg["legend_width"] = (
            self.cfg["legend_entry_width"]
            + self.cfg["legend_margin"]
            + self.cfg["legend_entry_width"]
        )

        self.cfg["diagram_height"] = (
            self.cfg["chart_height"]
            + self.cfg["title_margin"]
            + self.cfg["title_height"]
        )
        self.cfg["diagram_width"] = self.cfg["chart_width"]

        self.cfg["title_bottommiddle_y"] = self.cfg["title_height"]
        self.cfg["title_bottommiddle_x"] = self.cfg["diagram_width"] // 2

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
            k2 = k.replace("_", "-")
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
        element = self.create_element("text", **kwargs)
        element.textContent = text
        return element

    # __pragma__ ('nokwargs')

    def create_element_svg(self, height, width, css_class=None):
        """Return an SVG element"""
        svg = self.create_element(
            "svg",
            version="1.1",
            height=height,
            width=width,
            viewBox="0 0 {} {}".format(width, height),
        )
        if css_class:
            svg.setAttribute("class", css_class)
        return svg

    def create_rectangle(self, x, y, width, height, color=None, title=None):
        """
        Return a rect-element in a group container

        If a title is given, the container also contains a <title> element.
        """
        g = self.create_element("g")
        rect = self.create_element("rect", x=x, y=y, width=width, height=height)
        if color:
            rect.setAttribute("fill", color)
        if title:
            t = self.create_element("title")
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
        label_group = self.create_element("g", id=desc)
        color_rect = self.create_rectangle(0, 0, 20, 20, color)
        label_group.appendChild(color_rect)

        desc_element = self.create_element_text(desc, x="30", y="18")
        desc_element.textContent = desc
        label_group.appendChild(desc_element)

        # move the group to right position
        x, y = self.legend_calc_xy(pos)
        label_group.setAttribute("transform", "translate({}, {})".format(x, y))

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
        x = self.cfg["bar_bottomleft_x"] + self.cfg["legend_margin"]
        x += column * (self.cfg["legend_margin"] + self.cfg["legend_entry_width"])
        return x

    def legend_calc_y(self, row):
        """
        Calculate the Y-axis using the given row

        @type row: int
        @rtype: int
        """
        y = self.cfg["bar_bottomleft_y"] + self.cfg["legend_margin"]
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

        x = self.cfg["bar_bottomleft_x"] + self.cfg["legend_margin"]
        y = self.cfg["bar_bottomleft_y"] + self.cfg["legend_margin"]
        x += col * (self.cfg["legend_margin"] + self.cfg["legend_entry_width"])
        y += row * 40

        return x, y

    def generate_bar_area(self, elements):
        """
        Generate colord stacked bars. All entries are group within a g-element.

        @rtype: Node
        """
        bar_group = self.create_element(
            "g", id="bar_group", stroke="black", stroke_width=2
        )
        current_x = 0
        total_length = sum([length for unused, length in elements])

        for i, two in enumerate(elements):
            name, length = two
            color = self.colors[i % len(self.colors)]
            rect_len = int(length / total_length * self.cfg["chart_width"])
            if rect_len == 0:
                rect_len = 1
            rect = self.create_rectangle(
                current_x,
                self.cfg["bar_topleft_y"],
                rect_len,
                self.cfg["chart_height"],
                color,
                name,
            )
            current_x += rect_len
            bar_group.appendChild(rect)

        return bar_group

    def generate_legend(self, elements):
        """
        Generate a legend for all elements. All entries are grouped within a g-element.

        @rtype: Node
        """
        legend_group = self.create_element("g", id="legend_group")
        for i, two in enumerate(elements):
            element_name = two[0]
            color = self.colors[i % len(self.colors)]
            label_group = self.create_legend_entry(color, element_name, i)
            legend_group.appendChild(label_group)

        # re-calculate chart height after all legend entries added
        self.cfg["diagram_height"] = self.legend_calc_y(
            self.legend_max_row(len(elements))
        )

        return legend_group

    def generate_chart(self, title, *elements):
        """
        Return an SVG bar chart for all elements

        @param str title: Chart title
        @param elements: List of tuple with name and length of the entry (not normalized)
        @rtype: Node
        """
        filtered_elements = [(name, length) for name, length in elements if length > 0]
        bar_group = self.generate_bar_area(filtered_elements)
        legend_group = self.generate_legend(filtered_elements)
        svg = self.create_element_svg(
            self.cfg["diagram_height"], self.cfg["diagram_width"], self.cfg["css_class"]
        )
        chart_title = self.create_element_text(
            title,
            font_size=self.cfg["title_height"],
            font_weight="bold",
            stroke_width="0",
            text_anchor="middle",
            x=self.cfg["title_bottommiddle_x"],
            y=self.cfg["title_bottommiddle_y"],
        )
        svg.appendChild(chart_title)
        svg.appendChild(bar_group)
        svg.appendChild(legend_group)
        return svg


class OOMDisplay:
    """Display the OOM analysis"""

    oom_result = OOMResult()
    """
    OOM analysis details

    @rtype: OOMResult
    """

    example_archlinux_6_1_1 = """\
doxygen invoked oom-killer: gfp_mask=0x140dca(GFP_HIGHUSER_MOVABLE|__GFP_COMP|__GFP_ZERO), order=0, oom_score_adj=0
CPU: 3 PID: 473206 Comm: doxygen Tainted: G           OE      6.1.1-arch1-1 #1 9bd09188b430be630e611f984454e4f3c489be77
Hardware name: To Be Filled By O.E.M. To Be Filled By O.E.M./Z77 Extreme6, BIOS P2.80 07/01/2013
Call Trace:
 <TASK>
 dump_stack_lvl+0x48/0x60
 dump_header+0x4a/0x211
 oom_kill_process.cold+0xb/0x10
 out_of_memory+0x1f1/0x520
 __alloc_pages_slowpath.constprop.0+0xcbd/0xe10
 __alloc_pages+0x224/0x250
 __folio_alloc+0x1b/0x50
 vma_alloc_folio+0xa0/0x360
 __handle_mm_fault+0x92f/0xfa0
 handle_mm_fault+0xdf/0x2d0
 do_user_addr_fault+0x1be/0x6a0
 ? sched_clock_cpu+0xd/0xb0
 exc_page_fault+0x74/0x170
 asm_exc_page_fault+0x26/0x30
RIP: 0033:0x7f5ba27c6d6f
Code: Unable to access opcode bytes at 0x7f5ba27c6d45.
RSP: 002b:00007ffd84637ec0 EFLAGS: 00010206
RAX: 0000000000015fd1 RBX: 0000000000001010 RCX: 00005658cf73d030
RDX: 0000000000001011 RSI: 00005658cf73e030 RDI: 0000000000000004
RBP: 00007f5ba2909ba0 R08: 0000000000001001 R09: 00007f5ba2909c70
R10: 00007f5ba2909c70 R11: 0000000000000000 R12: 0000000000001001
R13: 0000000000000063 R14: ffffffffffffff78 R15: 00007f5ba2909c00
 </TASK>
Mem-Info:
active_anon:1413442 inactive_anon:1509191 isolated_anon:0
 active_file:29 inactive_file:186 isolated_file:0
 unevictable:2047 dirty:56 writeback:20
 slab_reclaimable:130091 slab_unreclaimable:89303
 mapped:1293 shmem:19540 pagetables:25704
 sec_pagetables:0 bounce:0
 kernel_misc_reclaimable:0
 free:34629 free_pcp:0 free_cma:0
Node 0 active_anon:5653768kB inactive_anon:6036764kB active_file:728kB inactive_file:132kB unevictable:8188kB isolated(anon):0kB isolated(file):0kB mapped:5172kB dirty:224kB writeback:80kB shmem:78160kB shmem_thp: 0kB shmem_pmdmapped: 0kB anon_thp: 1236992kB writeback_tmp:0kB kernel_stack:10592kB pagetables:102816kB sec_pagetables:0kB all_unreclaimable? no
Node 0 DMA free:13312kB boost:0kB min:64kB low:80kB high:96kB reserved_highatomic:0KB active_anon:0kB inactive_anon:0kB active_file:0kB inactive_file:0kB unevictable:0kB writepending:0kB present:15984kB managed:15360kB mlocked:0kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB
lowmem_reserve[]: 0 3191 15659 15659 15659
Node 0 DMA32 free:63304kB boost:0kB min:13760kB low:17200kB high:20640kB reserved_highatomic:0KB active_anon:1816112kB inactive_anon:1188180kB active_file:0kB inactive_file:240kB unevictable:544kB writepending:28kB present:3348656kB managed:3283120kB mlocked:0kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB
lowmem_reserve[]: 0 0 12468 12468 12468
Node 0 Normal free:61900kB boost:8192kB min:61948kB low:75384kB high:88820kB reserved_highatomic:0KB active_anon:1529368kB inactive_anon:7156872kB active_file:0kB inactive_file:860kB unevictable:7644kB writepending:276kB present:13096960kB managed:12774792kB mlocked:64kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB
lowmem_reserve[]: 0 0 0 0 0
Node 0 DMA: 0*4kB 0*8kB 0*16kB 0*32kB 0*64kB 0*128kB 0*256kB 0*512kB 1*1024kB (U) 2*2048kB (UM) 2*4096kB (M) = 13312kB
Node 0 DMA32: 550*4kB (UM) 250*8kB (UE) 46*16kB (UE) 14*32kB (UME) 6*64kB (UME) 2*128kB (UM) 1*256kB (U) 14*512kB (ME) 7*1024kB (ME) 19*2048kB (ME) 1*4096kB (M) = 63624kB
Node 0 Normal: 6676*4kB (UME) 2120*8kB (UE) 595*16kB (UME) 188*32kB (UME) 50*64kB (UME) 1*128kB (M) 0*256kB 0*512kB 0*1024kB 0*2048kB 0*4096kB = 62528kB
Node 0 hugepages_total=0 hugepages_free=0 hugepages_surp=0 hugepages_size=2048kB
44659 total pagecache pages
24863 pages in swap cache
Free swap  = 84kB
Total swap = 25165820kB
4115400 pages RAM
0 pages HighMem/MovableOnly
97082 pages reserved
0 pages cma reserved
0 pages hwpoisoned
Tasks state (memory values in pages):
[  pid  ]   uid  tgid total_vm      rss pgtables_bytes swapents oom_score_adj name
[    246]     0   246    16404       66   159744      303          -250 systemd-journal
[    274]     0   274     8511        0    98304      638         -1000 systemd-udevd
[    493]     0   493      631        1    40960       36             0 acpid
[    495]    84   495     2120        0    57344      130             0 avahi-daemon
[    496]     0   496     1761       14    57344      187             0 crond
[    497]    81   497     2282        1    61440      358          -900 dbus-daemon
[    499]     0   499     2729        0    57344      382             0 smartd
[    500]     0   500    12576       23    90112      299             0 systemd-logind
[    501]     0   501     4280        0    73728      286             0 systemd-machine
[    504]   993   504      767        0    49152      122             0 dhcpcd
[    505]     0   505      850        1    53248       84             0 dhcpcd
[    506]   993   506      721        0    49152       90             0 dhcpcd
[    507]   993   507      719        0    49152       97             0 dhcpcd
[    509]    84   509     2120        0    53248      138             0 avahi-daemon
[    526]     0   526     6756        0    86016      417             0 cupsd
[    558]     0   558    58147        0    86016      300             0 lightdm
[    569]     0   569   204061     1279   708608     7704             0 Xorg
[    687]     0   687    40542        0    77824      371             0 lightdm
[    693]   504   693     5035        0    81920      605           100 systemd
[    694]   504   694     6218        0    81920      891           100 (sd-pam)
[    700]   504   700   116292      236   253952     5766             0 xfce4-session
[    709]   504   709     2278       15    61440      317           200 dbus-daemon
[    720]   504   720    60626        0   110592      936           200 gvfsd
[    725]   504   725    94774        0   102400     1371           200 gvfsd-fuse
[    732]   504   732    77011        0    94208      853           200 at-spi-bus-laun
[    738]   504   738     2144        0    61440      192           200 dbus-daemon
[    745]   504   745    40251        0    77824      268           200 at-spi2-registr
[    747]   102   747    77578        0   102400      906             0 polkitd
[    760]   504   760     1855        0    53248      209             0 ssh-agent
[    767]   504   767    38905       55    73728       67           200 gpg-agent
[    769]   504   769   242402     1658   401408     4392             0 xfwm4
[    778]   504   778    58286      225   167936     1911             0 xfsettingsd
[    791]   504   791   453174     1056   393216     2624           200 pulseaudio
[    792]   133   792    22084        0    57344      175             0 rtkit-daemon
[    841]   504   841   176141     1378   266240     3418             0 xfce4-panel
[    881]   504   881   137016       15   249856     3888             0 Thunar
[    886]   504   886   114166      558   208896     1267             0 panel-6-systray
[    887]   504   887   114470      462   212992     2358             0 panel-2-actions
[    888]   504   888   159010     1173   315392    10226             0 xfdesktop
[    906]   504   906    59197        0    86016      852           200 gsettings-helpe
[    911]   504   911   355202        0   442368    10408             0 claws-mail
[    912]   504   912   796658     8304  1429504    81625             0 clementine
[    913]   504   913   242116     2555   327680     4878             0 xfce4-terminal
[    914]   504   914    58010        0   167936     1998             0 xfce4-power-man
[    922]     0   922    58307        0    90112      828             0 upowerd
[    959]   504   959   161371      132   184320     1131           200 gvfs-udisks2-vo
[    976]   504   976     2115        1    53248      243             0 bash
[    978]   504   978     2030        0    61440      231             0 bash
[    979]   504   979     2030        0    57344      231             0 bash
[    980]   504   980     2054        0    53248      241             0 bash
[    982]   504   982     2029        0    49152      243             0 bash
[    986]     0   986    98535      216   131072     1210             0 udisksd
[    987]   504   987     2029        0    53248      229             0 bash
[    989]   504   989     2054        0    53248      241             0 bash
[    998]   504   998     2029        0    57344      230             0 bash
[   1008]   504  1008     2238        1    49152      387             0 bash
[   1227]   504  1227    79220        0   114688     1551           200 gvfsd-trash
[   1238]   504  1238    39834        0    77824      749           200 gvfsd-metadata
[   1267]   504  1267    17396        0   135168      526             0 clementine-tagr
[   1268]   504  1268    17397        0   131072      539             0 clementine-tagr
[   1269]   504  1269    17398        0   126976      549             0 clementine-tagr
[   1270]   504  1270    17398        0   135168      547             0 clementine-tagr
[   1298]   504  1298    57817        0   172032     1926             0 polkit-gnome-au
[   1299]   504  1299     1216      138    49152       69         -1000 xscreensaver
[   1300]   504  1300   102371       46   225280     3021             0 xfce4-notifyd
[   1308]   504  1308   252426     1143   356352     3844             0 pavucontrol
[   1310]   504  1310     1926        0    57344      134             0 xscreensaver-sy
[   1676]   504  1676    97743        0   131072     1047           200 gvfsd-network
[   1682]   504  1682    79674        0   118784      975           200 gvfsd-dnssd
[   5514]   504  5514    38890        0    73728      792           200 dconf-service
[  10333]   504 10333   159849      468   299008     8753             0 mousepad
[ 316097]   504 316097   117647     2682   217088     8661             0 python2
[ 322400]   504 322400   211848        0   303104     5300             0 xfce4-appfinder
[ 331049]   504 331049  2316564   516062 12025856   547863             0 java
[ 351065]   504 351065     2202       61    57344      760             0 fsnotifier
[ 375042]   504 375042  8546231     9209  1327104    24903             0 chrome
[ 375046]   504 375046     1493        0    49152       27             0 cat
[ 375047]   504 375047     1493        0    53248       46             0 cat
[ 375049]   504 375049  8393904        0    61440      113             0 chrome_crashpad
[ 375051]   504 375051  8391851        0    53248      112             0 chrome_crashpad
[ 375057]   504 375057  8461795       34   397312     2772             0 chrome
[ 375058]   504 375058  8461793        3   409600     2774             0 chrome
[ 375060]   504 375060  8391944        1    77824      114             0 nacl_helper
[ 375063]   504 375063  8461799       11   266240     2798             0 chrome
[ 375091]   504 375091  8476826     3620   970752    17473           200 chrome
[ 375094]   504 375094  8474193      273   503808     4651           200 chrome
[ 376692]   504 376692 296469227     2362  1826816    57194           300 chrome
[ 376850]   504 376850  8540727      588   471040     2920           200 chrome
[ 384429]   504 384429 296196870      161   892928    10673           300 chrome
[ 384480]   504 384480 296197707     1513  1761280    35094           300 chrome
[ 384572]   504 384572 296192141      146   806912     9569           300 chrome
[ 429251]   504 429251 296191891      151   802816    10933           300 chrome
[ 429292]   504 429292 296195734      159   798720     7995           300 chrome
[ 429373]   504 429373 296193695      132  1060864    19693           300 chrome
[ 429392]   504 429392 296192194      867   962560    15007           300 chrome
[ 442829]   504 442829 296195874      170   942080    11840           300 chrome
[ 443457]   504 443457     2081        0    53248      247             0 bash
[ 452899]   504 452899 296191069      184   663552     5157           300 chrome
[ 453235]   504 453235 296190983      145   675840     4694           300 chrome
[ 453303]   504 453303 296453346      213   884736    17367           300 chrome
[ 466649]   504 466649 296458526     1742   847872     9381           300 chrome
[ 469274]   504 469274 296191525       39   790528     8550           300 chrome
[ 469323]   504 469323 296188917      156   663552     4015           300 chrome
[ 470905]   504 470905     2030        0    57344      234             0 bash
[ 471736]   504 471736 296191883      107   847872    11573           300 chrome
[ 472463]   504 472463 296191588     2361   737280     3564           300 chrome
[ 472477]   504 472477 296182731       87   581632     3768           300 chrome
[ 472728]   993 472728      850        0    49152       90             0 dhcpcd
[ 473029]   504 473029    58100       56    86016      134           200 xfconfd
[ 473206]   504 473206  7572670  2308581 60686336  5225427             0 doxygen
[ 473207]   504 473207     2835      124    61440      143             0 top
[ 473257]   504 473257  8547051     5143   983040     4216           200 chrome
oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=/,mems_allowed=0,global_oom,task_memcg=/user.slice/user-504.slice/session-2.scope,task=doxygen,pid=473206,uid=504
Out of memory: Killed process 473206 (doxygen) total-vm:30290680kB, anon-rss:9234320kB, file-rss:4kB, shmem-rss:0kB, UID:504 pgtables:59264kB oom_score_adj:0
oom_reaper: reaped process 473206 (doxygen), now anon-rss:0kB, file-rss:0kB, shmem-rss:0kB
    """

    example_rhel7 = """\
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
Node 0 DMA free:15872kB min:40kB low:48kB high:60kB active_anon:0kB inactive_anon:0kB active_file:0kB inactive_file:0kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:15992kB managed:15908kB mlocked:0kB dirty:0kB writeback:0kB mapped:0kB shmem:0kB slab_reclaimable:0kB slab_unreclaimable:0kB kernel_stack:0kB pagetables:0kB unstable:0kB bounce:0kB free_pcp:0kB local_pcp:0kB free_cma:0kB writeback_tmp:0kB pages_scanned:0 all_unreclaimable? yes
lowmem_reserve[]: 0 2780 15835 15835
Node 0 DMA32 free:59728kB min:7832kB low:9788kB high:11748kB active_anon:2154380kB inactive_anon:604748kB active_file:500kB inactive_file:112kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:3094644kB managed:2848912kB mlocked:0kB dirty:0kB writeback:0kB mapped:4016kB shmem:5140kB slab_reclaimable:6448kB slab_unreclaimable:2796kB kernel_stack:1040kB pagetables:6876kB unstable:0kB bounce:0kB free_pcp:3788kB local_pcp:228kB free_cma:0kB writeback_tmp:0kB pages_scanned:28 all_unreclaimable? no
lowmem_reserve[]: 0 0 13055 13055
Node 0 Normal free:36692kB min:36784kB low:45980kB high:55176kB active_anon:12301636kB inactive_anon:793132kB active_file:604kB inactive_file:176kB unevictable:0kB isolated(anon):0kB isolated(file):128kB present:13631488kB managed:13368348kB mlocked:0kB dirty:0kB writeback:0kB mapped:4108kB shmem:207940kB slab_reclaimable:47900kB slab_unreclaimable:28884kB kernel_stack:6624kB pagetables:43340kB unstable:0kB bounce:0kB free_pcp:4204kB local_pcp:640kB free_cma:0kB writeback_tmp:0kB pages_scanned:128 all_unreclaimable? no
lowmem_reserve[]: 0 0 0 0
Node 1 Normal free:49436kB min:45444kB low:56804kB high:68164kB active_anon:14967844kB inactive_anon:1244560kB active_file:1552kB inactive_file:1992kB unevictable:0kB isolated(anon):0kB isolated(file):0kB present:16777212kB managed:16514220kB mlocked:0kB dirty:16kB writeback:0kB mapped:10760kB shmem:138504kB slab_reclaimable:55300kB slab_unreclaimable:23152kB kernel_stack:6176kB pagetables:50672kB unstable:0kB bounce:0kB free_pcp:3360kB local_pcp:248kB free_cma:0kB writeback_tmp:0kB pages_scanned:125777 all_unreclaimable? yes
lowmem_reserve[]: 0 0 0 0
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
"""

    example_ubuntu2110 = """\
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
"""

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
        self.set_html_defaults()
        self.update_toc()

        element = document.getElementById("version")
        element.textContent = "v{}".format(VERSION)

    def _add_tooltip_size(self, element: Node, item: str, size_in_bytes: int):
        """Add tooltip with human-readable size"""
        if (
            size_in_bytes is not None
            and (
                (item.endswith("_bytes") and size_in_bytes >= 1024)
                or (item.endswith("_kb") and size_in_bytes >= 1024 * 1024)
                or (item.endswith("_pages"))
            )
            and not element.classList.contains("js-dont-add-human-readable-sizes")
        ):
            element.classList.add("js-human-readable-sizes")
            tooltip = document.createElement("span")
            tooltip.className = "js-human-readable-sizes__tooltip"
            tooltip.textContent = self._size_to_human_readable(size_in_bytes)
            element.appendChild(tooltip)
        # An else-branch with removal of the tooltip is not necessary, because
        # they are already removed by during the initialization in set_html_defaults().

    def _calc_size_in_bytes(self, item: str) -> Optional[int]:
        """Return item size in bytes"""
        content = self.oom_result.details.get(item, "")
        assert isinstance(content, int)
        size = None
        if item.endswith("_pages"):
            pages_in_bytes = self.oom_result.details.get("page_size_kb") * 1024
            size = content * pages_in_bytes
        elif item.endswith("_bytes"):
            size = content
        elif item.endswith("_kb"):
            size = content * 1024
        elif item.endswith("_percent"):
            size = None
        return size

    def _is_numeric_item(self, item) -> bool:
        """
        Check if the item is numeric, it's an integer, and it ends with _bytes, _kb, _pages, or _percent.
        """
        content = self.oom_result.details.get(item, "")
        return (
            item.endswith("_bytes")
            or item.endswith("_kb")
            or item.endswith("_pages")
            or item.endswith("_percent")
        ) and isinstance(content, int)

    def _prepare_numeric_value(self, item: str) -> str:
        """Return formatted numeric item value"""
        content = self.oom_result.details.get(item, "")
        assert isinstance(content, int)
        formatted = ""
        if item.endswith("_pages"):
            if content == 1:
                formatted = "{}&nbsp;page".format(content)
            else:
                formatted = "{}&nbsp;pages".format(content)
        elif item.endswith("_bytes"):
            if content == 1:
                formatted = "{}&nbsp;Byte".format(content)
            else:
                formatted = "{}&nbsp;Bytes".format(content)
        elif item.endswith("_kb"):
            if content == 1:
                formatted = "{}&nbsp;kByte".format(content)
            else:
                formatted = "{}&nbsp;kBytes".format(content)
        elif item.endswith("_percent"):
            formatted = "{}&nbsp;%".format(content)
        else:
            internal_error('Unknown item "{}" in _prepare_numeric_value()'.format(item))

        return formatted

    @staticmethod
    def _size_to_human_readable(value: int) -> str:
        """Convert a size in bytes to a human-readable format (e.g., kB or GB)."""
        units = ["Bytes", "kB", "MB", "GB", "TB", "PB"]
        size = float(value)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return "{} {}".format(int(size), units[unit_index])
        else:
            return "{:.1f} {}".format(size, units[unit_index])

    def _set_item(self, item):
        """
        Insert the item content into all HTML elements whose class matches the item name.
        """
        elements = document.getElementsByClassName(item)
        content = self.oom_result.details.get(item, "")
        size_in_bytes = None
        if isinstance(content, str):
            content = content.strip()
        is_numeric = self._is_numeric_item(item)
        if is_numeric:
            content = self._prepare_numeric_value(item)
            size_in_bytes = self._calc_size_in_bytes(item)

        for element in elements:
            row_in_result_table = element.closest("#result_table tr")

            # Hide table rows if the element has no content
            if isinstance(content, str) and content == "<not found>":
                if row_in_result_table:
                    row_in_result_table.classList.add("js-text--display-none")
                    continue

            element.innerHTML = content
            if row_in_result_table:
                row_in_result_table.classList.remove("js-text--display-none")
            if is_numeric:
                self._add_tooltip_size(element, item, size_in_bytes)

        if DEBUG:
            show_element_by_id("notify_box")

    def update_toc(self):
        """
        Update the TOC to show visible h2/h3 headlines.

        Headlines without an id attribute are not shown.
        """
        new_toc = ""
        assigned_level = None

        toc_content = document.querySelectorAll("nav > ul")[0]

        for element in document.querySelectorAll("h2, h3"):
            if not (is_visible(element) and element.id):
                continue
            current_level = int(element.tagName[1])

            # set assigned level to level of first item
            if assigned_level is None:
                assigned_level = current_level

            # close child list if a higher level follows
            elif current_level < assigned_level:
                new_toc += "</ul>"

            # open child list if a lower level follows
            elif current_level > assigned_level:
                new_toc += "<ul>"

            assigned_level = current_level

            new_toc += '<li><a href="#{}">{}</a></li>'.format(
                element.id, element.textContent
            )

        toc_content.innerHTML = new_toc

    def _show_pstable(self):
        """
        Create and show the process table with additional information
        """
        # update table heading
        for i, element in enumerate(
            document.querySelectorAll("#pstable_header > tr > td")
        ):
            element.classList.remove(
                "pstable__row-pages--width",
                "pstable__row-numeric--width",
                "pstable__row-oom-score-adj--width",
            )

            key = self.oom_result.kconfig.pstable_items[i]
            if key in ["notes", "names"]:
                klass = "pstable__row-notes--width"
            elif key == "oom_score_adj":
                klass = "pstable__row-oom-score-adj--width"
            elif (
                key.endswith("_bytes") or key.endswith("_kb") or key.endswith("_pages")
            ):
                klass = "pstable__row-pages--width"
            else:
                klass = "pstable__row-numeric--width"
            element.firstChild.textContent = self.oom_result.kconfig.pstable_html[i]
            element.classList.add(klass)

        # create new table
        new_table = ""
        table_content = document.getElementById("pstable_content")
        for pid in self.oom_result.details["_pstable_index"]:
            if pid == self.oom_result.details["trigger_proc_pid"]:
                css_class = 'class="js-pstable__triggerproc--bgcolor"'
            elif pid == self.oom_result.details["killed_proc_pid"]:
                css_class = 'class="js-pstable__killedproc--bgcolor"'
            else:
                css_class = ""
            process = self.oom_result.details["_pstable"][pid]
            fmt_list = [
                process[i]
                for i in self.oom_result.kconfig.pstable_items
                if not i == "pid"
            ]
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
            """.format(
                *fmt_list
            )
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
                if self.sort_order == "descending":
                    element.innerHTML = self.svg_array_down
                else:
                    element.innerHTML = self.svg_array_up
            else:
                element.innerHTML = self.svg_array_updown

    def set_html_defaults(self):
        """Reset the HTML document but don't clean elements"""

        # clear JS console
        console.js_clear()

        # show all hidden elements in the result table
        show_elements_by_selector("table .js-text--display-none")

        # hide all elements marked to be hidden by default
        hide_elements_by_selector(".js-text--default-hide")

        # show all elements marked to be shown by default
        show_elements_by_selector(".js-text--default-show")

        # remove tooltips human-readable sizes
        for element in document.querySelectorAll(".js-human-readable-sizes__tooltip"):
            element.remove()

        # clear notification box
        element = document.getElementById("notify_box")
        while element.firstChild:
            element.removeChild(element.firstChild)

        # remove svg charts
        for element_id in ("svg_swap", "svg_ram"):
            element = document.getElementById(element_id)
            while element.firstChild:
                element.removeChild(element.firstChild)

        self._clear_pstable()

    def _clear_pstable(self):
        """Clear process table"""
        element = document.getElementById("pstable_content")
        while element.firstChild:
            element.removeChild(element.firstChild)

        # reset sort triangles
        self.sorted_column_number = None
        self.sort_order = None
        self.pstable_set_sort_triangle()

        # reset table heading
        for i, element in enumerate(
            document.querySelectorAll("#pstable_header > tr > td")
        ):
            element.classList.remove(
                "pstable__row-pages--width",
                "pstable__row-numeric--width",
                "pstable__row-oom-score-adj--width",
            )
            element.firstChild.textContent = "col {}".format(i + 1)

    def copy_example_to_form(self):
        """Copy example to input area"""
        selection = document.getElementById("examples").value
        if selection == "empty":
            self.reset_form()
        elif selection == "RHEL7":
            document.getElementById("textarea_oom").value = self.example_rhel7
        elif selection == "Ubuntu_2110":
            document.getElementById("textarea_oom").value = self.example_ubuntu2110
        elif selection == "ArchLinux":
            document.getElementById("textarea_oom").value = self.example_archlinux_6_1_1

    def reset_form(self):
        """Reset HTML input form"""
        document.getElementById("textarea_oom").value = ""
        document.getElementById("examples").value = "empty"
        self.set_html_defaults()
        self.update_toc()

    def toggle_oom(self, show=False):
        """Toggle the visibility of the full OOM message"""
        oom_element = document.getElementById("oom")
        row_with_oom = oom_element.parentNode.parentNode
        toggle_msg = document.getElementById("oom_toogle_msg")

        if show or row_with_oom.classList.contains("js-text--display-none"):
            row_with_oom.classList.remove("js-text--display-none")
            toggle_msg.text = "(click to hide)"
        else:
            row_with_oom.classList.add("js-text--display-none")
            toggle_msg.text = "(click to show)"

    def analyse_and_show(self):
        """Analyse the OOM text inserted into the form and show the results"""
        # set defaults and clear notifications / JS console
        self.set_html_defaults()

        self.oom = OOMEntity(self.load_from_form())
        analyser = OOMAnalyser(self.oom)
        success = analyser.analyse()
        if success:
            self.oom_result = analyser.oom_result
            self.show_oom_details()
            self.update_toc()

        # scroll to the top to show the results
        window.scrollTo({"top": 0, "behavior": "smooth"})

    def load_from_form(self):
        """
        Return the OOM text from the textarea element

        @rtype: str
        """
        element = document.getElementById("textarea_oom")
        oom_text = element.value
        return oom_text

    def show_oom_details(self):
        """
        Show all extracted details as well as additionally generated information
        """
        self._show_all_items()
        self._show_ram_usage()
        self._show_swap_usage()
        self._show_trigger_process()
        self._show_alloc_failure()
        self._show_kernel_upgrade()
        self._show_memory_fragmentation()
        self._show_page_size()

        # generate process table
        self._show_pstable()
        self.pstable_set_sort_triangle()

        element = document.getElementById("oom")
        element.textContent = self.oom_result.oom_text
        self.toggle_oom(show=False)

    def _show_alloc_failure(self):
        """Show details why the memory allocation failed"""

        if (
            self.oom_result.mem_alloc_failure
            == OOMMemoryAllocFailureType.failed_below_low_watermark
        ):
            show_elements_by_selector(".js-alloc-failure--show")
            show_elements_by_selector(".js-alloc-failure-below-low-watermark--show")
        elif (
            self.oom_result.mem_alloc_failure
            == OOMMemoryAllocFailureType.failed_no_free_chunks
        ):
            show_elements_by_selector(".js-alloc-failure--show")
            show_elements_by_selector(".js-alloc-failure-no-free-chunks--show")
        elif (
            self.oom_result.mem_alloc_failure
            == OOMMemoryAllocFailureType.failed_unknown_reason
        ):
            show_elements_by_selector(".js-alloc-failure--show")
            show_elements_by_selector(".js-alloc-failure-unknown-reason--show")
        else:
            debug(
                "Memory allocation failed: {}".format(self.oom_result.mem_alloc_failure)
            )

    def _show_kernel_upgrade(self):
        """Show the hint to upgrade from 32-bit to a 64-bit kernel"""
        if "32-bit" in self.oom_result.details["platform"]:
            show_elements_by_selector(".js-kernel-upgrade64--show")
        else:
            hide_elements_by_selector(".js-kernel-upgrade64--show")

    def _show_memory_fragmentation(self):
        """Show details about memory fragmentation"""
        if self.oom_result.mem_fragmented is None:
            return
        show_elements_by_selector(".js-memory-fragmentation--show")
        if self.oom_result.mem_fragmented:
            show_elements_by_selector(".js-memory-heavy-fragmentation--show")
        else:
            show_elements_by_selector(".js-memory-no-heavy-fragmentation--show")
        if self.oom_result.details["trigger_proc_numa_node"] is None:
            hide_elements_by_selector(".js-memory-shortage-node--hide")

    def _show_page_size(self):
        """Show page size"""
        if self.oom_result.details.get("_page_size_guessed", True):
            show_elements_by_selector(".js-pagesize-guessed--show")
        else:
            show_elements_by_selector(".js-pagesize-determined--show")

    def _show_ram_usage(self):
        """Generate RAM usage diagram"""
        ram_title_attr = (
            ("Active mem", "active_anon_pages"),
            ("Inactive mem", "inactive_anon_pages"),
            ("Isolated mem", "isolated_anon_pages"),
            ("Active PC", "active_file_pages"),
            ("Inactive PC", "inactive_file_pages"),
            ("Isolated PC", "isolated_file_pages"),
            ("Unevictable", "unevictable_pages"),
            ("Dirty", "dirty_pages"),
            ("Writeback", "writeback_pages"),
            ("Unstable", "unstable_pages"),
            ("Slab reclaimable", "slab_reclaimable_pages"),
            ("Slab unreclaimable", "slab_unreclaimable_pages"),
            ("Mapped", "mapped_pages"),
            ("Shared", "shmem_pages"),
            ("Pagetable", "pagetables_pages"),
            ("Bounce", "bounce_pages"),
            ("Free", "free_pages"),
            ("Free PCP", "free_pcp_pages"),
            ("Free CMA", "free_cma_pages"),
        )
        chart_elements = [
            (title, self.oom_result.details[value])
            for title, value in ram_title_attr
            if value in self.oom_result.details
        ]
        svg = SVGChart()
        svg_ram = svg.generate_chart("RAM Summary", *chart_elements)
        elem_svg_ram = document.getElementById("svg_ram")
        elem_svg_ram.appendChild(svg_ram)

    def _show_swap_usage(self):
        """Show/hide swap space and generate a usage diagram"""
        if self.oom_result.swap_active:
            # generate swap usage diagram
            svg = SVGChart()
            svg_swap = svg.generate_chart(
                "Swap Summary",
                ("Swap Used", self.oom_result.details["swap_used_kb"]),
                ("Swap Free", self.oom_result.details["swap_free_kb"]),
                ("Swap Cached", self.oom_result.details["swap_cache_kb"]),
            )
            elem_svg_swap = document.getElementById("svg_swap")
            elem_svg_swap.appendChild(svg_swap)
            show_elements_by_selector(".js-swap-active--show")
            hide_elements_by_selector(".js-swap-inactive--show")
        else:
            hide_elements_by_selector(".js-swap-active--show")
            show_elements_by_selector(".js-swap-inactive--show")

    def _show_trigger_process(self):
        """Show trigger process details w/ or w/o UID"""
        if "trigger_proc_uid" in self.oom_result.details:
            show_elements_by_selector(".js-trigger-proc-pid-uid--show")
            hide_elements_by_selector(".js-trigger-proc-pid-only--show")
        else:
            hide_elements_by_selector(".js-trigger-proc-pid-uid--show")
            show_elements_by_selector(".js-trigger-proc-pid-only--show")

    def _show_all_items(self):
        """Switch to the output view and show most items"""
        hide_element_by_id("input")
        show_element_by_id("analysis")

        if self.oom_result.oom_type == OOMType.KERNEL_AUTOMATIC:
            show_elements_by_selector(".js-oom-kernel-automatic--show")
        elif self.oom_result.oom_type == OOMType.KERNEL_MANUAL:
            show_elements_by_selector(".js-oom-kernel-manual--show")
        elif self.oom_result.oom_type == OOMType.CGROUP_AUTOMATIC:
            show_elements_by_selector(".js-oom-cgroup-automatic--show")

        for item in self.oom_result.details.keys():
            if item.startswith("_"):  # ignore internal items
                continue
            self._set_item(item)

        # Show "OOM Score" only if it's available
        if "killed_proc_score" in self.oom_result.details:
            show_elements_by_selector(".js-killed-proc-score--show")

    def sort_pstable(self, column_number):
        """
        Sort process table by values

        @param int column_number: Number of columns to sort
        """
        # TODO Check operator overloading
        #      Operator overloading (Pragma opov) does not work in this context.
        #      self.oom_result.kconfig.pstable_items + ['notes'] will compile to a string
        #      "pid,uid,tgid,total_vm_pages,rss_pages,nr_ptes_pages,swapents_pages,oom_score_adjNotes" and not to an
        #      array
        ps_table_and_notes = self.oom_result.kconfig.pstable_items[:]
        ps_table_and_notes.append("notes")
        column_name = ps_table_and_notes[column_number]
        if column_name not in ps_table_and_notes:
            internal_error(
                'Can not sort process table with an unknown column name "{}"'.format(
                    column_name
                )
            )
            return

        # reset sort order if the column has changes
        if column_number != self.sorted_column_number:
            self.sort_order = None
        self.sorted_column_number = column_number

        if not self.sort_order or self.sort_order == "descending":
            self.sort_order = "ascending"
            self.sort_psindex_by_column(column_name)
        else:
            self.sort_order = "descending"
            self.sort_psindex_by_column(column_name, True)

        self._show_pstable()
        self.pstable_set_sort_triangle()

    def sort_psindex_by_column(self, column_name, reverse=False):
        """
        Sort the pid list '_pstable_index' based on the values in the process dict '_pstable'.

        Is uses bubble sort with all disadvantages but just a few lines of code
        """
        ps = self.oom_result.details["_pstable"]
        ps_index = self.oom_result.details["_pstable_index"]

        def getvalue(column, pos):
            if column == "pid":
                value = ps_index[pos]
            else:
                value = ps[ps_index[pos]][column]
            # JS sorts alphanumeric by default, convert values explicit to integers to sort numerically
            if (
                column not in self.oom_result.kconfig.pstable_non_ints
                and value is not js_undefined
            ):
                value = int(value)
            return value

        # We set swapped to True so the loop looks runs at least once
        swapped = True
        while swapped:
            swapped = False
            for i in range(len(ps_index) - 1):
                v1 = getvalue(column_name, i)
                v2 = getvalue(column_name, i + 1)

                if (not reverse and v1 > v2) or (reverse and v1 < v2):
                    # Swap the elements
                    ps_index[i], ps_index[i + 1] = ps_index[i + 1], ps_index[i]

                    # Set the flag to True so we'll loop again
                    swapped = True


OOMDisplayInstance = OOMDisplay()
