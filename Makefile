UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: lab.www

lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -j $(NPROC)

dry: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www --dry -j $(NPROC)

force: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www --force $(NPROC)

doc: PHONY
	mkdir -p doc
	cd doc.src; ../bin/gen -d ../doc

clean: PHONY
	rm -rf lab.www

# The following targets are used only by automated jenkins builds
deploy-jenkins: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/

deploy-jenkins-force: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ --force



.PHONY: PHONY
