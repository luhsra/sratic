PYTHON := "python3"
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: src/data/bib www

# The Bibilography comes from a github bib repository that is public.
# The first rule indicates that init is automatically cloned, if it
# was not cloned beforehand.
#
# The sync rule is established to explicitly sync the external. This
# is done also in the jenkins rules.
src/data/bib:
	$(PYTHON) ./init

sync: PHONY
	$(PYTHON) ./init


www: PHONY
	cd src; $(PYTHON) ../bin/gen -b "." -d ../www -j $(NPROC)

dry: PHONY
	cd src; $(PYTHON) ../bin/gen -b "." -d ../www --dry -j $(NPROC)

force: sync PHONY
	cd src; $(PYTHON) ../bin/gen -b "." -d ../www --force

doc: PHONY
	mkdir -p doc
	cd src; $(PYTHON) ../bin/gen -d ../doc

clean: PHONY
	rm -rf www

# The following targets are used only by automated jenkins builds
deploy-jenkins: sync PHONY
	cd src; $(PYTHON) ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ --dump-objects

deploy-jenkins-force: sync PHONY
	cd src; $(PYTHON) ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/ --force --dump-objects



.PHONY: PHONY
