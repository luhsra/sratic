lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static

deploy: PHONY
	cd lab.src; ../bin/gen -d ~/proj.lab/www/lab.sra.uni-hannover.de/ -s ../static

deploy-jenkins: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ -s ../static

doc: PHONY
	mkdir -p doc
	cd doc.src; ../bin/gen -d ../doc -s ../static

clean: PHONY
	rm -rf lab.www

.PHONY: PHONY
