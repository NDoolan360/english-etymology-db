import re
from typing import List, Tuple

from mwparserfromhell.nodes.extras import Parameter
from mwparserfromhell.nodes.template import Template
from mwparserfromhell.nodes.text import Text
from mwparserfromhell.nodes.wikilink import Wikilink
from mwparserfromhell.string_mixin import StringMixIn
from mwparserfromhell.wikicode import Wikicode

from elements import Etymology
from templates import parse_template


NAMESPACE = "{http://www.mediawiki.org/xml/export-0.10/}"

def tag(s: str):
    return NAMESPACE + s


def clean_wikicode(wc: Wikicode):
    """
    Performs operations on each etymology section that get rid of extraneous nodes
    and create new templates based on natural-language parsing.
    """
    cleaner = lambda x: ((not isinstance(x, (Text, Wikilink, Template))) or
                         (isinstance(x, Text) and not bool(x.value.strip())))
    for node in wc.filter(recursive=False, matches=cleaner):
        wc.remove(node)

    merge_etyl_templates(wc)
    get_plus_combos(wc)
    get_comma_combos(wc)
    get_from_chains(wc)
    remove_links(wc)


def combine_template_chains(wc: Wikicode, new_template_name: str,
                            template_indices: List[int], text_indices: List[int]) -> None:
    """
    Helper function for combining templates that are linked via free text into
    a structured template hierarchy.
    """
    index_combos = []

    index_combo = []
    combine = False
    for i in template_indices:
        if (i+1 in text_indices) or (i-2 in index_combo and combine):
            index_combo.append(i)

        combine = i+1 in text_indices
        if not combine:
            if len(index_combo) > 1:
                index_combos.append(index_combo)
            index_combo = []

    if len(index_combo) > 1:
        index_combos.append(index_combo)

    combo_nodes = [[wc.nodes[i] for i in chain] for chain in index_combos]

    for combo in combo_nodes:
        params = [Parameter(str(i+1), t, showkey=False) for i, t in enumerate(combo)]
        new_template = Template(new_template_name, params)
        wc.insert_before(combo[0], new_template, recursive=False)
        for node in combo:
            wc.remove(node, recursive=False)


def merge_etyl_templates(wc: Wikicode) -> Wikicode:
    """
    Given a chunk of wikicode, finds instances where the deprecated `etyl` template is immediately followed by
    either a word in free text, a linked word, or a generic `mention`/`link`/`langname-mention` template.
    It replaces this pattern with a new `derived-parsed` template -- meaning the same thing as the `derived` template
    but namespaced to differentiate. For cases where the `mention` language is different from the `etyl` language,
    we use the former. The template is removed if we can't parse it effectively.
    """
    etyl_indices = [i for i, node in enumerate(wc.nodes)
                    if isinstance(node, Template) and node.name == "etyl" and i < len(wc.nodes) - 1]

    nodes_to_remove = []
    for i in etyl_indices:
        make_new_template = False
        etyl = wc.nodes[i]
        related_language: Parameter = etyl.params[0]
        if len(etyl.params) == 1:
            language = "en"
        else:
            language = etyl.params[1]
        node = wc.nodes[i+1]
        val = False
        if isinstance(node, Text):
            val = re.split(",| |", node.value.strip())[0]
            if val:
                make_new_template = True
        elif isinstance(node, Wikilink):
            val = node.text or node.title
            val = re.split(",| |", val.strip())[0]
            if val:
                make_new_template = True
        elif isinstance(node, Template):
            if node.name in ("m", "mention", "m+", "langname-mention", "l", "link"):
                related_language = node.params[0]
                if len(node.params) > 1:
                    val = node.params[1].value
                    make_new_template = True
                    nodes_to_remove.append(node)

        if make_new_template and val:
            params = [Parameter(str(i+1), str(param), showkey=False)
                      for i, param in enumerate([language, related_language, val])]
            new_template = Template("derived-parsed", params)
            wc.replace(etyl, new_template, recursive=False)
        else:
            nodes_to_remove.append(etyl)

    for node in nodes_to_remove:
        wc.remove(node, recursive=False)
    return wc


def get_comma_combos(wc: Wikicode) -> None:
    """
    Given a chunk of wikicode, finds templates separated by the symbol ",", which indicates morphemes
    related to both each other and the original word. It combines them into a single nested template, `related-parsed`.
    """
    template_indices = [i for i, node in enumerate(wc.nodes) if isinstance(node, Template)]
    text_indices = [i for i, node in enumerate(wc.nodes) if isinstance(node, Text) and str(node).strip() == ","]

    combine_template_chains(wc, new_template_name="related-parsed", template_indices=template_indices,
                            text_indices=text_indices)


def get_plus_combos(wc: Wikicode) -> None:
    """
    Given a chunk of wikicode, finds templates separated by the symbol "+", which indicates multiple
    morphemes that affix to make a single etymological relation. It combines these templates into a single nested
    `affix-parsed` template -- meaning the same thing as the `affix` template, but namespaced to differentiate.
    """
    template_indices = [i for i, node in enumerate(wc.nodes) if isinstance(node, Template)]
    text_indices = [i for i, node in enumerate(wc.nodes) if isinstance(node, Text) and str(node).strip() == "+"]

    combine_template_chains(wc, new_template_name="affix-parsed", template_indices=template_indices,
                            text_indices=text_indices)


def get_from_chains(wc: Wikicode) -> None:
    """
    Given a chunk of wikicode, finds templates separated by either "from" or "<", indicating an ordered chain
    of inheritance. It combines these templates into a single nested `from-parsed` template.
    """
    is_inheritance_str = lambda x: str(x).strip() == "<" or re.sub("[^a-z]+", "", str(x).lower()) == "from"

    template_indices = [i for i, node in enumerate(wc.nodes) if isinstance(node, Template)]
    text_indices = [i for i, node in enumerate(wc.nodes)
                    if isinstance(node, Text) and is_inheritance_str(node)]

    combine_template_chains(wc, new_template_name="from-parsed", template_indices=template_indices,
                            text_indices=text_indices)


def remove_links(wc: Wikicode) -> None:
    """
    Given a chunk of wikicode, replaces all inner links with their text representation
    """
    for link in wc.filter_wikilinks():
        wc.replace(link, link.text)
