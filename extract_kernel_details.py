#!/usr/bin/env python3

# -*- coding: UTF-8 -*-
#
# Extract GFP flags (get free pages) from the kernel include files
# include/linux/gfp.h or gfp_types.h for use in OOMAnalyser.py
#
# Copyright (c) 2022-2025 Carsten Grohmann
# License: MIT (see LICENSE.txt)
# THIS PROGRAM COMES WITH NO WARRANTY

import argparse
import json
import logging
import os.path
import re
import sys

from collections import OrderedDict
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Union

import git

# Examples:
#   #define __GFP_DMA ((__force gfp_t)___GFP_DMA)
#   #define __GFP_KSWAPD_RECLAIM  ((__force gfp_t)___GFP_KSWAPD_RECLAIM) /* kswapd can wake */
#   #define GFP_ATOMIC    (__GFP_HIGH|__GFP_ATOMIC|__GFP_KSWAPD_RECLAIM)
#   #define GFP_HIGHUSER  (GFP_USER | __GFP_HIGHMEM)
#   #define GFP_TRANSHUGE_LIGHT ((GFP_HIGHUSER_MOVABLE | __GFP_COMP | __GFP_NOMEMALLOC | __GFP_NOWARN) & ~__GFP_RECLAIM)
REC_COMPOUND = re.compile(
    r"^#define (?P<constant>_{0,3}GFP_[_A-Z\d]+)"
    r"\s+"  # spaces
    r"\("  # opening "("
    r"(?:\(__force gfp_t\))?"  # optional: (__force gfp_t)
    r"\(*(?P<value>.+)"
    r"\)"  # closing ")")
)
"""Regex to extract compound flags"""

REC_EXCLUDE = re.compile(
    r"(__LINUX_GFP_H|GFP_ZONE_TABLE|ZONES_SHIFT|GFP_ZONE_BAD|BITS_SHIFT|THISNODE|MASK)"
)
"""Regex to exclude lines that look like GFP flags but are not"""

# Examples:
#   #define ___GFP_DMA	  0x01u
#   #define ___GFP_DMA32  0x04u
REC_NUMERIC = re.compile(
    r"^#define (?P<constant>_{0,3}GFP[_A-Z\d]+)\s+(?P<value>0x\d+)u"
)
"""Regex extract to GFP constants"""

REC_PAGE_ALLOC_COSTLY_ORDER = re.compile(
    r"^#define[ \t]+PAGE_ALLOC_COSTLY_ORDER[ \t]+(?P<order>\d+)", re.MULTILINE
)
"""Regex to extract PAGE_ALLOC_COSTLY_ORDER"""

REC_TAG_MAJOR_MINOR_VERSION = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)(\.\d+)?$")
"""Regex to extract major and minor version number from kernel tag"""


def extract_gfp_lines(lines: Iterable[str]) -> List[str]:
    """Extract all lines with GFP flag definitions"""
    content = []
    ifdef_lines = []
    ifdef_type = "notset"
    line_with_backslash = ""

    for i, line in enumerate(lines):
        if REC_EXCLUDE.search(line):
            continue
        line = line.rstrip()
        line = line.replace(r"\t", " ")
        line = line.replace(r"~\s+", " ~")
        if line_with_backslash:
            if line.endswith("\\"):
                line_with_backslash += line[:-1]  # remove tailing /
            else:
                content.append(f"{line_with_backslash}{line}")
                line_with_backslash = ""
            continue
        if line.startswith("#if"):
            ifdef_type = "single_if"
            ifdef_lines.append(f"{i} {line}")
        elif line.startswith("#else"):
            ifdef_type = "if_else"
            ifdef_lines.append(f"{i} {line}")
        elif line.startswith("#endif"):
            ifdef_lines.append(f"{i} {line}")
            # ignore empty #if, #else and #endif
            if (
                (ifdef_type == "notset" and len(ifdef_lines) == 1)
                or (ifdef_type == "single_if" and len(ifdef_lines) == 2)
                or (ifdef_type == "if_else" and len(ifdef_lines) == 3)
            ):
                ifdef_lines.clear()
            else:
                content.extend(ifdef_lines)
            ifdef_type = "notset"
        elif line.startswith("#define") and "GFP" in line:
            if line.endswith("\\"):
                line_with_backslash = line[:-1]  # remove tailing /
            else:
                content.append(line)

    return content


def extract_numeric_constants(inlist: List[str]) -> Dict[str, str]:
    """Process all lines and extract flags with numeric values"""
    d = {}
    for i in inlist:
        match = REC_NUMERIC.search(i)
        if match:
            name = match.group("constant")
            value = match.group("value")
            if name in d and d[name] != value:
                logging.error(
                    "Duplicate entry found for %s current: %s, new %s",
                    name,
                    d[name],
                    value,
                )
            else:
                d[name] = value
    return d


