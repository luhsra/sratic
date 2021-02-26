PYTHON := PYTHONPATH=$(PWD) python3
SRATIC = ${PYTHON} -m sratic
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


SRA_OPTS = -b "." -d ../www -t ../templates


www: PHONY
	cd src; ${SRATIC} ${SRA_OPTS} -j $(NPROC)

dry: PHONY
	cd src; ${SRATIC} ${SRA_OPTS} --dry -j $(NPROC)

force: sync PHONY
	cd src; ${SRATIC} ${SRA_OPTS} --force

doc: PHONY
	mkdir -p doc.www
	cd doc.src; ${SRATIC} -t ../doc.templates -d ../doc.www

clean: PHONY
	rm -rf www

# The following targets are used only by automated jenkins builds
deploy-jenkins: sync PHONY
	cd src; ${SRATIC} -t ../templates  -d /proj/www/lab.sra.uni-hannover.de/ --dump-objects

deploy-jenkins-force: sync PHONY
	cd src; ${SRATIC} -t ../templates  -d /proj/www/lab.sra.uni-hannover.de/ --force --dump-objects


osg.www: PHONY
	mkdir -p osg.www
	cd osg.src; ${SRATIC} -t ../osg.templates  -d ../osg.www




.PHONY: PHONY
