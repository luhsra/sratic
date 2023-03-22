export LC_ALL=en_US.UTF-8

PWD=$(shell pwd)

TARGET=example.www

PYTHON := PYTHONPATH=$(PWD) python3
SRATIC = ${PYTHON} -m sratic
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
	NPROC := $(shell sysctl hw.ncpu | awk '{print $$2}')
else
	NPROC := $(shell nproc)
endif

all: www

www: PHONY
	mkdir -p example.www
	cd example; ${SRATIC} -b . -t ../example.templates -d ../example.www -j $(NPROC)

clean: PHONY
	rm -rf $(TARGET)/* 

serve:
	${PYTHON} -m http.server -d $(TARGET)

PHONY:

.PHONY: PHONY