def convert_numerics(flags):
    """Convert numeric flags to decimal"""
    for k in flags:
        try:
            flags[k] = int(flags[k], 16)
        except ValueError:
            logging.error('Non-hexadecimal value "%s" for flag %s', flags[k], k)
    return flags


def sort_by_value(d: Dict[str, str]) -> Dict[str, str]:
    """Sort dictionary by value"""
    sorted_dict = dict(sorted(d.items(), key=lambda item: item[1]))
    return sorted_dict


def sort_by_key(d: Dict[str, str]) -> Dict[str, str]:
    """Sort dictionary by keys"""
    sorted_dict = {k: d[k] for k in sorted(d)}
    return sorted_dict


def extract_compound_constants(inlist: List[str]) -> Dict[str, str]:
    """Process all lines and extract flags with compound"""
    d = {}
    for i in inlist:
        match = REC_COMPOUND.search(i)
        if match:
            name = match.group("constant")
            value = re.sub(r"[\s)]+", "", match.group("value"))
            if name in d and d[name] != value:
                logging.error(
                    "Duplicate entry found for %s current: %s, new %s",
                    name,
                    d[name],
                    value,
                )
            else:
                d[name] = value
    return d


def check_existence(compound, numeric):
    """Check that all flags exists"""
    for k in compound:
        flags = re.split(r"[\s|&]", compound[k])
        for flag in flags:
            if flag.startswith("~"):
                flag = flag[1:]
            if not ((flag in compound) or (flag in numeric)):
                logging.error("Undefined flag %s in %s->%s", flag, k, flags)


def filter_gfp_plain_bitmasks(d: Dict[str, str]) -> Dict[str, str]:
    """Return plain integer GFP bitmasks"""
    res = {key: value for key, value in d.items() if key.startswith("___G")}
    return res


def filter_gfp_modifier(d: Dict[str, str]) -> Dict[str, str]:
    """Return modifier, mobility and placement hints"""
    res = {key: value for key, value in d.items() if key.startswith("__G")}
    return res


def filter_gfp_useful_combinations(d: Dict[str, str]) -> Dict[str, str]:
    """Return useful GFP flag combinations"""
    res = {key: value for key, value in d.items() if key.startswith("G")}
    return res


def format_gfp_flags(d: Dict[str, Union[str, int]]) -> Dict[str, str]:
    """Return flags with formatted values of given flags"""
    res = {}
    for key, value in d.items():
        if isinstance(value, int):
            value = "0x%02x" % value
        else:
            value = value.replace("|", " | ")
            value = value.replace("&~", " & ~")
            value = f'"{value}"'
        res[key] = value
    return res


def format_block_gfp_flags(desc: str, flags: Dict[str, str]) -> str:
    """Generate a block with the given flags"""
    res = f"""\
        #
        #
        # {desc}:
"""
    for n in flags:
        res += f'        "{n}": {{"value": {flags[n]}}},\n'
    wo_tailing_newline = res.rstrip()
    return wo_tailing_newline


def extract_gfp_flags(gfp_filename: str) -> Dict[str, Dict[str, Union[str, int]]]:
    """Extract GFP flags from given file"""
    with open(gfp_filename) as f:
        flags_unfiltered = extract_gfp_lines(f)

    numeric = extract_numeric_constants(flags_unfiltered)
    numeric = convert_numerics(numeric)

    compound = extract_compound_constants(flags_unfiltered)
    check_existence(compound, numeric)

    flags_merged = {**numeric, **compound}
    useful = filter_gfp_useful_combinations(flags_merged)
    useful = sort_by_key(useful)
    useful = format_gfp_flags(useful)

    modifier = filter_gfp_modifier(flags_merged)
    modifier = sort_by_key(modifier)
    modifier = format_gfp_flags(modifier)

    plain = filter_gfp_plain_bitmasks(flags_merged)
    plain = sort_by_value(plain)
    plain = format_gfp_flags(plain)

    return {"useful": useful, "modifier": modifier, "plain": plain}


def search_gfp_file(repo_dir: str) -> Optional[str]:
    """Return of the file with the CFP definitions"""
    for gfp_filename in [
        # introduced in kernel 6.0 with commit cb5a065b4ea9c062a18143c8a14e831179687f54:
        # mm: Split <linux/gfp_types.h> out of <linux/gfp.h>
        os.path.join(repo_dir, "include/linux/gfp_types.h"),
        os.path.join(repo_dir, "include/linux/gfp.h"),
    ]:
        full = os.path.join(gfp_filename)
        if os.path.exists(full):
            return full
    return None


