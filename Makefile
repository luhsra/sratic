lab.www: PHONY
	cd lab.src; ../bin/gen -b "." -d ../lab.www

deploy: PHONY
	cd lab.src; ../bin/gen -d ~/proj.lab/www/lab.sra.uni-hannover.de/

deploy-jenkins: PHONY
	cd lab.src; ../bin/gen -d /proj/www/lab.sra.uni-hannover.de/
.PHONY: PHONY
