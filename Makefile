UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: lab.www

lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static -j $(NPROC)

dry: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static --dry -j $(NPROC)

force: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -s ../static --force $(NPROC)

doc: PHONY
	mkdir -p doc
	cd doc.src; ../bin/gen -d ../doc -s ../static

clean: PHONY
	rm -rf lab.www

# The following targets are used only by automated jenkins builds
deploy-jenkins: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ -s ../static

deploy-jenkins-force: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ -s ../static --force



.PHONY: PHONY