def extract_page_alloc_costly_order(repo_dir: str) -> Optional[int]:
    """Extract PAGE_ALLOC_COSTLY_ORDER from mmzone.h"""
    mmzone_h = os.path.join(repo_dir, "include/linux/mmzone.h")
    with open(mmzone_h) as f:
        content = f.read()
        match = REC_PAGE_ALLOC_COSTLY_ORDER.search(content)
        if match:
            return int(match.group("order"))
    logging.error("Missing PAGE_ALLOC_COSTLY_ORDER definition in %s", mmzone_h)
    return None


def query_all_tags(
    minimum_major: int = 1, minimum_minor: int = 1
) -> List[git.TagReference]:
    """
    Return a sorted list of kernel tags with the given minimum major
    and minor version number.
    """
    sorted_tags = []

    for tag in repo.tags:
        match = REC_TAG_MAJOR_MINOR_VERSION.match(tag.name)
        if not match:
            logging.debug(
                "Could not extract major and minor version number from tag %s", tag.name
            )
            continue
        version_major = int(match.group("major"))
        version_minor = int(match.group("minor"))
        assert version_minor < 100
        if version_major < minimum_major or (
            version_major == minimum_major and version_minor < minimum_minor
        ):
            continue
        sorted_tags.append((version_major * 100 + version_minor, tag))

    sorted_tags = [x[1] for x in sorted(sorted_tags, key=lambda item: item[0])]

    return sorted_tags


def prepare_repo(tag: git.TagReference) -> None:
    """Checkout repo with the requested tag"""
    logging.info("Checkout working copy for tag %s", tag.name)
    repo.git.checkout(tag.name, force=True)


def cleanup_repo() -> None:
    """Discard any changes in repo and switch back to master branch"""
    logging.info("Discard any changes in repo and switch back to master branch")
    repo.heads.master.checkout(force=True)


