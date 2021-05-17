export LC_ALL=en_US.UTF-8

PWD=$(shell pwd)

TARGET=www
SRATARGET=$(TARGET)
OSGTARGET=$(TARGET)
DOCTARGET=$(TARGET)

PYTHON := PYTHONPATH=$(PWD) python3
SRATIC = ${PYTHON} -m sratic
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: bib www

# The Bibilography comes from a github bib repository that is public.
# The first rule indicates that init is automatically cloned, if it
# was not cloned beforehand.
#
# The sync rule is established to explicitly sync the external. This
# is done also in the jenkins rules.
bib:
	$(PYTHON) ./init

sync: PHONY
	$(PYTHON) ./init


SRA_OPTS = -b "." -d ../../$(SRATARGET) -t ../../templates/sra


www: PHONY
	cd src/sra; ${SRATIC} ${SRA_OPTS} -j $(NPROC)

dry: PHONY
	cd src/sra; ${SRATIC} ${SRA_OPTS} --dry -j $(NPROC)

force: sync PHONY
	cd src/sra; ${SRATIC} ${SRA_OPTS} --force

doc: PHONY
	mkdir -p $(DOCTARGET)
	cd src/doc; ${SRATIC} -t ../../templates/doc -d ../../$(DOCTARGET)

clean: PHONY
	rm -rf $(SRATARGET) $(OSGTARGET) $(DOCTARGET) ise.www

# The following targets are used only by automated jenkins builds
deploy-jenkins: sync PHONY
	cd src/sra; ${SRATIC} -t ../../templates/sra  -d /proj/www/lab.sra.uni-hannover.de/ --dump-objects

deploy-jenkins-force: sync PHONY
	cd src/sra; ${SRATIC} -t ../../templates/sra  -d /proj/www/lab.sra.uni-hannover.de/ --force --dump-objects

sra.deploy: sync PHONY
	cd src/sra; ${SRATIC} -t ../../templates/sra  -d /proj/www/from-gitlab --dump-objects

serve:
	python -m http.server -d $(TARGET)

# TUHH: Operating System Group
osg: PHONY
	mkdir -p $(OSGTARGET)
	cd src/osg; ${SRATIC} -t ../../templates/osg  -d ../../$(OSGTARGET)

osg.www: sync PHONY
	mkdir -p $(OSGTARGET)
	cd src/osg; ${SRATIC} -t ../../templates/osg  -d ../../$(OSGTARGET)

# Build the docker Image
osg.docker:
	docker build -t collaborating.tuhh.de:5005/e-exk4/internal/www docker
	docker push     collaborating.tuhh.de:5005/e-exk4/internal/www

.PHONY: PHONY
