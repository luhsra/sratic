UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif	

lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static -j $(NPROC)

force: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static --force $(NPROC)

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