def write_gfp_oom_template(
    cfg: SimpleNamespace,
    tag: git.TagReference,
    changes: SimpleNamespace,
    gfp_filename: str,
):
    """Write prepared GFP flags to a template file"""
    output_file = os.path.join(cfg.output_dir, f"gfp_{tag.name}")
    logging.info("Write output file for tag %s: %s", tag.name, output_file)

    match = REC_TAG_MAJOR_MINOR_VERSION.match(tag.name)
    major = match.group("major")
    minor = match.group("minor")

    of = open(output_file, "wt")

    # write header
    of.write(f"class KernelConfig_{major}_{minor}(KernelConfig_XX_YY):\n")
    of.write("    # Supported changes:\n")
    if changes.gfp_flags:
        of.write("    #  * update GFP flags\n")
    of.write("\n")
    of.write(f'    name = "Configuration for Linux kernel {major}.{minor} or later"\n')
    of.write(f'    release = ({major}, {minor}, "")\n')
    of.write("\n")
    if changes.gfp_flags:
        of.write(
            f"""\
    # NOTE: These flags are automatically extracted from the {gfp_filename} file.
    #       Please do not change them manually!
    GFP_FLAGS = {{
{format_block_gfp_flags("Useful GFP flag combinations", changes.gfp_flags["useful"])}
{format_block_gfp_flags("Modifier, mobility and placement hints", changes.gfp_flags["modifier"])}
{format_block_gfp_flags("Plain integer GFP bitmasks (for internal use only)", changes.gfp_flags["plain"])}
    }}
"""
        )
    if changes.page_order:
        of.write(
            f"""\

    # NOTE: This value is automatically extracted from include/linux/mmzone.h.
    #       Please do not change it manually!
    PAGE_ALLOC_COSTLY_ORDER = {changes.page_order}
"""
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cfg = SimpleNamespace()

    parser = argparse.ArgumentParser(
        description="Extract GFP flags (get free pages) from the kernel "
        "include files include/linux/gfp.h or gfp_types.h for use in "
        "OOMAnalyser.py",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "repo_dir",
        help="Linux kernel git repository",
    )
    parser.add_argument(
        "output_dir",
        default="./out",
        nargs="?",
        help="Output directory",
    )
    parser.add_argument(
        "--major",
        default=5,
        dest="minimum_major_version",
        metavar="minimum major version number",
        nargs="?",
        type=int,
        help="Major version number to start",
    )
    parser.add_argument(
        "--minor",
        default=18,
        dest="minimum_minor_version",
        metavar="minimum minor version number",
        nargs="?",
        type=int,
        help="Minor version number to start",
    )
    parser.add_argument(
        "--paco",
        default=3,
        dest="page_order",
        metavar="PAGE_ALLOC_COSTLY_ORDER",
        nargs="?",
        type=int,
        help="Record changes in PAGE_ALLOC_COSTLY_ORDER if they differ from the default",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="extract_kernel_details.py version 0.2 - Copyright (c) 2022-2025 Carsten Grohmann",
    )
    parser.parse_args(namespace=cfg)

    if not os.path.exists(cfg.output_dir):
        logging.error("Output directory %s does not exists", cfg.output_dir)
        sys.exit(1)
    elif os.path.exists(cfg.output_dir) and not os.path.isdir(cfg.output_dir):
        logging.error("Output directory %s exists, but is not a directory")
        sys.exit(1)

    if not os.path.exists(cfg.repo_dir):
        logging.error("Repository %s does not exists", cfg.repo_dir)
        sys.exit(1)

    repo = git.Repo(cfg.repo_dir)
    if repo.bare:
        logging.error("Repository in %s is a bare repository - abort", cfg.repo_dir)
        cleanup_repo()
        sys.exit(1)

    all_tags = query_all_tags(cfg.minimum_major_version, cfg.minimum_minor_version)
    if not all_tags:
        logging.error("No tags found for repository in %s", cfg.repo_dir)
        cleanup_repo()
        sys.exit(1)

    logging.info("Start processing %d tags ...", len(all_tags))

    details = OrderedDict()
    last_modified_tag = SimpleNamespace(
        gfp_flags=None, page_order=None, gfp_filename=""
    )

    for tag in all_tags:
        logging.info("Process tag %s", tag.name)
        prepare_repo(tag)

        # process GFP flags
        gfp_file = search_gfp_file(cfg.repo_dir)
        if not gfp_file:
            logging.error(
                "Missing GFP header file, neither gfp.h nor gfp_types.h exists. Skip tag %s",
                tag.name,
            )
            continue
        details[tag] = SimpleNamespace(
            gfp_flags=None,
            page_order=None,
            gfp_filename=os.path.basename(gfp_file),
        )
        current_value = extract_gfp_flags(gfp_file)
        current_json = json.dumps(current_value, sort_keys=True)
        logging.info("Check for differences in GFP flags ...")

        if last_modified_tag.gfp_flags is None:  # set current, if never set before
            logging.info("New GFP flags found")
            details[tag].gfp_flags = current_value
            details[tag].gfp_flags_json = current_json
            last_modified_tag.gfp_flags = tag
        else:  # already set - check for updates
            last_json = details[last_modified_tag.gfp_flags].gfp_flags_json
            if last_json == current_json:
                logging.info(
                    "No differences in GFP flags to last tag %s found - ignore it",
                    last_modified_tag.gfp_flags.name,
                )
                details[tag].gfp_flags = None
            else:
                logging.info("New GFP flags found")
                details[tag].gfp_flags = current_value
                details[tag].gfp_flags_json = current_json
                last_modified_tag.gfp_flags = tag

        # Process PAGE_ALLOC_COSTLY_ORDER
        logging.info("Check for differences in PAGE_ALLOC_COSTLY_ORDER ...")
        current_value = extract_page_alloc_costly_order(cfg.repo_dir)
        if current_value is None:
            pass  # ignore, as error already logged
        else:
            if last_modified_tag.page_order is None:  # set current, if never set before
                if current_value == cfg.page_order:  # value is equal with default
                    logging.info(
                        "Extracted PAGE_ALLOC_COSTLY_ORDER is equal to the default value - ignore it"
                    )
                    details[tag].page_order = None
                else:  # value differs from default
                    logging.info("New PAGE_ALLOC_COSTLY_ORDER value found")
                    details[tag].page_order = current_value
                    last_modified_tag.page_order = tag

            # already set - check for updates
            else:
                # do not compare with the default value if a value is already set,
                # otherwise this change will be lost when changing back to
                # default (current value) from non-default (last value).
                last_value = details[last_modified_tag.page_order].page_order
                if last_value == current_value:  # no changes to last value
                    logging.info(
                        "No differences for PAGE_ALLOC_COSTLY_ORDER to last tag %s found",
                        last_modified_tag.page_order.name,
                    )
                    details[tag].page_order = None
                else:  # value has changed
                    logging.info("New PAGE_ALLOC_COSTLY_ORDER value found")
                    details[tag].page_order = current_value
                    last_modified_tag.page_order = tag

    logging.info("Write output files...")
    for tag in details:
        if details[tag].gfp_flags or details[tag].page_order:
            write_gfp_oom_template(
                cfg=cfg,
                tag=tag,
                changes=details[tag],
                gfp_filename=details[tag].gfp_filename,
            )

    cleanup_repo()
    logging.info("Script is done")
