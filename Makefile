WIKI_FILENAME=enwiktionary-latest-pages-articles.xml.bz2
$(WIKI_FILENAME):
	curl -sLo $@ https://dumps.wikimedia.your.org/enwiktionary/latest/$(WIKI_FILENAME)

ZIPPED_CSV=etymology.csv.gz
$(ZIPPED_CSV): $(WIKI_FILENAME)
	python3 -m venv .venv && source .venv/bin/activate && python3 main.py

UNZIPPED_CSV=etymology.csv
$(UNZIPPED_CSV): $(ZIPPED_CSV)
	funzip $< > $@

.PHONY clean
clean:
	rm -f $(UNZIPPED_CSV)
	rm -i $(ZIPPED_CSV) $(ZIPPED_XML)
