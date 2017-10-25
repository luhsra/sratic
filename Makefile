UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: lab.src/data/bib lab.www

# The Bibilography comes from a github bib repository that is public.
# The first rule indicates that init is automatically cloned, if it
# was not cloned beforehand.
#
# The sync rule is established to explicitly sync the external. This
# is done also in the jenkins rules.
lab.src/data/bib:
	./init

sync: PHONY
	./init


lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www -j $(NPROC)

dry: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www --dry -j $(NPROC)

force: sync PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www --force

doc: PHONY
	mkdir -p doc
	cd doc.src; ../bin/gen -d ../doc

clean: PHONY
	rm -rf lab.www

# The following targets are used only by automated jenkins builds
deploy-jenkins: sync PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/

deploy-jenkins-force: sync PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ --force



.PHONY: PHONY
