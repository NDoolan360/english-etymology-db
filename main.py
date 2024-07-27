import bz2
import gzip
import csv
import logging
from multiprocessing import Pool
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, List, Tuple
from lxml import etree
import mwparserfromhell

from elements import Etymology
from templates import unparsed_templates
from wiki import clean_wikicode, parse_template, tag

WIKI_INPUT_PATH = Path.cwd().joinpath("enwiktionary-latest-pages-articles.xml.bz2")
ETYMOLOGY_OUTPUT_PATH = Path.cwd().joinpath("etymology.csv.gz")

def write_all():
    with gzip.open(ETYMOLOGY_OUTPUT_PATH, "wt") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(Etymology.header())
        entries_parsed = 0
        time = datetime.now()
        for etys in Pool().imap_unordered(parse_wikitext, stream_terms()):
            if not etys:
                continue
            rows = [e.to_row() for e in etys]
            entries_parsed += len(rows)
            writer.writerows(rows)
            elapsed = (datetime.now() - time)
            if elapsed.total_seconds() > 1:
                elapsed -= timedelta(microseconds=elapsed.microseconds)
            if entries_parsed % 100 == 0:
                print(f"Entries parsed: {entries_parsed} Time elapsed: {elapsed} "
                      f"Entries per second: {entries_parsed // elapsed.total_seconds()}{' ' * 10}", end="\r", flush=True)


def stream_terms() -> Generator[Tuple[str, str], None, None]:
    with bz2.open(WIKI_INPUT_PATH, "rb") as f_in:
        for event, elem in etree.iterparse(f_in, huge_tree=True):
            if elem.tag == tag("text"):
                page = elem.getparent().getparent()
                ns = page.find(tag("ns"))
                if ns is not None and ns.text == "0":
                    term = elem.getparent().getparent().find(tag("title")).text
                    yield term, elem.text
                page.clear()


def parse_wikitext(unparsed_data: Tuple[str, str]) -> List[Etymology]:
  term, unparsed_wikitext = unparsed_data
  wikitext = mwparserfromhell.parse(unparsed_wikitext)
  parsed_etys = []
  for language_section in wikitext.get_sections(levels=[2]):
      lang = str(language_section.nodes[0].title)
      etymologies = language_section.get_sections(matches="Etymology", flat=True)

      # TODO get definition

      # definitions = language_section.get_sections(matches="Definition", flat=True)
      for e in etymologies:
          clean_wikicode(e)
          for n in e.ifilter_templates(recursive=False):
              name = str(n.name)
              parsed = parse_template(name, term, lang, n)
              parsed_etys.extend([e for e in parsed if e.is_valid()])
  return [e for e in parsed_etys if e.is_valid()]


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    write_all()
    print(unparsed_templates)
