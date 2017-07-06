lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static -j $(shell nproc)

force: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static --force $(shell nproc)

deploy: PHONY
	cd lab.src; ../bin/gen -d ~/proj.lab/www/lab.sra.uni-hannover.de/ -s ../static

deploy-jenkins: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ -s ../static

deploy-jenkins-force: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ -s ../static --force


doc: PHONY
	mkdir -p doc
	cd doc.src; ../bin/gen -d ../doc -s ../static

clean: PHONY
	rm -rf lab.www

.PHONY: PHONY
